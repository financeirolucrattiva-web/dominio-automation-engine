"""Fallback de visão por IA (Claude) — ÚLTIMO recurso de percepção,
só quando OCR (Tesseract + winocr) e casamento de imagem (OpenCV,
`tela.achar_icone()`/`achar_icone_robusto()`) já falharam.

Decisão do usuário, 05/10/2026 (ver docs/00-analise-e-plano-fase0.md,
seção 0.58, e docs/HANDOFF.md): abre uma EXCEÇÃO CONTROLADA à regra
"nunca manda print pra IA" (seção 5.5) — só sob as condições abaixo,
todas obrigatórias, nenhuma opcional:

1. Só entra em jogo depois de `ia.ESTRATEGIAS_RETRY` esgotar as opções
   sem IA (zoom, recorte central, novo print, outro motor de OCR) —
   nunca é a primeira tentativa, nunca roda em todo clique.
2. Antes de enviar qualquer imagem, roda OCR nela aqui mesmo (na própria
   máquina) e checa com `erros.anonimizar()` se o texto lido tem
   qualquer coisa que pareça dado real (número, nome em maiúsculo,
   caminho, e-mail). Se tiver, RECUSA enviar — sem exceção, mesmo que o
   resto da imagem pareça inofensivo. Só manda a imagem quando essa
   verificação local não encontra nada sensível (o caso normal: barra
   de ícone, título de diálogo, texto de botão — texto estrutural da
   aplicação, não dado de cliente). Isso faz a função recusar sozinha
   a maior parte das capturas de tela inteira (que normalmente mostram
   nome de empresa/código em algum canto) — é o comportamento
   pretendido, não um bug: quem chama deve preferir mandar um recorte
   pequeno em volta do elemento (`tela.recortar_ao_redor()`/
   `recortar_a_partir_de()`), não a tela inteira, pra essa trava não
   bloquear o uso legítimo.
3. A pergunta pra IA e a resposta são sempre de um formato FECHADO
   (JSON Schema, mesmo padrão de `erros.ACOES`/`ia.ESTRATEGIAS_RETRY`)
   — a IA nunca decide ação nenhuma no Domínio, só aponta uma
   coordenada dentro da imagem recortada ou classifica um estado visual
   entre opções que quem chama já definiu.
4. Toda imagem efetivamente enviada fica salva localmente em
   `data/visao_enviado/` (gitignored, nunca sobe pro GitHub) com
   timestamp, pra auditoria depois — dado o risco maior desse tipo de
   envio comparado a texto anonimizado, nada é descartado sem rastro.
   Uma recusa por dado sensível também fica registrada (sem salvar a
   imagem recusada).
5. Sem chave de API configurada, sem a biblioteca `anthropic`, ou sem
   `Pillow`, a função devolve `None` e quem chamou cai no comportamento
   de sempre (busca falhou → diagnóstico de texto → revisão humana) —
   mesma degradação graciosa do resto da IA neste projeto.

Nenhuma função aqui clica em nada nem decide ação — só percepção
(“onde está” / “que estado é esse”), igual ao resto do `PerceptionEngine`
informal já existente em `tela.py`.
"""

import base64
import datetime
import io
import json
import re
import unicodedata
from pathlib import Path

from . import erros, ia, tela

# Vocabulário de interface já visto de verdade no Domínio (menus,
# botões, títulos de tela — ver docs/00-analise-e-plano-fase0.md) —
# cresce conforme novas telas forem mapeadas. Uma palavra em maiúsculo
# que NÃO está aqui é tratada como possível nome de empresa e bloqueia
# o envio — proposital recusar demais a errar pra menos (seção 0.58).
_PALAVRAS_SEGURAS = {
    "OK", "FECHAR", "CANCELAR", "SIM", "NAO", "ATENCAO", "AVISO",
    "SPED", "EFD", "ICMS", "IPI", "PIS", "COFINS", "CNPJ", "CPF",
    "RELATORIOS", "INFORMATIVOS", "FEDERAIS", "ESTADUAIS", "LIVROS",
    "FISCAIS", "LIVRO", "REGISTRO", "GERAL", "TERMOS", "ENTRADAS",
    "SAIDAS", "INVENTARIO", "CONCLUIR", "ATIVIDADE", "SELECIONE",
    "ARQUIVO", "SALVAR", "DOWNLOADS", "DESKTOP", "DOCUMENTOS", "PDF",
    "EXCEL", "ESCRITA", "DOMINIO", "EMPRESAS", "COMPETENCIA",
    "INICIAL", "FINAL", "MODELO",
}


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")

MODELO = "claude-sonnet-5-5"  # precisa ver imagem; sonnet já é suficiente e mais barato que Opus para uma classificação fechada
PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
PASTA_ENVIADOS = PASTA_DADOS / "visao_enviado"
ARQUIVO_LOG = PASTA_DADOS / "visao_envios.log"


