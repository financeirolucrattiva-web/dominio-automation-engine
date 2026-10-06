"""Motor de estados mínimo — generaliza o padrão já repetido em 4
rotinas reais contra o Domínio (SPED Fiscal, EFD Contribuições,
Registro de Saídas, Registro de Entradas): tirar print, checar se
apareceu um texto de SUCESSO, checar se apareceu um texto de ERRO,
esperar e tentar de novo — pulando a checagem (OCR) quando a tela não
mudou desde a última vez (fingerprint, `tela.assinatura_tela()`, seção
0.58).

Generalização de baixo risco, feita DEPOIS de 4 rotinas reais provarem
o mesmo padrão — não suposição de arquitetura. A primeira (e por
enquanto única) aplicação é `dominio.esperar_e_achar()`, refeita por
cima deste motor mantendo assinatura e comportamento idênticos ao de
antes — nenhuma das 4 rotinas precisou mudar uma linha, porque todas
já chamavam `esperar_e_achar()`, não este módulo diretamente.

Não é um "StateEngine" completo no sentido do prompt original do
projeto (sem máquina de transição formal entre MUITOS estados nomeados
— ainda não temos rotinas o bastante pra justificar isso) — é
deliberadamente menor: só o núcleo de "esperar até um de vários
detectores achar alguma coisa", que é o que as 4 rotinas reais
realmente precisam até agora. Crescer pra algo maior quando uma rotina
nova pedir de verdade, não antes.
"""

import time

from . import tela


def esperar_por_estado(detectores, espera_minima=6, tentativas=90, intervalo=2):
    """Tira print repetidamente até um dos `detectores` achar alguma
    coisa, ou esgotar as tentativas — nunca por tempo fixo sozinho
    (mesmo princípio de sempre neste projeto).

    `detectores`: lista de `(nome_estado, funcao)`, testados NESSA
    ORDEM a cada tentativa — o primeiro que achar algo vence (mesmo
    princípio de `TITULOS_ERRO` ser percorrido em ordem, em
    `dominio.py`). `funcao(imagem)` devolve uma posição `(x, y)` (achou)
    ou `None`.

    Pula a chamada de todos os detectores (que geralmente envolvem OCR,
    a parte mais lenta) quando a tela está idêntica à tentativa
    anterior (`tela.assinatura_tela()`/`tela_mudou()`, seção 0.58) —
    rodar os detectores de novo sobre a mesma imagem nunca mudaria a
    resposta.

    Devolve `(imagem, nome_estado, posicao)` quando um detector achar,
    ou `(None, None, None)` se esgotar as tentativas sem achar nada.
    """
    print(f"Esperando pelo menos {espera_minima}s antes de checar...")
    time.sleep(espera_minima)
    assinatura_anterior = None
    for tentativa in range(1, tentativas + 1):
        imagem = tela.capturar_tela()
        assinatura_atual = tela.assinatura_tela(imagem)
        if not tela.tela_mudou(assinatura_anterior, assinatura_atual):
            print(f"Tela igual à tentativa anterior, pulando checagem (tentativa {tentativa}/{tentativas})...")
            time.sleep(intervalo)
            continue
        assinatura_anterior = assinatura_atual

        for nome_estado, funcao in detectores:
            pos = funcao(imagem)
            if pos is not None:
                return imagem, nome_estado, pos

        print(f"Nenhum estado esperado reconhecido ainda (tentativa {tentativa}/{tentativas}) — esperando mais {intervalo}s...")
        time.sleep(intervalo)
    return None, None, None
