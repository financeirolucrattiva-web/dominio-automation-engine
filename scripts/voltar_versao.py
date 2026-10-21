"""Volta a instalação para uma versão estável marcada (tag `estavel-*`), sem apagar nada.

Cria (ou reutiliza) uma branch local `voltar-<tag>` apontando para a tag e troca para ela. Commits,
`data/`, `saida/` e configurações ficam como estão. Para voltar à versão mais nova, `Atualizar.bat`
reabre a main (ele aceita estar em outra branch). Pare o servidor antes e reinicie depois.

Uso:
    python scripts/voltar_versao.py --listar
    python scripts/voltar_versao.py                # a estável mais recente
    python scripts/voltar_versao.py --para estavel-2026-10-21
"""
from pathlib import Path
import argparse
import sys

try:
    from scripts.atualizar_projeto import AtualizacaoRecusada, _git
except ImportError:  # executado como `python scripts/voltar_versao.py`
    from atualizar_projeto import AtualizacaoRecusada, _git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PREFIXO = "estavel-"


def tags_estaveis(pasta=ROOT):
    """[(tag, data, assunto)] da mais nova para a mais antiga; tenta baixar as tags, offline segue local."""
    _git(pasta, "fetch", "--tags", "--quiet", "origin", aceitar=(0, 1, 128))
    saida = _git(pasta, "tag", "--list", PREFIXO + "*", "--sort=-creatordate",
                 "--format=%(refname:short)|%(creatordate:short)|%(contents:subject)").stdout
    tags = []
    for linha in saida.splitlines():
        nome, _, resto = linha.partition("|")
        data, _, assunto = resto.partition("|")
        if nome.strip():
            tags.append((nome.strip(), data.strip(), assunto.strip()))
    return tags


def _conferir_instalacao(pasta):
    raiz = Path(_git(pasta, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if raiz != pasta:
        raise AtualizacaoRecusada("Execute na raiz do projeto clonado.")
    git_dir = Path(_git(pasta, "rev-parse", "--absolute-git-dir").stdout.strip())
    estados = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge",
               "rebase-apply", "sequencer", "BISECT_LOG")
    if any((git_dir / estado).exists() for estado in estados):
        raise AtualizacaoRecusada("Existe uma operacao Git em andamento. Nada foi alterado.")
    if _git(pasta, "status", "--porcelain=v1", "--untracked-files=no").stdout.strip():
        raise AtualizacaoRecusada(
            "Existem alteracoes locais em arquivos versionados. Elas foram preservadas.\n"
            "Confira git status --short --branch antes de trocar de versao.")
    if _git(pasta, "symbolic-ref", "--quiet", "HEAD", aceitar=(0, 1)).returncode != 0:
        # HEAD destacado: o commit atual pode nao estar em nenhuma branch e ficaria inalcancavel.
        if not _git(pasta, "for-each-ref", "--contains", "HEAD", "--format=%(refname)", "refs/heads", "refs/remotes").stdout.strip():
            raise AtualizacaoRecusada(
                "HEAD destacado com commits que nao estao em nenhuma branch. Nada foi alterado. "
                "Guarde esse trabalho numa branch (git switch -c minha-branch) e tente de novo.")


def voltar(pasta=ROOT, tag=None):
    """Troca de versao com o servidor/rotina parados: as travas de execucao impedem trocar o codigo
    no meio de uma rotina (ImportError)."""
    from contextlib import ExitStack
    from app.trava_execucao import TravaExecucao
    pasta = Path(pasta).resolve()
    _conferir_instalacao(pasta)
    with ExitStack() as pilha:
        for nome in ("sessao_executor.lock", "executor_simulado.lock"):
            trava = TravaExecucao(pasta / "data" / nome)
            try:
                trava.adquirir()
            except OSError:
                raise AtualizacaoRecusada("Pare o servidor e aguarde a rotina atual terminar antes de voltar.") from None
            pilha.callback(trava.liberar)
        return _voltar_travado(pasta, tag)


def _voltar_travado(pasta, tag):
    disponiveis = tags_estaveis(pasta)
    if tag is None:
        if not disponiveis:
            raise AtualizacaoRecusada("Nenhuma versao estavel (tag estavel-*) encontrada.")
        tag = disponiveis[0][0]
    if not tag.startswith(PREFIXO):
        raise AtualizacaoRecusada("Use uma tag que comece com " + PREFIXO + ".")
    existe = _git(pasta, "rev-parse", "--verify", "--quiet", "refs/tags/" + tag + "^{commit}", aceitar=(0, 1))
    if existe.returncode != 0:
        raise AtualizacaoRecusada("A tag " + tag + " nao existe. Use --listar.")
    commit = existe.stdout.strip()
    atual = _git(pasta, "rev-parse", "HEAD").stdout.strip()
    branch = "voltar-" + tag
    ja = _git(pasta, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch, aceitar=(0, 1))
    if ja.returncode == 0 and ja.stdout.strip() != commit:
        branch = branch + "-" + commit[:7]
        ja = _git(pasta, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch, aceitar=(0, 1))
    if atual == commit:
        print("A instalacao ja esta na versao " + tag + " (" + commit[:7] + ").")
    elif ja.returncode == 0:
        _git(pasta, "switch", "--no-overwrite-ignore", branch)
    else:
        _git(pasta, "switch", "--no-overwrite-ignore", "--create", branch, commit)
    print("Versao " + tag + " (" + commit[:7] + ") ativa na branch " + branch + ".")
    print("Reinicie o servidor. Para voltar a versao mais nova, rode Atualizar.bat.")
    return tag


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listar", action="store_true", help="mostra as versoes estaveis e sai")
    parser.add_argument("--para", metavar="TAG", help="tag estavel-* (padrao: a mais recente)")
    argumentos = parser.parse_args(argv)
    try:
        if argumentos.listar:
            tags = tags_estaveis()
            if not tags:
                print("Nenhuma versao estavel (tag estavel-*) encontrada.")
            for nome, data, assunto in tags:
                print(nome + "  " + data + "  " + assunto)
            return 0
        voltar(ROOT, argumentos.para)
    except (AtualizacaoRecusada, OSError) as erro:
        print("Nao foi possivel voltar a versao: " + str(erro), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
