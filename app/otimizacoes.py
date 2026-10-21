"""Interruptores das otimizações de velocidade, com volta ao caminho clássico.

Cada otimização tem um nome e vem LIGADA por padrão. O caminho clássico (o que já rodou contra o
Domínio real, só mais lento) continua no código ao lado de cada uma, então voltar a ele não exige
mexer em código nem atualizar versão:

- `data/otimizacoes.json`: `{"modo_seguro": true}` desliga todas; `{"ocr_paralelo": false}` desliga
  só uma. A mudança vale na leitura seguinte (o arquivo é relido quando seu horário muda).
- Variável de ambiente `DOMINIO_MODO_SEGURO=1`: desliga todas.
- Arquivo ilegível ou com valor inesperado: modo seguro (na dúvida, o caminho clássico) e um aviso.
- Desligamento automático: se uma otimização falha de um jeito inesperado, `desligar()` a apaga
  pelo resto do processo (o servidor reiniciado volta ao arquivo) e a rotina segue pelo clássico.

O estado vigente é impresso uma vez por processo (`OTIMIZACOES {...}`) para que o log mostre com
qual configuração a rodada foi feita.
"""
import json
import os
from pathlib import Path
import threading

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "otimizacoes.json"

NOMES = {
    # Descrições em ASCII: o atalho `Ver Otimizacoes.bat` as imprime no console do Windows.
    "ocr_paralelo": "leituras OCR de uma mesma captura rodam em paralelo (tela.pre_aquecer_ocr)",
    "geometria_lembrada": "posicao dos campos de data lembrada entre leituras (leitura_resumo.ler_campos)",
    "ocr_centro_seletor": "OCR do Procurar Pasta so no centro da tela, com volta a tela inteira",
    "fechar_adobe_curto": "Livros nao espera 20 s por um Adobe que ja foi fechado",
}

# Os testes forçam True/False para todas (as simulações antigas de OCR dependem da ordem das
# chamadas). `None` = segue arquivo/ambiente.
_forcado = None
_desligadas = {}
_trava = threading.Lock()
_cache = {"mtime": None, "config": None, "aviso": False}
_impresso = False


def _ler_arquivo():
    """Devolve (modo_seguro, {nome: bool}); qualquer problema vira modo seguro."""
    try:
        mtime = ARQUIVO.stat().st_mtime_ns
    except FileNotFoundError:
        return False, {}
    except OSError:
        return True, {}
    if _cache["mtime"] == mtime and _cache["config"] is not None:
        return _cache["config"]
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        if not isinstance(dados, dict) or any(not isinstance(v, bool) for v in dados.values()):
            raise ValueError("valores precisam ser verdadeiro/falso")
        desconhecidos = set(dados) - set(NOMES) - {"modo_seguro"}
        if desconhecidos:
            raise ValueError("nome desconhecido: " + ", ".join(sorted(desconhecidos)))
        config = (bool(dados.get("modo_seguro", False)), {k: v for k, v in dados.items() if k in NOMES})
    except (OSError, ValueError) as erro:
        if not _cache["aviso"]:
            print("OTIMIZACOES arquivo invalido (" + str(erro) + "); usando o modo seguro.", flush=True)
            _cache["aviso"] = True
        config = (True, {})
    _cache.update(mtime=mtime, config=config)
    return config


def _modo_seguro_no_ambiente():
    return os.environ.get("DOMINIO_MODO_SEGURO", "").strip().lower() in ("1", "true", "sim", "yes")


def ativa(nome):
    """True se a otimização `nome` deve ser usada agora."""
    if nome not in NOMES:
        raise KeyError("Otimização desconhecida: " + nome)
    if _forcado is not None:
        return bool(_forcado) and nome not in _desligadas
    _imprimir_uma_vez()
    if nome in _desligadas or _modo_seguro_no_ambiente():
        return False
    seguro, individuais = _ler_arquivo()
    if seguro:
        return False
    return individuais.get(nome, True)


def desligar(nome, motivo):
    """Desliga `nome` pelo resto do processo (a rotina segue pelo caminho clássico)."""
    if nome not in NOMES:
        raise KeyError("Otimização desconhecida: " + nome)
    with _trava:
        primeira = nome not in _desligadas
        _desligadas[nome] = str(motivo)[:120]
    if primeira:
        print("OTIMIZACAO_DESLIGADA " + json.dumps({"nome": nome, "motivo": _desligadas[nome]},
              ensure_ascii=False), flush=True)


def estado():
    return {nome: ativa(nome) for nome in NOMES}


def _imprimir_uma_vez():
    global _impresso
    if _impresso:
        return
    _impresso = True
    seguro, individuais = _ler_arquivo()
    if seguro or _modo_seguro_no_ambiente():
        print("OTIMIZACOES modo_seguro=True (caminho classico em tudo)", flush=True)
    else:
        print("OTIMIZACOES " + json.dumps({n: individuais.get(n, True) for n in NOMES}), flush=True)


def restaurar_para_testes():
    global _forcado, _impresso
    _forcado = None
    _impresso = False
    _desligadas.clear()
    _cache.update(mtime=None, config=None, aviso=False)
