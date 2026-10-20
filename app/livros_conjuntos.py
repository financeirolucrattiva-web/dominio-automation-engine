"""Entradas, Saídas e ICMS em uma emissão; ainda requer teste no Windows.

Usa o menu observado e exporta um PDF por relatório numa pasta exclusiva.
O worker publica somente os PDFs conferidos no destino da empresa.
"""
import datetime as dt
from pathlib import Path
import time
import uuid
import json

from app import arquivos, estados, formulario_livros, tela
from app.controle_execucao import ponto_seguro, ExecucaoInterrompida
from app.seletor_pasta import SeletorPastaNaoConfirmado

TIPOS = tuple(formulario_livros.ROTULOS)
OPCAO_PDF = 'Gerar um arquivo PDF para cada relatório'


def _achar_opcao_pdf(imagem):
    # O leitor padrão agrupa até quatro palavras; esta opção tem sete.
    pos = tela.achar_texto(imagem, OPCAO_PDF, escala=4, max_palavras=8)
    if pos is None:
        pos = tela.achar_texto_windows(imagem, OPCAO_PDF, escala=4, max_palavras=8)
    return pos


def _achar_ok(imagem):
    """Confirma o botão literal e suas bordas na captura atual, sem emitir."""
    from app.botao_livros import achar_ok_livros
    return achar_ok_livros(imagem, registrar=lambda detalhe:
        print('LIVROS_OK '+json.dumps(detalhe, ensure_ascii=False), flush=True))


def _captura_falha(dominio, prefixo):
    try:
        dominio.salvar(tela.capturar_tela(), prefixo+'erro_livros_conjuntos.png')
    except Exception:
        print('Captura local dos livros indisponível; consulte as etapas.', flush=True)


def _ler_selecao(imagem=None):
    imagem = imagem if imagem is not None else tela.capturar_tela()
    return formulario_livros.ler_selecao_com_ocr(imagem, registrar=lambda detalhe:
        print('LIVROS_SELECAO '+json.dumps(detalhe,ensure_ascii=False),flush=True))


def _ler_periodo(imagem=None):
    from app.leitura_resumo import ler_campos
    imagem = imagem if imagem is not None else tela.capturar_tela()
    from app import dominio
    return ler_campos(imagem, livros=True, registrar=lambda detalhe:
        print('LIVROS_PERIODO '+json.dumps(detalhe,ensure_ascii=False),flush=True),
        salvar_recorte=lambda recorte,nome: dominio.salvar(recorte,'livros_data_'+nome+'.png'))


def _aguardar_formulario(dominio, prefixo, referencia=None):
    def detectar(imagem):
        try:
            _ler_selecao(imagem)
            return (0, 0)
        except ValueError:
            return None
    return _aguardar(dominio, 'formulario', detectar, prefixo, tentativas=20, referencia=referencia)


def _aguardar(dominio, nome, detector, prefixo, tentativas=90, referencia=None):
    detectores = [(titulo, lambda img, t=titulo:
                   tela.achar_texto_ou_no_centro(img, t, escala=2)) for titulo in dominio.TITULOS_ERRO]
    # Pixels exatos e releitura a cada 3 tentativas mesmo com a tela parada: uma
    # leitura de OCR negativa numa tela estática (ex.: a prévia já aberta) não pode
    # virar resultado permanente (64 vezes "Tela igual..." até estourar o prazo).
    imagem, estado, pos = estados.esperar_por_estado(
        detectores + [(nome, detector)], espera_minima=.3,
        tentativas=tentativas, intervalo=1,
        comparacao_exata=True, rever_a_cada=3, limite_segundos=max(90, tentativas*3),
        # Sem OCR enquanto a tela é a de antes do clique; lê só quando ela estabilizar.
        referencia_inicial=referencia, aguardar_estabilidade=referencia is not None)
    if estado in dominio.TITULOS_ERRO:
        texto = dominio._ler_texto_caixa(imagem, pos)
        acao = dominio.erros.decidir(texto, documento='Livros Fiscais')
        dominio.salvar(imagem, prefixo+'erro_aviso_livros_conjuntos.png')
        dominio._fechar_caixa_erro(texto, prefixo)
        if acao == dominio.erros.PARAR_LOTE:
            raise dominio.LoteInterrompido('Aviso interrompeu Livros Fiscais.')
        return None
    return imagem if estado == nome else None


