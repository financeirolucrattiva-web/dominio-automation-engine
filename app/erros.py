"""Decide o que fazer quando o Domínio mostra uma caixa de erro.

Fluxo (seção 0.32 do documento):

1. O texto da caixa de erro é lido por OCR **aqui, no próprio PC** —
   a imagem nunca sai da máquina.
2. O texto é anonimizado (`anonimizar()`): números, datas, CNPJ/CPF,
   caminhos de arquivo, e-mails e nomes de empresa viram marcadores
   genéricos antes de qualquer outra coisa acontecer.
3. Procura esse erro no catálogo: primeiro os erros já conhecidos
   (`ERROS_CONHECIDOS`, versionado), depois os que a IA já decidiu antes
   (`data/erros_aprendidos.json`, local, nunca sobe pro GitHub).
4. Só se for um erro nunca visto, pergunta pra IA (`app/ia.py`), que
   só pode escolher uma das ações fixas de `ACOES` — nunca inventa
   clique, nunca digita nada. A decisão vira regra local; o mesmo erro
   não consulta a IA de novo.
5. Sem IA configurada (sem chave, sem internet) ou com resposta de
   baixa confiança, cai no comportamento seguro de antes: `PULAR`.

Nenhuma das ações altera lançamento nem transmite nada — são só formas
diferentes de sair da caixa de erro (regra de segurança da seção 5.7).
"""

import datetime
import difflib
import json
import re
import unicodedata
from pathlib import Path

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO_APRENDIDOS = PASTA_DADOS / "erros_aprendidos.json"

PULAR = "PULAR"
TENTAR_DE_NOVO = "TENTAR_DE_NOVO"
CONTINUAR = "CONTINUAR"
PARAR_LOTE = "PARAR_LOTE"

ACOES = {
    PULAR: "Fecha a caixa de erro e a tela de geração, marca falha neste "
           "documento e segue pra próxima empresa/documento. Use para erro "
           "de cadastro/configuração daquela empresa, que tentar de novo "
           "não resolve.",
    TENTAR_DE_NOVO: "Fecha a caixa de erro e a tela de geração e tenta gerar "
                    "o mesmo documento mais uma vez. Use para erro "
                    "passageiro (tempo esgotado, arquivo em uso, falha "
                    "momentânea de conexão/bloqueio).",
    CONTINUAR: "Só fecha a caixa (Enter) e continua esperando a geração "
               "terminar. Use quando a mensagem é um aviso informativo e a "
               "geração segue normalmente depois dele.",
    PARAR_LOTE: "Fecha a caixa e a tela de geração e para o lote inteiro. "
                "Use quando o erro vai se repetir em todas as empresas "
                "(sessão expirada, licença, sistema fora do ar, sem "
                "permissão, disco cheio).",
}

# Erros já vistos contra o Domínio de verdade, com a ação decidida por
# gente (não pela IA). Chave = trecho do texto já normalizado
# (`normalizar()`), sem acento, minúsculo.
ERROS_CONHECIDOS = {
    # Seção 0.25: pasta/arquivo de destino não configurado naquela
    # empresa — é cadastro dentro do Domínio, tentar de novo não resolve.
    "caminho especificado nao e valido": PULAR,
    # Seção 0.32: "Outros dados não digitados! Deseja copiar do último
    # mês digitado?" (Sim/Não) — decisão do usuário: nunca copiar dado
    # de um mês pro outro sozinho, responder Não e pular a empresa pra
    # alguém revisar à mão (`_fechar_caixa_erro()` clica em "No"
    # especificamente, não em Enter — o botão em foco na caixa real é
    # "Yes", não "No").
    "outros dados nao digitados": PULAR,
    # Seção 0.32: "Saldo dos impostos não foram calculados no
    # período" (só OK) — decisão do usuário: apertar OK mas não gerar
    # sem a apuração feita, pular a empresa pra revisão.
    "saldo dos impostos nao foram calculados": PULAR,
    # Seção 0.57, texto CONFIRMADO ao vivo (a entrada acima era um
    # texto antecipado, nunca visto de verdade até agora — a redação
    # real é diferente): "Falta apurar saldo dos impostos neste
    # intervalo de data!" — visto na tela "Livros Fiscais" ao marcar
    # "Registro de Saídas" numa competência cuja apuração de ICMS
    # ainda não foi fechada no Domínio. Mesma decisão: PULAR, nunca
    # força a geração sem a apuração feita.
    "falta apurar saldo dos impostos": PULAR,
}

# Textos conhecidos de caixa Sim/Não onde o botão certo pra fechar
# **não** é o padrão (em foco) da caixa — precisa achar e clicar no
# texto do botão certo, não usar Enter. Seção 0.32.
BOTAO_NAO_PADRAO = {
    "outros dados nao digitados": "No",
}

# Siglas que aparecem em maiúsculo em mensagem do Domínio e não são
# nome de empresa — não podem ser apagadas pela anonimização.
_SIGLAS_PERMITIDAS = {
    "SPED", "EFD", "ICMS", "IPI", "PIS", "COFINS", "CNPJ", "CPF", "IE",
    "NCM", "CFOP", "CST", "CSOSN", "NF", "NFE", "NFCE", "CTE", "OK",
    "ST", "DIFAL", "REINF", "ECD", "ECF", "DCTF", "UF", "TXT", "XML",
    "ERRO", "ATENCAO", "AVISO", "SIM", "NAO", "CANCELAR",
}

# Decisões tomadas nesta execução do programa — pro resumo do lote.
decisoes_da_sessao = []


