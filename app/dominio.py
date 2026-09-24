"""Ações de alto nível no Domínio: trocar de empresa e gerar o SPED
Fiscal.

Reúne a lógica que antes só existia em `scripts/trocar_empresa.py` e
`scripts/explorar.py` (ver docs/00-analise-e-plano-fase0.md, seções
0.8, 0.10-0.14), pra poder ser chamada tanto isolada (um script por
ação, uso manual/exploratório) quanto em lote, empresa por empresa
(`scripts/executar_lote.py`, seção 0.17).

Cada função devolve `True`/`False` em vez de só imprimir e parar — quem
chama (um script isolado ou um loop) decide o que fazer com uma falha,
inclusive continuar pra próxima empresa em vez de travar tudo (erro
isolado por empresa, roadmap seção 6).
"""

import datetime
import time
from pathlib import Path

from . import empresas, erros, ia, interacao, tela

PASTA_CAPTURAS = Path(__file__).resolve().parent.parent / "capturas"

# Títulos de caixa já vistos contra o Domínio real que sinalizam erro/
# aviso, não sucesso (seção 0.25/0.32). "Atenção" é o padrão; "Aviso
# Empresa" tem o código da empresa no resto do título (ex.: "Aviso
# Empresa: 52") — comparado só pelo prefixo fixo, nunca pelo código.
TITULOS_ERRO = ("Atenção", "Aviso Empresa")


class LoteInterrompido(Exception):
    """A IA (ou o catálogo de erros conhecidos) decidiu que este erro
    vai se repetir em toda empresa do lote (ex.: sessão expirada,
    licença, sistema fora do ar) — não adianta insistir empresa por
    empresa. `executar_lote()` para o lote inteiro ao ver isso, em vez
    de só marcar aquela empresa como falha (seção 0.32)."""


def salvar(imagem, nome):
    tela.salvar(imagem, PASTA_CAPTURAS / nome)


def achar_ou_parar(imagem, alvo, nome_erro, escala=2, _tentativas_ia=2):
    """Acha `alvo` em `imagem`; se não achar, salva print de erro e
    desiste — mas antes de desistir de vez, se tiver IA configurada,
    pede pra ela escolher uma técnica de nova tentativa já validada
    neste projeto (`ia.ESTRATEGIAS_RETRY`, seção 0.51): mais zoom,
    recorte central, ou tirar um print novo. **A IA só ESCOLHE entre
    essas técnicas prontas — nunca escreve nem executa código novo, e
    nenhuma delas clica em nada**: só mudam COMO a tela é lida de novo,
    nunca O QUE é clicado depois disso (quem chamou `achar_ou_parar()`
    continua decidindo isso, do jeito de sempre). Até 2 tentativas
    guiadas pela IA (`_tentativas_ia`, controlado pela própria função
    em cada chamada recursiva) antes de desistir de vez e mostrar o
    diagnóstico da seção 0.49. Sem chave configurada, comportamento
    idêntico a antes desta seção: desiste na primeira falha.
    """
    pos = tela.achar_texto(imagem, alvo, escala=escala, debug=True)
    if pos is not None:
        return pos

    print(f"Não achei '{alvo}'.")
    salvar(imagem, nome_erro)

    if _tentativas_ia <= 0 or not ia.disponivel():
        _sugerir_diagnostico(alvo, imagem)
        return None

    texto_visto = erros.anonimizar(tela.ler_texto(imagem, escala=2))
    escolha = ia.escolher_estrategia_retry(alvo, texto_visto)
    if escolha is None:
        _sugerir_diagnostico(alvo, imagem)
        return None

    estrategia, motivo = escolha
    print(f"IA sugere tentar de novo: {estrategia} — {motivo}")

    if estrategia == "ZOOM_MAIOR":
        return achar_ou_parar(imagem, alvo, nome_erro, escala=escala + 2, _tentativas_ia=_tentativas_ia - 1)

    if estrategia == "RECORTE_CENTRAL":
        centro, dx, dy = tela.recortar_centro(imagem)
        pos_centro = tela.achar_texto(centro, alvo, escala=escala)
        if pos_centro is not None:
            print(f"Achou '{alvo}' no recorte central, depois da sugestão da IA.")
            return pos_centro[0] + dx, pos_centro[1] + dy
        return achar_ou_parar(imagem, alvo, nome_erro, escala=escala, _tentativas_ia=_tentativas_ia - 1)

    if estrategia == "NOVA_TELA":
        time.sleep(1)
        return achar_ou_parar(tela.capturar_tela(), alvo, nome_erro, escala=escala, _tentativas_ia=_tentativas_ia - 1)

    # DESISTIR (ou qualquer coisa fora do esperado) — desiste de vez.
    _sugerir_diagnostico(alvo, imagem)
    return None


def _sugerir_diagnostico(alvo, imagem):
    """Depois de uma busca de texto falhar, pede um palpite da IA sobre
    o motivo (seção 0.49) e imprime, se vier algo — só sugestão em
    texto, nunca decide nem muda nada sozinha; quem lê e ajusta
    continua sendo uma pessoa. Sem chave configurada, não faz nada
    (mesma degradação graciosa do resto da IA neste projeto)."""
    if not ia.disponivel():
        return
    texto_visto = erros.anonimizar(tela.ler_texto(imagem, escala=2))
    sugestao = ia.diagnosticar_busca_falha(alvo, texto_visto)
    if sugestao:
        print(f"Palpite da IA sobre o que houve: {sugestao}")