def _esperar_periodo(papel=None, esperado=None, tentativas=5):
    """Aguarda leitura nova, sem redigitar para compensar OCR transitório."""
    for tentativa in range(tentativas):
        ponto_seguro()
        try:
            campos = formulario_livros._validar_periodo_confirmado(_ler_periodo())
            if papel is None or campos[papel]['valor'] == esperado:
                return campos
        except ValueError:
            pass
        print(f'LIVROS_PERIODO_RELEITURA campo={papel or "campos"} tentativa={tentativa+1} confirmado=False',flush=True)
        if tentativa < tentativas-1:
            time.sleep(.3)
    raise ValueError('Período dos livros não confirmado; não emitir.')


def _assinatura_segura():
    try:
        return tela.assinatura_tela(tela.capturar_tela())
    except Exception:
        return None  # qualquer dúvida: refaz a leitura


def _selecao_por_pixels(referencia):
    """Estado das 16 caixas já conhecidas, sem OCR (ver formulario_livros.reler_por_pixels)."""
    return formulario_livros.reler_por_pixels(tela.capturar_tela(), referencia)


def _conferir_antes_ok(inicial, final, tentativas=5, referencia=None, leitura_previa=None):
    """As duas datas e todas as opções precisam bater na MESMA captura.

    `referencia`: leitura completa anterior das caixas (permite reler só pixels).
    `leitura_previa`: (datas, impressão digital) da última leitura de OCR sem ação
    depois dela; se a tela é a mesma, não repete o OCR das datas (~20 s).
    """
    usar_pixels = isinstance(referencia, dict) and 'altura' in referencia
    for tentativa in range(tentativas):
        ponto_seguro()
        imagem = tela.capturar_tela()
        try:
            periodo = None
            if leitura_previa is not None and tentativa == 0:
                campos, antes = leitura_previa
                agora = _assinatura_segura()
                if (antes is not None and agora is not None and not tela.tela_mudou(antes, agora)
                        and campos['inicial']['valor'] == inicial and campos['final']['valor'] == final):
                    periodo = campos
            if periodo is None:
                periodo = formulario_livros._validar_periodo_confirmado(_ler_periodo(imagem))
            selecao = None
            if usar_pixels:
                try:
                    selecao = formulario_livros.reler_por_pixels(imagem, referencia)
                except ValueError:
                    selecao = None
            if selecao is None:
                selecao = _ler_selecao(imagem)
            if (set(selecao['livros']) == set(TIPOS) and len(selecao['outros']) == 13
                    and all(type(l['marcada']) is bool for l in selecao['livros'].values())
                    and all(type(c['marcada']) is bool for c in selecao['outros'])
                    and periodo['inicial']['valor'] == inicial and periodo['final']['valor'] == final
                    and all(l['marcada'] for l in selecao['livros'].values())
                    and not any(c['marcada'] for c in selecao['outros'])):
                return imagem
            if any(c['marcada'] is True for c in selecao['outros']):
                raise ValueError('Outra opção está marcada; não emitir.')
        except ValueError:
            pass
        if tentativa < tentativas-1:
            time.sleep(.3)
    raise ValueError('Período ou seleção final dos três livros divergiu; não emitir.')


def _preencher(inicial, final, interacao, referencia=None):
    campos = None
    leitura = None  # (datas, impressão digital) da última leitura sem ação depois dela
    for papel, valor in (('inicial', inicial), ('final', final)):
        if campos is None:
            campos = _esperar_periodo()
            leitura = (campos, _assinatura_segura())
        if campos[papel]['valor'] == valor:
            continue  # Não arriscar reescrever um campo que já confirmou.
        interacao.clicar(*campos[papel]['posicao'])
        interacao.selecionar_tudo_alternativo()
        interacao.digitar(valor.replace('/', ''))
        interacao.pressionar_tecla('tab')
        campos = _esperar_periodo(papel, valor)
        leitura = (campos, _assinatura_segura())
    return _conferir_antes_ok(inicial, final, referencia=referencia, leitura_previa=leitura)


