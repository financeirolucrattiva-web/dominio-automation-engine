"""Acompanhamento local do worker; não lê nem opera o desktop."""

from contextlib import contextmanager
import datetime as dt
import json
from pathlib import Path
import re
import signal
import threading
import time

from app import painel

ATIVOS = frozenset(('pendente', 'executando'))


def periodo_competencia(valor):
    """Aceita os dois formatos apresentados ao operador, sempre mês completo."""
    if not isinstance(valor, str):
        raise ValueError('Competência inválida.')
    valor = valor.strip()
    if re.fullmatch(r'\d{2}/\d{4}', valor):
        mes, ano = valor.split('/')
        valor = ano + '-' + mes
    if not re.fullmatch(r'\d{4}-\d{2}', valor):
        raise ValueError('Use MM/AAAA ou AAAA-MM.')
    inicio = dt.date.fromisoformat(valor + '-01')
    fim = (inicio.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    return inicio.isoformat(), fim.isoformat()


@contextmanager
def solicitar_cancelamento():
    """Ctrl+C solicita parada no ponto seguro, sem interromper join/limpeza."""
    solicitado = threading.Event()
    anteriores = {}
    if threading.current_thread() is threading.main_thread():
        for nome in ('SIGINT', 'SIGBREAK'):
            sinal = getattr(signal, nome, None)
            if sinal is not None:
                anteriores[sinal] = signal.signal(sinal, lambda *_: solicitado.set())
    try:
        yield solicitado
    finally:
        for sinal, anterior in anteriores.items():
            signal.signal(sinal, anterior)


class ProgressoConsole:
    """Exibe somente eventos aceitos pelo repositório, nunca texto livre OCR."""

    def __init__(self, repo):
        self.repo = repo
        self.lidos = {}
        self.ultima_etapa = 'Aguardando o worker'
        self.ultimo_aviso = time.monotonic()

    def atualizar(self, tarefas):
        for tarefa in tarefas:
            identificador = tarefa['id']
            eventos = self.repo.eventos(identificador)
            for evento in eventos[self.lidos.get(identificador, 0):]:
                rotina = painel.NOMES_ROTINAS.get(evento['routine_id'], 'Rotina')
                etapa = painel.NOMES_ETAPAS.get(evento['step'], 'Etapa')
                status = painel.NOMES_STATUS.get(evento['status'], 'Não confirmado')
                self.ultima_etapa = rotina + ' / ' + etapa
                print(f"[piloto] {rotina} — {etapa}: {status} ({evento['elapsed_seconds']:.1f} s)", flush=True)
            self.lidos[identificador] = len(eventos)

    def avisar_espera(self, inicio, cancelando=False):
        agora = time.monotonic()
        if agora - self.ultimo_aviso >= 5:
            estado = 'Cancelamento solicitado; aguardando ponto seguro' if cancelando else 'Em execução'
            print(f"[piloto] {estado}; {agora - inicio:.0f} s; {self.ultima_etapa}.", flush=True)
            self.ultimo_aviso = agora


def acompanhar_lote(repo, servico, identificador, cancelamento, limite_segundos=1800):
    """Aguarda estados finais e cancelamento cooperativo, sem repetir emissão."""
    progresso = ProgressoConsole(repo)
    inicio = time.monotonic()
    cancelando = False
    while True:
        final = repo.obter_lote(identificador)
        if final is None:
            raise RuntimeError('Lote não encontrado no histórico local.')
        progresso.atualizar(final['tarefas'])
        if final['status'] not in ATIVOS and not any(t['status'] in ATIVOS for t in final['tarefas']):
            return final
        if not servico.disponivel:
            print('[piloto] Worker indisponível. Não será criada outra execução; confira o histórico local.', flush=True)
            return final
        esgotado = time.monotonic() - inicio >= limite_segundos
        if (cancelamento.is_set() or esgotado) and not cancelando:
            if esgotado:
                print('[piloto] Limite da execução atingido; solicitando cancelamento seguro.', flush=True)
            else:
                print('[piloto] Ctrl+C recebido; cancelando o lote sem iniciar a próxima rotina.', flush=True)
            try:
                servico.cancelar_lote(identificador)
            except ValueError:
                # Pode ter concluído entre a leitura e o pedido de cancelamento.
                atual = repo.obter_lote(identificador)
                if atual is None or atual['status'] in ATIVOS:
                    raise
            cancelando = True
        progresso.avisar_espera(inicio, cancelando)
        time.sleep(.3)


def acompanhar_tarefa(repo, servico, identificador, cancelamento, limite_segundos=900):
    """CLI isolado: pausa e encerra pelo controle público no cancelamento."""
    progresso = ProgressoConsole(repo)
    inicio = time.monotonic()
    anunciado = False
    while True:
        final = repo.obter(identificador)
        if final is None:
            raise RuntimeError('Tarefa não encontrada no histórico local.')
        progresso.atualizar([final])
        if final['status'] not in ATIVOS:
            return final
        if not servico.disponivel:
            print('[piloto] Worker indisponível; confira o histórico antes de repetir.', flush=True)
            return final
        cancelar = cancelamento.is_set() or time.monotonic() - inicio >= limite_segundos
        if cancelar:
            if not anunciado:
                print('[piloto] Cancelamento solicitado; aguardando ponto seguro. Não repita a emissão.', flush=True)
                anunciado = True
            controle = servico.estado_controle()
            if controle is not None and controle['tarefa_id'] == identificador:
                try:
                    servico.controlar(identificador, 'pausar')
                except ValueError:
                    time.sleep(.3)
                    continue  # Pode ter finalizado entre a leitura e o controle.
                servico.encerrar()
                final = repo.obter(identificador)
                progresso.atualizar([final])
                return final
        progresso.avisar_espera(inicio, cancelar)
        time.sleep(.3)


def encerrar_servico(servico):
    """Evita join indefinido por falta do pedido cooperativo ao encerrar o CLI."""
    controle = servico.estado_controle()
    if controle is not None:
        try:
            servico.controlar(controle['tarefa_id'], 'pausar')
        except ValueError:
            pass  # A ação pode ter finalizado durante a consulta.
    servico.encerrar()


def salvar_diagnostico_tarefa(repo, final, raiz):
    """Mesma saída limitada, para o teste isolado dos livros."""
    lote = {'id': final['id'], 'status': final['status'], 'motivo': final.get('motivo'),
            'plano': {'inicio': final['pedido']['inicio'], 'fim': final['pedido']['fim']},
            'tarefas': [final]}
    return salvar_diagnostico(repo, lote, raiz)


def salvar_diagnostico(repo, final, raiz):
    """Relatório local com estados; omite empresa, caminhos e OCR livre."""
    rotinas = []
    for tarefa in final['tarefas']:
        eventos = repo.eventos(tarefa['id'])
        modelo = painel.EstadoPainel()
        for evento in eventos:
            modelo.receber(evento)
        rotinas.append({'tarefa_id': tarefa['id'], 'capacidade': tarefa['pedido']['capacidade'],
            'status': tarefa['status'], 'motivo': tarefa.get('motivo'),
            'retorno_confirmado': modelo.retorno == 'Tela principal confirmada',
            'etapas': eventos,
            'artefatos': [{'tipo': a['tipo'], 'disponivel': a['disponivel']}
                         for a in tarefa.get('artefatos', [])]})
    dados = {'lote_id': final['id'], 'status': final['status'], 'motivo': final.get('motivo'),
        'inicio': final['plano']['inicio'], 'fim': final['plano']['fim'],
        'homologacao_fiscal': False, 'rotinas': rotinas,
        'quantidade_pendencias': final['plano'].get('quantidade_pendencias', 0)}
    pasta = Path(raiz) / 'logs'
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / ('piloto_presumido_' + final['id'] + '.json')
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    return destino