def esperar_e_achar(alvo, texto_erro=TITULOS_ERRO, escala=2, espera_minima=6, tentativas=90, intervalo=2):
    """Espera pelo menos `espera_minima` segundos e depois fica
    verificando a tela por estado (a cada `intervalo` segundos, até
    `tentativas` vezes) em vez de confiar num tempo fixo — achado real
    (seção 0.12): a confirmação de sucesso do SPED Fiscal às vezes
    demora mais que 5 segundos pra aparecer.

    `tentativas` (padrão 90, ~3 minutos no total): calibrado contra
    empresa real, não só a de teste — achado real, seção 0.27: uma
    empresa real com bastante movimento (industrial, com inventário)
    ainda não tinha terminado a exportação depois de 13 tentativas
    (~32s, o teto antigo de 15). A tela de parâmetros fica parada,
    sem nenhum texto novo, enquanto ainda está gerando — não é falha
    de OCR, é só demorar mais que uma empresa de teste, pequena.

    A cada tentativa, também verifica se apareceu uma caixa de erro do
    Domínio (`texto_erro` — um título ou uma tupla de títulos, padrão
    `TITULOS_ERRO`, ex.: "O caminho especificado não é válido.") em vez
    de insistir pelas `tentativas` inteiras esperando um sucesso que
    nunca vai chegar — achado real, primeiro erro visto contra dado
    real (seção 0.25). Passar `texto_erro=None` desliga essa checagem.

    Se não achar `alvo`/`texto_erro` na tela inteira, tenta de novo só
    na região central (`tela.recortar_centro()`) antes de desistir
    daquela tentativa — achado real, seção 0.29: numa empresa real com
    formulário bem mais cheio de campo que o de teste, a confirmação
    de sucesso ficou visível e legível na tela mas o OCR de tela
    inteira não achou (mesmo problema da seção 0.10, tela densa
    confunde o Tesseract — antes só resolvido pro botão OK, agora
    também pra confirmação). Não substitui a busca em tela inteira
    (que já funcionou antes pra EFD Contribuições, seção 0.22) — só
    reforça quando ela falha.

    Devolve `(imagem, posição, houve_erro)`:
    - `(imagem, posição_do_alvo, False)` — achou `alvo` (sucesso).
    - `(imagem, posição_do_erro, True)` — achou `texto_erro` antes do
      alvo (erro do Domínio, não sucesso).
    - `(None, None, False)` — esgotou as tentativas sem achar nada.
    """
    print(f"Esperando pelo menos {espera_minima}s antes de checar...")
    time.sleep(espera_minima)
    for tentativa in range(1, tentativas + 1):
        imagem = tela.capturar_tela()
        pos = tela.achar_texto_ou_no_centro(imagem, alvo, escala=escala, debug=True)
        if pos is not None:
            return imagem, pos, False
        titulos = (texto_erro,) if isinstance(texto_erro, str) else (texto_erro or ())
        for titulo in titulos:
            pos_erro = tela.achar_texto_ou_no_centro(imagem, titulo, escala=escala)
            if pos_erro is not None:
                print(f"Achei uma caixa de erro/aviso do Domínio ('{titulo}') em vez da confirmação.")
                return imagem, pos_erro, True
        print(f"Ainda não achei '{alvo}' (tentativa {tentativa}/{tentativas}) — esperando mais {intervalo}s...")
        time.sleep(intervalo)
    return None, None, False


def _ler_texto_caixa(imagem, pos):
    """Lê o texto da caixa de erro/aviso encontrada em `pos`, num
    recorte pequeno ao redor dela (não a tela inteira — mesmo motivo de
    `recortar_ao_redor` em todo o resto do projeto: menos ruído pro
    OCR). `raio_y` maior que o padrão porque a caixa (título + ícone +
    mensagem + botões) é mais alta que larga."""
    recorte, _, _ = tela.recortar_ao_redor(imagem, *pos, raio_x=260, raio_y=140)
    return tela.ler_texto(recorte, escala=2)


def _fechar_caixa_erro(texto_lido, prefixo=""):
    """Fecha a caixa de erro/aviso que está na tela agora.

    A maioria é diálogo de um botão só (Enter fecha, mesmo truque da
    seção 0.13). Uma exceção conhecida (seção 0.32): "Outros dados não
    digitados! Deseja copiar do último mês digitado?" tem Sim/Não, e o
    botão em foco na caixa real era "Yes" — Enter apertaria o errado.
    Pra esses casos, `erros.BOTAO_NAO_PADRAO` guarda o texto do botão
    certo; acha e clica nele por OCR. Se não achar o botão nomeado,
    cai pro Enter como último recurso, mesmo arriscando o botão errado
    — melhor que travar sem fechar a caixa nenhuma."""
    chave = erros.normalizar(texto_lido)
    for trecho, botao in erros.BOTAO_NAO_PADRAO.items():
        if trecho in chave:
            imagem = tela.capturar_tela()
            pos_botao = tela.achar_texto_ou_no_centro(imagem, botao, escala=2, debug=True)
            if pos_botao is not None:
                print(f"Clicando em '{botao}' (não o botão em foco).")
                interacao.clicar(*pos_botao)
                return
            print(f"Não achei o botão '{botao}' — usando Enter mesmo assim.")
            salvar(imagem, f"{prefixo}erro_botao_nao_achado.png")
            break
    interacao.pressionar_enter()


