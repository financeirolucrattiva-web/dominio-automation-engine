"""Configurador visual de rotinas: o operador marca, em um print da tela do Domínio, onde clicar, passar o mouse,
esperar uma imagem, e acrescenta teclas, textos e parâmetros. Nada de texto exato por OCR: cada alvo é um recorte
da imagem, procurado na tela por casamento de imagem (`tela.achar_icone_robusto`).

Ciclo de vida: rascunho -> testada (execução supervisionada que terminou bem, no servidor) -> aprovada. Qualquer
edição volta a rascunho. O servidor recorta os modelos de imagem da CAPTURA GUARDADA; o navegador só envia
retângulos, nunca imagens. O código daqui não importa desktop: os dispositivos (captura, mouse, teclado) entram
por `Dispositivos`, o que permite testar sem o Domínio.
"""
import datetime as dt
import hashlib
import io
import json
import os
import re
import tempfile
import threading
import time
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASTA = ROOT / "data" / "configurador"

TIPOS_ALVO = ("clicar", "duplo_clique", "hover", "esperar_imagem")
TIPOS = TIPOS_ALVO + ("tecla", "digitar", "esperar_segundos")
TECLAS = ("tab", "enter", "esc", "home", "end", "up", "down", "left", "right", "pageup", "pagedown", "f8")
PARAMETROS = ("inicio", "fim", "competencia", "empresa_codigo")
# Mesma regra das rotinas por texto: o configurador é só para gerar/ler, nunca para transmitir, retificar ou excluir.
_PROIBIDAS = re.compile(r"\b(transmit\w*|retific\w*|exclu\w*|apag\w*|delet\w*|envi\w*|assin\w*)\b")
_TEXTO_LIVRE = re.compile(r"^[0-9A-Za-zÀ-ÿ .,/\-_:()]{1,60}$")
_ID = re.compile(r"^[0-9a-f]{32}$")
_LOCK = threading.Lock()


class ConfiguradorErro(ValueError):
    pass


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))


