"""Catálogo local de textos de elemento (menu, botão, rótulo) já
CONFIRMADOS corretos — pedido do usuário (07/10/2026, seção 0.83):
"não queria que você arrumasse sempre, gostaria que ele se auto
arrumasse". Em vez de corrigir palpite ruim do gravador um por um pra
sempre, cada palpite novo é conferido contra um vocabulário que
**cresce sozinho**, sem precisar catalogar nada na mão antes.

Como cresce: toda vez que uma rotina gravada é APROVADA
(`rotina_gravada.marcar_status(..., STATUS_APROVADA)`), o texto de
cada passo de clique dela entra automaticamente aqui — aprovação
humana É a confirmação, não precisa de um passo a mais. Começa também
com um "DNA" inicial: textos já usados com sucesso nas rotinas
escritas à mão (`app/dominio.py` — SPED Fiscal, EFD Contribuições,
Registro de Saídas/Entradas), extraídos do próprio código-fonte, não
inventados — meses de uso real, não suposição.

**O que isso NÃO é**: não é um banco de telas/screenshots completo da
aplicação (catalogar cada tela do Domínio manualmente é trabalho
grande, não feito ainda) — é um vocabulário de TEXTO, mais barato de
manter, e já suficiente pra pegar o tipo de erro real visto até agora
(OCR concatenando item de menu com o vizinho por causa do traço
separador, achado real — ver `tela.texto_mais_proximo()`). Virar
reconhecimento visual completo (imagem, não só texto) é um passo
futuro, não este.
"""

import json
import re
import unicodedata
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "vocabulario_elementos.json"

# "DNA" inicial — textos já usados com sucesso em rotinas escritas à
# mão, extraídos de app/dominio.py (grep pelos alvos literais de
# achar_texto()/achar_ou_parar()/esperar_e_achar()), não inventados.
# Ver docs/00-analise-e-plano-fase0.md seção 0.83 pra como foi extraído.
VOCABULARIO_INICIAL = {
    "Acessar", "Data inicial", "Domínio", "Empresas", "Escrita Fiscal",
    "Fechar", "Federais", "Informativ", "Livros", "Livros Fiscais",
    "OK", "Relatórios", "SPED Fiscal", "Contribui", "Registro de Entradas",
    "Registro de Saídas", "REGISTRO", "Inicial", "Final", "Inicia", "Fina",
}


def _normalizar(texto):
    """Minúsculo, sem acento, sem espaço duplicado — compara por
    semelhança, não por igualdade exata (OCR varia maiúscula, espaço,
    acento entre uma leitura e outra do mesmo elemento real)."""
    t = unicodedata.normalize("NFKD", texto.strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t)


def _carregar():
    vocabulario = set(VOCABULARIO_INICIAL)
    if ARQUIVO.exists():
        try:
            dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
            vocabulario |= set(dados.get("textos", []))
        except (OSError, ValueError):
            pass
    return vocabulario


def _salvar(vocabulario):
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(
        json.dumps({"textos": sorted(vocabulario)}, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def registrar_confirmado(texto):
    """Adiciona `texto` ao vocabulário local — chamado quando uma
    rotina gravada é aprovada (confirmação humana de que o clique
    estava certo). Vazio ou já conhecido não faz nada (idempotente —
    aprovar a mesma rotina de novo não duplica)."""
    texto = (texto or "").strip()
    if not texto:
        return
    vocabulario = _carregar()
    if texto in vocabulario or _normalizar(texto) in {_normalizar(v) for v in vocabulario}:
        return
    vocabulario.add(texto)
    _salvar(vocabulario)


def avaliar_palpite(texto):
    """Confere um palpite de OCR (de um clique recém-gravado) contra o
    vocabulário já confirmado. Só INFORMA — nunca decide nem corrige
    sozinho; quem usa (a tela de revisão) mostra pra pessoa decidir.

    Devolve um dict:
    - `{"status": "vazio"}` — nada pra avaliar.
    - `{"status": "conhecido"}` — bate (exato ou por prefixo conhecido,
      ex. "Informativ"/"Contribui") com algo já confirmado antes.
    - `{"status": "parecido", "sugestao": "<texto conhecido>"}` — não
      bate exato, mas contém um texto já conhecido dentro dele (caso
      clássico do bug do traço separador: o palpite concatenou um item
      conhecido com vizinhos) — sugere o pedaço conhecido como
      alternativa mais confiável.
    - `{"status": "novo"}` — não parece com nada visto antes. Não é
      necessariamente ERRADO (pode ser a primeira vez que esse elemento
      é usado) — só não tem como conferir sozinho ainda; vira
      conhecido automaticamente se a rotina for aprovada.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"status": "vazio"}

    vocabulario = _carregar()
    normalizado = _normalizar(texto)

    for conhecido in vocabulario:
        conhecido_norm = _normalizar(conhecido)
        if normalizado == conhecido_norm or normalizado.startswith(conhecido_norm) or conhecido_norm.startswith(normalizado):
            return {"status": "conhecido"}

    melhor = None
    for conhecido in vocabulario:
        conhecido_norm = _normalizar(conhecido)
        if len(conhecido_norm) >= 4 and conhecido_norm in normalizado:
            if melhor is None or len(conhecido_norm) > len(_normalizar(melhor)):
                melhor = conhecido
    if melhor is not None:
        return {"status": "parecido", "sugestao": melhor}

    return {"status": "novo"}
