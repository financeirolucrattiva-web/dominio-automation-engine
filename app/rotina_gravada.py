"""Executa uma rotina gravada pelo gravador (`scripts/gravar.py`)
direto a partir dos passos salvos, sem precisar de código Python novo
nem de um programador revisando/colando função dentro de
`app/dominio.py` — pedido do usuário (07/10/2026, seção 0.82): criar
rotina nova tem que ficar fácil pra quem não programa.

Reaproveita a MESMA lógica de confiabilidade já validada no resto do
projeto (`dominio.achar_ou_parar()`, espera por estado via fingerprint
de tela, catálogo de erro) — não é um motor novo e separado, é o motor
de sempre lendo um roteiro gravado em vez de um roteiro escrito à mão.

**Diferença importante em relação a `dominio.AUTOMACOES_EXTRAS`**: uma
rotina gravada aqui nunca foi revisada por um programador linha a
linha. Cada passo de clique usa o texto que o OCR adivinhou no
MOMENTO DA GRAVAÇÃO — mesmo risco já documentado desde o início do
gravador (seção 0.35): pode estar errado. Rodar uma vez supervisionado
antes de confiar sem olhar é esperado, não opcional.
"""

import json
import re
import time
import unicodedata
from pathlib import Path

from . import dominio, interacao, registro_elementos, tela

PASTA_ROTINAS = Path(__file__).resolve().parent.parent / "data" / "rotinas_gravadas"

# Ciclo de vida pedido pelo usuário (07/10/2026, seção 0.82): toda
# rotina gravada nasce RASCUNHO (nunca revisada linha a linha por
# programador) e só vira APROVADA depois de uma execução supervisionada
# confirmada como correta — só rotina APROVADA entra na opção de lote
# (várias empresas); rascunho só roda uma empresa de cada vez, sempre
# supervisionado.
STATUS_RASCUNHO = "rascunho"
STATUS_APROVADA = "aprovada"


def _slug(texto):
    texto = unicodedata.normalize("NFKD", texto.upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9]+", "_", texto).strip("_")
    return texto.lower() or "rotina_sem_nome"


