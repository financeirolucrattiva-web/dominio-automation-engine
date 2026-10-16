"""Console compacto do processo servidor, com diagnóstico técnico local limitado."""
from contextlib import contextmanager, redirect_stdout
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
import time


PREFIXOS_TECNICOS = (
    'RESUMO_RECORTE ', 'RESUMO_OCR ', 'RESUMO_PERIODO ',
    'RESUMO_FORMULARIO ', 'RESUMO_LEITURA_CAMPOS ',
    'RESUMO_BOTAO ', 'LIVROS_OK ', 'LIVROS_MARCACAO ', 'LIVROS_SELECAO ',
    'LIVROS_PERIODO ', 'LIVROS_PERIODO_RELEITURA ',
    'PASTA_NAVEGACAO ',
)
PREFIXOS_ESPERA = (
    'Esperando pelo menos ', 'Nenhum estado esperado reconhecido ainda ',
    'Tela igual à tentativa anterior, pulando checagem ',
)


class _ArquivoDiagnostico(RotatingFileHandler):
    def handleError(self, record):
        # Sem perder diagnóstico silenciosamente se o disco deixar de gravar.
        raise OSError('arquivo_diagnostico_indisponivel')


class ConsoleServidor:
    def __init__(self, original, pasta, detalhado=False, max_bytes=2*1024*1024):
        self.original=original
        self.detalhado=detalhado
        self._lock=threading.RLock()
        self._pendentes={}
        self._ultimo_aviso=time.monotonic()
        self._arquivo=None
        try:
            pasta=Path(pasta)
            pasta.mkdir(parents=True,exist_ok=True)
            self._arquivo=_ArquivoDiagnostico(pasta/'servidor_detalhes.log',
                maxBytes=max_bytes,backupCount=3,encoding='utf-8')
            self._arquivo.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        except OSError:
            self._usar_saida_completa()

    def __getattr__(self,nome):
        return getattr(self.original,nome)

    def _usar_saida_completa(self):
        self.detalhado=True
        self.original.write('[servidor] Diagnóstico local indisponível; logs completos no terminal.\n')
        self.original.flush()

    def _linha(self,linha,terminador='\n'):
        tecnica=linha.startswith(PREFIXOS_TECNICOS)
        espera=linha.startswith(PREFIXOS_ESPERA)
        if self._arquivo is not None and (tecnica or espera or linha.startswith('[estado]')):
            # Listas OCR livres podem incluir dados fiscais; não as duplicar.
            registro=linha.split('Palavras vistas:',1)[0].rstrip()
            try:
                self._arquivo.handle(logging.LogRecord('dominio.diagnostico',logging.DEBUG,
                    __file__,0,registro,(),None))
            except OSError:
                try:self._arquivo.close()
                except OSError:pass
                self._arquivo=None
                self._usar_saida_completa()
        agora=time.monotonic()
        if self.detalhado or not (tecnica or espera):
            self.original.write(linha+terminador)
            if linha.strip():self._ultimo_aviso=agora
        elif agora-self._ultimo_aviso>=10:
            self.original.write('[servidor] Reconhecendo a tela; detalhes em data/servidor_detalhes.log.\n')
            self.original.flush()
            self._ultimo_aviso=agora

    def write(self,texto):
        if not isinstance(texto,str):raise TypeError('A saída do console precisa ser texto.')
        with self._lock:
            ident=threading.get_ident()
            restante=self._pendentes.pop(ident,'')+texto
            while '\n' in restante:
                linha,restante=restante.split('\n',1)
                self._linha(linha.rstrip('\r'))
            if restante:self._pendentes[ident]=restante
        return len(texto)

    def flush(self):
        with self._lock:
            ident=threading.get_ident()
            parcial=self._pendentes.get(ident,'')
            # print(..., flush=True) não deve vazar metade de um JSON técnico.
            if parcial and not parcial.startswith(PREFIXOS_TECNICOS+PREFIXOS_ESPERA):
                self._linha(self._pendentes.pop(ident),terminador='')
            self.original.flush()

    def encerrar(self):
        with self._lock:
            for parcial in self._pendentes.values():self._linha(parcial,terminador='')
            self._pendentes.clear()
            if self._arquivo is not None:
                try:self._arquivo.close()
                except OSError:self._usar_saida_completa()
                self._arquivo=None
            self.original.flush()


@contextmanager
def saida_servidor(pasta,detalhado=False):
    console=ConsoleServidor(sys.stdout,pasta,detalhado=detalhado)
    print('Logs do terminal: '+('detalhados.' if console.detalhado else 'resumidos; etapas e falhas continuam visíveis.'))
    if console._arquivo is not None:
        print('Diagnóstico técnico local: data/servidor_detalhes.log (rotação automática).')
    try:
        with redirect_stdout(console):yield console
    finally:
        console.encerrar()