def trocar_empresa(codigo, prefixo=""):
    """Troca a empresa selecionada no Domínio via F8, buscando por
    código (seção 0.14). Assume que o modo de busca "Busca por" já está
    em Código — o Domínio lembra do último modo usado, não volta pro
    padrão sozinho (achado real, mesma seção); ainda não automatizamos
    forçar esse rádio.

    `prefixo` vai na frente do nome de cada print salvo (ex.: código da
    empresa, terminado em "_") — sem isso, uma segunda empresa que falhe
    no mesmo passo, no mesmo lote, sobrescreveria o print de erro da
    primeira (achado real, seção 0.19: print de erro precisa sobreviver
    até o fim de todo o lote, não só até a próxima falha).

    Devolve True se clicou em "Acessar" e confirmou que a tela de troca
    fechou, False se algo falhou no caminho (fica registrado por print
    + screenshot de erro).
    """
    # Refaz o foco no Domínio antes de qualquer ação (seção 0.6) — não
    # só uma vez no início do lote inteiro. Achado real, seção 0.28: o
    # foco pode ir pra outra janela (ex.: o console do próprio script)
    # no meio de um lote longo, e sem refazer o foco aqui, o F8/clique
    # seguinte acaba indo pra janela errada.
    interacao.focar_dominio()

    print("Abrindo 'Troca de empresas' (F8)...")
    interacao.pressionar_tecla("f8")
    time.sleep(1)

    # Título do diálogo não lê de forma confiável no OCR (seção 0.14) —
    # "Acessar" é bem mais confiável e confirma que a tela carregou.
    imagem = tela.capturar_tela()
    pos = tela.achar_texto_ou_no_centro(imagem, "Acessar", escala=2, debug=True)
    if pos is None:
        # Achado real, seção 0.52: se uma tela de geração da empresa
        # anterior ficou presa aberta (ex.: _fechar_tela_geracao()
        # desistiu), F8 não abre a "Troca de empresas" — e sem
        # recuperar aqui, toda empresa seguinte do lote falha do mesmo
        # jeito, em cascata (visto contra dado real: 4 empresas
        # seguidas perdidas por causa de uma travada). Tenta limpar
        # com Esc (mesmo recurso genérico da seção 0.34) e F8 de novo,
        # 1 vez, antes de desistir de verdade.
        print("Não achei o botão 'Acessar' — talvez uma tela anterior tenha ficado presa. Tentando limpar (Esc) e F8 de novo...")
        salvar(imagem, f"{prefixo}erro_f8.png")
        interacao.pressionar_esc_repetidas()
        interacao.focar_dominio()
        interacao.pressionar_tecla("f8")
        time.sleep(1)
        imagem = tela.capturar_tela()
        pos = tela.achar_texto_ou_no_centro(imagem, "Acessar", escala=2, debug=True)
        if pos is None:
            print("Ainda não achei o botão 'Acessar' depois de tentar limpar — F8 não abriu a Troca de empresas.")
            salvar(imagem, f"{prefixo}erro_f8_apos_esc.png")
            return False
        print("Limpou depois do Esc — 'Troca de empresas' abriu na segunda tentativa.")
    print(f"'Troca de empresas' aberta (botão 'Acessar' em: {pos})")

    print(f"Digitando '{codigo}'...")
    interacao.digitar(str(codigo))
    time.sleep(1)
    salvar(tela.capturar_tela(), f"{prefixo}troca_empresa_digitado.png")

    # Depois de digitar, a linha já fica selecionada sozinha — não
    # precisa clicar nela, só em "Acessar" (confirmado pelo usuário,
    # seção 0.14). Reaproveita a posição já achada (o botão não se move
    # com o filtro do grid).
    print(f"Clicando em Acessar: {pos}")
    interacao.clicar(*pos)

    # Espera por estado (não tempo fixo, seção 0.12) até a tela de
    # 'Troca de empresas' realmente fechar, em vez de confiar num
    # time.sleep() curto — achado real, seção 0.26: um tempo fixo não
    # bastava sempre; o passo seguinte (abrir Relatórios) podia rodar
    # com essa tela ainda aberta atrás, e o próximo documento lia o
    # grid de busca de empresa por engano em vez do menu de verdade.
    for tentativa in range(1, 11):
        time.sleep(1)
        ainda_aberta = tela.achar_texto_ou_no_centro(tela.capturar_tela(), "Acessar", escala=2)
        if ainda_aberta is None:
            break
        print(f"'Troca de empresas' ainda aberta (tentativa {tentativa}/10) — esperando mais 1s...")
    else:
        print("'Troca de empresas' não fechou sozinha. Parando pra não seguir às cegas.")
        salvar(tela.capturar_tela(), f"{prefixo}erro_troca_nao_fechou.png")
        return False

    salvar(tela.capturar_tela(), f"{prefixo}depois_trocar_empresa.png")
    return True


