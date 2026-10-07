"""Baixa somente os dois modelos OCR públicos, sem ler capturas ou documentos."""

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PASTA_MODELOS = ROOT / "data" / "modelos_ocr"
MODELOS = (
    ("PP-OCRv5_mobile_det", "0d63e78e2b680928f6b1747d76a08db6e645efb7"),
    ("latin_PP-OCRv5_mobile_rec", "ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57"),
)
ARQUIVOS = ("inference.json", "inference.pdiparams", "inference.yml")


def preparar(baixar, pasta=PASTA_MODELOS):
    """Nenhuma imagem é entrada do downloader; revisão e arquivos são fixos."""
    pasta = Path(pasta)
    for nome, revisao in MODELOS:
        destino = pasta / nome
        marcador = destino / "revisao.json"
        esperado = {"repositorio": f"PaddlePaddle/{nome}", "revisao": revisao}
        try:
            existente = json.loads(marcador.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existente = None
        if existente == esperado and all((destino / arquivo).is_file() and (destino / arquivo).stat().st_size > 0 for arquivo in ARQUIVOS):
            print(f"Modelo local já preparado: {nome}.")
            continue
        if destino.exists() and (not destino.is_dir() or destino.is_symlink()):
            raise ValueError("A pasta local do modelo não é um diretório válido.")
        pasta.mkdir(parents=True, exist_ok=True)
        # Valida numa pasta vazia: arquivos de uma revisão anterior nunca
        # podem completar por engano um download novo interrompido.
        with tempfile.TemporaryDirectory(prefix=".download-", dir=pasta) as staging:
            temporario = Path(staging)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                baixar(repo_id=esperado["repositorio"], revision=revisao,
                       allow_patterns=list(ARQUIVOS), local_dir=str(temporario))
            if not all((temporario / arquivo).is_file() and (temporario / arquivo).stat().st_size > 0 for arquivo in ARQUIVOS):
                raise ValueError("O download não confirmou todos os arquivos do modelo.")
            (temporario / "revisao.json").write_text(json.dumps(esperado), encoding="utf-8")
            backup = pasta / f".anterior-{nome}-{uuid.uuid4().hex}"
            if destino.exists():
                destino.replace(backup)
            try:
                temporario.replace(destino)
            except Exception:
                if backup.exists() and not destino.exists():
                    backup.replace(destino)
                raise
            else:
                if backup.exists():
                    shutil.rmtree(backup, ignore_errors=True)
        print(f"Modelo local preparado: {nome}.")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        # Configuração explícita do operador tem precedência. O padrão
        # fica junto aos dados locais, sem depender de cache fora do projeto.
        os.environ.setdefault("HF_HOME", str(ROOT / "data" / "huggingface_cache"))
        from huggingface_hub import snapshot_download
        preparar(snapshot_download)
    except Exception as erro:
        print(f"Preparação dos modelos não concluída ({type(erro).__name__}). Rode novamente o instalador com internet disponível.")
        return 1
    print("Dois modelos PP-OCRv5 preparados; nenhuma captura foi enviada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
