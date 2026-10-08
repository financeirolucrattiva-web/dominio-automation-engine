"""Configuração opcional de rede local após instalar os componentes do servidor."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    from app.rede_local import detectar_ips, preparar_rede
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", help="IPv4 deste PC na rede local.")
    parser.add_argument("--porta", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        ip = args.ip
        if not ip:
            escolha = input("Acesso: [1] somente neste PC, [2] interface em outro PC da rede. Escolha [2]: ").strip()
            if escolha == "1":
                print("Acesso local mantido. Use Testar Interface Servidor.bat.")
                return 0
            if escolha not in ("", "2"):
                print("Opção inválida; configuração não alterada.")
                return 1
            ips = detectar_ips()
            if ips:
                print("IPv4 detectado(s): " + ", ".join(ips))
            padrao = ips[0] if len(ips) == 1 else ""
            ip = input(f"IPv4 do PC com Domínio [{padrao or 'consulte ipconfig'}]: ").strip() or padrao
        resultado = preparar_rede(ip, args.porta)
        print("Endereço da interface: " + resultado["endereco"])
        print("Pacote para copiar ao outro PC: data/rede_local/interface_cliente")
        print("Certificado público SHA256: " + resultado["certificado_sha256"])
        print("Neste PC, execute Liberar Acesso Rede.bat como administrador (rede privada).")
        print("Depois abra Testar Interface na Rede.bat. No outro PC, rode Instalar Interface.bat do pacote.")
        print("A chave de acesso é a mesma de data/servidor_chave.txt, criada ao iniciar o servidor.")
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Configuração não concluída. Confira IP/porta e certificados locais antes de repetir.")
        return 1
    except ImportError:
        print("Instale os componentes com Instalar Servidor.bat antes de configurar a rede.")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Configuração cancelada.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