def gerar_sped(item_menu, texto_confirmacao, prefixo=""):
    """Navega Relatórios > Informativos > Federais > `item_menu`, clica
    OK, confirma o aviso de sucesso e fecha a tela — ponta a ponta.

    Generalizado a partir do que validou "SPED Fiscal" (seções 0.8,
    0.10-0.13) depois de confirmar, por print real, que a tela de "EFD
    Contribuições" segue a mesma estrutura: Período/Opções/Arquivo à
    esquerda, coluna de botões à direita começando com OK/Fechar/
    Empresas... na mesma ordem (seção 0.21) — só o texto do item de
    menu e da confirmação de sucesso mudam entre os dois.

    `item_menu`: texto a achar no submenu Federais (ex.: "SPED Fiscal",
    "Contribui" — usar um trecho específico o bastante pra não colidir
    com item parecido, ex.: "EFD-Reinf" x "EFD Contribuições").
    `texto_confirmacao`: texto a achar na caixa de sucesso (ex.:
    "exporta" pra "Final da exportação.", "sucesso" pra "Arquivo
    gerado com sucesso." — **cada tela de geração tem o seu próprio
    texto de confirmação, não é sempre o mesmo** — achado real, seção
    0.21).

    Devolve True se terminou com a confirmação de sucesso vista e a
    tela fechada, False se parou em algum passo no meio do caminho.
    """
    # Refaz o foco no Domínio antes de qualquer ação — mesmo motivo de
    # trocar_empresa() (seção 0.28): o foco pode ter ido pra outra
    # janela (ex.: console do script) entre um documento e outro do
    # mesmo lote; sem isso, o clique em "Relatórios" abaixo pode
    # acabar clicando na janela errada.
    interacao.focar_dominio()

    # 1. Relatórios (barra de menu — sem pré-processamento, já funciona)
    imagem = tela.capturar_tela()
    pos = tela.achar_texto(tela.recortar_topo(imagem), "Relatórios")
    if pos is None:
        print("Não achei 'Relatórios'. O Domínio está aberto e visível?")
        salvar(imagem, f"{prefixo}erro_relatorios.png")
        return False
    print(f"Clicando em Relatórios: {pos}")
    interacao.clicar(*pos)
    time.sleep(2)

    # 2. Informativos (dentro do menu suspenso — precisa de escala=2)
    imagem = tela.capturar_tela()
    area = tela.recortar_area_menu(imagem)
    pos = achar_ou_parar(area, "Informativ", f"{prefixo}erro_informativos.png")
    if pos is None:
        return False
    print(f"Passando o mouse em Informativos: {pos}")
    interacao.passar_mouse(*pos)
    time.sleep(2)

    # 3. Federais (submenu de Informativos)
    imagem = tela.capturar_tela()
    area = tela.recortar_area_menu(imagem)
    pos = achar_ou_parar(area, "Federais", f"{prefixo}erro_federais.png")
    if pos is None:
        return False
    print(f"Passando o mouse em Federais: {pos}")
    interacao.passar_mouse(*pos)
    time.sleep(2)

    # 4. Item de menu (submenu de Federais) — "SPED Fiscal", "EFD
    # Contribuições", etc.
    imagem = tela.capturar_tela()
    area = tela.recortar_area_menu(imagem)
    pos = achar_ou_parar(area, item_menu, f"{prefixo}erro_menu.png")
    if pos is None:
        return False
    print(f"Clicando em {item_menu}: {pos}")
    # clicar_com_desvio, não clicar: o alvo fica dentro do submenu que
    # abriu de "Federais" — uma linha reta a partir de onde o mouse
    # está (posição de "Federais") pode atravessar, na diagonal, a
    # linha de "Estaduais" logo abaixo e trocar o submenu aberto antes
    # de clicar (seção 0.24, pedido real do usuário).
    interacao.clicar_com_desvio(*pos)
    time.sleep(2)

    salvar(tela.capturar_tela(), f"{prefixo}depois_menu.png")

    # Sempre seleciona a competência anterior (mês já fechado) antes de
    # prosseguir — nunca confia no período que já estiver na tela.
    # Pedido do usuário, vale pra todo documento (SPED Fiscal e EFD
    # Contribuições, seção 0.23) — reforça na prática a regra de
    # segurança da seção 5.7 (nunca operar sobre competência corrente).
    if not selecionar_competencia_anterior(prefixo=prefixo):
        print("Não consegui selecionar a competência anterior. Parando.")
        _fechar_tela_geracao(item_menu, prefixo)
        return False

    # 5. OK da tela de geração — primeira ação real (gera arquivo).
    # "OK" tem só 2 letras — continua ilegível pro OCR mesmo dentro do
    # recorte do diálogo a escala=4 (achado real, seção 0.22): "Fechar"
    # e "Empresas..." leram certo nesse recorte, "OK" não. Em vez de
    # insistir em ler "OK", calcula a posição por aritmética a partir
    # de "Fechar" (uma posição acima, mesmo espaçamento entre Fechar e
    # Empresas) — nunca precisa ler "OK" de jeito nenhum.
    #
    # O recorte em si (pela área do diálogo, achado a partir do
    # título — item_menu, "SPED Fiscal"/"EFD Contribuições" —, que
    # sempre lê certo) continua necessário: "Empresas..."/"Fechar" não
    # liam nem na tela inteira, de forma consistente e repetida, não é
    # problema de timing (seção 0.22).
    imagem = tela.capturar_tela()
    titulo = tela.achar_texto_ou_no_centro(imagem, item_menu, escala=2, debug=True)
    if titulo is None:
        print(f"Não achei o título do diálogo ('{item_menu}').")
        salvar(imagem, f"{prefixo}erro_titulo_dialogo.png")
        # A tela de geração continua aberta mesmo sem conseguir ler o
        # título dela (achado real, seção 0.26: "SPED Fiscal" às vezes
        # sai como "spEo" no OCR) — tenta fechar mesmo assim, senão ela
        # fica aberta pro próximo documento/empresa se confundir com
        # ela (mesmo princípio da seção 0.25).
        _fechar_tela_geracao(item_menu, prefixo)
        return False
    xt, yt = titulo
    print(f"Título do diálogo em: {(xt, yt)}")

    area_dialogo, dxd, dyd = tela.recortar_a_partir_de(imagem, xt, yt)
    salvar(area_dialogo, f"{prefixo}area_dialogo.png")

    # escala=4 (não 2): foi a escala usada na tentativa anterior onde
    # "Fechar"/"Empresas..." apareceram certos na lista de debug, ainda
    # que buscando "OK" — usa a mesma, já comprovada nesse recorte.
    ancora_empresas = tela.achar_texto(area_dialogo, "Empresas", escala=4, debug=True)
    ancora_fechar = tela.achar_texto(area_dialogo, "Fechar", escala=4, debug=True)
    if ancora_empresas is None or ancora_fechar is None:
        print("Não achei 'Empresas...'/'Fechar' na área do diálogo. Parando.")
        salvar(area_dialogo, f"{prefixo}erro_ok.png")
        _fechar_tela_geracao(item_menu, prefixo)
        return False
    espaco_botao = ancora_empresas[1] - ancora_fechar[1]
    pos_local = (ancora_fechar[0], ancora_fechar[1] - espaco_botao)
    pos = (pos_local[0] + dxd, pos_local[1] + dyd)
    print(f"'OK' calculado a partir de 'Fechar' ({ancora_fechar}) + espaçamento ({espaco_botao}px): {pos}")

    # Guarda a posição de "Fechar" em coordenada de tela cheia — o
    # diálogo não muda de lugar entre abrir e fechar, então dá pra
    # reaproveitar essa posição depois em vez de reler "Fechar" por
    # OCR (achado real, seção 0.31: "Fechar" lia certo aqui, antes do
    # OK, e ficou ilegível 3 tentativas seguidas depois da geração).
    pos_fechar_conhecido = (ancora_fechar[0] + dxd, ancora_fechar[1] + dyd)

    print(f"Clicando em OK: {pos}")
    interacao.clicar(*pos)

    # 6-7. Aguardar o resultado por estado (não por tempo fixo, seção
    # 0.12/0.16) até achar a confirmação de sucesso OU uma caixa de
    # erro do Domínio (seção 0.25), depois confirmar com Enter (diálogo
    # de um botão só, "OK" ilegível pro OCR de novo — seção 0.13) e
    # checar que ela realmente sumiu.
    print("Aguardando o resultado da geração (verificando por estado)...")
    imagem, ancora_confirm, houve_erro = esperar_e_achar(texto_confirmacao, escala=2)
    if houve_erro:
        # Domínio mostrou um erro/aviso (ex.: caminho de arquivo
        # inválido) em vez da confirmação de sucesso. Não adianta
        # continuar esperando por um "sucesso" que não vai aparecer:
        # salva a evidência, lê o texto da caixa (só pra decidir o que
        # fazer — nunca sai da máquina sem passar por
        # `erros.anonimizar()` primeiro, seção 5.5/0.32) e decide a
        # ação com `erros.decidir()` (catálogo conhecido, aprendido, ou
        # IA como último recurso).
        print("O Domínio mostrou uma caixa de erro/aviso em vez da confirmação de sucesso.")
        salvar(imagem, f"{prefixo}erro_dominio.png")
        texto_lido = _ler_texto_caixa(imagem, ancora_confirm)
        acao = erros.decidir(texto_lido, documento=item_menu)

        _fechar_caixa_erro(texto_lido, prefixo)
        time.sleep(1)

        if acao == erros.CONTINUAR:
            # Só um aviso informativo — a caixa já fechou, a geração
            # deve seguir sozinha. Volta a esperar pela confirmação de
            # verdade, sem reabrir nada.
            print("Aviso dispensado — voltando a esperar a confirmação de sucesso.")
            imagem, ancora_confirm, houve_erro_de_novo = esperar_e_achar(texto_confirmacao, escala=2)
            if houve_erro_de_novo or ancora_confirm is None:
                print("Depois do aviso, ainda não veio a confirmação de sucesso. Parando este documento.")
                salvar(tela.capturar_tela(), f"{prefixo}erro_apos_aviso.png")
                _fechar_tela_geracao(item_menu, prefixo, pos_fechar_conhecido)
                return False
            # segue o fluxo normal a partir daqui, como se tivesse achado de primeira
        else:
            _fechar_tela_geracao(item_menu, prefixo, pos_fechar_conhecido)
            if acao == erros.PARAR_LOTE:
                raise LoteInterrompido(texto_lido)
            if acao == erros.TENTAR_DE_NOVO and not prefixo.endswith("retry_"):
                print("Tentando gerar este documento mais uma vez.")
                return gerar_sped(item_menu, texto_confirmacao, prefixo=f"{prefixo}retry_")
            return False
    if ancora_confirm is None:
        print(f"Não achei a confirmação ('{texto_confirmacao}') depois de esperar. Deu erro na geração?")
        salvar(tela.capturar_tela(), f"{prefixo}erro_confirmacao.png")
        _fechar_tela_geracao(item_menu, prefixo, pos_fechar_conhecido)
        return False
    xc, yc = ancora_confirm
    print(f"Âncora confirmação em: {(xc, yc)}")
    salvar(imagem, f"{prefixo}resultado.png")

    print("Confirmando com Enter (diálogo padrão de um só botão)...")
    interacao.pressionar_enter()

    # Confere por estado, com mais de uma tentativa, antes de concluir
    # que o Enter não funcionou — achado real, seção 0.28: a tela
    # remota (GO-Global) pode demorar mais que 1s pra repintar depois
    # de fechar um diálogo sobre um formulário grande e cheio de campo
    # (visto numa empresa real com bastante opção configurada) — uma
    # checagem única e rápida demais pode ler um quadro que ainda não
    # repintou e concluir "ainda aberto" por engano, quando a
    # confirmação já tinha fechado de verdade (o resto do lote seguiu
    # confirmando isso: `_fechar_tela_geracao()` logo depois já não
    # achava mais a tela).
    ainda_aberto = None
    for _ in range(3):
        time.sleep(1)
        ainda_aberto = tela.achar_texto_ou_no_centro(tela.capturar_tela(), texto_confirmacao, escala=2, debug=True)
        if ainda_aberto is None:
            break
    if ainda_aberto is not None:
        print("Enter não fechou a confirmação. Parando pra não seguir às cegas.")
        salvar(tela.capturar_tela(), f"{prefixo}erro_enter_confirmacao.png")
        _fechar_tela_geracao(item_menu, prefixo, pos_fechar_conhecido)
        return False
    print("Confirmação fechada.")

    # 8. Fechar a tela de geração.
    return _fechar_tela_geracao(item_menu, prefixo, pos_fechar_conhecido)


