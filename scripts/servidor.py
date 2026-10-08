"""Interface conectada ao executor dedicado; consulta é o modo padrão."""

import argparse
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def simular(pedido, receber_evento):
    """Eventos sintéticos; nunca importa ou opera o desktop."""
    from app import painel
    identificador = pedido["request_id"].replace("-", "")
    etapas = painel.ETAPAS_LIVROS if pedido["capacidade"].startswith("registro_") else painel.ETAPAS_GERACAO
    for etapa in etapas + ("fim",):
        time.sleep(0.15)
        receber_evento({"execution_id": identificador, "routine_id": pedido["capacidade"], "attempt": 1,
                        "step": etapa, "status": "concluido" if etapa == "fim" else "confirmado",
                        "elapsed_seconds": 0.15, "evidence": "tela_principal_reconhecida" if etapa == "encerrar" else None})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modos = parser.add_mutually_exclusive_group()
    modos.add_argument("--simular", action="store_true", help="Testa conexão/estados com eventos sintéticos; não opera o Domínio.")
    modos.add_argument("--executar", action="store_true", help="Habilita as rotinas conhecidas na sessão Windows dedicada.")
    parser.add_argument("--rede-local", action="store_true", help="Usa o endereço/HTTPS preparados pelo instalador do servidor.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int)
    parser.add_argument("--certificado", type=Path, help="Certificado HTTPS em PEM.")
    parser.add_argument("--chave-tls", type=Path, help="Chave HTTPS em PEM.")
    args = parser.parse_args(argv)
    if args.rede_local:
        if args.host != "127.0.0.1" or args.porta is not None or args.certificado or args.chave_tls:
            parser.error("Use --rede-local com a configuração salva, sem host/porta/certificados manuais.")
        try:
            from app.rede_local import carregar_rede
            config = carregar_rede()
            args.host, args.porta = config["ip"], config["porta"]
            args.certificado, args.chave_tls = config["certificado"], config["chave_tls"]
        except (OSError, ValueError, KeyError, TypeError):
            print("Configure a rede com Instalar Servidor.bat ou atalhos/servidor/Configurar Acesso Rede.bat antes de iniciar.")
            return 1
    if args.porta is None:
        args.porta = 8765
    if not 1 <= args.porta <= 65535:
        parser.error("Porta inválida.")
    if bool(args.certificado) != bool(args.chave_tls):
        parser.error("Informe certificado e chave HTTPS juntos.")
    if args.host not in ("127.0.0.1", "localhost", "::1") and args.certificado is None:
        parser.error("Acesso de outro PC requer HTTPS: use certificado/chave ou proxy HTTPS na conexão local.")
    if args.executar and sys.platform != "win32":
        parser.error("Execução real requer Windows com sessão dedicada e Domínio visível.")
    try:
        import uvicorn
        from app.api_servidor import criar_app, obter_chave
        from app.servidor import RepositorioTarefas, ServicoExecucao
    except ImportError:
        print("Instale os componentes com Instalar Servidor.bat ou pip install -r requirements-servidor.txt.")
        return 1
    (ROOT / "data").mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT / "data" / "servidor.log", encoding="utf-8", level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    executor, modo = None, "consulta"
    if args.simular:
        executor, modo = simular, "simulacao"
    elif args.executar:
        from app.executor_servidor import ExecutorDominio
        executor, modo = ExecutorDominio(), "windows"
    nome_banco = "servidor_simulado.sqlite3" if args.simular else "servidor.sqlite3"
    try:
        servico = ServicoExecucao(RepositorioTarefas(ROOT / "data" / nome_banco), executor, modo)
        app = criar_app(servico, obter_chave())
        print(f"Modo do servidor: {modo}. Porta {args.porta}.")
        if args.rede_local:
            print(f"Endereço da interface: https://{args.host}:{args.porta}")
        print("Chave de acesso local: data/servidor_chave.txt (não cole em chats nem publique).")
        print("Uma execução por sessão. Ctrl+C aguarda a rotina atual terminar.")
        if args.simular:
            print("SIMULAÇÃO: nenhum documento fiscal será gerado.")
        uvicorn.run(app, host=args.host, port=args.porta, workers=1, access_log=False,
                    ssl_certfile=str(args.certificado) if args.certificado else None,
                    ssl_keyfile=str(args.chave_tls) if args.chave_tls else None)
    except (OSError, ValueError):
        print("Servidor não iniciado; confira dependências, porta, certificados e arquivos locais. Veja data/servidor.log.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