def _sem_acento(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def anonimizar(texto, nomes_sensiveis=()):
    """Tira do texto tudo que pode identificar empresa ou pessoa, antes
    de guardar ou mandar pra IA.

    - nomes em `nomes_sensiveis` (ex.: apelido da empresa atual) → <EMPRESA>
    - caminhos de arquivo (C:\\..., \\\\servidor\\...) → <CAMINHO>
    - e-mails → <EMAIL>
    - qualquer número (CNPJ, CPF, data, valor, código) → #
    - sequência de palavras em MAIÚSCULO que não é sigla fiscal
      conhecida (quase sempre razão social) → <NOME>, a não ser que a
      mensagem inteira esteja em maiúsculo (aí apagaria tudo).
    """
    # A detecção de nome em maiúsculo roda primeiro, sobre o texto
    # ainda original — se rodasse depois de inserir os outros
    # marcadores (<CAMINHO>, <EMPRESA>...), o próprio texto do
    # marcador (ex.: "CAMINHO", todo maiúsculo) seria pego de novo por
    # essa mesma regra e viraria "<<NOME>>" por engano.
    t = texto
    letras = [c for c in t if c.isalpha()]
    maiusculas = sum(1 for c in letras if c.isupper())
    if letras and maiusculas / len(letras) < 0.6:
        def trocar(m):
            palavras = m.group(0).split()
            if all(_sem_acento(p).strip(".,:;-") in _SIGLAS_PERMITIDAS for p in palavras):
                return m.group(0)
            return "<NOME>"
        t = re.sub(r"\b[A-ZÀ-Ý][A-ZÀ-Ý&.\-]{2,}(?:\s+[A-ZÀ-Ý&][A-ZÀ-Ý&.\-]*)*\b", trocar, t)

    for nome in nomes_sensiveis:
        nome = (nome or "").strip()
        if len(nome) >= 3:
            t = re.sub(re.escape(nome), "<EMPRESA>", t, flags=re.IGNORECASE)
    t = re.sub(r"[A-Za-z]:[\\/][^\s'\"]*", "<CAMINHO>", t)
    t = re.sub(r"\\\\[^\s'\"]+", "<CAMINHO>", t)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<EMAIL>", t)
    t = re.sub(r"\d+", "#", t)

    t = re.sub(r"[ \t]+", " ", t)
    t = "\n".join(linha.strip() for linha in t.splitlines() if linha.strip())
    return t[:1000]


def normalizar(texto):
    """Versão do texto usada como chave de comparação: sem acento,
    minúsculo, sem marcador de anonimização, só letras e espaço."""
    t = _sem_acento(texto).lower()
    t = re.sub(r"<[a-z]+>|#", " ", t)
    t = re.sub(r"[^a-z]+", " ", t)
    return " ".join(t.split())


def carregar_aprendidos():
    try:
        return json.loads(ARQUIVO_APRENDIDOS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        print(f"Aviso: não consegui ler {ARQUIVO_APRENDIDOS.name} ({e}) — ignorando.")
        return []


def salvar_aprendidos(lista):
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_APRENDIDOS.write_text(
        json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _procurar(chave):
    """Devolve (acao, origem) se o erro já é conhecido, senão None.
    Aceita texto quase igual (OCR raramente lê duas vezes idêntico)."""
    for trecho, acao in ERROS_CONHECIDOS.items():
        if trecho in chave:
            return acao, "catálogo fixo"
    for item in carregar_aprendidos():
        if item.get("chave") and difflib.SequenceMatcher(None, item["chave"], chave).ratio() >= 0.85:
            return item["acao"], f"aprendido ({item.get('origem', '?')})"
    return None


def decidir(texto_ocr, nomes_sensiveis=(), documento=""):
    """Decide a ação pra uma caixa de erro. Devolve uma das chaves de
    `ACOES`. Sempre devolve algo — no pior caso, `PULAR`."""
    texto = anonimizar(texto_ocr, nomes_sensiveis)
    chave = normalizar(texto)
    print(f"Texto da caixa de erro (já anonimizado): {texto!r}")

    if not chave:
        print("Não consegui ler texto nenhum na caixa de erro — ação padrão: PULAR.")
        decisoes_da_sessao.append((documento, texto, PULAR, "sem texto"))
        return PULAR

    achado = _procurar(chave)
    if achado:
        acao, origem = achado
        print(f"Erro já conhecido ({origem}) — ação: {acao}")
        decisoes_da_sessao.append((documento, texto, acao, origem))
        return acao

    from . import ia
    resposta = ia.classificar_erro(texto, documento)
    if resposta is None:
        print("Erro novo e IA indisponível — ação padrão: PULAR.")
        decisoes_da_sessao.append((documento, texto, PULAR, "IA indisponível"))
        return PULAR

    acao, confianca, motivo = resposta
    print(f"IA decidiu: {acao} (confiança {confianca}) — {motivo}")
    if confianca != "alta":
        print("Confiança baixa — não arrisco: PULAR, e não guardo como regra.")
        decisoes_da_sessao.append((documento, texto, PULAR, f"IA sugeriu {acao}, confiança baixa"))
        return PULAR

    lista = carregar_aprendidos()
    lista.append({
        "chave": chave,
        "texto": texto,
        "acao": acao,
        "motivo": motivo,
        "origem": "IA",
        "documento": documento,
        "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    salvar_aprendidos(lista)
    decisoes_da_sessao.append((documento, texto, acao, "IA (nova regra)"))
    return acao