def _fechar_tela_geracao(item_menu, prefixo="", pos_fechar_conhecido=None):
    """Fecha a tela de geração (Período/Opções/Arquivo) clicando em
    'Fechar' — mesma técnica do passo 5 de `gerar_sped()`: recorta pela
    área do diálogo a partir do título (`item_menu`), acha 'Fechar'
    dentro do recorte.

    Reaproveitado tanto depois de um sucesso (passo 8) quanto depois de
    qualquer falha no meio do caminho — dispensar uma caixa de erro do
    Domínio (seção 0.25), não achar o título do diálogo, não achar
    "Empresas.../Fechar", não achar a confirmação — em todos esses
    casos a tela de geração pode continuar aberta, e deixá-la aberta
    contaminava o próximo documento/empresa do lote (achado real, seção
    0.26: sem fechar, a leitura do documento seguinte lia campos da
    tela velha por engano). O Domínio precisa voltar a um estado limpo
    antes de seguir em frente, com sucesso ou sem.

    Tenta achar o título (`item_menu`) e, separadamente, o botão
    "Fechar" dentro do recorte, até 3 vezes cada (com uma pausa entre
    elas) antes de desistir — o título ou o "Fechar" podem falhar no
    OCR só por acaso, uma vez (achado real, seção 0.26: "SPED Fiscal"
    leu como "spEo"; seção 0.30: título achou na 2ª tentativa mas
    "Fechar" não achou nem assim, deixando a tela de EFD Contribuições
    aberta pra trás e atrapalhando a troca de empresa seguinte). Só
    conclui "já fechou sozinha" se o título nunca aparecer em nenhuma
    das tentativas — achar o título mas nunca achar "Fechar" é tratado
    como "ainda aberta, não consegui fechar", não como "já fechou".

    `pos_fechar_conhecido`: posição de "Fechar" em coordenada de tela
    cheia, se já foi achada antes na mesma chamada de `gerar_sped()"
    (ao calcular a posição de "OK" a partir dela). O diálogo não muda
    de lugar entre abrir e fechar — reaproveitar essa posição evita
    reler "Fechar" por OCR, que às vezes fica ilegível depois da
    geração mesmo tendo lido certo antes dela (achado real, seção
    0.31: 3 tentativas seguidas, título achado, "Fechar" nunca). Se
    informado, tenta clicar ali primeiro e confirma que o título
    sumiu; só cai pro jeito antigo (achar tudo de novo por OCR) se
    isso não fechar de verdade.
    """
    if pos_fechar_conhecido is not None:
        print(f"Clicando em Fechar (posição já conhecida, achada antes do OK): {pos_fechar_conhecido}")
        interacao.clicar(*pos_fechar_conhecido)
        time.sleep(1)
        ainda_aberto = tela.achar_texto_ou_no_centro(tela.capturar_tela(), item_menu, escala=2)
        if ainda_aberto is None:
            salvar(tela.capturar_tela(), f"{prefixo}depois_fechar.png")
            print(f"{item_menu} fechado.")
            return True
        print("Clique na posição conhecida não fechou a tela — tentando achar 'Fechar' de novo por OCR.")

    titulo_achado_alguma_vez = False
    for tentativa in range(1, 4):
        if tentativa > 1:
            time.sleep(1)
        imagem = tela.capturar_tela()
        titulo_fechar = tela.achar_texto_ou_no_centro(imagem, item_menu, escala=2, debug=True)
        if titulo_fechar is None:
            continue
        titulo_achado_alguma_vez = True
        xf, yf = titulo_fechar
        area_fechar, dxf, dyf = tela.recortar_a_partir_de(imagem, xf, yf)
        pos_fechar = tela.achar_texto(area_fechar, "Fechar", escala=4, debug=True)
        if pos_fechar is not None:
            pos_fechar_tela = (pos_fechar[0] + dxf, pos_fechar[1] + dyf)
            print(f"Clicando em Fechar: {pos_fechar_tela}")
            interacao.clicar(*pos_fechar_tela)
            time.sleep(1)
            salvar(tela.capturar_tela(), f"{prefixo}depois_fechar.png")
            print(f"{item_menu} fechado.")
            return True
        print(f"Achei o título mas não 'Fechar' (tentativa {tentativa}/3) — tentando de novo...")

    if not titulo_achado_alguma_vez:
        print("Não achei mais a tela de geração — já deve ter fechado sozinha.")
        return True

    print("Achei a tela de geração, mas não consegui achar/clicar 'Fechar'. Ficou aberta.")
    imagem_final = tela.capturar_tela()
    salvar(imagem_final, f"{prefixo}erro_fechar.png")
    _sugerir_diagnostico("Fechar", imagem_final)

    # Achado real, seção 0.52: sem isso, a tela de geração fica presa
    # aberta e derruba toda empresa seguinte do lote em cascata — o F8
    # da próxima nem abre a "Troca de empresas" (ela também tenta se
    # recuperar do mesmo jeito, mas cobrir aqui também evita o
    # problema de nascer). Esc é o mesmo recurso genérico da seção
    # 0.34 — fecha diálogo/menu empilhado sem precisar saber o que
    # era. Continua devolvendo False: a geração pode ter falhado
    # mesmo, isso só evita que o problema se espalhe pro resto do lote.
    print("Tentando limpar com Esc antes de seguir pra próxima empresa/documento...")
    interacao.pressionar_esc_repetidas()
    return False


