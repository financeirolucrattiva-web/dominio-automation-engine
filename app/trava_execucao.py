"""Exclusão entre console local e executor do mesmo projeto/sessão."""

from pathlib import Path


class TravaExecucao:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.arquivo = None

    def adquirir(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        arquivo = self.caminho.open("a+b")
        try:
            if arquivo.seek(0, 2) == 0:
                arquivo.write(b"0")
                arquivo.flush()
            arquivo.seek(0)
            import os
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            arquivo.close()
            raise
        self.arquivo = arquivo

    def liberar(self):
        if self.arquivo is not None:
            self.arquivo.close()  # o SO libera o lock, inclusive após queda do processo
            self.arquivo = None
