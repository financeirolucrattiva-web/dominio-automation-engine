"""Consulta à IA (Claude Haiku) para classificar uma caixa de erro nova.

Regras fixas (seção 5.5 e 0.32 do documento):

- Só recebe **texto já anonimizado** (`erros.anonimizar()`), nunca
  imagem, nunca nome/código/CNPJ de empresa.
- Só **escolhe** uma das ações fixas de `erros.ACOES` — a resposta é
  forçada num formato JSON com a lista fechada de ações; qualquer coisa
  fora disso é descartada.
- Tudo que é enviado fica registrado em `data/ia_envios.log` (local),
  pra conferir depois exatamente o que saiu da máquina.

Chave da API: variável de ambiente `ANTHROPIC_API_KEY` ou uma linha só
no arquivo `data/chave_api.txt` (pasta `data/` nunca sobe pro GitHub).
Sem chave, `classificar_erro()` devolve None e o motor segue sem IA.
"""

import datetime
import json
import os
from pathlib import Path

from . import erros

MODELO = "claude-haiku-4-5"
PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO_CHAVE = PASTA_DADOS / "chave_api.txt"
ARQUIVO_LOG = PASTA_DADOS / "ia_envios.log"

_SISTEMA = (
    "Você ajuda um robô que opera o sistema contábil Domínio Escrita Fiscal "
    "(Thomson Reuters) pela tela, gerando arquivos SPED Fiscal (EFD ICMS/IPI) e "
    "EFD Contribuições, empresa por empresa, em lote. No meio da geração apareceu "
    "uma caixa de mensagem do Domínio. Você recebe só o texto dela (lido por OCR, "
    "pode ter erro de leitura; dados da empresa foram trocados por marcadores como "
    "<EMPRESA>, <NOME>, <CAMINHO> e #). Escolha a ação do robô entre as opções "
    "abaixo. Nenhuma ação altera lançamentos nem transmite nada.\n\n"
    + "\n".join(f"- {nome}: {descricao}" for nome, descricao in erros.ACOES.items())
    + "\n\nUse confiança \"alta\" só quando o texto deixa claro o que aconteceu. "
    "Se o texto estiver ilegível ou ambíguo, use confiança \"baixa\". "
    "Responda o motivo em português, em uma frase curta."
)

_FORMATO = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "acao": {"type": "string", "enum": list(erros.ACOES)},
            "confianca": {"type": "string", "enum": ["alta", "baixa"]},
            "motivo": {"type": "string"},
        },
        "required": ["acao", "confianca", "motivo"],
        "additionalProperties": False,
    },
}


def _chave_api():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"].strip()
    try:
        return ARQUIVO_CHAVE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def obter_chave_api():
    """Versão pública de `_chave_api()` — reaproveitada por `app/visao.py`
    pra não duplicar a lógica de onde a chave mora (variável de ambiente
    ou `data/chave_api.txt`)."""
    return _chave_api()


def _registrar(texto, resultado):
    try:
        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        with ARQUIVO_LOG.open("a", encoding="utf-8") as f:
            agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            f.write(f"[{agora}] ENVIADO: {texto!r}\n[{agora}] RESPOSTA: {resultado}\n")
    except OSError:
        pass


def disponivel():
    """True se tem chave configurada e a biblioteca instalada."""
    if not _chave_api():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def classificar_erro(texto_anonimizado, documento=""):
    """Pergunta à IA qual ação tomar. Devolve (acao, confianca, motivo)
    ou None se a IA não estiver disponível ou a resposta não servir."""
    chave = _chave_api()
    if not chave:
        print("IA não configurada (sem chave em data/chave_api.txt nem ANTHROPIC_API_KEY).")
        return None
    try:
        import anthropic
    except ImportError:
        print("Biblioteca 'anthropic' não instalada (rode Atualizar.bat / pip install -r requirements.txt).")
        return None

    pergunta = f"Documento sendo gerado: {documento or 'não informado'}\n\nTexto da caixa:\n{texto_anonimizado}"
    print("Consultando a IA (só o texto anonimizado acima é enviado)...")
    try:
        cliente = anthropic.Anthropic(api_key=chave, timeout=30.0, max_retries=2)
        resposta = cliente.messages.create(
            model=MODELO,
            max_tokens=512,
            system=_SISTEMA,
            messages=[{"role": "user", "content": pergunta}],
            output_config={"format": _FORMATO},
        )
    except anthropic.AuthenticationError:
        print("A chave da IA foi recusada — confira data/chave_api.txt.")
        _registrar(texto_anonimizado, "erro: chave recusada")
        return None
    except anthropic.APIConnectionError:
        print("Sem conexão com a IA (internet?).")
        _registrar(texto_anonimizado, "erro: sem conexão")
        return None
    except anthropic.APIError as e:
        print(f"A IA respondeu com erro: {e}")
        _registrar(texto_anonimizado, f"erro: {e}")
        return None

    if resposta.stop_reason != "end_turn":
        _registrar(texto_anonimizado, f"resposta incompleta ({resposta.stop_reason})")
        return None
    texto = next((b.text for b in resposta.content if b.type == "text"), "")
    _registrar(texto_anonimizado, texto)
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    if dados.get("acao") not in erros.ACOES:
        return None
    return dados["acao"], dados.get("confianca", "baixa"), dados.get("motivo", "")


