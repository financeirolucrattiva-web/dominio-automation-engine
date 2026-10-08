"""Regiões de menus confirmadas por OCR, nunca coordenadas para clique cego."""

import json
import os
from pathlib import Path
import tempfile

ARQUIVO = Path(__file__).resolve().parents[1] / "data" / "mapa_menus.json"


class MapaMenus:
    def __init__(self, caminho=ARQUIVO):
        self.caminho = Path(caminho)

    def _carregar(self):
        try:
            if self.caminho.stat().st_size > 32_000:
                return {}
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError, UnicodeError):
            return {}

    def localizar(self, imagem, contexto, alvo, achar):
        if not hasattr(imagem, "crop"):
            return achar(imagem, alvo)
        dados = self._carregar()
        chave = f"{contexto}:{alvo}"
        anterior = dados.get(chave)
        if (isinstance(anterior, dict) and anterior.get("tamanho") == list(imagem.size)
                and isinstance(anterior.get("centro"), list) and len(anterior["centro"]) == 2
                and all(type(v) is int for v in anterior["centro"])):
            x, y = anterior["centro"]
            if 0 <= x < imagem.width and 0 <= y < imagem.height:
                # Janela de busca proporcional; nenhum deslocamento escolhe a ação.
                rx, ry = max(80, imagem.width // 8), max(30, imagem.height // 8)
                area = (max(0, x-rx), max(0, y-ry), min(imagem.width, x+rx), min(imagem.height, y+ry))
                pos = achar(imagem.crop(area), alvo)
                if pos is not None:
                    pos = (pos[0]+area[0], pos[1]+area[1])
                    self._salvar(dados, chave, imagem, pos)
                    return pos
        pos = achar(imagem, alvo)
        if pos is not None:
            self._salvar(dados, chave, imagem, pos)
        return pos

    def _salvar(self, dados, chave, imagem, pos):
        dados[chave] = {"tamanho": list(imagem.size), "centro": list(pos)}
        temporario = None
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.caminho.parent, delete=False, prefix=".menus_", suffix=".tmp") as arquivo:
                temporario = Path(arquivo.name)
                json.dump(dados, arquivo, ensure_ascii=True)
            os.replace(temporario, self.caminho)
        except OSError:
            pass  # cache indisponível não muda a navegação validada
        finally:
            if temporario is not None:
                try:
                    temporario.unlink(missing_ok=True)
                except OSError:
                    pass
