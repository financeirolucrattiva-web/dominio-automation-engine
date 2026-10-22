"""Pré-voo: confere o ambiente ANTES de rodar um lote (não opera o Domínio, não usa mouse nem teclado).

    python scripts/verificar_ambiente.py

Cada linha é OK, ALERTA (pode seguir, mas leia) ou ERRO (não rode o lote até corrigir). Código de saída
1 se houver ERRO. Só lê arquivos locais e uma captura de tela; nada é impresso do conteúdo da tela.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, ALERTA, ERRO = "OK", "ALERTA", "ERRO"
ESPACO_MINIMO_GB = 2


def verificar_tesseract():
    try:
        import pytesseract
        from app import tela  # noqa: F401  (acha o executável e grava o caminho)
        versao = str(pytesseract.get_tesseract_version())
        idiomas = pytesseract.get_languages(config="")
    except Exception as erro:
        return ERRO, "Tesseract não encontrado/funcionando (" + type(erro).__name__ + "). Rode Instalar.bat."
    if "por" not in idiomas:
        return ERRO, "Tesseract " + versao + " sem o idioma português (por)."
    return OK, "Tesseract " + versao + " com português."


def verificar_ocr_windows():
    try:
        import winocr  # noqa: F401
        from PIL import Image
        from app import tela
        leitura = tela.ler_dados_ocr_windows(Image.new("RGB", (120, 40), "white"), 2)
    except Exception as erro:
        return ALERTA, "OCR do Windows indisponível (" + type(erro).__name__ + "): fica só o Tesseract (mais lento)."
    if leitura is None:
        return ALERTA, "OCR do Windows não respondeu: fica só o Tesseract (mais lento)."
    return OK, "OCR do Windows disponível."


def verificar_calibracao():
    from app import tela_principal
    if tela_principal.carregar_referencia() is None:
        return ERRO, "Tela principal NÃO calibrada (data/tela_principal.json ausente ou inválido). Rode Calibrar Tela Principal.bat."
    return OK, "Tela principal calibrada."


def verificar_resolucao():
    try:
        from PIL import ImageGrab
        largura, altura = ImageGrab.grab().size
    except Exception as erro:
        return ALERTA, "Não consegui ler o tamanho da tela (" + type(erro).__name__ + ")."
    return OK, f"Tela {largura}x{altura} (a calibração e os atalhos foram medidos nessa resolução; se mudou, calibre de novo)."


def verificar_pasta_saida(pasta=None, espaco_gb=ESPACO_MINIMO_GB):
    pasta = Path(pasta or ROOT / "saida")
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=pasta, delete=True):
            pass
        livre = shutil.disk_usage(pasta).free / 1e9
    except OSError as erro:
        return ERRO, "Pasta de saída não gravável (" + type(erro).__name__ + "): " + str(pasta)
    if livre < espaco_gb:
        return ALERTA, f"Pouco espaço livre: {livre:.1f} GB (recomendado >= {espaco_gb} GB)."
    return OK, f"Pasta de saída gravável; {livre:.0f} GB livres."


def verificar_unidade_cliente():
    from app import dominio
    letra = dominio._unidade_cliente()
    origem = "data/unidade_cliente.txt" if (ROOT / "data" / "unidade_cliente.txt").exists() else "padrão"
    return OK, f"Unidade do cliente na sessão remota: {letra}: ({origem})."


def verificar_otimizacoes():
    from app import otimizacoes
    otimizacoes.restaurar_para_testes()
    estado = otimizacoes.estado()
    desligadas = [n for n, v in estado.items() if not v]
    if len(desligadas) == len(estado):
        return ALERTA, "Modo seguro ativo (tudo no caminho clássico, mais lento). 'Modo Rapido' liga de novo."
    if desligadas:
        return ALERTA, "Otimizações desligadas: " + ", ".join(desligadas) + "."
    return OK, "Otimizações de velocidade ligadas."


def verificar_atalho_saida():
    from app import atalho_saida
    atalho = atalho_saida.atalho_configurado()
    if atalho is None:
        return OK, "Atalho curto da saída não configurado (usa o caminho completo; opcional)."
    if atalho_saida.destino_de_navegacao(ROOT / "saida") != atalho:
        return ALERTA, f"Atalho {atalho} configurado, mas NÃO aponta para a pasta de saída: o caminho completo será usado."
    return OK, f"Atalho curto da saída ativo: {atalho}."


def servidor_escutando(porta=8765):
    import socket
    enderecos = ["127.0.0.1"]
    try:
        enderecos.append(socket.gethostbyname(socket.gethostname()))
    except OSError:
        pass
    for endereco in enderecos:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex((endereco, porta)) == 0:
                return True
    return False


def verificar_servidor():
    return OK, ("Servidor escutando na porta 8765 (necessário para rodar pelo painel)." if servidor_escutando() else
                "Servidor não está escutando na porta 8765 (ok se o lote for pelo atalho com o servidor parado).")


def verificar_servidor_parado():
    """Para o lote por atalho (scripts/explorar_presumido.py): servidor ligado recusaria a execução."""
    if servidor_escutando():
        return ERRO, "O servidor está ligado. Pare o servidor antes de rodar o lote por este atalho (ou use o painel)."
    return OK, "Servidor parado (o atalho assume a fila sozinho)."


def verificar_versao():
    try:
        saida = subprocess.run(["git", "log", "--oneline", "-1"], cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip()
        ramo = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout.strip()
    except OSError:
        return ALERTA, "Git não encontrado: não sei qual versão está instalada."
    return OK, f"Versão {saida} (branch {ramo or 'destacada'})."


def verificar_dominio_aberto():
    try:
        from app import interacao
        janela = interacao.identificar_janela_dominio_atual()
    except Exception as erro:
        return ALERTA, "Não consegui procurar a janela do Domínio (" + type(erro).__name__ + ")."
    if janela is None:
        return ALERTA, "Domínio não está em primeiro plano agora (deixe-o na tela azul antes de iniciar o lote)."
    return OK, "Janela do Domínio em primeiro plano."


VERIFICACOES = (
    ("versão", verificar_versao), ("Tesseract", verificar_tesseract), ("OCR Windows", verificar_ocr_windows),
    ("calibração", verificar_calibracao), ("tela", verificar_resolucao), ("saída", verificar_pasta_saida),
    ("unidade", verificar_unidade_cliente), ("otimizações", verificar_otimizacoes),
    ("atalho saída", verificar_atalho_saida), ("servidor", verificar_servidor), ("Domínio", verificar_dominio_aberto),
)


VERIFICACOES_LOTE = tuple((n, verificar_servidor_parado if n == "servidor" else f) for n, f in VERIFICACOES)


def executar(verificacoes=VERIFICACOES):
    resultados = []
    for nome, funcao in verificacoes:
        try:
            status, mensagem = funcao()
        except Exception as erro:  # uma checagem com defeito nunca esconde as outras
            status, mensagem = ALERTA, "Checagem falhou (" + type(erro).__name__ + ")."
        resultados.append((nome, status, mensagem))
    return resultados


def main(argv=None):
    resultados = executar(VERIFICACOES)
    for nome, status, mensagem in resultados:
        print(f"[{status:<6}] {nome}: {mensagem}")
    erros = [r for r in resultados if r[1] == ERRO]
    alertas = [r for r in resultados if r[1] == ALERTA]
    print()
    if erros:
        print(f"{len(erros)} ERRO(S): corrija antes de rodar o lote.")
        return 1
    print("Pode rodar o lote." + (f" ({len(alertas)} alerta(s) acima.)" if alertas else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