def resumir_lote(linhas_resumo):
    """Pede pra IA um parágrafo curto, em português simples, resumindo
    o resultado de um lote (`dominio.executar_lote()`, seção 0.49) — só
    texto, nunca decide nem executa nada; o resumo técnico linha a
    linha continua sendo impresso do mesmo jeito de sempre, isto é só
    um complemento. Sem chave/lib, devolve None e o motor segue sem.

    `linhas_resumo`: lista de strings já sem apelido de empresa (só
    código, seção 0.20) — mesmo cuidado de não expor nome de cliente
    que o resto deste módulo já toma.
    """
    chave = _chave_api()
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    pergunta = "Resultado do lote, uma linha por empresa:\n\n" + "\n".join(linhas_resumo)
    try:
        cliente = anthropic.Anthropic(api_key=chave, timeout=30.0, max_retries=2)
        resposta = cliente.messages.create(
            model=MODELO,
            max_tokens=300,
            system=(
                "Você resume em português simples o resultado de um lote de "
                "geração de arquivos fiscais (SPED Fiscal/EFD Contribuições), "
                "rodado por um robô, empresa por empresa. Escreva só um "
                "parágrafo curto (3-5 frases): quantas empresas, quantos "
                "sucessos e falhas, e se houver o mesmo motivo de falha se "
                "repetindo, mencione. Não invente número que não esteja na "
                "lista recebida. Não sugira ação nenhuma, só descreva o que "
                "aconteceu."
            ),
            messages=[{"role": "user", "content": pergunta}],
        )
    except anthropic.APIError:
        return None

    if resposta.stop_reason != "end_turn":
        return None
    texto = next((b.text for b in resposta.content if b.type == "text"), None)
    _registrar(pergunta, texto or "sem resposta de texto")
    return texto


def diagnosticar_busca_falha(alvo, texto_visto, contexto=""):
    """Pede pra IA uma hipótese de por que uma busca de texto na tela
    (`dominio.achar_ou_parar()`) não achou `alvo` — a partir do texto
    que o OCR realmente leu (seção 0.49). **Só sugestão em texto**:
    nunca decide, nunca clica, nunca muda código sozinha — quem lê o
    palpite e decide o que fazer continua sendo uma pessoa. Sem
    chave/lib, devolve None e o motor segue só com o aviso técnico de
    sempre ("Não achei 'X'.").

    `texto_visto`: string com o texto lido por OCR na tela onde a
    busca falhou, **já anonimizada** por quem chama (mesmo cuidado de
    `erros.anonimizar()`) — pode ter erro de leitura, mesma limitação
    de sempre (seção 0.10/0.29).
    """
    chave = _chave_api()
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    pergunta = (
        f"Automação: {contexto or 'não informado'}\n"
        f"Texto procurado, não encontrado: {alvo!r}\n\n"
        f"Texto que o OCR leu na tela (pode ter erro de leitura):\n{texto_visto[:1500]}"
    )
    try:
        cliente = anthropic.Anthropic(api_key=chave, timeout=30.0, max_retries=2)
        resposta = cliente.messages.create(
            model=MODELO,
            max_tokens=400,
            system=(
                "Você ajuda a depurar um robô que navega o sistema Domínio "
                "Escrita Fiscal lendo a tela por OCR (Tesseract) e clicando "
                "em texto encontrado. Uma busca por um texto-alvo falhou. "
                "Você recebe o texto-alvo e o que o OCR leu na tela inteira. "
                "Hipóteses comuns já vistas neste projeto: o OCR leu a "
                "palavra errada por erro de leitura; a tela está densa "
                "demais e OCR de tela inteira não pega texto pequeno (nesse "
                "caso, sugira recortar a área antes e aumentar o zoom só "
                "dentro do recorte, em vez de buscar na tela inteira); ou a "
                "tela mudou de estado (fechou sozinha, apareceu outra "
                "caixa). Responda em português, só um parágrafo curto (3-4 "
                "frases) com a hipótese mais provável e uma sugestão "
                "concreta. Você só sugere — não decide nem executa nada."
            ),
            messages=[{"role": "user", "content": pergunta}],
        )
    except anthropic.APIError:
        return None

    if resposta.stop_reason != "end_turn":
        return None
    texto = next((b.text for b in resposta.content if b.type == "text"), None)
    _registrar(pergunta, texto or "sem resposta de texto")
    return texto


