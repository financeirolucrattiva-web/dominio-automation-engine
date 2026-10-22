"""Atalho curto (junção NTFS) para a pasta de saída, só para a navegação do "Procurar Pasta".

O seletor de pasta do Domínio parte da raiz da unidade e cada nível custa ~12 s (abrir o ramo, digitar,
conferir). `C:\\Users\\<usuario>\\<projeto>\\saida` são 4 níveis; uma junção `C:\\saida` apontando para a
MESMA pasta é 1 nível. Os arquivos continuam sendo gravados e lidos na pasta real (a junção é a mesma
pasta); só o caminho escolhido no diálogo muda.

Opt-in: só vale se `data/atalho_saida.txt` existir (criado por `scripts/configurar_atalho_saida.py`) e,
a cada uso, se o atalho ainda apontar para a pasta de saída real. Qualquer dúvida: caminho completo.
"""
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "atalho_saida.txt"


def atalho_configurado(arquivo=None):
    """Path do atalho gravado no arquivo de configuração, ou None."""
    try:
        texto = Path(arquivo or ARQUIVO).read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    return Path(texto) if texto else None


def destino_de_navegacao(pasta_real, arquivo=None):
    """O que escolher no Procurar Pasta: o atalho curto, se configurado e se ele aponta para `pasta_real`.

    Devolve `pasta_real` (caminho completo) em qualquer outro caso. Não cria nada."""
    pasta_real = Path(pasta_real)
    atalho = atalho_configurado(arquivo)
    if atalho is None:
        return pasta_real
    try:
        if (atalho.is_absolute() and atalho.drive.casefold() == pasta_real.drive.casefold()
                and len(atalho.parts) < len(pasta_real.parts)
                and atalho.is_dir() and atalho.resolve() == pasta_real.resolve()):
            return atalho
    except OSError:
        pass
    return pasta_real


def caminho_na_sessao_remota(atalho, letra_unidade):
    """`C:\\saida` -> `M:\\saida` (a unidade do cliente na sessão remota), SEM resolver a junção."""
    atalho = Path(atalho)
    return letra_unidade.rstrip(":") + ":" + str(atalho)[len(atalho.drive):]
