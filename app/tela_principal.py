"""Referência local do corpo vazio da tela principal do Domínio.

Não captura tela, não envia dados e não escolhe ações. A calibração deve
ser chamada somente depois de confirmação humana e de duas capturas com
foco/cabeçalho verificados. Mede a cor azul dominante e um retângulo
inteiramente uniforme; persiste somente geometria e cor, nunca a imagem.

Os mínimos relativos são critérios preliminares conservadores. Ainda
precisam de validação na sessão Windows. Uma correspondência só comprova
o retângulo calibrado: o chamador também deve verificar foco e cabeçalho.
Qualquer pixel diferente, inclusive um controle pequeno, recusa o quadro.
"""

import colorsys
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image


ARQUIVO_REFERENCIA = Path(__file__).resolve().parent.parent / "data" / "tela_principal.json"
VERSAO_REFERENCIA = 1

# Critérios de amplitude, não coordenadas tiradas de uma captura. A
# geometria concreta é sempre medida na imagem capturada localmente.
_LARGURA_MINIMA_PERCENTUAL = 90
_ALTURA_MINIMA_PERCENTUAL = 70
_AREA_MINIMA_PERCENTUAL = 65
_CHAVES_REFERENCIA = {"versao", "tamanho", "retangulo", "cor_rgb"}


def _azul(cor):
    """Classe de cor do canvas observado; não fixa seu RGB exato."""
    matiz, saturacao, brilho = colorsys.rgb_to_hsv(*(componente / 255 for componente in cor))
    return 200 / 360 <= matiz <= 260 / 360 and saturacao >= 0.25 and brilho >= 0.20


def _amplo(retangulo, tamanho):
    esquerda, topo, direita, base = retangulo
    largura, altura = tamanho
    largura_corpo, altura_corpo = direita - esquerda, base - topo
    return (
        largura_corpo * 100 >= largura * _LARGURA_MINIMA_PERCENTUAL
        and altura_corpo * 100 >= altura * _ALTURA_MINIMA_PERCENTUAL
        and largura_corpo * altura_corpo * 100 >= largura * altura * _AREA_MINIMA_PERCENTUAL
    )


def _validar_referencia(referencia):
    """Valida também referências em memória antes de comparar ou salvar."""
    if not isinstance(referencia, dict) or set(referencia) != _CHAVES_REFERENCIA:
        raise ValueError("Metadados da tela principal inválidos.")
    if type(referencia["versao"]) is not int or referencia["versao"] != VERSAO_REFERENCIA:
        raise ValueError("Versão da referência da tela principal incompatível.")
    for chave, quantidade in (("tamanho", 2), ("retangulo", 4), ("cor_rgb", 3)):
        valores = referencia[chave]
        if not isinstance(valores, list) or len(valores) != quantidade or any(type(v) is not int for v in valores):
            raise ValueError("Metadados da tela principal inválidos.")
    largura, altura = referencia["tamanho"]
    esquerda, topo, direita, base = referencia["retangulo"]
    cor = referencia["cor_rgb"]
    if largura <= 0 or altura <= 0 or not (0 <= esquerda < direita <= largura and 0 <= topo < base <= altura):
        raise ValueError("Geometria da referência da tela principal inválida.")
    if any(not 0 <= valor <= 255 for valor in cor) or not _azul(cor):
        raise ValueError("A referência não contém uma cor azul de canvas.")
    if not _amplo(referencia["retangulo"], referencia["tamanho"]):
        raise ValueError("O corpo vazio da tela principal é pequeno demais.")
    return {chave: list(valor) if isinstance(valor, list) else valor for chave, valor in referencia.items()}


def _maior_retangulo(mascara):
    """Maior retângulo composto apenas de pixels True, sem amostragem."""
    altura, largura = mascara.shape
    alturas = np.zeros(largura, dtype=np.int64)
    melhor_area, melhor = 0, None
    for linha in range(altura):
        alturas = np.where(mascara[linha], alturas + 1, 0)
        pilha = []
        for coluna in range(largura + 1):
            atual = int(alturas[coluna]) if coluna < largura else 0
            inicio = coluna
            while pilha and pilha[-1][1] > atual:
                inicio, altura_retangulo = pilha.pop()
                area = altura_retangulo * (coluna - inicio)
                if area > melhor_area:
                    melhor_area = area
                    melhor = [inicio, linha + 1 - altura_retangulo, coluna, linha + 1]
            if atual and (not pilha or pilha[-1][1] < atual):
                pilha.append((inicio, atual))
    return melhor


def construir_referencia(imagem):
    """Mede o corpo azul vazio de uma captura humana confirmada.

    Recusa superfícies claras de PDF/diálogo e corpos pequenos ou
    interrompidos. A verificação de foco, âncoras e estabilidade pertence
    ao chamador; só esta função não autoriza a calibração.
    """
    if not isinstance(imagem, Image.Image) or imagem.width <= 0 or imagem.height <= 0:
        raise ValueError("Captura da tela principal inválida.")
    pixels = np.asarray(imagem.convert("RGB"), dtype=np.uint8)
    codigos = (pixels[:, :, 0].astype(np.uint32) << 16) | (pixels[:, :, 1].astype(np.uint32) << 8) | pixels[:, :, 2]
    cores, contagens = np.unique(codigos, return_counts=True)
    dominante = int(cores[np.argmax(contagens)])
    cor = [dominante >> 16, (dominante >> 8) & 255, dominante & 255]
    if not _azul(cor):
        raise ValueError("Não há canvas azul dominante nesta captura.")
    retangulo = _maior_retangulo(codigos == dominante)
    if retangulo is None:
        raise ValueError("Não há corpo uniforme para calibrar a tela principal.")
    return _validar_referencia({
        "versao": VERSAO_REFERENCIA,
        "tamanho": [imagem.width, imagem.height],
        "retangulo": retangulo,
        "cor_rgb": cor,
    })


def corresponde(imagem, referencia):
    """Compara cada pixel do corpo calibrado, sem tolerância percentual."""
    try:
        referencia = _validar_referencia(referencia)
        if not isinstance(imagem, Image.Image) or list(imagem.size) != referencia["tamanho"]:
            return False
        pixels = np.asarray(imagem.crop(tuple(referencia["retangulo"])).convert("RGB"), dtype=np.uint8)
        return bool(np.all(pixels == np.asarray(referencia["cor_rgb"], dtype=np.uint8)))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def salvar_referencia(referencia, caminho=ARQUIVO_REFERENCIA):
    """Substitui o JSON atomicamente após validar todos os metadados."""
    referencia = _validar_referencia(referencia)
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=caminho.parent, prefix=".tela_principal_", suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(referencia, arquivo, ensure_ascii=True, sort_keys=True)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _sem_chaves_repetidas(pares):
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError("Metadados da referência contêm chaves repetidas.")
        resultado[chave] = valor
    return resultado


def carregar_referencia(caminho=ARQUIVO_REFERENCIA):
    """Retorna None para referência ausente, ilegível ou incompatível."""
    try:
        with Path(caminho).open(encoding="utf-8") as arquivo:
            conteudo = arquivo.read(4097)
        if len(conteudo) > 4096:
            return None
        return _validar_referencia(json.loads(conteudo, object_pairs_hook=_sem_chaves_repetidas))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return None
