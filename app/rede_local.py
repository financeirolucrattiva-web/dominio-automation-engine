"""HTTPS da rede local e pacote público do cliente; não opera o Domínio."""

import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PASTA_REDE = ROOT / "data" / "rede_local"
REDES = tuple(ipaddress.ip_network(rede) for rede in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def validar_ip(valor):
    ip = ipaddress.IPv4Address(valor)
    if not any(ip in rede for rede in REDES):
        raise ValueError("Use o IPv4 da rede local deste PC (10.x, 172.16–31.x ou 192.168.x).")
    return str(ip)


def detectar_ips():
    try:
        valores = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    ips = set()
    for valor in valores:
        try:
            ips.add(validar_ip(valor[4][0]))
        except ValueError:
            pass
    return sorted(ips)


def _gravar(caminho, dados, privado=False):
    caminho = Path(caminho)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        if privado:
            temporario.chmod(0o600)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _autoridade(pasta, agora):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    nome = pasta / "autoridade"
    if nome.exists():
        # Arquivo incompleto/corrompido não é substituído silenciosamente:
        # isso invalidaria a confiança já instalada nos PCs clientes.
        cert = x509.load_pem_x509_certificate((nome / "ca.pem").read_bytes())
        chave = serialization.load_pem_private_key((nome / "ca-key.pem").read_bytes(), password=None)
        formato = (serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if (cert.public_key().public_bytes(*formato) != chave.public_key().public_bytes(*formato)
                or not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
                or not cert.not_valid_before_utc <= agora < cert.not_valid_after_utc):
            raise ValueError("Autoridade local inválida ou vencida; arquivos preservados.")
        return cert, chave
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sujeito = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "Dominio Automation Engine - Rede local")])
    cert = (x509.CertificateBuilder().subject_name(sujeito).issuer_name(sujeito)
            .public_key(chave.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(agora - dt.timedelta(minutes=5)).not_valid_after(agora + dt.timedelta(days=730))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, None, None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(chave.public_key()), critical=False)
            .sign(chave, hashes.SHA256()))
    with tempfile.TemporaryDirectory(dir=pasta) as tmp:
        preparado = Path(tmp) / "autoridade"
        preparado.mkdir()
        (preparado / "ca.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        _gravar(preparado / "ca-key.pem", chave.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), privado=True)
        preparado.rename(nome)
    return cert, chave


def preparar_rede(ip, porta=8765, pasta=PASTA_REDE):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    ip = validar_ip(ip)
    if type(porta) is not int or not 1 <= porta <= 65535:
        raise ValueError("Porta inválida.")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    agora = dt.datetime.now(dt.timezone.utc)
    autoridade, chave_ca = _autoridade(pasta, agora)
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sujeito = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, ip)])
    cert = (x509.CertificateBuilder().subject_name(sujeito).issuer_name(autoridade.subject)
            .public_key(chave.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(agora - dt.timedelta(minutes=5))
            .not_valid_after(min(agora + dt.timedelta(days=365), autoridade.not_valid_after_utc))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, None, None), critical=True)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(chave_ca.public_key()), critical=False)
            .sign(chave_ca, hashes.SHA256()))
    # Uma revisão nova evita pares cert/chave parcialmente substituídos.
    revisao = pasta / ("certificados_" + uuid.uuid4().hex)
    revisao.mkdir()
    _gravar(revisao / "servidor.pem", cert.public_bytes(serialization.Encoding.PEM)
            + autoridade.public_bytes(serialization.Encoding.PEM))
    _gravar(revisao / "servidor-key.pem", chave.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), privado=True)
    cliente = pasta / "interface_cliente"
    (cliente / "scripts").mkdir(parents=True, exist_ok=True)
    for origem, destino in ((ROOT / "Instalar Interface.bat", cliente / "Instalar Interface.bat"),
                            (ROOT / "scripts" / "instalar_interface.ps1", cliente / "scripts" / "instalar_interface.ps1")):
        shutil.copyfile(origem, destino)
    _gravar(cliente / "scripts" / "dominio-rede.cer", autoridade.public_bytes(serialization.Encoding.DER))
    publico = {"endereco": f"https://{ip}:{porta}", "certificado_sha256": autoridade.fingerprint(hashes.SHA256()).hex().upper()}
    _gravar(cliente / "scripts" / "endereco.json", json.dumps(publico).encode("utf-8"))
    config = {"versao": 1, "ip": ip, "porta": porta, "python": sys.executable,
              "certificado": str((revisao / "servidor.pem").relative_to(pasta)),
              "chave_tls": str((revisao / "servidor-key.pem").relative_to(pasta))}
    _gravar(pasta / "config.json", json.dumps(config).encode("utf-8"))
    return {**publico, "pacote_cliente": cliente}


def carregar_rede(pasta=PASTA_REDE):
    pasta = Path(pasta).resolve()
    config = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    if (not isinstance(config, dict) or type(config.get("versao")) is not int or config["versao"] != 1
            or type(config.get("porta")) is not int or not 1 <= config["porta"] <= 65535):
        raise ValueError("Configuração da rede inválida.")
    config["ip"] = validar_ip(config["ip"])
    for nome in ("certificado", "chave_tls"):
        caminho = (pasta / config[nome]).resolve()
        if not caminho.is_relative_to(pasta) or not caminho.is_file():
            raise ValueError("Certificados da rede indisponíveis.")
        config[nome] = caminho
    return config