def salvar_rotina_gravada(nome_exibicao, passos, parametros=None):
    """Salva os passos gravados (mesmo formato de `scripts/gravar.py`,
    `Gravador.passos`) como uma rotina pronta pra aparecer na
    interface — nenhum código Python é gerado nem precisa ser colado
    em lugar nenhum.

    `parametros`: lista dos nomes de parâmetro usados — cada passo
    `"digitar"` marcado como parâmetro já deve ter sido ajustado
    ANTES de chamar esta função (`passo["parametro"] = "<nome>"`,
    substituindo o texto fixo gravado por uma variável preenchida na
    hora de executar). Devolve o caminho do arquivo salvo.
    """
    PASTA_ROTINAS.mkdir(parents=True, exist_ok=True)
    slug = _slug(nome_exibicao)
    caminho = PASTA_ROTINAS / f"{slug}.json"
    numero = 1
    while caminho.exists():
        numero += 1
        caminho = PASTA_ROTINAS / f"{slug}_{numero}.json"
    dados = {
        "nome_exibicao": nome_exibicao,
        "passos": passos,
        "parametros": sorted(set(parametros or [])),
        "status": STATUS_RASCUNHO,
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def listar_rotinas_gravadas():
    """Devolve lista de dicts (`nome_exibicao`, `parametros`, `status`,
    `caminho`) — só lê o catálogo local, não executa nada. Entrada
    corrompida ou incompleta é ignorada silenciosamente (arquivo local,
    pode ter sido editado à mão por engano). Arquivo salvo antes do
    campo `status` existir (seção 0.82) é tratado como
    `STATUS_RASCUNHO` — nunca promove sozinho pra aprovada."""
    if not PASTA_ROTINAS.is_dir():
        return []
    rotinas = []
    for caminho in sorted(PASTA_ROTINAS.glob("*.json")):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "passos" not in dados or "nome_exibicao" not in dados:
            continue
        rotinas.append({
            "nome_exibicao": dados["nome_exibicao"],
            "parametros": dados.get("parametros", []),
            "status": dados.get("status", STATUS_RASCUNHO),
            "caminho": caminho,
        })
    return rotinas


def marcar_status(caminho, status):
    """Atualiza o status (`STATUS_RASCUNHO`/`STATUS_APROVADA`) de uma
    rotina já salva — usado depois de uma execução supervisionada que a
    pessoa confirmou como correta (ou pra voltar uma aprovada pra
    rascunho, se algo mudar no Domínio e precisar regravar).

    Virar APROVADA também alimenta `registro_elementos` (seção 0.83,
    "se auto arrumar" em vez de correção manual pra sempre) — o texto
    de cada passo de clique dessa rotina entra no vocabulário de
    elementos confirmados, pra conferir palpite de futuras gravações
    automaticamente. Aprovação humana É a confirmação; nenhum passo a
    mais precisa acontecer."""
    if status not in (STATUS_RASCUNHO, STATUS_APROVADA):
        raise ValueError(f"Status inválido: {status!r}")
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["status"] = status
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    if status == STATUS_APROVADA:
        for passo in dados.get("passos", []):
            if passo.get("tipo", "clicar") == "clicar":
                registro_elementos.registrar_confirmado(passo.get("texto_adivinhado"))


def excluir_rotina_gravada(caminho):
    """Apaga uma rotina gravada do catálogo local — sem confirmação
    aqui dentro (quem chama, a interface, já confirma com a pessoa
    antes)."""
    Path(caminho).unlink(missing_ok=True)


def criar_gerador(passos, parametros=None):
    """Embrulha `executar_passos()` numa função `(prefixo="") -> bool`
    — mesmo formato que os geradores de SPED Fiscal/EFD Contribuições
    já usam em `dominio._GERADORES`/`dominio.executar_lote()`. É o que
    permite uma rotina aprovada entrar no MESMO loop de lote (troca de
    empresa automática, recuperação, pausa — seção 0.82), via
    `dominio.executar_lote(documentos_personalizados=[(nome, gerador)])`,
    em vez de duplicar esse loop."""
    def gerador(prefixo=""):
        return executar_passos(passos, parametros=parametros, prefixo=prefixo)
    return gerador


def carregar_passos(caminho):
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return dados["passos"]


def _esperar_tela_mudar(tentativas=10, intervalo=0.5):
    assinatura_antes = tela.assinatura_tela(tela.capturar_tela())
    for _ in range(tentativas):
        time.sleep(intervalo)
        if tela.tela_mudou(assinatura_antes, tela.assinatura_tela(tela.capturar_tela())):
            return


def executar_passos(passos, parametros=None, prefixo=""):
    """Toca os passos gravados na ordem — clique usa
    `dominio.achar_ou_parar()` (mesma confiabilidade/catálogo de erro
    do resto do motor, inclusive a escolha de estratégia de retentativa
    pela IA quando configurada) e espera genérica por fingerprint entre
    ações (seção 0.58/0.81), igual ao rascunho que `scripts/gravar.py`
    geraria — só que direto, sem precisar gerar/colar código Python.

    `parametros`: dict nome -> valor, pros passos `"digitar"` marcados
    com `"parametro"` — passo sem marcação usa o texto literal gravado.

    Devolve `True` se todos os passos completaram, `False` na primeira
    falha (mesmo print de erro salvo de sempre, em `capturas/`)."""
    parametros = parametros or {}
    interacao.focar_dominio()

    for passo in passos:
        tipo = passo.get("tipo", "clicar")
        indice = passo.get("indice", "?")

        if tipo == "digitar":
            nome_parametro = passo.get("parametro")
            if nome_parametro:
                texto = parametros.get(nome_parametro, "")
                print(f"Passo {indice}: digitando valor do parâmetro {nome_parametro!r}")
            else:
                texto = passo.get("texto", "")
                print(f"Passo {indice}: digitando texto fixo gravado")
            interacao.digitar(texto)
            continue

        if tipo == "hover":
            print(f"Passo {indice}: hover em ({passo['x']}, {passo['y']})")
            interacao.passar_mouse(passo["x"], passo["y"])
            time.sleep(0.5)
            continue

        if tipo == "tecla":
            print(f"Passo {indice}: tecla {passo['tecla']}")
            if passo["tecla"] == "enter":
                interacao.pressionar_enter()
            else:
                interacao.pressionar_tecla(passo["tecla"])
            continue

        # "clicar" (ou gravação antiga sem campo "tipo")
        alvo = passo.get("texto_adivinhado") or ""
        if not alvo:
            print(
                f"Passo {indice}: o OCR não adivinhou nenhum texto pra esse clique na hora "
                "da gravação — não dá pra reproduzir com segurança. Parando."
            )
            return False
        imagem = tela.capturar_tela()
        pos = dominio.achar_ou_parar(imagem, alvo, f"{prefixo}erro_rotina_gravada_passo_{indice:02d}.png")
        if pos is None:
            return False
        print(f"Passo {indice}: clicando em {alvo!r} -> {pos}")
        interacao.clicar(*pos)
        _esperar_tela_mudar()

    print("Rotina gravada concluída (todos os passos executados).")
    return True
