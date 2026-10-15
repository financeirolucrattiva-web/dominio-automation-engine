"""Evidências locais da execução; nunca escolhe ações ou reaproveita cliques."""
import hashlib
import html
import json
import marshal
import os
from pathlib import Path
import subprocess
import sys
import uuid

PROTOCOLO='resumo-rastro-20261015-v1'


class RastroResumo:
    def __init__(self, pasta, funcoes=()):
        self.id=uuid.uuid4().hex
        self.pasta=Path(pasta)/('resumo_'+self.id)
        self.eventos=[];self.melhor=-1;self.avisou=False;self.ultima=None
        self.manifesto={'protocolo':PROTOCOLO,'id':self.id,'pid':os.getpid(),
            'python':sys.version,'executavel':sys.executable,'funcoes_carregadas':{}}
        for funcao in funcoes:
            if not hasattr(funcao,'__code__'):continue
            self.manifesto['funcoes_carregadas'][funcao.__name__]={
                'codigo_memoria':hashlib.sha256(marshal.dumps(funcao.__code__)).hexdigest(),
                'arquivo':funcao.__code__.co_filename}
        try:
            self.manifesto['git']=subprocess.check_output(['git','rev-parse','HEAD'],
                cwd=Path(__file__).resolve().parents[1],stderr=subprocess.DEVNULL,timeout=2,text=True).strip()
        except (OSError,subprocess.SubprocessError):self.manifesto['git']=None
        print(f'RESUMO_EXECUCAO protocolo={PROTOCOLO}; rastro={self.id}',flush=True)
        self._gravar()

    def _gravar(self):
        try:
            self.pasta.mkdir(parents=True,exist_ok=True)
            (self.pasta/'rastro.json').write_text(json.dumps(self.manifesto|
                {'eventos':self.eventos},ensure_ascii=False,indent=2),encoding='utf-8')
            secoes=[]
            for e in self.eventos:
                legenda=html.escape(json.dumps({k:v for k,v in e.items() if k!='imagem'},ensure_ascii=False))
                figura=''
                if e.get('imagem'):
                    marca=''
                    if e.get('posicao') and e.get('tamanho'):
                        x,y=e['posicao'];w,h=e['tamanho']
                        marca=f'<b style="left:{x/w*100}%;top:{y/h*100}%">+</b>'
                    figura=f'<div><img src="{e["imagem"]}">{marca}</div>'
                secoes.append(f'<section><pre>{legenda}</pre>{figura}</section>')
            pagina='<!doctype html><meta charset="utf-8"><title>Rastro local do Resumo</title>'
            pagina+='<style>body{font:14px sans-serif;margin:24px}pre{white-space:pre-wrap}div{position:relative;width:100%;max-width:1440px}img{width:100%;display:block}b{position:absolute;color:red;font-size:32px;transform:translate(-50%,-50%)}section{margin-bottom:24px}</style>'
            pagina+='<h1>Rastro local do Resumo</h1><p>As capturas ficam neste computador. Marca vermelha: posição solicitada.</p>'
            if self.melhor>=0:pagina+='<p><a href="melhor_formulario.png">Melhor captura do formulário</a></p>'
            if self.ultima:pagina+='<p><a href="ultima_tela_espera.png">Última tela analisada antes da recuperação</a></p>'
            (self.pasta/'indice.html').write_text(pagina+''.join(secoes),encoding='utf-8')
        except OSError:
            if not self.avisou:
                print('RESUMO_RASTRO gravacao_local_indisponivel',flush=True);self.avisou=True

    def quadro(self, fase, imagem, posicao=None, evidencia=None):
        evento={'fase':fase}
        if posicao is not None:evento['posicao']=list(posicao)
        if evidencia is not None:evento['evidencia']=evidencia
        if hasattr(imagem,'save'):
            try:
                self.pasta.mkdir(parents=True,exist_ok=True)
                nome=f'{len(self.eventos):03d}.png'
                imagem.save(self.pasta/nome)
                evento.update(imagem=nome,tamanho=list(imagem.size),
                    sha256=hashlib.sha256(imagem.tobytes()).hexdigest())
            except OSError:evento['captura']='indisponivel'
        self.eventos.append(evento);self._gravar()

    def evento(self, fase, **detalhe):
        self.eventos.append({'fase':fase,**detalhe});self._gravar()

    def leitura(self, imagem, detalhe):
        # Só booleans, medidas e códigos do leitor, nunca texto livre OCR.
        nota=(8 if detalhe.get('controles')==2 else 4 if detalhe.get('titulo') else 0)+min(3,detalhe.get('rotulos',0))
        if hasattr(imagem,'save'):
            try:
                digest=hashlib.sha256(imagem.tobytes()).hexdigest()
                if digest!=self.ultima:
                    self.pasta.mkdir(parents=True,exist_ok=True)
                    imagem.save(self.pasta/'ultima_tela_espera.png');self.ultima=digest
            except OSError:pass
        if nota>self.melhor and hasattr(imagem,'save'):
            try:
                self.pasta.mkdir(parents=True,exist_ok=True)
                imagem.save(self.pasta/'melhor_formulario.png');self.melhor=nota
            except OSError:pass
        self.evento('reconhecer_formulario',**detalhe)

    def acao(self, alvo, tipo, posicao, capturar, agir, mouse=None):
        for fase in ('antes','depois'):
            if fase=='depois':
                try:agir()  # O callback confere foco/controle da ação.
                except BaseException as erro:
                    self.evento('acao_interrompida',alvo=alvo,tipo_erro=type(erro).__name__)
                    raise
            try:imagem=capturar()
            except Exception:imagem=None
            self.quadro(f'{tipo}_{alvo}_{fase}',imagem,posicao)
        if mouse is not None:
            try:self.evento('ponteiro_apos_acao',posicao=list(mouse()))
            except Exception:pass

    def finalizar(self, sucesso):
        self.evento('fim',sucesso=bool(sucesso))
        print(f'RESUMO_RASTRO arquivo_local=capturas/resumo_{self.id}/indice.html',flush=True)
