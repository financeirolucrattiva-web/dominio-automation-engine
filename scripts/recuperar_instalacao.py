"""Recupera código e Git a partir de um clone saudável, preservando dados.

Execute este script no clone NOVO da main, com --destino apontando para
a instalação anterior. Pare o servidor antes. Biblioteca padrão e trava
local; não instala dependências, gera certificados ou opera o Domínio.
"""
import argparse
from contextlib import ExitStack
import io
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.trava_execucao import TravaExecucao

PROTEGIDAS = {"data", "saida", "capturas", "screenshots", "logs", ".venv", ".venv-ocr-paddle"}
REPOSITORIO = "https://github.com/financeirolucrattiva-web/dominio-automation-engine"


def _git(fonte, *args):
    resultado = subprocess.run(["git", "-C", str(fonte), *args], capture_output=True)
    if resultado.returncode:
        raise ValueError("O Git do clone novo não está válido. Faça outro clone da main antes de recuperar.")
    return resultado.stdout


def _gravar(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def recuperar(destino, fonte=ROOT):
    destino, fonte = Path(destino).resolve(), Path(fonte).resolve()
    if destino == fonte or fonte.is_relative_to(destino) or destino.is_relative_to(fonte):
        raise ValueError("Use um clone novo fora da instalação anterior; os caminhos devem ser distintos.")
    if not destino.is_dir() or not (destino / "web").is_dir():
        raise ValueError("O destino deve ser a pasta da instalação anterior, contendo web/.")
    for pasta in (fonte / ".git", destino / ".git", destino / "data"):
        if pasta.is_symlink() or (pasta.exists() and not pasta.is_dir()):
            raise ValueError("Use clones completos e pastas locais, sem links de diretório ou worktrees.")
    if not (fonte / ".git").is_dir():
        raise ValueError("O clone novo precisa de Git válido.")
    if ((fonte / ".git/objects/info/alternates").exists() or (fonte / ".git/commondir").exists()
            or list((fonte / ".git").rglob("*.lock"))):
        raise ValueError("O clone novo deve ser independente e não ter operação Git em andamento.")
    if _git(fonte, "branch", "--show-current").decode().strip() != "main":
        raise ValueError("O clone novo deve estar na main.")
    remoto = _git(fonte, "remote", "get-url", "origin").decode().strip().removesuffix(".git")
    if remoto != REPOSITORIO:
        raise ValueError("O clone novo deve vir do repositório dominio-automation-engine esperado.")
    if _git(fonte, "config", "--local", "--list").decode().find("core.worktree=") >= 0:
        raise ValueError("Use um clone novo independente, sem core.worktree.")
    _git(fonte, "fsck", "--full", "--no-reflogs")
    revisao = _git(fonte, "rev-parse", "HEAD").decode().strip()
    arquivo = zipfile.ZipFile(io.BytesIO(_git(fonte, "archive", "--format=zip", "HEAD")))
    html = arquivo.read("web/index.html")
    if b"\0" in html or b"form-login" not in html or b"<!doctype html>" not in html.lower():
        raise ValueError("O HTML do clone novo está inválido; a instalação anterior foi preservada.")
    restaurar = {}
    for item in arquivo.infolist():
        rel = PurePosixPath(item.filename)
        if item.is_dir():
            continue
        if (rel.is_absolute() or ".." in rel.parts or "\\" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16) or rel.parts[0] == ".git"):
            raise ValueError("Arquivo do clone novo não pode ser usado na recuperação.")
        if rel.parts[0] in PROTEGIDAS or rel.parts[0] == ".env":
            continue
        caminho = destino.joinpath(*rel.parts)
        if (not caminho.resolve().is_relative_to(destino)
                or any(p.is_symlink() for p in (caminho, *caminho.parents) if p != destino.parent)):
            raise ValueError("Há um link de diretório/arquivo no destino; nenhuma recuperação foi aplicada.")
        if caminho.exists() and not caminho.is_file():
            raise ValueError("Há uma pasta no lugar de um arquivo do código; destino preservado.")
        restaurar[Path(*rel.parts)] = arquivo.read(item)
    with ExitStack() as pilha:
        for nome in ("sessao_executor.lock", "executor_simulado.lock"):
            trava = TravaExecucao(destino / "data" / nome)
            try:
                trava.adquirir()
            except OSError:
                raise ValueError("Pare o servidor e aguarde a rotina atual terminar antes da recuperação.") from None
            pilha.callback(trava.liberar)
        backup = destino / "data" / ("recuperacao_codigo_" + uuid.uuid4().hex)
        backup.mkdir()
        # Tudo é preparado antes de substituir qualquer arquivo/Git anterior.
        shutil.copytree(fonte / ".git", backup / "git_novo")
        existentes = set()
        for rel in restaurar:
            caminho = destino / rel
            if caminho.exists():
                existentes.add(rel)
                copia = backup / "codigo_anterior" / rel
                copia.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(caminho, copia)
        gravados = []
        git_movido = git_novo = False
        try:
            for rel, dados in restaurar.items():
                _gravar(destino / rel, dados)
                gravados.append(rel)
            if (destino / ".git").exists():
                (destino / ".git").rename(backup / "git_anterior")
                git_movido = True
            (backup / "git_novo").rename(destino / ".git")
            git_novo = True
            if _git(destino, "rev-parse", "HEAD").decode().strip() != revisao:
                raise ValueError("A referência Git recuperada não corresponde ao clone novo.")
            _git(destino, "fsck", "--full", "--no-reflogs")
        except BaseException:
            if git_novo:
                (destino / ".git").rename(backup / "git_novo")
            if git_movido:
                (backup / "git_anterior").rename(destino / ".git")
            for rel in reversed(gravados):
                if rel in existentes:
                    _gravar(destino / rel, (backup / "codigo_anterior" / rel).read_bytes())
                else:
                    (destino / rel).unlink(missing_ok=True)
            raise
    return {"revisao": revisao, "backup": backup, "arquivos": len(restaurar)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", required=True, type=Path, help="Pasta da instalação anterior.")
    args = parser.parse_args(argv)
    try:
        resultado = recuperar(args.destino)
    except ValueError as erro:
        print(str(erro))
        return 1
    except (OSError, KeyError, zipfile.BadZipFile):
        print("Recuperação não concluída. Confira clone da main, pastas/permissões e servidor parado.")
        print("Nenhum cadastro ou documento fiscal é restaurado/substituído por este script.")
        return 1
    print(f"Código e Git recuperados na main ({resultado['revisao'][:12]}).")
    print(f"Backup do código/Git anterior: {resultado['backup']}")
    print("Dados, empresas, certificados, saída fiscal e arquivos locais preservados.")
    print("Reabra o servidor na pasta anterior e atualize o navegador com Ctrl+F5.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