def _conferir_conjunto(pasta, inicial, final, cnpj, nome, artefatos=None):
    """Classifica pelo conteúdo, nunca pelo nome, ordem ou primeiro preview."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
    candidatos = {}
    for caminho in sorted(pasta.glob('*.pdf')):
        ponto_seguro()
        try:
            if caminho.is_symlink() or not caminho.is_file():
                continue
            with caminho.open('rb') as entrada:
                assinatura = (caminho.stat().st_size, caminho.stat().st_mtime_ns)
                if entrada.read(5) != b'%PDF-':
                    continue
                entrada.seek(0)
                leitor = PdfReader(entrada, strict=True)
                if not leitor.pages:
                    continue
                texto = leitor.pages[0].extract_text() or ''
                for pagina in leitor.pages[1:]:
                    pagina.extract_text()
            if assinatura != (caminho.stat().st_size, caminho.stat().st_mtime_ns):
                continue
            tipos = []
            for tipo in TIPOS:
                try:
                    arquivos.validar_livro(texto, tipo, inicial, final, cnpj)
                    tipos.append(tipo)
                except ValueError:
                    pass
            if len(tipos) == 1:
                candidatos.setdefault(tipos[0], []).append(caminho)
        except (OSError, ValueError):
            continue
        except Exception:
            # PDF ilegível fica no staging local e nunca vira artefato válido.
            continue
    artefatos = [] if artefatos is None else artefatos
    for tipo in TIPOS:
        ponto_seguro()
        if len(candidatos.get(tipo, [])) != 1:
            continue
        try:
            caminho = arquivos.finalizar_pdf(candidatos[tipo][0], tipo, inicial, final,
                                             cnpj_esperado=cnpj, nome_empresa=nome)
            artefatos.append({'tipo': tipo, 'caminho': str(caminho)})
        except (OSError, ValueError, PyPdfError):
            continue  # Os outros livros já confirmados continuam disponíveis.
    return artefatos


def _aguardar_arquivos(pasta, capturar, dominio, prefixo, leitores_antes=None):
    anterior = None
    estaveis = 0
    fechados = set()
    for _ in range(60):
        if leitores_antes is not None:
            # O Domínio abre cada PDF no Acrobat, que toma o foco e faria a trava de foco
            # encerrar a rodada: fecha antes de qualquer checagem de foco.
            try:
                dominio._fechar_leitores_pdf_uma_vez(leitores_antes, fechados)
            except ExecucaoInterrompida:
                raise
            except Exception:
                pass
        ponto_seguro()
        imagem = capturar()
        for titulo in dominio.TITULOS_ERRO:
            pos = tela.achar_texto_ou_no_centro(imagem, titulo, escala=2)
            if pos is not None:
                texto = dominio._ler_texto_caixa(imagem, pos)
                acao = dominio.erros.decidir(texto, documento='Livros Fiscais')
                dominio.salvar(imagem, prefixo+'erro_exportacao_livros_conjuntos.png')
                dominio._fechar_caixa_erro(texto, prefixo)
                if acao == dominio.erros.PARAR_LOTE:
                    raise dominio.LoteInterrompido('Exportação de livros interrompida.')
                return False
        try:
            atuais = tuple((p.name,p.stat().st_size,p.stat().st_mtime_ns)
                           for p in sorted(pasta.glob('*.pdf')) if p.is_file() and not p.is_symlink())
        except OSError:
            atuais = ()
        estaveis = estaveis+1 if atuais and atuais == anterior else 0
        if len(atuais) == 3 and all(p[1] for p in atuais) and estaveis >= 2:
            return True
        if len(atuais) > 3:
            return False
        anterior = atuais
        time.sleep(1)
    return False


def gerar_livros_fiscais(pasta_destino, data_inicial=None, data_final=None, prefixo='', cnpj_esperado=None):
    from app import dominio, interacao
    acompanhamento = estados.AcompanhamentoRotina('livros_fiscais')
    artefatos = []
    try:
        sucesso = _executar(dominio, interacao, acompanhamento, artefatos,
                            pasta_destino, data_inicial, data_final, prefixo, cnpj_esperado)
        if not sucesso:
            print('Livros Fiscais: etapa não confirmada — '+str(acompanhamento.etapa)+'.', flush=True)
            _captura_falha(dominio, prefixo)
            dominio._limpar_ao_encerrar(acompanhamento)
        acompanhamento.concluir(sucesso)
        return sucesso, artefatos
    except dominio.LoteInterrompido:
        dominio._limpar_ao_encerrar(acompanhamento)
        acompanhamento.concluir(False, evidencia='excecao')
        raise
    except ExecucaoInterrompida:
        acompanhamento.concluir(False, evidencia='excecao')
        # O worker verifica o cancelamento após registrar PDFs já conferidos.
        # Nenhuma tecla/clique de limpeza é enviada depois da interrupção.
        return False, artefatos
    except Exception as erro:
        # Só mensagem fixa/tipo da exceção; caminhos e OCR ficam locais.
        print('Livros Fiscais interrompidos ('+type(erro).__name__+'). Confira a etapa e a captura local.', flush=True)
        if isinstance(erro, SeletorPastaNaoConfirmado):
            print('Destino dos livros não confirmado: '+str(erro), flush=True)
        _captura_falha(dominio, prefixo)
        dominio._limpar_ao_encerrar(acompanhamento)
        acompanhamento.concluir(False, evidencia='excecao')
        return False, artefatos
    except BaseException:
        acompanhamento.concluir(False, evidencia='excecao')
        raise


def _executar(dominio, interacao, acompanhamento, artefatos, pasta_destino,
              inicial, final, prefixo, cnpj_esperado):
    acompanhamento.iniciar('validar_dados')
    if inicial is None and final is None:
        inicial, final = dominio.competencia_anterior()
    datas = [dt.datetime.strptime(v, '%d/%m/%Y').date() for v in (inicial, final)]
    proximo_mes = (datas[0].replace(day=28)+dt.timedelta(days=4)).replace(day=1)
    if (datas[0].day != 1 or datas[1] != proximo_mes-dt.timedelta(days=1)
            or datas[1] >= dt.date.today().replace(day=1)):
        return False
    pasta = Path(pasta_destino).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    staging = pasta / ('LIVROS'+str(uuid.uuid4().int % 10**12).zfill(12))
    staging.mkdir()  # Não reutiliza nem apaga pasta de uma execução anterior.
    acompanhamento.confirmar('datas_validas')
    acompanhamento.iniciar('identificar_empresa')
    imagem = tela.capturar_tela()
    empresa = tela.ler_empresa_selecionada(imagem)
    acompanhamento.janela_dominio = interacao.identificar_janela_dominio_atual()
    if empresa is None or acompanhamento.janela_dominio is None:
        return False
    acompanhamento.confirmar('cabecalho_nome_codigo_lidos')
    acompanhamento.iniciar('abrir_livros')
    pos = tela.achar_texto(tela.recortar_topo(imagem), 'Relatórios')
    if pos is None:
        return False
    interacao.clicar(*pos)
    pos = dominio._esperar_item_menu('relatorios','Livros',prefixo+'erro_menu_livros.png')
    if pos is None:return False
    interacao.passar_mouse(*pos)
    pos = dominio._esperar_item_menu('relatorios/livros','Livros Fiscais',prefixo+'erro_menu_livros_fiscais.png')
    if pos is None:return False
    antes_do_formulario=tela.capturar_tela()
    interacao.clicar_com_desvio(*pos)
    if _aguardar_formulario(dominio,prefixo,referencia=antes_do_formulario) is None:
        return False
    referencia=formulario_livros.marcar_tres_livros(_ler_selecao,interacao.clicar,tentativas=8,intervalo=.5,
                                                       ler_rapido=_selecao_por_pixels)
    acompanhamento.confirmar('titulo_livros_fiscais_lido')
    acompanhamento.iniciar('preencher_periodo')
    imagem = _preencher(inicial,final,interacao,referencia=referencia)
    acompanhamento.confirmar('campos_periodo_confirmados')
    acompanhamento.iniciar('gerar_previa')
    pos=_achar_ok(imagem)
    if pos is None:return False
    ponto_seguro()
    if (acompanhamento.janela_dominio is None
            or not interacao.janela_dominio_em_foco(acompanhamento.janela_dominio)):
        print('LIVROS_OK {"fase":"clique","motivo":"foco_nao_confirmado","confirmado":false}',flush=True)
        return False
    antes_do_ok=imagem  # formulário de antes do OK
    print('LIVROS_OK '+json.dumps({'fase':'clique','motivo':'enviando_ok_confirmado',
                                 'posicao':list(pos)}),flush=True)
    interacao.clicar(*pos)
    def previa(imagem):
        if tela.achar_texto(imagem,'CNPJ',escala=2) is None:return None
        for alvo in ('REGISTRO DE ENTRADAS','REGISTRO DE SAÍDAS','APURAÇÃO DO ICMS','REGISTRO DE ICMS'):
            pos=tela.achar_texto(imagem,alvo,escala=2)
            if pos is not None:return pos
        # O título da prévia vem espaçado ("R E G I S T R O ...") e o OCR nem sempre o
        # lê como frase; com o rótulo CNPJ já achado, a palavra REGISTRO sozinha basta
        # (mesma âncora do fluxo individual); o PDF exportado ainda é conferido por tipo.
        return tela.achar_texto(imagem,'REGISTRO',escala=2)
    print('LIVROS_OK {"fase":"previa","motivo":"aguardando_estado"}',flush=True)
    imagem=_aguardar(dominio,'previa',previa,prefixo,referencia=antes_do_ok)
    print('LIVROS_OK '+json.dumps({'fase':'previa','motivo':'espera_concluida',
                                 'confirmado':imagem is not None}),flush=True)
    if imagem is None:return False
    # A prévia cobre o cabeçalho do Domínio: sem o código legível, a identidade
    # vem do nome conferido antes + CNPJ/período da prévia. Código legível e
    # diferente continua bloqueando.
    atual=tela.ler_empresa_selecionada(imagem)
    if atual is not None and str(int(atual[1]))!=str(int(empresa[1])):return False
    cnpj=None
    textos=[]
    for escala in (2,4):
        texto=tela.ler_texto(imagem,escala=escala)
        textos.append(texto)
        for tipo in TIPOS:
            try:
                cnpj=arquivos.validar_livro(texto,tipo,inicial,final,cnpj_esperado)
                break
            except ValueError:pass
        if cnpj is not None:break
    if cnpj is None:
        # Alternativa só se a conferência rígida não confirmou a prévia.
        for texto in textos:
            try:
                cnpj=arquivos.validar_previa_livro(texto,inicial,final,cnpj_esperado,nome_empresa=empresa[0])
                break
            except ValueError:pass
    if cnpj is None:return False
    acompanhamento.confirmar('ancora_registro_lida')
    acompanhamento.iniciar('exportar_pdf')
    pos=tela.achar_icone_robusto(imagem,Path(__file__).parent/'icones/salvar_pdf.png')
    if pos is None:return False
    antes_do_menu=imagem  # prévia de antes do clique no ícone PDF
    interacao.clicar(*pos)
    imagem=_aguardar(dominio,'menu_pdf',_achar_opcao_pdf,prefixo,tentativas=15,referencia=antes_do_menu)
    if imagem is None:return False
    pos=_achar_opcao_pdf(imagem)
    if pos is None:return False
    antes_da_pasta=imagem  # menu PDF aberto, antes de escolher a opção
    interacao.clicar_com_desvio(*pos)
    imagem=_aguardar(dominio,'pasta',lambda img:tela.achar_texto_ou_no_centro(img,'Procurar Pasta',escala=4),prefixo,tentativas=15,referencia=antes_da_pasta)
    if imagem is None:return False
    from app.seletor_pasta import selecionar_pasta
    leitores_antes=dominio._linha_base_leitores_pdf()
    selecionar_pasta(dominio.caminho_visto_pela_sessao_remota(staging),tela.capturar_tela,
                     interacao.clicar,interacao.pressionar_tecla,clicar_duplo=interacao.clicar_duplo)
    completa=_aguardar_arquivos(staging,tela.capturar_tela,dominio,prefixo,leitores_antes)
    if completa:
        acompanhamento.confirmar('arquivo_novo_estavel')
        acompanhamento.iniciar('conferir_pdf')
    _conferir_conjunto(staging,inicial,final,cnpj,empresa[0],artefatos=artefatos)
    dominio._fechar_leitores_pdf(leitores_antes, acompanhamento.janela_dominio)  # garante que nenhum Acrobat ficou na frente
    if not completa or {a['tipo'] for a in artefatos}!=set(TIPOS):return False
    acompanhamento.confirmar('pdf_tipo_periodo_cnpj_confirmados')
    acompanhamento.iniciar('encerrar')
    if not dominio.voltar_ao_inicio(acompanhamento.janela_dominio):
        acompanhamento.registrar_encerramento_inconclusivo()
        return False
    acompanhamento.confirmar('tela_principal_reconhecida')
    return True
