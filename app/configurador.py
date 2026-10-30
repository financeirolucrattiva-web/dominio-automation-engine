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
# trocar_empresa e voltar_tela_principal reaproveitam as funções já validadas nos lotes reais (F8 + código e a
# subida até a tela azul); a empresa vem do parâmetro empresa_codigo, nunca de texto digitado no passo.
TIPOS = TIPOS_ALVO + ("se_aparecer", "tecla", "digitar", "esperar_segundos", "trocar_empresa", "voltar_tela_principal")
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
                 assinatura, mudou, janela_ok, dormir=time.sleep, trocar_empresa=None, voltar_inicio=None,
                 empresa_atual=None):
        self.trocar_empresa, self.voltar_inicio, self.empresa_atual = trocar_empresa, voltar_inicio, empresa_atual
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

        def trocar_empresa(codigo):
            from app import dominio
            return dominio.trocar_empresa(str(int(codigo)), prefixo="configurador_",
                                          recuperar_inicio=lambda: dominio.voltar_ao_inicio(janela))

        def voltar_inicio():
            from app import dominio
            return dominio.voltar_ao_inicio(janela)

        def empresa_atual():
            """Código da empresa no cabeçalho do Domínio, ou None se não der para ler (tela fora da principal)."""
            lida = tela.ler_empresa_selecionada(tela.capturar_tela())
            return str(lida[1]) if lida is not None and str(lida[1]).isdigit() else None
        return cls(tela.capturar_tela, lambda img, caminho: tela.achar_icone_robusto(img, str(caminho)),
                   interacao.clicar, interacao.clicar_duplo, interacao.passar_mouse,
                   interacao.pressionar_tecla, interacao.digitar,
                   tela.assinatura_tela, tela.tela_mudou, janela_ok,
                   trocar_empresa=trocar_empresa, voltar_inicio=voltar_inicio, empresa_atual=empresa_atual)


def _rotulo(numero, valor, o_que):
    if not isinstance(valor, str) or not 3 <= len(valor.strip()) <= 80 or any(ord(c) < 32 for c in valor):
        raise ConfiguradorErro(f"Passo {numero}: descreva {o_que} em poucas palavras (3 a 80 letras).")
    if _PROIBIDAS.search(_sem_acento(valor)):
        raise ConfiguradorErro(f"Passo {numero}: o configurador não automatiza transmitir, retificar, excluir ou enviar.")
    return valor.strip()