def gerar_sped_fiscal(prefixo=""):
    """SPED Fiscal (EFD ICMS/IPI) — validado ponta a ponta com o
    Domínio real (seções 0.8, 0.11-0.13). Wrapper fino sobre
    `gerar_sped()`."""
    return gerar_sped("SPED Fiscal", "exporta", prefixo=prefixo)


def gerar_efd_contribuicoes(prefixo=""):
    """EFD Contribuições (PIS/COFINS) — validado ponta a ponta com o
    Domínio real (seção 0.40): navegação (Relatórios > Informativos >
    Federais > "Contribui"), competência anterior, OK e Fechar todos
    confirmados por execução real, não só inspeção visual. A busca
    literal por "sucesso" pode não achar nada numa tela real densa
    (mesma limitação das seções 0.10/0.29) — quando isso acontece, o
    fallback de `esperar_e_achar()` pelo diálogo de um só botão
    (Enter) fecha do mesmo jeito. Wrapper fino sobre `gerar_sped()`."""
    return gerar_sped("Contribui", "sucesso", prefixo=prefixo)


def competencia_anterior():
    """Devolve (data_inicial, data_final) do mês fechado mais recente
    — o anterior ao mês corrente —, no formato `DD/MM/AAAA` (seção
    0.23). Ex.: rodando em 22/09/2026, devolve
    `("01/08/2026", "31/08/2026")`. Nunca o mês corrente — é a mesma
    regra de segurança da seção 5.7 (só gerar sobre competência já
    fechada, nunca a que ainda está em curso)."""
    hoje = datetime.date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
    primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
    fmt = "%d/%m/%Y"
    return primeiro_dia_mes_anterior.strftime(fmt), ultimo_dia_mes_anterior.strftime(fmt)


