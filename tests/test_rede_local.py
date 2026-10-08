"""HTTPS real em memória/loopback e pacote cliente sem dependências fiscais."""

import contextlib
import datetime as dt
import importlib.util
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import rede_local

CRYPTO = importlib.util.find_spec("cryptography") is not None
if CRYPTO:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization


@unittest.skipUnless(CRYPTO, "Dependência opcional do servidor: cryptography")
class TestRedeLocal(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.pasta = Path(temp.name) / "rede"
        self.resultado = rede_local.preparar_rede("192.168.1.50", pasta=self.pasta)
        self.config = rede_local.carregar_rede(self.pasta)

    def test_certificado_serve_so_o_ip_configurado_com_cadeia_e_chave_validas(self):
        cert = x509.load_pem_x509_certificate(self.config["certificado"].read_bytes())
        ca = x509.load_pem_x509_certificate((self.pasta / "autoridade" / "ca.pem").read_bytes())
        cert.verify_directly_issued_by(ca)
        self.assertFalse(cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
        self.assertEqual(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress), [ipaddress.ip_address("192.168.1.50")])
        self.assertLessEqual(cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc), dt.timedelta(days=365))
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(self.config["certificado"], self.config["chave_tls"])

    def test_pacote_cliente_nao_inclui_chaves_privadas_python_ocr_ou_chave_de_acesso(self):
        arquivos = self.resultado["pacote_cliente"]
        encontrados = {str(p.relative_to(arquivos)) for p in arquivos.rglob("*") if p.is_file()}
        self.assertEqual(encontrados, {"Instalar Interface.bat", "scripts/instalar_interface.ps1", "scripts/dominio-rede.cer", "scripts/endereco.json"})
        dados = json.loads((arquivos / "scripts" / "endereco.json").read_text())
        self.assertEqual(dados["endereco"], "https://192.168.1.50:8765")
        ca = x509.load_der_x509_certificate((arquivos / "scripts" / "dominio-rede.cer").read_bytes())
        self.assertEqual(dados["certificado_sha256"], ca.fingerprint(hashes.SHA256()).hex().upper())
        for arquivo in arquivos.rglob("*"):
            if arquivo.is_file():
                self.assertNotIn(b"PRIVATE KEY", arquivo.read_bytes())

    def test_novo_ip_reusa_confianca_dos_clientes_e_preserva_certificado_anterior(self):
        ca_antes = (self.pasta / "autoridade" / "ca.pem").read_bytes()
        caminho_antes = self.config["certificado"]
        rede_local.preparar_rede("192.168.1.51", pasta=self.pasta)
        self.assertEqual((self.pasta / "autoridade" / "ca.pem").read_bytes(), ca_antes)
        self.assertTrue(caminho_antes.is_file())
        self.assertEqual(rede_local.carregar_rede(self.pasta)["ip"], "192.168.1.51")

    def test_autoridade_corrompida_nao_e_substituida_nem_publica_novo_config(self):
        chave = self.pasta / "autoridade" / "ca-key.pem"
        chave.write_bytes(b"invalida")
        antes = (self.pasta / "config.json").read_bytes()
        with self.assertRaises(ValueError):
            rede_local.preparar_rede("192.168.1.51", pasta=self.pasta)
        self.assertEqual(chave.read_bytes(), b"invalida")
        self.assertEqual((self.pasta / "config.json").read_bytes(), antes)

    def test_config_nao_aceita_certificados_fora_da_pasta_local(self):
        config = json.loads((self.pasta / "config.json").read_text())
        config["certificado"] = "../fora.pem"
        (self.pasta.parent / "fora.pem").write_text("publico")
        (self.pasta / "config.json").write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            rede_local.carregar_rede(self.pasta)

    def test_tls_real_confia_na_autoridade_mas_recusa_hostname_divergente(self):
        servidor = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        servidor.load_cert_chain(self.config["certificado"], self.config["chave_tls"])
        cliente = ssl.create_default_context(cafile=str(self.pasta / "autoridade" / "ca.pem"))
        for hostname, sucesso in (("192.168.1.50", True), ("192.168.1.51", False)):
            esquerdo, direito = socket.socketpair()
            erros = []
            def receber():
                try:
                    with servidor.wrap_socket(esquerdo, server_side=True) as conexao:
                        self.assertEqual(conexao.recv(1), b"x")
                except Exception as erro:
                    erros.append(erro)
            thread = threading.Thread(target=receber)
            thread.start()
            try:
                if sucesso:
                    with cliente.wrap_socket(direito, server_hostname=hostname) as conexao:
                        conexao.sendall(b"x")
                else:
                    with self.assertRaises(ssl.SSLCertVerificationError):
                        cliente.wrap_socket(direito, server_hostname=hostname)
            finally:
                direito.close()
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            if sucesso:
                self.assertEqual(erros, [])


class TestValidacaoRede(unittest.TestCase):
    def test_ip_publico_loopback_ipv6_e_texto_invalido_recusados(self):
        for ip in ("127.0.0.1", "0.0.0.0", "8.8.8.8", "203.0.113.5", "::1", "host;comando", "172.32.1.1"):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                rede_local.validar_ip(ip)
        for ip in ("192.168.0.5", "10.0.0.8", "172.16.0.1", "172.31.255.1"):
            self.assertEqual(rede_local.validar_ip(ip), ip)

    def test_falha_de_gravacao_atomica_preserva_config_anterior(self):
        with tempfile.TemporaryDirectory() as temp:
            arquivo = Path(temp) / "config.json"
            arquivo.write_bytes(b"anterior")
            with patch.object(rede_local.os, "replace", side_effect=OSError("falha")), self.assertRaises(OSError):
                rede_local._gravar(arquivo, b"novo")
            self.assertEqual(arquivo.read_bytes(), b"anterior")
            self.assertEqual(list(Path(temp).iterdir()), [arquivo])

    @unittest.skipUnless(all(importlib.util.find_spec(nome) for nome in ("uvicorn", "fastapi")), "Componentes opcionais da API")
    def test_cli_configurado_usa_ip_certificado_porta_e_preserva_modo_simulado(self):
        arquivo = Path(__file__).resolve().parents[1] / "scripts" / "servidor.py"
        spec = importlib.util.spec_from_file_location("cli_rede", arquivo)
        modulo = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", list(sys.path)):
            spec.loader.exec_module(modulo)
        config = {"ip": "192.168.1.50", "porta": 9876, "certificado": Path("cert.pem"), "chave_tls": Path("key.pem")}
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(modulo, "ROOT", Path(temp)), patch.object(modulo.logging, "basicConfig"), patch.object(rede_local, "carregar_rede", return_value=config), patch("uvicorn.run") as rodar, patch("app.api_servidor.obter_chave", return_value="x"*48), contextlib.redirect_stdout(__import__("io").StringIO()):
                self.assertEqual(modulo.main(["--rede-local", "--simular"]), 0)
        self.assertEqual(rodar.call_args.kwargs["host"], "192.168.1.50")
        self.assertEqual(rodar.call_args.kwargs["port"], 9876)
        self.assertEqual(rodar.call_args.kwargs["ssl_certfile"], "cert.pem")
        self.assertEqual(rodar.call_args.kwargs["ssl_keyfile"], "key.pem")


if __name__ == "__main__":
    unittest.main()
