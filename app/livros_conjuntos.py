"""Entradas, Saídas e ICMS em uma emissão; ainda requer teste no Windows.

Usa o menu observado e exporta um PDF por relatório numa pasta exclusiva.
O worker publica somente os PDFs conferidos no destino da empresa.
"""
import datetime as dt
from pathlib import Path
import time
import uuid

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


def _captura_falha(dominio, prefixo):
    try:
        dominio.salvar(tela.capturar_tela(), prefixo+'erro_livros_conjuntos.png')
    except Exception:
        print('Captura local dos livros indisponível; consulte as etapas.', flush=True)


def _ler_formulario(imagem=None):
    from app.leitura_resumo import ler_campos
    imagem = imagem if imagem is not None else tela.capturar_tela()
    periodo = ler_campos(imagem, livros=True)
    return formulario_livros.ler_com_ocr(imagem, periodo_confirmado=periodo)


def _aguardar_formulario(dominio, prefixo):
    def detectar(imagem):
        try:
            _ler_formulario(imagem)
            return (0, 0)
        except ValueError:
            return None
    return _aguardar(dominio, 'formulario', detectar, prefixo, tentativas=20)


def _aguardar(dominio, nome, detector, prefixo, tentativas=90):
    detectores = [(titulo, lambda img, t=titulo:
                   tela.achar_texto_ou_no_centro(img, t, escala=2)) for titulo in dominio.TITULOS_ERRO]
    imagem, estado, pos = estados.esperar_por_estado(
        detectores + [(nome, detector)], espera_minima=.3,
        tentativas=tentativas, intervalo=1)
    if estado in dominio.TITULOS_ERRO:
        texto = dominio._ler_texto_caixa(imagem, pos)
        acao = dominio.erros.decidir(texto, documento='Livros Fiscais')
        dominio.salvar(imagem, prefixo+'erro_aviso_livros_conjuntos.png')
        dominio._fechar_caixa_erro(texto, prefixo)
        if acao == dominio.erros.PARAR_LOTE:
            raise dominio.LoteInterrompido('Aviso interrompeu Livros Fiscais.')
        return None
    return imagem if estado == nome else None


def _preencher(inicial, final, interacao):
    for papel, valor in (('inicial', inicial), ('final', final)):
        campos = _ler_formulario()['periodo']
        interacao.clicar(*campos[papel]['posicao'])
        interacao.selecionar_tudo_alternativo()
        interacao.digitar(valor.replace('/', ''))
        interacao.pressionar_tecla('tab')
        confirmado = False
        for _ in range(5):
            ponto_seguro()
            try:
                campos = _ler_formulario()['periodo']
                confirmado = campos[papel]['valor'] == valor
                if confirmado:
                    break
            except ValueError:
                pass
            time.sleep(.3)
        if not confirmado:
            raise ValueError('Data '+papel+' dos livros não confirmou o período solicitado.')
    final_lido = _ler_formulario()
    if (final_lido['periodo']['inicial']['valor'] != inicial or final_lido['periodo']['final']['valor'] != final
            or not all(l['marcada'] for l in final_lido['livros'].values())
            or any(c['marcada'] for c in final_lido['outros'])):
        raise ValueError('Período ou seleção final dos três livros divergiu; não emitir.')


def _conferir_conjunto(pasta, inicial, final, cnpj, nome):
    """Classifica pelo conteúdo, nunca pelo nome, ordem ou primeiro preview."""
    from pypdf import PdfReader
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
    artefatos = []
    for tipo in TIPOS:
        if len(candidatos.get(tipo, [])) != 1:
            continue
        try:
            caminho = arquivos.finalizar_pdf(candidatos[tipo][0], tipo, inicial, final,
                                             cnpj_esperado=cnpj, nome_empresa=nome)
            artefatos.append({'tipo': tipo, 'caminho': str(caminho)})
        except (OSError, ValueError):
            continue  # Os outros livros já confirmados continuam disponíveis.
    return artefatos


def _aguardar_arquivos(pasta, capturar, dominio, prefixo):
    anterior = None
    estaveis = 0
    for _ in range(60):
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
    interacao.clicar_com_desvio(*pos)
    if _aguardar_formulario(dominio,prefixo) is None:
        return False
    formulario_livros.marcar_tres_livros(_ler_formulario,interacao.clicar)
    acompanhamento.confirmar('titulo_livros_fiscais_lido')
    acompanhamento.iniciar('preencher_periodo')
    _preencher(inicial,final,interacao)
    acompanhamento.confirmar('campos_periodo_confirmados')
    acompanhamento.iniciar('gerar_previa')
    imagem=tela.capturar_tela()
    pos=tela.achar_texto_ou_no_centro(imagem,'OK',escala=4)
    if pos is None:return False
    interacao.clicar(*pos)
    def previa(imagem):
        if tela.achar_texto(imagem,'CNPJ',escala=2) is None:return None
        for alvo in ('REGISTRO DE ENTRADAS','REGISTRO DE SAÍDAS','APURAÇÃO DO ICMS','REGISTRO DE ICMS'):
            pos=tela.achar_texto(imagem,alvo,escala=2)
            if pos is not None:return pos
        return None
    imagem=_aguardar(dominio,'previa',previa,prefixo)
    if imagem is None:return False
    atual=tela.ler_empresa_selecionada(imagem)
    if atual is None or str(int(atual[1]))!=str(int(empresa[1])):return False
    cnpj=None
    for escala in (2,4):
        texto=tela.ler_texto(imagem,escala=escala)
        for tipo in TIPOS:
            try:
                cnpj=arquivos.validar_livro(texto,tipo,inicial,final,cnpj_esperado)
                break
            except ValueError:pass
        if cnpj is not None:break
    if cnpj is None:return False
    acompanhamento.confirmar('ancora_registro_lida')
    acompanhamento.iniciar('exportar_pdf')
    pos=tela.achar_icone_robusto(imagem,Path(__file__).parent/'icones/salvar_pdf.png')
    if pos is None:return False
    interacao.clicar(*pos)
    imagem=_aguardar(dominio,'menu_pdf',_achar_opcao_pdf,prefixo,tentativas=15)
    if imagem is None:return False
    pos=_achar_opcao_pdf(imagem)
    if pos is None:return False
    interacao.clicar_com_desvio(*pos)
    imagem=_aguardar(dominio,'pasta',lambda img:tela.achar_texto_ou_no_centro(img,'Procurar Pasta',escala=4),prefixo,tentativas=15)
    if imagem is None:return False
    from app.seletor_pasta import selecionar_pasta
    selecionar_pasta(dominio.caminho_visto_pela_sessao_remota(staging),tela.capturar_tela,
                     interacao.clicar,interacao.pressionar_tecla)
    completa=_aguardar_arquivos(staging,tela.capturar_tela,dominio,prefixo)
    if completa:
        acompanhamento.confirmar('arquivo_novo_estavel')
        acompanhamento.iniciar('conferir_pdf')
    artefatos.extend(_conferir_conjunto(staging,inicial,final,cnpj,empresa[0]))
    if not completa or {a['tipo'] for a in artefatos}!=set(TIPOS):return False
    acompanhamento.confirmar('pdf_tipo_periodo_cnpj_confirmados')
    acompanhamento.iniciar('encerrar')
    if not dominio.voltar_ao_inicio(acompanhamento.janela_dominio):
        acompanhamento.registrar_encerramento_inconclusivo()
        return False
    acompanhamento.confirmar('tela_principal_reconhecida')
    return True