# Técnicas de nova tentativa já usadas e validadas neste projeto
# (seções 0.10/0.28/0.29/0.46) — a IA só ESCOLHE uma destas, nunca
# escreve nem executa código novo (mesmo formato fechado de
# erros.ACOES). Nenhuma delas clica em nada: só mudam COMO a tela é
# lida de novo, nunca O QUE é clicado depois (seção 0.51).
ESTRATEGIAS_RETRY = {
    "ZOOM_MAIOR": "Tenta de novo a mesma busca com mais zoom no OCR — "
                  "ajuda com texto pequeno.",
    "RECORTE_CENTRAL": "Tenta de novo só na região central da tela — "
                        "ajuda quando a tela está densa e a busca na "
                        "tela inteira se perde.",
    "NOVA_TELA": "Tira um novo print e tenta de novo — ajuda se a tela "
                 "ainda estava mudando/repintando.",
    "OUTRO_MOTOR_OCR": "Tenta de novo a mesma busca com o motor de OCR "
                       "nativo do Windows em vez do Tesseract — ajuda "
                       "quando o texto existe e está legível, mas o "
                       "Tesseract especificamente lê errado (ex.: troca "
                       "de letra no fim da palavra).",
    "VISAO_IA": "Última tentativa, mais lenta e só usada se as outras "
                "falharem: pergunta pra um modelo de IA com visão onde "
                "está o elemento, na mesma imagem. Útil quando o "
                "elemento é um ícone sem texto, ou quando o texto "
                "existe mas nenhum motor de OCR consegue ler (ex.: "
                "'OK' de 2 letras). A imagem só é enviada se uma "
                "verificação local não achar nada que pareça dado real "
                "de empresa nela — pode ser recusada automaticamente.",
    "DESISTIR": "Não tenta de novo — deixa como falha, pra uma pessoa "
                "olhar.",
}

_FORMATO_RETRY = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "estrategia": {"type": "string", "enum": list(ESTRATEGIAS_RETRY)},
            "motivo": {"type": "string"},
        },
        "required": ["estrategia", "motivo"],
        "additionalProperties": False,
    },
}


def escolher_estrategia_retry(alvo, texto_visto):
    """Pede pra IA escolher, entre `ESTRATEGIAS_RETRY` (conjunto
    fechado), qual tentar de novo depois de uma busca de texto falhar
    (seção 0.51) — usada por `dominio.achar_ou_parar()` antes de
    desistir de vez. Devolve `(estrategia, motivo)` ou `None` (sem
    chave/lib, resposta fora do formato, ou erro de API) — nesse caso
    quem chamou cai pro comportamento de sempre (desiste e mostra o
    diagnóstico da seção 0.49)."""
    chave = _chave_api()
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    pergunta = (
        f"Texto procurado, não encontrado: {alvo!r}\n\n"
        f"Texto que o OCR leu na tela (pode ter erro de leitura):\n{texto_visto[:1500]}"
    )
    try:
        cliente = anthropic.Anthropic(api_key=chave, timeout=20.0, max_retries=1)
        resposta = cliente.messages.create(
            model=MODELO,
            max_tokens=200,
            system=(
                "Você ajuda um robô que navega o Domínio Escrita Fiscal "
                "lendo a tela por OCR. Uma busca de texto na tela falhou. "
                "Escolha, entre as opções abaixo, qual tentar de novo:\n\n"
                + "\n".join(f"- {nome}: {descricao}" for nome, descricao in ESTRATEGIAS_RETRY.items())
                + "\n\nEscolha DESISTIR se o texto parece não existir de "
                "verdade nesta tela (não é só problema de leitura do OCR)."
            ),
            messages=[{"role": "user", "content": pergunta}],
            output_config={"format": _FORMATO_RETRY},
        )
    except anthropic.APIError:
        return None

    if resposta.stop_reason != "end_turn":
        return None
    texto = next((b.text for b in resposta.content if b.type == "text"), "")
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    if dados.get("estrategia") not in ESTRATEGIAS_RETRY:
        return None
    _registrar(pergunta, texto)
    return dados["estrategia"], dados.get("motivo", "")
