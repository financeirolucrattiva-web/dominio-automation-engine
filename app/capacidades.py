"""Descrições das quatro rotinas conhecidas, sem executar a interface.

Este catálogo prepara a etapa 3 do roadmap. Pré-condições e permissões
são metadados para revisão, não verificações de execução. Listar uma
rotina não a habilita para agentes nem comprova validação da versão atual.
O módulo não lê empresas, arquivos fiscais, capturas ou configuração de IA.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Parametro:
    nome: str
    tipo: str
    obrigatorio: bool
    descricao: str


@dataclass(frozen=True)
class Validacao:
    mecanismo_historico: str
    conteudo_historico: str
    versao_atual: str
    referencias: tuple[str, ...]


@dataclass(frozen=True)
class Capacidade:
    id: str
    nome: str
    objetivo: str
    funcao: str
    parametros: tuple[Parametro, ...]
    contexto: tuple[str, ...]
    precondicoes: tuple[str, ...]
    politica_periodo: str
    operacoes_permitidas: tuple[str, ...]
    etapas: tuple[str, ...]
    resultado: str
    checagens_atuais: tuple[str, ...]
    recuperacao: tuple[str, ...]
    validacao: Validacao
    pendencias: tuple[str, ...]
    status: str = "preparatoria"
    agentes_habilitados: bool = False

    def como_dict(self):
        """Devolve uma cópia serializável, sem carregar o gerador."""
        return asdict(self)


_PREFIXO = Parametro(
    "prefixo", "str", False,
    "Prefixo local de evidências; não define empresa ou competência.",
)
_PARAMETROS_SPED = (
    _PREFIXO,
    Parametro("data_inicial", "str | None", False, "DD/MM/AAAA; competência escolhida pelo usuário; chamadas locais antigas usam mês anterior."),
    Parametro("data_final", "str | None", False, "Último dia da mesma competência passada, informada junto com a data inicial."),
)
_PARAMETROS_LIVROS = (
    Parametro("pasta_destino", "str | Path", True, "Pasta local de saída dos PDFs."),
    Parametro("data_inicial", "str | None", False, "DD/MM/AAAA; sem datas, usa o mês anterior."),
    Parametro("data_final", "str | None", False, "DD/MM/AAAA; informar junto com a data inicial."),
    _PREFIXO,
    Parametro("cnpj_esperado", "str | None", False, "Conferência opcional da identidade no PDF local."),
)
_CONTEXTO = (
    "A empresa já selecionada é contexto da sessão, não argumento do gerador.",
    "O regime filtra a planilha; tipo/sped escolhem documentos no lote existente.",
    "O catálogo não deduz obrigações tributárias a partir do regime.",
)
_PRECONDICOES = (
    "Domínio Escrita Fiscal visível numa sessão Windows disponível.",
    "Empresa correta confirmada pelo operador antes de iniciar.",
    "Competência passada, fechada e apurada; mês anterior não comprova apuração.",
    "Apenas um operador de mouse e teclado durante a execução.",
)
_ETAPAS_SPED = (
    "Abrir a tela de geração conhecida.",
    "Preencher e conferir o período nos dois campos.",
    "Gerar e aguardar o resultado ou aviso.",
    "Dispensar a confirmação e tentar fechar a tela de geração.",
)
_ETAPAS_LIVROS = (
    "Validar as datas e identificar a empresa no cabeçalho.",
    "Abrir Livros Fiscais e selecionar o livro solicitado.",
    "Preencher e conferir o período nos dois campos.",
    "Reconhecer a prévia e exportar para um PDF temporário exclusivo.",
    "Conferir tipo, período e identidade antes de publicar o nome final.",
    "Retomar foco do Domínio e tentar encerrar a prévia.",
)
_RECUPERACAO_SPED = (
    "Avisos conhecidos seguem as decisões existentes de geração/leitura.",
    "Falha tenta fechar a tela de geração; retorno visual positivo ainda precisa de validação.",
    "Uma decisão PARAR_LOTE permanece uma interrupção do lote, não sucesso.",
)
_RECUPERACAO_LIVROS = (
    "Após prévia reconhecida, exige foco do Domínio antes de enviar Esc.",
    "Recuperação preserva a falha original da conferência do PDF.",
    "Retorno automático à tela principal precisa de validação no Windows.",
)
_CHECAGENS_LIVROS = (
    "Nome e código lidos no cabeçalho não comprovam uma empresa esperada.",
    "Os campos do período precisam corresponder às datas solicitadas.",
    "Arquivo temporário exclusivo precisa aparecer e estabilizar.",
    "PDF precisa abrir e confirmar título, período e CNPJ antes do nome final.",
)
_PENDENCIAS_SPED = (
    "Conferir o conteúdo contra arquivo já entregue de competência fechada.",
    "Validar acompanhamento por etapas e retorno à tela principal na versão atual.",
    "Validar lote acompanhado sem contaminar a empresa seguinte após falha.",
)


_CAPACIDADES = (
    Capacidade(
        id="sped_fiscal", nome="SPED Fiscal",
        objetivo="Gerar EFD ICMS/IPI pela rotina de exportação conhecida.",
        funcao="app.dominio.gerar_sped_fiscal", parametros=_PARAMETROS_SPED,
        contexto=_CONTEXTO, precondicoes=_PRECONDICOES + (
            "Destino de exportação configurado e conferido dentro do Domínio.",
            "Competência já entregue disponível para comparação de conteúdo.",
        ),
        politica_periodo="Competência passada escolhida pelo usuário; sem argumentos, chamadas locais preservam o mês anterior.",
        operacoes_permitidas=("gerar", "ler"), etapas=_ETAPAS_SPED,
        resultado="bool; não devolve caminho nem comprovação independente do arquivo.",
        checagens_atuais=(
            "Período conferido nos campos antes de gerar.",
            "Confirmação/avisos reconhecidos na interface.",
            "Booleano não comprova conteúdo nem retorno visual positivo à tela principal.",
        ),
        recuperacao=_RECUPERACAO_SPED,
        validacao=Validacao(
            "Geração observada no Windows em versões anteriores.",
            "Comparação com obrigação já entregue ainda pendente.",
            "Revalidação da execução confiável permanece pendente.",
            ("0.11", "0.27", "0.40", "0.59", "5.7"),
        ),
        pendencias=_PENDENCIAS_SPED,
    ),
    Capacidade(
        id="efd_contribuicoes", nome="EFD Contribuições",
        objetivo="Gerar EFD PIS/COFINS pela rotina de exportação conhecida.",
        funcao="app.dominio.gerar_efd_contribuicoes", parametros=_PARAMETROS_SPED,
        contexto=_CONTEXTO, precondicoes=_PRECONDICOES + (
            "Destino de exportação configurado e conferido dentro do Domínio.",
            "Competência já entregue disponível para comparação de conteúdo.",
        ),
        politica_periodo="Competência passada escolhida pelo usuário; sem argumentos, chamadas locais preservam o mês anterior.",
        operacoes_permitidas=("gerar", "ler"), etapas=_ETAPAS_SPED,
        resultado="bool; não devolve caminho nem comprovação independente do arquivo.",
        checagens_atuais=(
            "Período conferido nos campos antes de gerar.",
            "Confirmação/avisos reconhecidos na interface.",
            "Booleano não comprova conteúdo nem retorno visual positivo à tela principal.",
        ),
        recuperacao=_RECUPERACAO_SPED,
        validacao=Validacao(
            "Geração observada no Windows em versões anteriores.",
            "Comparação com obrigação já entregue ainda pendente.",
            "Revalidação da execução confiável permanece pendente.",
            ("0.22", "0.40", "0.59", "5.7"),
        ),
        pendencias=_PENDENCIAS_SPED,
    ),
    Capacidade(
        id="registro_saidas", nome="Registro de Saídas",
        objetivo="Exportar o Livro Registro de Saídas em PDF local.",
        funcao="app.dominio.gerar_registro_saidas", parametros=_PARAMETROS_LIVROS,
        contexto=_CONTEXTO, precondicoes=_PRECONDICOES + (
            "Pasta local de destino disponível e unidade compartilhada com a sessão remota.",
        ),
        politica_periodo="Datas informadas nos campos; sem datas, mês anterior. Competência pelo período solicitado.",
        operacoes_permitidas=("gerar", "ler"), etapas=_ETAPAS_LIVROS,
        resultado="(bool, caminho | None); PDF conferido com encerramento pendente pode preservar o caminho e retornar False.",
        checagens_atuais=_CHECAGENS_LIVROS, recuperacao=_RECUPERACAO_LIVROS,
        validacao=Validacao(
            "Exportação observada no Windows; recuperação de foco/Esc confirmada pelo operador.",
            "Verificação anterior do livro registrada em 0.59.",
            "Conferência atual recusou o período do PDF; execução final não confirmada.",
            ("0.59", "0.63", "0.65", "0.67", "0.69"),
        ),
        pendencias=(
            "Diagnóstico da conferência de período e nome final pausado pelo usuário.",
            "Validar reconhecimento automático da tela principal no Windows.",
            "Confirmar execução completa com as verificações atuais do PDF.",
        ),
    ),
    Capacidade(
        id="registro_entradas", nome="Registro de Entradas",
        objetivo="Exportar o Livro Registro de Entradas em PDF local.",
        funcao="app.dominio.gerar_registro_entradas", parametros=_PARAMETROS_LIVROS,
        contexto=_CONTEXTO, precondicoes=_PRECONDICOES + (
            "Pasta local de destino disponível e unidade compartilhada com a sessão remota.",
        ),
        politica_periodo="Datas informadas nos campos; sem datas, mês anterior. Competência pelo período solicitado.",
        operacoes_permitidas=("gerar", "ler"), etapas=_ETAPAS_LIVROS,
        resultado="(bool, caminho | None); PDF conferido com encerramento pendente pode preservar o caminho e retornar False.",
        checagens_atuais=_CHECAGENS_LIVROS, recuperacao=_RECUPERACAO_LIVROS,
        validacao=Validacao(
            "Exportação observada no Windows na versão registrada em 0.60.",
            "Verificação anterior do livro registrada em 0.60.",
            "Nova conferência de PDF e recuperação compartilhadas ainda precisam de revalidação desta rotina.",
            ("0.60", "0.63", "0.65", "0.67", "0.69"),
        ),
        pendencias=(
            "Revalidar Entradas com a conferência atual do PDF, após resolver a pendência compartilhada.",
            "Validar reconhecimento automático da tela principal no Windows.",
            "Confirmar execução completa sem depender do sucesso da versão anterior.",
        ),
    ),
)


def listar_capacidades():
    """Lista somente descrições congeladas; não executa nenhuma rotina."""
    return _CAPACIDADES


def obter_capacidade(identificador):
    """Busca um ID exato no catálogo fixo; não resolve nomes de funções."""
    for capacidade in _CAPACIDADES:
        if capacidade.id == identificador:
            return capacidade
    raise ValueError(f"Capacidade desconhecida: {identificador!r}")
