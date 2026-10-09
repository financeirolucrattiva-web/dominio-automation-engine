"""Atualiza a instalação pela main sem criar commits ou descartar trabalho local."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


class AtualizacaoRecusada(RuntimeError):
    pass


def _git(pasta, *args, aceitar=(0,)):
    try:
        resultado = subprocess.run(
            ["git", *args], cwd=pasta, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as erro:
        raise AtualizacaoRecusada("Git nao encontrado. Confira a instalacao e o PATH.") from erro
    if resultado.returncode not in aceitar:
        detalhe = resultado.stderr.strip() or resultado.stdout.strip()
        raise AtualizacaoRecusada(f"git {' '.join(args)} falhou.\n{detalhe}")
    return resultado


def atualizar(pasta=ROOT):
    pasta = Path(pasta).resolve()
    raiz = Path(_git(pasta, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if raiz != pasta:
        raise AtualizacaoRecusada("Execute o atualizador na raiz do projeto clonado.")

    git_dir = Path(_git(pasta, "rev-parse", "--absolute-git-dir").stdout.strip())
    estados = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge",
               "rebase-apply", "sequencer", "BISECT_LOG")
    if any((git_dir / estado).exists() for estado in estados):
        raise AtualizacaoRecusada(
            "Existe uma operacao Git em andamento. Nenhuma integracao foi feita.\n"
            "Confira git status antes de concluir ou cancelar essa operacao."
        )
    if _git(pasta, "status", "--porcelain=v1", "--untracked-files=no").stdout.strip():
        raise AtualizacaoRecusada(
            "Existem alteracoes locais em arquivos versionados. Elas foram preservadas.\n"
            "Confira git status --short --branch e guarde/revise essas alteracoes antes de atualizar."
        )

    branch_anterior = _git(pasta, "symbolic-ref", "--quiet", "--short", "HEAD",
                           aceitar=(0, 1)).stdout.strip()
    if not branch_anterior:
        raise AtualizacaoRecusada(
            "HEAD destacado: a instalacao nao esta em uma branch. Nenhum commit foi movido.\n"
            "Confira git status e preserve eventuais commits locais em uma branch antes de atualizar."
        )

    print("Buscando a versao publicada da main...")
    # Ref explicita atualiza origin/main mesmo com refspec local restrito a outra branch.
    _git(pasta, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main")
    tem_main = _git(pasta, "show-ref", "--verify", "--quiet", "refs/heads/main",
                    aceitar=(0, 1)).returncode == 0
    if tem_main:
        ancestral = _git(pasta, "merge-base", "--is-ancestor", "refs/heads/main",
                         "refs/remotes/origin/main", aceitar=(0, 1))
        if ancestral.returncode != 0:
            raise AtualizacaoRecusada(
                "A main local tem commits que nao estao na main publicada. Eles foram preservados.\n"
                "Nao foi criado merge, reset ou rebase. Para diagnosticar, use:\n"
                "git status --short --branch\n"
                "git log --oneline --left-right main...origin/main"
            )

    if branch_anterior != "main":
        print("Abrindo a main; commits das outras branches continuam preservados.")
        if tem_main:
            _git(pasta, "switch", "--no-overwrite-ignore", "main")
        else:
            _git(pasta, "switch", "--no-overwrite-ignore", "--create", "main",
                 "--no-track", "refs/remotes/origin/main")
    # Fast-forward apenas move a referencia para commits existentes; nao precisa de identidade.
    _git(pasta, "merge", "--ff-only", "--no-overwrite-ignore", "refs/remotes/origin/main")
    revisao = _git(pasta, "rev-parse", "--short", "HEAD").stdout.strip()
    print(f"Codigo atualizado na main ({revisao}). Conferindo dependencias a seguir.")
    return revisao


def main():
    try:
        atualizar()
    except (AtualizacaoRecusada, OSError) as erro:
        print(f"Atualizacao interrompida: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
