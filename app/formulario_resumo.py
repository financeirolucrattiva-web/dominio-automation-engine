"""Localiza as duas datas por caixas OCR medidas na captura atual."""
import datetime as dt
import re


def campos_periodo(dados, escala=2):
    palavras = []
    for i, texto in enumerate(dados["text"]):
        texto = texto.strip()
        if texto:
            palavras.append({"texto": texto, "x": dados["left"][i] / escala,
                "y": dados["top"][i] / escala, "w": dados["width"][i] / escala,
                "h": dados["height"][i] / escala})
    campos = {}
    for papel in ("inicial", "final"):
        rotulos = [p for p in palavras if p["texto"].rstrip(":").casefold() == papel]
        if len(rotulos) != 1:
            raise ValueError("Rótulos do período ausentes ou ambíguos.")
        rotulo = rotulos[0]
        mesma_linha = lambda p: max(p["y"], rotulo["y"]) < min(p["y"] + p["h"], rotulo["y"] + rotulo["h"])
        if not any(p["texto"].casefold() == "data" and p["x"] < rotulo["x"] and mesma_linha(p) for p in palavras):
            raise ValueError("Rótulo de data incompleto.")
        datas = [p for p in palavras if p["x"] > rotulo["x"] + rotulo["w"] and mesma_linha(p)
                 and re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", p["texto"])]
        if len(datas) != 1:
            raise ValueError("Não identifiquei uma única data ao lado do rótulo.")
        data = datas[0]
        dt.datetime.strptime(data["texto"], "%d/%m/%Y")
        campos[papel] = {"valor": data["texto"],
                         "posicao": (int(data["x"] + data["w"] / 2), int(data["y"] + data["h"] / 2))}
    if campos["inicial"]["posicao"] == campos["final"]["posicao"]:
        raise ValueError("As datas não foram identificadas em campos distintos.")
    return campos