def disponivel():
    """True se tem chave configurada e as bibliotecas necessárias
    instaladas — mesmo padrão de `ia.disponivel()`."""
    if not ia.obter_chave_api():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _contem_dado_sensivel(imagem):
    """True se o OCR local achar qualquer coisa que pareça dado real —
    nesse caso a imagem NUNCA é enviada, sem exceção. Imagem sem texto
    nenhum (ícone puro) devolve False — é o caso normal de uso desta
    função.

    **Não usa só `erros.anonimizar()`** — aquela função, de propósito,
    NÃO mascara um texto que está inteiro em maiúsculo (pra não apagar
    a mensagem toda de uma caixa de erro, onde isso é comum e não é
    nome de empresa). Mas aqui o caso mais provável de vazamento é
    justamente esse: um nome de empresa sozinho, em maiúsculo, no
    título/cabeçalho da tela (achado real testando esta função,
    05/10/2026: "SPRAYAGRO CONSULTORIA LTDA" não era barrado por
    `anonimizar()` sozinho). Por isso a checagem própria abaixo roda
    PRIMEIRO e é mais conservadora: qualquer sequência de 2+ dígitos
    (CNPJ, CPF, data, valor, código) ou qualquer palavra de 4+ letras
    toda maiúscula que não esteja em `_PALAVRAS_SEGURAS` já barra —
    `anonimizar()` entra só como rede adicional (caminho, e-mail, nome
    em texto majoritariamente minúsculo)."""
    texto_bruto = (tela.ler_texto(imagem, escala=2) or "").strip()
    if not texto_bruto:
        return False

    if re.search(r"\d{2,}", texto_bruto):
        return True

    for palavra in re.findall(r"[A-Za-zÀ-ÿ]{4,}", texto_bruto):
        if palavra.isupper() and _sem_acento(palavra).upper() not in _PALAVRAS_SEGURAS:
            return True

    anonimizado = erros.anonimizar(texto_bruto)
    return any(m in anonimizado for m in ("<NOME>", "<EMPRESA>", "<CAMINHO>", "<EMAIL>"))


def _imagem_para_base64(imagem):
    buffer = io.BytesIO()
    imagem.convert("RGB").save(buffer, format="PNG")
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def _registrar(contexto, pergunta, resultado, imagem=None, recusado_por_dado_sensivel=False):
    try:
        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        agora = datetime.datetime.now()
        linha_hora = agora.strftime("%d/%m/%Y %H:%M:%S")
        with ARQUIVO_LOG.open("a", encoding="utf-8") as f:
            if recusado_por_dado_sensivel:
                f.write(f"[{linha_hora}] RECUSADO (dado sensível detectado localmente) — contexto: {contexto}\n")
                return
            f.write(f"[{linha_hora}] contexto={contexto!r} pergunta={pergunta!r} resultado={resultado}\n")
        if imagem is not None:
            PASTA_ENVIADOS.mkdir(parents=True, exist_ok=True)
            carimbo = agora.strftime("%Y%m%d_%H%M%S_%f")
            imagem.save(PASTA_ENVIADOS / f"{carimbo}.png")
    except OSError:
        pass


def _chamar_claude_vision(imagem, pergunta_sistema, pergunta_usuario, formato, contexto):
    """Núcleo compartilhado: checa dado sensível, chama a API com a
    imagem + pergunta de formato fechado, registra tudo. Devolve o dict
    decodificado do JSON Schema, ou None (sem chave/lib, dado sensível
    detectado, erro de API, ou resposta fora do formato)."""
    if _contem_dado_sensivel(imagem):
        print("Visão por IA recusada: a imagem recortada parece conter dado real (número/nome/caminho) — não enviada.")
        _registrar(contexto, pergunta_usuario, None, recusado_por_dado_sensivel=True)
        return None

    chave = ia.obter_chave_api()
    if not chave:
        return None
    try:
        import anthropic
    except ImportError:
        print("Biblioteca 'anthropic' não instalada — visão por IA indisponível.")
        return None

    print(f"Consultando IA de visão (último recurso de percepção) — {contexto}")
    try:
        cliente = anthropic.Anthropic(api_key=chave, timeout=30.0, max_retries=1)
        resposta = cliente.messages.create(
            model=MODELO,
            max_tokens=400,
            system=pergunta_sistema,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _imagem_para_base64(imagem)}},
                    {"type": "text", "text": pergunta_usuario},
                ],
            }],
            output_config={"format": formato},
        )
    except anthropic.AuthenticationError:
        print("A chave da IA foi recusada — confira data/chave_api.txt.")
        _registrar(contexto, pergunta_usuario, "erro: chave recusada", imagem=imagem)
        return None
    except anthropic.APIConnectionError:
        print("Sem conexão com a IA (internet?).")
        _registrar(contexto, pergunta_usuario, "erro: sem conexão", imagem=imagem)
        return None
    except anthropic.APIError as e:
        print(f"IA de visão respondeu com erro: {e}")
        _registrar(contexto, pergunta_usuario, f"erro: {e}", imagem=imagem)
        return None

    if resposta.stop_reason != "end_turn":
        _registrar(contexto, pergunta_usuario, f"resposta incompleta ({resposta.stop_reason})", imagem=imagem)
        return None
    texto = next((b.text for b in resposta.content if b.type == "text"), "")
    _registrar(contexto, pergunta_usuario, texto, imagem=imagem)
    try:
        return json.loads(texto)
    except ValueError:
        return None