def _inteiro(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


class Dispositivos:
    """Tudo que toca a tela/teclado. Os reais são montados só no servidor Windows (`reais()`)."""

    def __init__(self, capturar, achar_template, clicar, clicar_duplo, passar_mouse, tecla, digitar,
                 assinatura, mudou, janela_ok, dormir=time.sleep):
        self.capturar, self.achar_template = capturar, achar_template
        self.clicar, self.clicar_duplo, self.passar_mouse = clicar, clicar_duplo, passar_mouse
        self.tecla, self.digitar = tecla, digitar
        self.assinatura, self.mudou, self.janela_ok, self.dormir = assinatura, mudou, janela_ok, dormir

    @classmethod
    def reais(cls):
        from app import interacao, tela
        janela = interacao.identificar_janela_dominio_atual()

        def janela_ok():
            return janela is not None and interacao.janela_dominio_ou_remota_em_foco(janela)
        return cls(tela.capturar_tela, lambda img, caminho: tela.achar_icone_robusto(img, str(caminho)),
                   interacao.clicar, interacao.clicar_duplo, interacao.passar_mouse,
                   interacao.pressionar_tecla, interacao.digitar,
                   tela.assinatura_tela, tela.tela_mudou, janela_ok)


def validar_passos(passos, tamanho_captura):
    """Valida e normaliza. `tamanho_captura(captura_id)` devolve (largura, altura) ou None se não existir."""
    if not isinstance(passos, list) or not 1 <= len(passos) <= 80:
        raise ConfiguradorErro("Configure entre 1 e 80 passos.")
    limpos = []
    for numero, passo in enumerate(passos, 1):
        if not isinstance(passo, dict) or passo.get("tipo") not in TIPOS:
            raise ConfiguradorErro(f"Passo {numero}: escolha uma ação da lista.")
        tipo = passo["tipo"]
        item = {"indice": numero, "tipo": tipo}
        if tipo in TIPOS_ALVO:
            rotulo = passo.get("rotulo")
            if (not isinstance(rotulo, str) or not 3 <= len(rotulo.strip()) <= 80
                    or any(ord(c) < 32 for c in rotulo)):
                raise ConfiguradorErro(f"Passo {numero}: descreva o alvo em poucas palavras (3 a 80 letras).")
            if _PROIBIDAS.search(_sem_acento(rotulo)):
                raise ConfiguradorErro(f"Passo {numero}: o configurador não automatiza transmitir, retificar, excluir ou enviar.")
            item["rotulo"] = rotulo.strip()
            captura = passo.get("captura_id")
            if not isinstance(captura, str) or not _ID.fullmatch(captura):
                raise ConfiguradorErro(f"Passo {numero}: capture a tela e marque o alvo na imagem.")
            tamanho = tamanho_captura(captura)
            if tamanho is None:
                raise ConfiguradorErro(f"Passo {numero}: a captura não existe mais; capture a tela de novo.")
            x, y, largura, altura = (passo.get(k) for k in ("x", "y", "largura", "altura"))
            if not all(_inteiro(v) for v in (x, y, largura, altura)):
                raise ConfiguradorErro(f"Passo {numero}: marque um retângulo na imagem.")
            if not (8 <= largura <= 600 and 8 <= altura <= 400):
                raise ConfiguradorErro(f"Passo {numero}: o retângulo deve ter entre 8x8 e 600x400 pixels.")
            if x < 0 or y < 0 or x + largura > tamanho[0] or y + altura > tamanho[1]:
                raise ConfiguradorErro(f"Passo {numero}: o retângulo sai da imagem.")
            item.update(captura_id=captura, x=x, y=y, largura=largura, altura=altura)
            if tipo == "esperar_imagem":
                segundos = passo.get("segundos", 15)
                if not _inteiro(segundos) or not 1 <= segundos <= 60:
                    raise ConfiguradorErro(f"Passo {numero}: a espera pela imagem vai de 1 a 60 segundos.")
                item["segundos"] = segundos
        elif tipo == "tecla":
            if passo.get("tecla") not in TECLAS:
                raise ConfiguradorErro(f"Passo {numero}: tecla não permitida.")
            item["tecla"] = passo["tecla"]
        elif tipo == "digitar":
            parametro, texto = passo.get("parametro"), passo.get("texto")
            if (parametro is None) == (texto is None):
                raise ConfiguradorErro(f"Passo {numero}: informe um parâmetro OU um texto fixo.")
            if parametro is not None:
                if parametro not in PARAMETROS:
                    raise ConfiguradorErro(f"Passo {numero}: parâmetro desconhecido.")
                item["parametro"] = parametro
            else:
                if not isinstance(texto, str) or not _TEXTO_LIVRE.fullmatch(texto):
                    raise ConfiguradorErro(f"Passo {numero}: texto fixo com até 60 letras, números e pontuação simples.")
                item["texto"] = texto
        else:  # esperar_segundos
            segundos = passo.get("segundos")
            if not _inteiro(segundos) or not 1 <= segundos <= 30:
                raise ConfiguradorErro(f"Passo {numero}: a espera vai de 1 a 30 segundos.")
            item["segundos"] = segundos
        limpos.append(item)
    return limpos


def _formatar_parametro(nome, valor):
    if not isinstance(valor, str):
        raise ConfiguradorErro("Parâmetro inválido.")
    if nome in ("inicio", "fim"):
        data = dt.date.fromisoformat(valor)
        return data.strftime("%d/%m/%Y")
    if nome == "competencia":
        data = dt.date.fromisoformat(valor + "-01")
        return data.strftime("%m/%Y")
    if not re.fullmatch(r"[0-9]{1,12}", valor):
        raise ConfiguradorErro("Código de empresa inválido.")
    return valor


def validar_parametros_teste(passos, parametros, hoje=None):
    """Só parâmetros usados pela rotina; período sempre passado e fechado (nunca a competência corrente)."""
    hoje = hoje or dt.date.today()
    usados = {p["parametro"] for p in passos if p["tipo"] == "digitar" and "parametro" in p}
    parametros = parametros or {}
    if set(parametros) - usados:
        raise ConfiguradorErro("Parâmetro que a rotina não usa.")
    for nome in usados:
        if nome not in parametros:
            raise ConfiguradorErro(f"Informe o parâmetro {nome}.")
    try:
        formatados = {nome: _formatar_parametro(nome, parametros[nome]) for nome in usados}
        for nome in ("inicio", "fim"):
            if nome in usados and dt.date.fromisoformat(parametros[nome]) >= hoje.replace(day=1):
                raise ConfiguradorErro("Use somente competência passada e fechada.")
        if "competencia" in usados and dt.date.fromisoformat(parametros["competencia"] + "-01") >= hoje.replace(day=1):
            raise ConfiguradorErro("Use somente competência passada e fechada.")
    except ValueError as erro:
        if isinstance(erro, ConfiguradorErro):
            raise
        raise ConfiguradorErro("Data inválida: use AAAA-MM-DD (ou AAAA-MM na competência).") from None
    return formatados


class Configurador:
    def __init__(self, pasta=PASTA, dispositivos=None, pasta_falhas=ROOT / "capturas"):
        self.pasta = Path(pasta)
        self._dispositivos = dispositivos  # None = montar os reais no primeiro uso
        self.pasta_falhas = Path(pasta_falhas)
        self._ultima_captura = None

    # ---- capturas -------------------------------------------------------------------------------------------
    def _arquivo_captura(self, captura_id):
        if not isinstance(captura_id, str) or not _ID.fullmatch(captura_id):
            return None
        caminho = self.pasta / "capturas" / f"{captura_id}.png"
        return caminho if caminho.is_file() and not caminho.is_symlink() else None

    def _tamanho_captura(self, captura_id):
        from PIL import Image
        caminho = self._arquivo_captura(captura_id)
        if caminho is None:
            return None
        with Image.open(caminho) as imagem:
            return imagem.size

    def capturar(self, sessao=None):
        """Print da tela inteira do servidor, no mesmo sistema de coordenadas que o executor usa."""
        dispositivos = self._dispositivos or Dispositivos.reais()
        if not dispositivos.janela_ok():
            raise ConfiguradorErro("dominio_fora_de_foco")
        if sessao is not None:
            sessao.verificar()
        imagem = dispositivos.capturar()
        captura_id = uuid.uuid4().hex
        destino = self.pasta / "capturas"
        destino.mkdir(parents=True, exist_ok=True)
        imagem.save(destino / f"{captura_id}.png", format="PNG")
        self._limpar_capturas_antigas(destino)
        self._ultima_captura = captura_id
        return captura_id

    def _limpar_capturas_antigas(self, destino, manter=12):
        arquivos = sorted(destino.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        em_uso = self._capturas_em_uso()
        for antigo in arquivos[manter:]:
            if antigo.stem not in em_uso:
                antigo.unlink(missing_ok=True)

    def _capturas_em_uso(self):
        usadas = set()
        for rotina in self.listar():
            dados = self._ler(rotina["id"])
            usadas |= {p.get("captura_id") for p in dados.get("passos", []) if p.get("captura_id")}
        return usadas

    def obter_captura(self, captura_id=None):
        captura_id = captura_id or self._ultima_captura
        caminho = self._arquivo_captura(captura_id)
        if caminho is None:
            return None
        return captura_id, caminho.read_bytes()

    # ---- rotinas ----------------------------------------------------------------------------------------------
    def _pasta_rotina(self, rotina_id):
        if not isinstance(rotina_id, str) or not _ID.fullmatch(rotina_id):
            raise ConfiguradorErro("Rotina não encontrada.")
        return self.pasta / "rotinas" / rotina_id

    def _ler(self, rotina_id):
        arquivo = self._pasta_rotina(rotina_id) / "rotina.json"
        try:
            if arquivo.is_symlink() or arquivo.stat().st_size > 500_000:
                raise OSError
            return json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ConfiguradorErro("Rotina não encontrada.") from None

    def _gravar(self, rotina_id, dados):
        pasta = self._pasta_rotina(rotina_id)
        pasta.mkdir(parents=True, exist_ok=True)
        temporario = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=pasta, encoding="utf-8", delete=False, suffix=".tmp") as arquivo:
                temporario = Path(arquivo.name)
                json.dump(dados, arquivo, ensure_ascii=False, indent=2)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, pasta / "rotina.json")
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)

    @staticmethod
    def _assinatura(dados):
        base = {"nome": dados["nome"], "passos": dados["passos"]}
        corpo = json.dumps(base, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(corpo).hexdigest()

    def _resumo(self, rotina_id, dados):
        teste = dados.get("ultimo_teste")
        return {"id": rotina_id, "nome": dados["nome"], "status": dados["status"],
                "quantidade_passos": len(dados["passos"]),
                "parametros": sorted({p["parametro"] for p in dados["passos"] if p.get("parametro")}),
                "ultimo_teste": teste and {"ok": teste["ok"], "em": teste["em"], "passo_falho": teste.get("passo_falho")}}

    def listar(self):
        resultado = []
        raiz = self.pasta / "rotinas"
        if not raiz.is_dir():
            return resultado
        for pasta in sorted(raiz.iterdir()):
            try:
                resultado.append(self._resumo(pasta.name, self._ler(pasta.name)))
            except ConfiguradorErro:
                continue
        return resultado

    def obter(self, rotina_id):
        dados = self._ler(rotina_id)
        passos = [{k: v for k, v in p.items() if k != "modelo"} | {"tem_modelo": "modelo" in p} for p in dados["passos"]]
        return {**self._resumo(rotina_id, dados), "passos": passos, "resultado_teste": dados.get("ultimo_teste")}

    def salvar(self, nome, passos, rotina_id=None):
        from PIL import Image
        if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 100 or any(ord(c) < 32 for c in nome):
            raise ConfiguradorErro("Informe um nome para a rotina.")
        nome = nome.strip()
        limpos = validar_passos(passos, self._tamanho_captura)
        with _LOCK:
            existentes = {r["id"]: r["nome"] for r in self.listar()}
            if any(n.casefold() == nome.casefold() and i != rotina_id for i, n in existentes.items()):
                raise ConfiguradorErro("Já existe uma rotina com esse nome.")
            if rotina_id is None:
                rotina_id = uuid.uuid4().hex
            else:
                self._ler(rotina_id)  # precisa existir
            pasta = self._pasta_rotina(rotina_id)
            pasta.mkdir(parents=True, exist_ok=True)
            for item in limpos:
                if item["tipo"] in TIPOS_ALVO:
                    with Image.open(self._arquivo_captura(item["captura_id"])) as captura:
                        recorte = captura.convert("RGB").crop((item["x"], item["y"], item["x"] + item["largura"],
                                                               item["y"] + item["altura"]))
                    nome_modelo = f"passo_{item['indice']:02d}.png"
                    recorte.save(pasta / nome_modelo, format="PNG")
                    item["modelo"] = nome_modelo
            for sobra in pasta.glob("passo_*.png"):
                if sobra.name not in {p.get("modelo") for p in limpos}:
                    sobra.unlink(missing_ok=True)
            dados = {"nome": nome, "passos": limpos, "status": "rascunho", "criada_em": dt.datetime.now().isoformat(timespec="seconds")}
            self._gravar(rotina_id, dados)
        return self.obter(rotina_id)

    def excluir(self, rotina_id):
        import shutil
        pasta = self._pasta_rotina(rotina_id)
        self._ler(rotina_id)
        shutil.rmtree(pasta, ignore_errors=True)

    def modelo(self, rotina_id, indice):
        dados = self._ler(rotina_id)
        for passo in dados["passos"]:
            if passo["indice"] == indice and "modelo" in passo:
                caminho = self._pasta_rotina(rotina_id) / passo["modelo"]
                if caminho.is_file() and not caminho.is_symlink():
                    return caminho.read_bytes()
        return None

    # ---- teste supervisionado e aprovação ----------------------------------------------------------------------
    def testar(self, rotina_id, parametros=None, sessao=None, hoje=None):
        """Executa os passos uma vez, com a pessoa olhando o Domínio. Guarda o resultado; só um teste bem
        sucedido, da versão atual dos passos, libera a aprovação."""
        dados = self._ler(rotina_id)
        valores = validar_parametros_teste(dados["passos"], parametros, hoje)
        dispositivos = self._dispositivos or Dispositivos.reais()
        resultado = executar_passos(dados["passos"], self._pasta_rotina(rotina_id), valores, dispositivos,
                                    sessao=sessao, pasta_falhas=self.pasta_falhas, rotina_id=rotina_id)
        with _LOCK:
            atual = self._ler(rotina_id)
            if self._assinatura(atual) == self._assinatura(dados):
                atual["ultimo_teste"] = {"ok": resultado["ok"], "em": dt.datetime.now().isoformat(timespec="seconds"),
                                         "assinatura": self._assinatura(atual), "passo_falho": resultado.get("passo_falho"),
                                         "passos": resultado["passos"]}
                atual["status"] = "testada" if resultado["ok"] else "rascunho"
                self._gravar(rotina_id, atual)
        return resultado

    def aprovar(self, rotina_id):
        with _LOCK:
            dados = self._ler(rotina_id)
            teste = dados.get("ultimo_teste")
            if not teste or not teste.get("ok") or teste.get("assinatura") != self._assinatura(dados):
                raise ConfiguradorErro("Aprove só depois de um teste bem sucedido desta versão dos passos.")
            dados["status"] = "aprovada"
            self._gravar(rotina_id, dados)
        return self.obter(rotina_id)


def executar_passos(passos, pasta_rotina, parametros, dispositivos, sessao=None, pasta_falhas=None, rotina_id="rotina"):
    """Toca os passos na ordem. Para no primeiro que falhar e devolve o que aconteceu em cada um."""
    registro, d = [], dispositivos

    def esperar_mudanca(antes, tentativas=10):
        for _ in range(tentativas):
            d.dormir(0.5)
            if d.mudou(antes, d.assinatura(d.capturar())):
                return True
        return False

    def procurar(passo, tempo):
        modelo = Path(pasta_rotina) / passo["modelo"]
        tentativas = int(tempo) + 1
        for numero in range(tentativas):
            posicao = d.achar_template(d.capturar(), modelo)
            if posicao is not None:
                return posicao
            if numero < tentativas - 1:
                d.dormir(1)
                if sessao is not None:
                    sessao.verificar()
        return None

    def falhar(passo, detalhe):
        registro.append({"indice": passo["indice"], "tipo": passo["tipo"], "ok": False, "detalhe": detalhe})
        if pasta_falhas is not None:
            try:
                Path(pasta_falhas).mkdir(parents=True, exist_ok=True)
                d.capturar().save(Path(pasta_falhas) / f"configurador_{rotina_id[:8]}_passo_{passo['indice']:02d}.png")
            except Exception:
                pass
        return {"ok": False, "passo_falho": passo["indice"], "mensagem": detalhe, "passos": registro}

    for passo in passos:
        if sessao is not None:
            sessao.verificar()
        if not d.janela_ok():
            return falhar(passo, "O Domínio saiu do foco; nada foi enviado neste passo.")
        tipo = passo["tipo"]
        if tipo in ("clicar", "duplo_clique", "hover"):
            posicao = procurar(passo, 8)
            if posicao is None:
                return falhar(passo, f"Não achei '{passo['rotulo']}' na tela.")
            antes = d.assinatura(d.capturar())
            {"clicar": d.clicar, "duplo_clique": d.clicar_duplo, "hover": d.passar_mouse}[tipo](*posicao)
            detalhe = f"{passo['rotulo']}: ok"
            if tipo != "hover" and not esperar_mudanca(antes):
                detalhe += " (a tela não mudou depois da ação)"
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": detalhe})
        elif tipo == "esperar_imagem":
            if procurar(passo, passo["segundos"]) is None:
                return falhar(passo, f"'{passo['rotulo']}' não apareceu em {passo['segundos']} s.")
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": f"{passo['rotulo']}: apareceu"})
        elif tipo == "tecla":
            d.tecla(passo["tecla"])
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": f"tecla {passo['tecla']}"})
        elif tipo == "digitar":
            texto = parametros[passo["parametro"]] if "parametro" in passo else passo["texto"]
            d.digitar(texto)
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True,
                             "detalhe": "digitou " + (passo.get("parametro") or "texto fixo")})
        else:
            d.dormir(passo["segundos"])
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": f"esperou {passo['segundos']} s"})
    return {"ok": True, "passo_falho": None, "mensagem": "Todos os passos foram executados.", "passos": registro}
