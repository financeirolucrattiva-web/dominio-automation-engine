"""Rascunhos no formato do gravador existente, sem importar desktop.

Cliques por texto, teclas de formulário e digitação parametrizada.
Aprovação e execução supervisionada continuam no fluxo do gravador.
"""
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import unicodedata
import uuid

PASTA = Path(__file__).resolve().parents[1] / "data" / "rotinas_gravadas"
PARAMETROS = {"inicio", "fim", "competencia", "empresa_codigo"}
TECLAS = {"tab", "enter", "esc", "home", "end", "up", "down", "left", "right", "f8"}
_LOCK = threading.Lock()


def validar_rotina(dados):
    if not isinstance(dados, dict) or set(dados) != {"nome", "passos"}:
        raise ValueError("Campos da rotina inválidos.")
    nome, passos = dados["nome"], dados["passos"]
    if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 100 or any(ord(c) < 32 for c in nome):
        raise ValueError("Informe um nome para a rotina.")
    if not isinstance(passos, list) or not 1 <= len(passos) <= 80:
        raise ValueError("Configure entre 1 e 80 passos.")
    resultado, parametros = [], set()
    for indice, passo in enumerate(passos, 1):
        if not isinstance(passo, dict) or set(passo) != {"tipo", "valor"} or not isinstance(passo["valor"], str):
            raise ValueError("Passo inválido.")
        tipo, valor = passo["tipo"], passo["valor"].strip()
        if tipo in ("clicar", "hover"):
            normalizado = "".join(c for c in unicodedata.normalize("NFKD", valor.casefold()) if not unicodedata.combining(c))
            if (not 1 <= len(valor) <= 100 or any(ord(c) < 32 for c in valor)
                    or re.search(r"\b(transmit\w*|retific\w*|exclu\w*|apagar|enviar)\b", normalizado)):
                raise ValueError("Use o texto de um menu de geração/leitura.")
            resultado.append({"indice": indice, "tipo": tipo, "texto_adivinhado": valor})
        elif tipo == "tecla" and valor in TECLAS:
            resultado.append({"indice": indice, "tipo": tipo, "tecla": valor})
        elif tipo == "digitar" and valor in PARAMETROS:
            resultado.append({"indice": indice, "tipo": tipo, "parametro": valor})
            parametros.add(valor)
        else:
            raise ValueError("Escolha clique por texto, tecla de formulário ou parâmetro de período/empresa.")
    return {"nome_exibicao": nome.strip(), "passos": resultado, "parametros": sorted(parametros), "status": "rascunho"}


def listar(pasta=PASTA):
    rotinas = []
    for caminho in sorted(Path(pasta).glob("*.json")):
        try:
            if caminho.is_symlink() or caminho.stat().st_size > 200_000:
                continue
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            if not isinstance(dados.get("nome_exibicao"), str) or not isinstance(dados.get("passos"), list):
                continue
            rotinas.append({"id": caminho.stem, "nome": dados["nome_exibicao"][:100],
                            "status": "aprovada" if dados.get("status") == "aprovada" else "rascunho",
                            "quantidade_passos": len(dados["passos"]),
                            "parametros": [p for p in dados.get("parametros", []) if p in PARAMETROS]})
        except (OSError, UnicodeError, ValueError, AttributeError, TypeError):
            continue
    return rotinas


def salvar(dados, pasta=PASTA):
    rotina = validar_rotina(dados)
    pasta = Path(pasta)
    with _LOCK:
        pasta.mkdir(parents=True, exist_ok=True)
        identificador = "painel_" + uuid.uuid4().hex
        temporario = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=pasta, encoding="utf-8", delete=False, prefix=".rotina_", suffix=".tmp") as arquivo:
                temporario = Path(arquivo.name)
                json.dump(rotina, arquivo, ensure_ascii=False, indent=2)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, pasta / (identificador + ".json"))
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)
    return {"id": identificador, "nome": rotina["nome_exibicao"], "status": "rascunho", "quantidade_passos": len(rotina["passos"]), "parametros": rotina["parametros"]}