def selecionar_competencia_anterior(prefixo=""):
    """Preenche Data inicial/Data final da tela de geração já aberta
    com o mês fechado anterior ao atual (`competencia_anterior()`) —
    mouse (clica no campo) + teclado (seleciona o valor atual, digita
    por cima, Tab pra confirmar) — pedido do usuário, seção 0.23.

    O deslocamento do rótulo "Data inicial:" até o campo de valor foi
    calibrado visualmente. **Só clica no campo "Data inicial"** —
    confirmado pelo usuário: `Tab` ao terminar o primeiro já leva o
    foco pro campo "Data final" sozinho (ordem de tabulação do
    formulário), não precisa de um segundo clique.

    Dois achados reais do primeiro teste (o valor **não mudou**, ficou
    o antigo): `Ctrl+A` não seleciona o conteúdo desse campo mascarado
    — troca pra `selecionar_tudo_alternativo()` (Home + Shift+End,
    mais universal); e a data é digitada **só com dígitos** (sem `/`),
    porque a máscara (`99/99/9999`) insere as barras sozinha — digitar
    a barra pode confundir o cursor da máscara.

    Depois de digitar, **confere de verdade** (por OCR) se os dois
    campos realmente mostram a competência esperada, em vez de só
    assumir que digitar funcionou — sem essa conferência, um clique ou
    seleção que falhasse silenciosamente (como já aconteceu) deixaria
    o motor seguir pra gerar com a competência errada, sem ninguém
    perceber.

    Devolve True só se achou o rótulo, preencheu, e **confirmou por
    OCR** que os dois valores batem com o esperado. False em qualquer
    outro caso, com print de erro salvo.
    """
    data_inicial, data_final = competencia_anterior()
    print(f"Selecionando competência anterior: {data_inicial} a {data_final}")

    imagem = tela.capturar_tela()

    pos_label_inicial = tela.achar_texto_ou_no_centro(imagem, "Data inicial", escala=2, debug=True)
    if pos_label_inicial is None:
        print("Não achei 'Data inicial'.")
        salvar(imagem, f"{prefixo}erro_data_inicial.png")
        return False

    # O campo de valor fica à direita do rótulo, não em cima dele —
    # deslocamento calibrado visualmente.
    deslocamento_x = 75
    campo_inicial = (pos_label_inicial[0] + deslocamento_x, pos_label_inicial[1])

    print(f"Clicando no campo Data inicial: {campo_inicial}")
    interacao.clicar(*campo_inicial)
    time.sleep(0.3)
    interacao.selecionar_tudo_alternativo()
    interacao.digitar(data_inicial.replace("/", ""))
    interacao.pressionar_tecla("tab")
    time.sleep(0.3)

    # Tab já deixou o foco em "Data final" sozinho — só seleciona o
    # valor atual e digita por cima, sem clicar de novo.
    interacao.selecionar_tudo_alternativo()
    interacao.digitar(data_final.replace("/", ""))
    interacao.pressionar_tecla("tab")
    time.sleep(0.3)

    imagem_depois = tela.capturar_tela()
    salvar(imagem_depois, f"{prefixo}depois_competencia.png")

    # Confere de verdade — não assume que digitar funcionou (achado
    # real: já aconteceu de o valor antigo continuar lá, sem mudar).
    achou_inicial = tela.achar_texto_ou_no_centro(imagem_depois, data_inicial, escala=2, debug=True)
    achou_final = tela.achar_texto_ou_no_centro(imagem_depois, data_final, escala=2, debug=True)
    if achou_inicial is None or achou_final is None:
        print(f"Não confirmei os dois campos com o período certo ({data_inicial} / {data_final}).")
        salvar(imagem_depois, f"{prefixo}erro_competencia_nao_confirmada.png")
        return False

    print("Competência anterior confirmada nos dois campos.")
    return True


# Qual função gera cada documento (seção 0.20) — usado por
# executar_lote() pra decidir o que rodar por empresa, a partir de
# empresas.documentos_necessarios().
_GERADORES = {
    "ICMS": gerar_sped_fiscal,
    "CONTRIBUICOES": gerar_efd_contribuicoes,
}


# Automações extras, promovidas do gravador depois de revisadas e
# corrigidas (seção 0.35/0.47) — cada uma vira uma opção a mais no
# menu de texto (scripts/app.py) e um botão a mais na interface
# gráfica (scripts/gui.py), na ordem desta lista, sem editar os dois
# na mão a cada automação nova (seção 0.48).
#
# Pra promover uma automação nova depois de gravada/revisada/testada:
# 1. Cole a função final aqui embaixo (ou em qualquer lugar deste
#    arquivo), mesmo padrão de gerar_sped_fiscal()/
#    gerar_efd_contribuicoes(): recebe prefixo="", devolve True/False.
# 2. Acrescente uma linha na lista abaixo:
#    ("Nome que aparece no menu", nome_da_funcao),
# 3. Suba pro GitHub — Atualizar.bat leva a opção nova pra toda
#    máquina, nos dois modos da interface.
#
# Não entra no lote (_GERADORES/tipo/sped acima) de propósito — isso é
# específico dos dois documentos SPED já conhecidos, ligado à planilha
# de empresas; automação extra roda uma empresa de cada vez, igual
# "Gerar SPED Fiscal".
AUTOMACOES_EXTRAS = [
    # ("Nome que aparece no menu", funcao_correspondente),
]


def _esperar_se_pausado(pausa):
    """Se `pausa` (um `threading.Event`) não estiver "set", bloqueia
    até ficar — usado pela interface gráfica pra pausar/continuar o
    lote (seção 0.34). Só é checado entre uma empresa e outra, nunca no
    meio de uma ação — pausar durante um clique deixaria o Domínio num
    estado que ninguém garante. `pausa=None` (uso por terminal,
    `scripts/app.py`/`scripts/executar_lote.py`) nunca bloqueia.
    """
    if pausa is not None and not pausa.is_set():
        print("\nPausado — aguardando continuar...")
        pausa.wait()
        print("Continuando.")


def _processar_empresa(e, prefixo_empresa):
    """Troca pra empresa `e` e gera cada documento que ela precisa
    (`empresas.documentos_necessarios()`). Devolve o dict de status por
    documento. Deixa `LoteInterrompido` subir pra quem chamou sem
    capturar — nunca é hora de tentar de novo sozinho pra esse caso, é
    decisão explícita (IA/catálogo) de parar o lote inteiro (seção
    0.32)."""
    if not trocar_empresa(e["codigo"], prefixo=prefixo_empresa):
        print("Falha ao trocar de empresa — pulando para a próxima.")
        return {"-": "falha ao trocar de empresa"}
    time.sleep(1)

    # Uma empresa pode precisar de 1 ou 2 documentos (tipo/sped, seção
    # 0.20) — gera cada um, com falha isolada por documento (um
    # documento falhar não impede tentar o outro).
    status_documentos = {}
    for documento in empresas.documentos_necessarios(e):
        print(f"\n--- {documento} ---")
        prefixo = f"{prefixo_empresa}{documento}_"
        gerador = _GERADORES.get(documento)
        if gerador is None:
            status_documentos[documento] = "documento desconhecido"
            continue
        status_documentos[documento] = "sucesso" if gerador(prefixo=prefixo) else "falha na geração"
    return status_documentos