def _retangulo(numero, dados, tamanho, minimo, maximo):
    if not isinstance(dados, dict):
        raise ConfiguradorErro(f"Passo {numero}: marque um retângulo na imagem.")
    x, y, largura, altura = (dados.get(k) for k in ("x", "y", "largura", "altura"))
    if not all(_inteiro(v) for v in (x, y, largura, altura)):
        raise ConfiguradorErro(f"Passo {numero}: marque um retângulo na imagem.")
    if not (minimo <= largura <= maximo[0] and minimo <= altura <= maximo[1]):
        raise ConfiguradorErro(f"Passo {numero}: o retângulo deve ter entre {minimo}x{minimo} e {maximo[0]}x{maximo[1]} pixels.")
    if x < 0 or y < 0 or x + largura > tamanho[0] or y + altura > tamanho[1]:
        raise ConfiguradorErro(f"Passo {numero}: o retângulo sai da imagem.")
    return {"x": x, "y": y, "largura": largura, "altura": altura}


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
        if tipo == "se_aparecer":
            # Condicional só para o que é variável (aviso que às vezes aparece): reconhece a TELA pelo recorte e
            # responde com um clique (posição relativa ao recorte, então vale mesmo que a janela apareça noutro
            # lugar) ou com uma tecla. Por padrão é opcional: se não aparecer, a rotina segue.
            item["rotulo"] = _rotulo(numero, passo.get("rotulo"), "a tela que pode aparecer")
            captura = passo.get("captura_id")
            if not isinstance(captura, str) or not _ID.fullmatch(captura):
                raise ConfiguradorErro(f"Passo {numero}: capture a tela e marque a tela esperada na imagem.")
            tamanho = tamanho_captura(captura)
            if tamanho is None:
                raise ConfiguradorErro(f"Passo {numero}: a captura não existe mais; capture a tela de novo.")
            item["captura_id"] = captura
            item.update(_retangulo(numero, passo, tamanho, 16, (900, 700)))
            resposta = passo.get("resposta")
            if not isinstance(resposta, dict) or resposta.get("tipo") not in ("clicar", "tecla"):
                raise ConfiguradorErro(f"Passo {numero}: escolha a resposta: clicar em um botão da tela ou apertar uma tecla.")
            if resposta["tipo"] == "tecla":
                if resposta.get("tecla") not in TECLAS:
                    raise ConfiguradorErro(f"Passo {numero}: tecla não permitida.")
                item["resposta"] = {"tipo": "tecla", "tecla": resposta["tecla"]}
            else:
                alvo = _retangulo(numero, resposta, tamanho, 8, (600, 400))
                item["resposta"] = {"tipo": "clicar", **alvo, "rotulo": _rotulo(numero, resposta.get("rotulo"), "o botão a clicar")}
                item["deslocamento"] = [alvo["x"] + alvo["largura"] // 2 - (item["x"] + item["largura"] // 2),
                                        alvo["y"] + alvo["altura"] // 2 - (item["y"] + item["altura"] // 2)]
            espera = passo.get("espera", 10)
            if not _inteiro(espera) or not 1 <= espera <= 120:
                raise ConfiguradorErro(f"Passo {numero}: a espera pela tela vai de 1 a 120 segundos.")
            obrigatorio = passo.get("obrigatorio", False)
            if not isinstance(obrigatorio, bool):
                raise ConfiguradorErro(f"Passo {numero}: obrigatório deve ser sim ou não.")
            item.update(espera=espera, obrigatorio=obrigatorio)
        elif tipo in TIPOS_ALVO:
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
                if not _inteiro(segundos) or not 1 <= segundos <= 120:
                    raise ConfiguradorErro(f"Passo {numero}: a espera pela imagem vai de 1 a 120 segundos.")
                item["segundos"] = segundos
            else:
                espera = passo.get("espera", 20)
                if not _inteiro(espera) or not 1 <= espera <= 120:
                    raise ConfiguradorErro(f"Passo {numero}: a espera pelo alvo vai de 1 a 120 segundos.")
                item["espera"] = espera
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
        elif tipo in ("trocar_empresa", "voltar_tela_principal"):
            pass  # sem campos: a empresa vem do parâmetro empresa_codigo
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
    if any(p["tipo"] == "trocar_empresa" for p in passos):
        usados.add("empresa_codigo")
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
                "parametros": sorted({p["parametro"] for p in dados["passos"] if p.get("parametro")}
                                     | ({"empresa_codigo"} if any(p["tipo"] == "trocar_empresa" for p in dados["passos"]) else set())),
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
        passos = [{k: v for k, v in p.items() if k not in ("modelo", "modelo_alvo")}
                  | {"tem_modelo": "modelo" in p, "tem_modelo_alvo": "modelo_alvo" in p} for p in dados["passos"]]
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
                if item["tipo"] in TIPOS_ALVO or item["tipo"] == "se_aparecer":
                    with Image.open(self._arquivo_captura(item["captura_id"])) as captura:
                        captura = captura.convert("RGB")
                        recorte = captura.crop((item["x"], item["y"], item["x"] + item["largura"], item["y"] + item["altura"]))
                        nome_modelo = f"passo_{item['indice']:02d}.png"
                        recorte.save(pasta / nome_modelo, format="PNG")
                        item["modelo"] = nome_modelo
                        resposta = item.get("resposta")
                        if resposta and resposta["tipo"] == "clicar":
                            botao = captura.crop((resposta["x"], resposta["y"], resposta["x"] + resposta["largura"],
                                                  resposta["y"] + resposta["altura"]))
                            botao.save(pasta / f"passo_{item['indice']:02d}_alvo.png", format="PNG")
                            item["modelo_alvo"] = f"passo_{item['indice']:02d}_alvo.png"
            guardados = {p.get("modelo") for p in limpos} | {p.get("modelo_alvo") for p in limpos}
            for sobra in pasta.glob("passo_*.png"):
                if sobra.name not in guardados:
                    sobra.unlink(missing_ok=True)
            dados = {"nome": nome, "passos": limpos, "status": "rascunho", "criada_em": dt.datetime.now().isoformat(timespec="seconds")}
            self._gravar(rotina_id, dados)
        return self.obter(rotina_id)

    # ---- pedidos ao Claude (VS Code) ------------------------------------------------------------------------------
    # Caixa de pedidos por arquivo: o painel grava o pedido com o contexto da rotina (passos, último teste), e o
    # Claude, na sessão do VS Code, lê (scripts/pedidos_configurador.py), corrige e escreve a resposta no mesmo
    # arquivo, que o painel mostra. Nada sai do PC: só texto digitado, descrições e o resultado do teste.
    def _pasta_pedidos(self):
        return self.pasta / "pedidos"

    def pedir(self, texto, rotina_id=None):
        if not isinstance(texto, str) or not 5 <= len(texto.strip()) <= 2000 or any(ord(c) < 32 and c not in "\n\t" for c in texto):
            raise ConfiguradorErro("Escreva o pedido com 5 a 2000 caracteres.")
        contexto = None
        nome = None
        if rotina_id is not None:
            dados = self._ler(rotina_id)
            nome, teste = dados["nome"], dados.get("ultimo_teste")
            contexto = {"status": dados["status"], "passos": [{k: v for k, v in p.items() if k not in ("modelo", "modelo_alvo")}
                                                              for p in dados["passos"]],
                        "ultimo_teste": teste and {"ok": teste["ok"], "em": teste["em"], "passo_falho": teste.get("passo_falho"),
                                                   "passos": teste.get("passos")}}
        pedido_id = uuid.uuid4().hex
        pasta = self._pasta_pedidos()
        pasta.mkdir(parents=True, exist_ok=True)
        registro = {"id": pedido_id, "criado_em": dt.datetime.now().isoformat(timespec="seconds"), "rotina_id": rotina_id,
                    "rotina_nome": nome, "texto": texto.strip(), "status": "pendente", "resposta": None, "contexto": contexto}
        (pasta / f"{pedido_id}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._resumo_pedido(registro)

    @staticmethod
    def _resumo_pedido(registro):
        return {k: registro.get(k) for k in ("id", "criado_em", "rotina_id", "rotina_nome", "texto", "status", "resposta", "respondido_em")}

    def _ler_pedido(self, pedido_id):
        if not isinstance(pedido_id, str) or not _ID.fullmatch(pedido_id):
            raise ConfiguradorErro("Pedido não encontrado.")
        arquivo = self._pasta_pedidos() / f"{pedido_id}.json"
        try:
            return json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ConfiguradorErro("Pedido não encontrado.") from None

    def listar_pedidos(self):
        pasta = self._pasta_pedidos()
        if not pasta.is_dir():
            return []
        registros = []
        for arquivo in pasta.glob("*.json"):
            try:
                registros.append(self._resumo_pedido(json.loads(arquivo.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                continue
        return sorted(registros, key=lambda r: r["criado_em"], reverse=True)[:50]

    def obter_pedido(self, pedido_id):
        return self._ler_pedido(pedido_id)

    def responder_pedido(self, pedido_id, resposta):
        registro = self._ler_pedido(pedido_id)
        if not isinstance(resposta, str) or not 1 <= len(resposta.strip()) <= 4000:
            raise ConfiguradorErro("Escreva a resposta com até 4000 caracteres.")
        registro.update(status="atendido", resposta=resposta.strip(), respondido_em=dt.datetime.now().isoformat(timespec="seconds"))
        (self._pasta_pedidos() / f"{pedido_id}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._resumo_pedido(registro)

    def excluir(self, rotina_id):
        import shutil
        pasta = self._pasta_rotina(rotina_id)
        self._ler(rotina_id)
        shutil.rmtree(pasta, ignore_errors=True)

    def modelo(self, rotina_id, indice, parte="modelo"):
        dados = self._ler(rotina_id)
        if parte not in ("modelo", "modelo_alvo"):
            return None
        for passo in dados["passos"]:
            if passo["indice"] == indice and parte in passo:
                caminho = self._pasta_rotina(rotina_id) / passo[parte]
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

    def esperar_estavel(tentativas=30):
        """Espera a tela parar de mudar (duas leituras seguidas iguais): o GO-Global repinta devagar."""
        anterior, estaveis = d.assinatura(d.capturar()), 0
        for _ in range(tentativas):
            d.dormir(0.5)
            atual = d.assinatura(d.capturar())
            estaveis = 0 if d.mudou(anterior, atual) else estaveis + 1
            if estaveis >= 2:
                return True
            anterior = atual
        return False

    def procurar(passo, tempo):
        modelo = Path(pasta_rotina) / passo["modelo"]
        tentativas = int(tempo) + 1
        for numero in range(tentativas):
            posicao = d.achar_template(d.capturar(), modelo)
            if posicao is not None:
                # Segue assim que aparece, mas só depois de ver o alvo parado no mesmo lugar numa segunda leitura
                # (o GO-Global pinta aos poucos: um quadro "meio desenhado" não deve receber o clique).
                d.dormir(0.4)
                confirmada = d.achar_template(d.capturar(), modelo)
                if confirmada is not None and abs(confirmada[0] - posicao[0]) <= 4 and abs(confirmada[1] - posicao[1]) <= 4:
                    return confirmada
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
            posicao = procurar(passo, passo.get("espera", 20))
            if posicao is None:
                return falhar(passo, f"Não achei '{passo['rotulo']}' na tela em {passo.get('espera', 20)} s.")
            antes = d.assinatura(d.capturar())
            {"clicar": d.clicar, "duplo_clique": d.clicar_duplo, "hover": d.passar_mouse}[tipo](*posicao)
            detalhe = f"{passo['rotulo']}: ok"
            if tipo != "hover":
                mudou = esperar_mudanca(antes)
                if not mudou:
                    detalhe += " (a tela não mudou depois da ação)"
                elif not esperar_estavel():
                    detalhe += " (a tela continuou mudando; seguindo assim mesmo)"
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": detalhe})
        elif tipo == "se_aparecer":
            posicao = procurar(passo, passo["espera"])
            if posicao is None:
                if passo["obrigatorio"]:
                    return falhar(passo, f"A tela '{passo['rotulo']}' não apareceu em {passo['espera']} s.")
                registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True,
                                 "detalhe": f"{passo['rotulo']}: não apareceu; seguindo"})
                continue
            resposta = passo["resposta"]
            if resposta["tipo"] == "clicar":
                dx, dy = passo["deslocamento"]
                antes = d.assinatura(d.capturar())
                d.clicar(posicao[0] + dx, posicao[1] + dy)
                esperar_mudanca(antes)
                esperar_estavel()
                detalhe = f"{passo['rotulo']}: apareceu; cliquei em '{resposta['rotulo']}'"
            else:
                d.tecla(resposta["tecla"])
                detalhe = f"{passo['rotulo']}: apareceu; tecla {resposta['tecla']}"
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": detalhe})
        elif tipo == "trocar_empresa":
            if d.trocar_empresa is None:
                return falhar(passo, "Troca de empresa indisponível neste modo.")
            alvo = parametros["empresa_codigo"]
            atual = d.empresa_atual() if d.empresa_atual is not None else None
            if atual is not None and int(atual) == int(alvo):
                # Igual às rotinas normais: já está na empresa certa, não repete o F8.
                registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True,
                                 "detalhe": f"já estava na empresa {alvo}; troca pulada"})
                continue
            if not d.trocar_empresa(alvo):
                return falhar(passo, f"Não consegui trocar para a empresa {alvo}; confira o Domínio.")
            depois = d.empresa_atual() if d.empresa_atual is not None else None
            if depois is not None and int(depois) != int(alvo):
                return falhar(passo, f"Depois da troca o Domínio mostra a empresa {depois}, não a {alvo}. Parei.")
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True,
                             "detalhe": f"empresa {alvo} selecionada"})
        elif tipo == "voltar_tela_principal":
            if d.voltar_inicio is None:
                return falhar(passo, "Volta à tela principal indisponível neste modo.")
            if not d.voltar_inicio():
                return falhar(passo, "Não consegui deixar o Domínio na tela principal; confira a tela.")
            registro.append({"indice": passo["indice"], "tipo": tipo, "ok": True, "detalhe": "tela principal confirmada"})
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