_FORMATO_LOCALIZAR = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "encontrado": {"type": "boolean"},
            "x": {"type": ["integer", "null"]},
            "y": {"type": ["integer", "null"]},
            "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
            "motivo": {"type": "string"},
        },
        "required": ["encontrado", "x", "y", "confianca", "motivo"],
        "additionalProperties": False,
    },
}


def localizar_elemento(imagem_recortada, descricao_alvo, contexto=""):
    """Última tentativa de achar um elemento visual (ícone/botão) numa
    imagem já recortada — só depois de OCR (`tela.achar_texto()`/
    `achar_texto_windows()`) e casamento de imagem (`tela.achar_icone()`/
    `achar_icone_robusto()`) já terem falhado.

    `imagem_recortada` DEVE ser um recorte pequeno (barra de ícone,
    título de diálogo, área de botão) — nunca a tela inteira; a função
    ainda roda `_contem_dado_sensivel()` como segunda trava, mas a
    responsabilidade de recortar pequeno é de quem chama (recortes
    maiores têm mais chance de conter dado de cliente em algum canto e
    serem recusados).

    Coordenadas devolvidas são relativas ao canto superior esquerdo do
    recorte enviado, não à tela inteira — quem chama soma o
    deslocamento conhecido do recorte.

    Devolve `(x, y, confianca, motivo)` ou `None` (sem chave/lib, dado
    sensível detectado, elemento não encontrado, ou erro de API) — em
    todos os casos quem chama deve cair no comportamento de sempre
    (desistir e pedir revisão humana)."""
    sistema = (
        "Você ajuda um robô a localizar um elemento visual (ícone, "
        "botão) numa captura de tela recortada do sistema Domínio "
        "Escrita Fiscal. A imagem já foi filtrada para conter só "
        "elementos de interface (barra de ferramentas, título de "
        "janela, botão) — nunca dado de cliente. Aponte o centro do "
        "elemento descrito, em pixels, relativo ao canto superior "
        "esquerdo DESTA imagem recortada. Se não achar o elemento "
        "descrito, responda encontrado=false, x=null, y=null."
    )
    pergunta = f"Elemento procurado: {descricao_alvo}"
    resultado = _chamar_claude_vision(
        imagem_recortada, sistema, pergunta, _FORMATO_LOCALIZAR, contexto or f"localizar:{descricao_alvo}"
    )
    if not resultado or not resultado.get("encontrado"):
        return None
    x, y = resultado.get("x"), resultado.get("y")
    if x is None or y is None:
        return None
    return x, y, resultado.get("confianca", "baixa"), resultado.get("motivo", "")


def classificar_estado(imagem_recortada, estados_possiveis, contexto=""):
    """Última tentativa de reconhecer qual estado visual uma tela
    recortada mostra (ex.: "carregando" vs "sucesso" vs "erro"), entre
    uma lista FECHADA de rótulos que quem chama já espera — mesmas
    travas de `localizar_elemento()` (dado sensível, log, chave
    opcional, formato fechado).

    Devolve `(estado, confianca, motivo)` ou `None`."""
    formato = {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "estado": {"type": "string", "enum": list(estados_possiveis) + ["desconhecido"]},
                "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                "motivo": {"type": "string"},
            },
            "required": ["estado", "confianca", "motivo"],
            "additionalProperties": False,
        },
    }
    sistema = (
        "Você ajuda um robô a reconhecer em que estado visual uma tela "
        "recortada do sistema Domínio Escrita Fiscal está, entre as "
        "opções fechadas abaixo. A imagem já foi filtrada para conter "
        "só elementos de interface, nunca dado de cliente.\n\nOpções: "
        + ", ".join(estados_possiveis) + ". Use \"desconhecido\" se "
        "nenhuma opção bater com confiança."
    )
    resultado = _chamar_claude_vision(
        imagem_recortada, sistema, "Qual o estado desta tela?", formato, contexto or "classificar_estado"
    )
    if not resultado:
        return None
    return resultado.get("estado", "desconhecido"), resultado.get("confianca", "baixa"), resultado.get("motivo", "")