def executar_lote(usar_real=False, regime=None, confirmar=None, pausa=None):
    """Pergunta o regime, mostra as empresas selecionadas, confirma, e
    roda `trocar_empresa()` + o(s) gerador(es) certo(s) pra cada uma —
    uma empresa pode precisar de 1 ou 2 documentos (`tipo`/`sped`,
    seção 0.20). Falha isolada por empresa e por documento, resumo no
    final (seção 0.17).

    `usar_real=False` (padrão) usa `data/empresas.exemplo.csv`
    (demonstração, sem risco). `usar_real=True` usa `data/empresas.csv`
    (planilha real) — trava de propósito: a Fase 5 em empresa real
    ainda depende da Fase 4 validada na empresa-alvo real (seção 5.7),
    o que ainda não aconteceu.

    `regime`/`confirmar` (opcionais, seção 0.33): a interface gráfica
    (`scripts/gui.py`) não tem terminal pra `input()` — passa o regime
    já escolhido (pula a pergunta) e uma função
    `confirmar(selecionadas) -> bool` no lugar da confirmação por
    `input()` (a própria janela mostra a lista e pergunta por caixa de
    diálogo). Sem informar os dois, o comportamento por terminal
    (`scripts/app.py`, `scripts/executar_lote.py`) continua idêntico a
    antes — pergunta os dois por `input()`.

    `pausa` (opcional, seção 0.34): um `threading.Event` que a
    interface gráfica usa pra pausar/continuar o lote entre uma
    empresa e outra (nunca no meio de uma ação). `pausa=None` (padrão,
    uso por terminal) nunca pausa.

    Se der um erro inesperado processando uma empresa (não uma falha
    limpa de documento, que já é tratada por dentro — uma exceção de
    verdade), tenta recuperar apertando Esc repetidas vezes
    (`interacao.pressionar_esc_repetidas()`, seção 0.34 — fecha
    diálogo/menu empilhado sem precisar saber o que era) e repete essa
    empresa mais 1 vez antes de desistir dela e seguir pra próxima —
    pedido do usuário, nunca trava o lote inteiro por causa disso.
    """
    if usar_real:
        print("ATENÇÃO: rodando contra data/empresas.csv (empresas REAIS).")
        caminho = None
    else:
        print("Rodando contra empresas.exemplo.csv (demonstração, sem risco).")
        caminho = empresas.ARQUIVO_EXEMPLO

    lista = empresas.carregar_empresas(caminho)
    if not lista:
        print("Lista de empresas vazia.")
        return

    regimes = empresas.regimes_disponiveis(lista)
    print(f"{len(lista)} empresa(s) na lista. Regimes disponíveis: {', '.join(regimes)}")
    if regime is None:
        regime = input("Qual regime você quer processar hoje? ").strip()

    selecionadas = empresas.filtrar_por_regime(lista, regime)
    if not selecionadas:
        print(f"Nenhuma empresa com regime '{regime}'.")
        return

    print(f"\n{len(selecionadas)} empresa(s) selecionada(s):")
    for e in selecionadas:
        print(f"  {e['codigo']} - {e['apelido']}")

    if confirmar is not None:
        if not confirmar(selecionadas):
            print("Cancelado.")
            return
    else:
        resposta = input(f"\nConfirma rodar o(s) documento(s) configurado(s) para essas {len(selecionadas)} empresa(s)? (sim/não) ").strip().lower()
        if resposta not in ("sim", "s"):
            print("Cancelado.")
            return

    print("\nFocando o Domínio...")
    interacao.focar_dominio()

    resultados = []
    for e in selecionadas:
        _esperar_se_pausado(pausa)
        print(f"\n=== {e['codigo']} - {e['apelido']} ===")
        prefixo_empresa = f"{e['codigo']}_"
        try:
            status_documentos = _processar_empresa(e, prefixo_empresa)
        except LoteInterrompido as erro:
            # A IA (ou o catálogo de erros conhecidos) decidiu que este
            # erro vai se repetir em toda empresa — parar o lote
            # inteiro agora, em vez de gastar tempo tentando empresa
            # por empresa contra o mesmo problema (seção 0.32). Nunca
            # tenta recuperar/repetir esse caso — é decisão explícita.
            print(f"\nParando o lote inteiro: {erro}")
            resultados.append((e, {"-": "lote interrompido"}))
            break
        except Exception as erro:
            # Não é uma falha limpa de documento (já tratada por
            # dentro de _processar_empresa) — é uma exceção de
            # verdade, o motor não sabe em que estado o Domínio ficou.
            # Recuperação genérica: Esc repetidas vezes (fecha
            # diálogo/menu empilhado, seção 0.34) e repete esta empresa
            # 1 vez antes de desistir dela — nunca trava o lote inteiro
            # por isso, pedido do usuário.
            print(f"\nErro inesperado processando {e['codigo']} ({erro}) — recuperando (Esc) e tentando de novo 1x.")
            interacao.pressionar_esc_repetidas()
            try:
                status_documentos = _processar_empresa(e, prefixo_empresa)
            except LoteInterrompido as erro2:
                print(f"\nParando o lote inteiro: {erro2}")
                resultados.append((e, {"-": "lote interrompido"}))
                break
            except Exception as erro2:
                print(f"Deu errado de novo depois de tentar recuperar — pulando {e['codigo']}: {erro2}")
                interacao.pressionar_esc_repetidas()
                status_documentos = {"-": "erro inesperado, pulada após 1 tentativa"}
        resultados.append((e, status_documentos))

    print("\n=== Resumo ===")
    if erros.decisoes_da_sessao:
        print("\nDecisões tomadas em caixas de erro/aviso durante este lote:")
        for documento, texto, acao, origem in erros.decisoes_da_sessao:
            resumo = texto.splitlines()[0] if texto else "(sem texto)"
            print(f"  [{documento}] \"{resumo}\" → {acao} ({origem})")

    houve_falha = False
    linhas_ia = []
    for e, status_documentos in resultados:
        detalhes = ", ".join(f"{doc}: {status}" for doc, status in status_documentos.items())
        print(f"  {e['codigo']} - {e['apelido']}: {detalhes}")
        linhas_ia.append(f"empresa {e['codigo']}: {detalhes}")
        if any(status != "sucesso" for status in status_documentos.values()):
            houve_falha = True
    if houve_falha:
        print("\nPrints de erro salvos em capturas/, com código da empresa e documento no início do nome de cada arquivo.")

    # Resumo em português simples, gerado por IA (seção 0.49) — só
    # texto, complementa o resumo técnico acima; sem chave configurada,
    # resumir_lote() devolve None e isso não aparece, sem travar nada.
    resumo_ia = ia.resumir_lote(linhas_ia)
    if resumo_ia:
        print("\nResumo em português (gerado por IA, só a partir da lista acima):")
        print(resumo_ia)
