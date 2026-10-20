"""Validação e nomes dos livros exportados, somente em disco local."""

import datetime
from pathlib import Path
import re
import shutil
import unicodedata


def _compactar(texto):
    texto = unicodedata.normalize("NFKD", texto.upper())
    return "".join(c for c in texto if not c.isspace() and not unicodedata.combining(c))


def empresa_do_cabecalho(texto):
    """Lê a linha NOME - CÓDIGO do cabeçalho conhecido, sem inventar nome."""
    candidatos = set()
    for linha in texto.splitlines():
        linha = " ".join(linha.split())
        correspondencia = re.fullmatch(r"(.+?)\s*[-–—]\s*(\d+)\s*", linha)
        if correspondencia is None:
            continue
        nome, codigo = correspondencia.groups()
        if not any(c.isalpha() for c in nome):
            continue
        if _compactar(nome) in ("GERENTE", "DOMINIO", "ESCRITAFISCAL"):
            continue
        if re.fullmatch(r"(?:JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[/ -]\d{4}", nome.upper()):
            continue
        candidatos.add((nome, codigo))
    return candidatos.pop() if len(candidatos) == 1 else None


def nome_empresa_seguro(nome):
    """Nome visível como componente portátil de arquivo, sem código/CNPJ."""
    texto = unicodedata.normalize("NFKD", nome.upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9]+", "_", texto).strip("_")[:100].rstrip("_")
    if not texto or not any(c.isalpha() for c in texto):
        raise ValueError("Nome da empresa ilegível para nomear o PDF.")
    return texto


def nome_relatorio(tipo, nome_empresa, inicio, fim, extensao=".pdf", codigo=None):
    """Convenção do painel: tipo, nome cadastrado e competência informada.

    Com `codigo` (código da empresa no Domínio) o nome fica
    `codigo_empresa_documento_competencia`, tudo separado por "_".
    """
    prefixos = {"Resumo por Acumulador": "acumulador",
                "resumo_acumulador": "acumulador",
                "Livro Fiscal de ICMS": "livro_icms",
                "registro_icms": "livro_icms",
                "Demonstrativo EFD Contribuições": "efd_contribuicoes"}
    prefixo = nome_empresa_seguro(prefixos.get(tipo, tipo)).lower()
    empresa = nome_empresa_seguro(nome_empresa).lower()
    inicial, final = (datetime.date.fromisoformat(data) for data in (inicio, fim))
    if final < inicial or not re.fullmatch(r"\.[a-zA-Z0-9]{1,10}", extensao):
        raise ValueError("Período ou extensão inválida para nomear o relatório.")
    competencia = f"{inicial:%Y-%m}"
    if (inicial.year, inicial.month) != (final.year, final.month):
        competencia += f"_a_{final:%Y-%m}"
    if codigo is not None:
        if not re.fullmatch(r"[0-9]{1,12}", str(codigo)):
            raise ValueError("Código da empresa inválido para nomear o relatório.")
        return f"{int(codigo)}_{empresa}_{prefixo}_{competencia}{extensao.lower()}"
    return f"{prefixo}_{empresa}_{competencia}{extensao.lower()}"


def nomear_relatorio_cadastrado(caminho, pasta_saida, tipo, nome_empresa, inicio, fim, pasta_destino=None, codigo=None):
    """Publica a saída já confirmada na pasta final, sem substituir anteriores."""
    caminho = Path(caminho).resolve(strict=True)
    if not caminho.is_relative_to(Path(pasta_saida).resolve()) or not caminho.is_file():
        raise ValueError("Arquivo fora da pasta de saída.")
    nome = nome_relatorio(tipo, nome_empresa, inicio, fim, caminho.suffix, codigo=codigo)
    pasta_final = Path(pasta_destino).resolve() if pasta_destino is not None else caminho.parent
    pasta_final.mkdir(parents=True, exist_ok=True)
    destino = pasta_final / nome
    if destino == caminho:
        # No Windows, Path compara sem distinguir maiúsculas/minúsculas.
        if destino.name != caminho.name:
            caminho.rename(destino)
        return destino
    numero = 1
    while True:
        criado = False
        try:
            with destino.open("xb") as saida:
                criado = True
                with caminho.open("rb") as entrada:
                    shutil.copyfileobj(entrada, saida)
            break
        except FileExistsError:
            numero += 1
            destino = pasta_final / f"{Path(nome).stem}_{numero}{Path(nome).suffix}"
        except Exception:
            if criado:
                destino.unlink(missing_ok=True)
            raise
    try:
        caminho.unlink()
    except OSError:
        pass  # A cópia publicada está completa; o exportador pode prender a origem.
    return destino


def validar_livro(texto, tipo, inicio, fim, cnpj_esperado=None):
    """Confirma tipo/período e devolve CNPJ inequívoco do cabeçalho.

    Aceita letras e datas espaçadas pelo posicionamento do texto no PDF.
    Não consulta serviços externos nem infere identidade por OCR.
    """
    titulos = {"registro_saidas": "REGISTRODESAIDAS", "registro_entradas": "REGISTRODEENTRADAS"}
    if tipo not in (*titulos, "registro_icms"):
        raise ValueError("Tipo de livro não reconhecido.")
    compacto = _compactar(texto)
    if tipo == "registro_icms":
        # O título exato ainda precisa de homologação no Windows. Não basta
        # ICMS nas colunas de Entradas/Saídas ou no nome escolhido pelo Domínio.
        # Exige título de registro/apuração com ICMS antes da identificação.
        limites_titulo = [compacto.find(m) for m in ("EMPRESA", "CNPJ", "INSCRICAO") if m in compacto]
        titulo = compacto[:min(limites_titulo)] if limites_titulo else compacto[:200]
        if ("ICMS" not in titulo or not any(m in titulo for m in ("REGISTRO", "APURACAO"))
                or any(m in compacto for m in ("REGISTRODEENTRADAS", "REGISTRODESAIDAS", "RESUMOPORACUMULADOR"))):
            raise ValueError("O cabeçalho não confirma um livro de registro/apuração de ICMS.")
        cabecalho = compacto
    else:
        titulo = titulos[tipo]
        if titulo not in compacto:
            raise ValueError("O PDF não contém o título do livro solicitado.")
        cabecalho = compacto[compacto.index(titulo):]
    # O período precisa estar no cabeçalho, antes das linhas de movimentos.
    limites = [cabecalho.find(m) for m in ("CODIFICACAO", "VALORESFISCAIS", "DEBITODOIMPOSTO", "CREDITODOIMPOSTO") if m in cabecalho]
    if limites:
        cabecalho = cabecalho[:min(limites)]
    else:
        cabecalho = cabecalho[:2500]
    periodo = re.search(re.escape(_compactar(inicio)) + r"(?:A|ATE|[-–])" + re.escape(_compactar(fim)), cabecalho)
    if periodo is None:
        raise ValueError("O cabeçalho do PDF não confirma o período solicitado.")
    # O CNPJ pode vir ANTES ou DEPOIS do período no cabeçalho (o livro de ICMS traz o período na
    # linha do título e a empresa/CNPJ abaixo); a busca vai até o início das tabelas, não até o período.
    # Prioriza o rótulo CNPJ; sem ele, exige um único CNPJ formatado.
    rotulados = re.findall(r"CNPJ[:.]?(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", cabecalho)
    encontrados = rotulados or re.findall(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", cabecalho)
    cnpjs = {re.sub(r"\D", "", cnpj) for cnpj in encontrados}
    if len(cnpjs) != 1:
        raise ValueError("Não foi possível identificar um único CNPJ no cabeçalho do PDF.")
    cnpj = cnpjs.pop()
    if cnpj_esperado is not None:
        esperado = re.sub(r"\D", "", str(cnpj_esperado))
        if len(esperado) != 14 or esperado != cnpj:
            raise ValueError("O CNPJ do PDF não corresponde à empresa esperada.")
    return cnpj


def nome_livro(tipo, cnpj, inicio, fim, nome_empresa=None):
    inicial = datetime.datetime.strptime(inicio, "%d/%m/%Y").date()
    final = datetime.datetime.strptime(fim, "%d/%m/%Y").date()
    if final < inicial:
        raise ValueError("Período final anterior ao inicial.")
    if tipo not in ("registro_saidas", "registro_entradas", "registro_icms") or not re.fullmatch(r"\d{14}", cnpj):
        raise ValueError("Tipo ou CNPJ inválido para nomear o PDF.")
    # A competência no nome vem do mês/ano informado na UI, mesmo
    # quando o usuário pede apenas parte desse mês. As datas completas
    # continuam sendo conferidas no conteúdo antes da publicação.
    if (inicial.year, inicial.month) == (final.year, final.month):
        competencia = inicial.strftime("%Y-%m")
    else:
        competencia = f"{inicial:%Y-%m}_a_{final:%Y-%m}"
    identificacao = nome_empresa_seguro(nome_empresa) if nome_empresa is not None else cnpj
    return f"{tipo}_{identificacao}_{competencia}.pdf"


def validar_resumo_acumulador(texto, inicio, fim, cnpj_esperado=None):
    """Título/Período/CNPJ do cabeçalho observado, independente da ordem PDF."""
    compacto = _compactar(texto)
    # As seções observadas vêm depois do cabeçalho/título. Dados nas
    # tabelas não podem compensar um período ou CNPJ errado no cabeçalho.
    limites = [compacto.find(m) for m in ("ENTRADAS", "SAIDAS", "CODIGODESCRICAO") if m in compacto]
    cabecalho = compacto[:min(limites)] if limites else compacto[:2500]
    if "RESUMOPORACUMULADOR" not in cabecalho:
        raise ValueError("O relatório não confirma o título Resumo por Acumulador.")
    datas = re.findall(r"PERIODO:?([0-9]{2}/[0-9]{2}/[0-9]{4})(?:ATE|A|[-–])([0-9]{2}/[0-9]{2}/[0-9]{4})", cabecalho)
    if datas != [(inicio, fim)]:
        raise ValueError("O cabeçalho do Resumo não confirma o período solicitado.")
    # O texto extraído do PDF pode trazer os rótulos separados dos valores
    # ("CNPJ:", "Insc. Est.:" e só depois os números). Prioriza o rótulo e, sem ele,
    # exige um único CNPJ formatado no cabeçalho (mesma regra dos livros).
    rotulados = re.findall(r"CNPJ:?([0-9]{2}\.?[0-9]{3}\.?[0-9]{3}/?[0-9]{4}-?[0-9]{2})", cabecalho)
    encontrados = set(rotulados or re.findall(r"(?<![0-9])[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}", cabecalho))
    cnpjs = {re.sub(r"\D", "", valor) for valor in encontrados}
    if len(cnpjs) != 1:
        raise ValueError("CNPJ do cabeçalho do Resumo ausente ou ambíguo.")
    cnpj = cnpjs.pop()
    if cnpj_esperado is not None and re.sub(r"\D", "", str(cnpj_esperado)) != cnpj:
        raise ValueError("O CNPJ do Resumo não corresponde à empresa esperada.")
    return cnpj


def _nome_confere(nome, compacto):
    """O nome lido do cabeçalho do Domínio traz ruído ("SPRAYAGRO �", pois o
    hífen antes do código vira um caractere estranho). Compara só as palavras
    úteis (2+ letras/dígitos); todas precisam aparecer no texto compactado."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", nome.upper()) if not unicodedata.combining(c))
    palavras = [p for p in re.split(r"[^A-Z0-9]+", sem_acento) if len(p) >= 2]
    return bool(palavras) and all(p in compacto for p in palavras)


def validar_previa_resumo(texto, inicio, fim, cnpj_esperado=None, nome_empresa=None):
    """Conferência da PRÉVIA do Resumo, lida por OCR da tela inteira.

    O OCR da tela cheia costuma perder os rótulos pequenos ("Período:",
    "CNPJ:") e trocar a pontuação do CNPJ. Esta conferência não depende
    desses rótulos, mas continua exigindo título, exatamente o par de datas
    pedido e um único CNPJ. A conferência rígida do PDF exportado
    (`validar_resumo_acumulador`) continua valendo antes do nome final.
    """
    compacto = _compactar(texto)
    limites = [compacto.find(m) for m in ("ENTRADAS", "SAIDAS", "CODIGODESCRICAO") if m in compacto]
    cabecalho = compacto[:min(limites)] if limites else compacto[:2500]
    if "RESUMOPORACUMULADOR" not in cabecalho:
        raise ValueError("A prévia não confirma o título Resumo por Acumulador.")
    datas = re.findall(r"([0-9]{2}/[0-9]{2}/[0-9]{4})(?:ATE|A|[-–])([0-9]{2}/[0-9]{2}/[0-9]{4})", cabecalho)
    if datas != [(inicio, fim)]:
        raise ValueError("A prévia do Resumo não confirma o período solicitado.")
    # CNPJ: busca no texto com espaços preservados; compactado, o número da
    # página gruda nos dígitos do CNPJ.
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto.upper()) if not unicodedata.combining(c))
    espacado = " ".join(sem_acento.split())
    corte = re.search(r"ENTRADAS|SAIDAS|CODIGO DESCRICAO", espacado)
    espacado = espacado[:corte.start()] if corte else espacado[:2500]
    encontrados = re.findall(r"(?<![0-9])([0-9]{2}[.,]?[0-9]{3}[.,]?[0-9]{3}/?[0-9]{4}-?[0-9]{2})(?![0-9])", espacado)
    cnpjs = {re.sub(r"\D", "", valor) for valor in encontrados}
    if len(cnpjs) != 1:
        raise ValueError("CNPJ da prévia do Resumo ausente ou ambíguo.")
    cnpj = cnpjs.pop()
    if cnpj_esperado is not None and re.sub(r"\D", "", str(cnpj_esperado)) != cnpj:
        raise ValueError("O CNPJ da prévia não corresponde à empresa esperada.")
    if nome_empresa and not _nome_confere(nome_empresa, cabecalho):
        raise ValueError("O nome da empresa na prévia não confere com a empresa conferida antes de abrir o Resumo.")
    return cnpj


def validar_previa_livro(texto, inicio, fim, cnpj_esperado=None, nome_empresa=None):
    """Conferência alternativa da PRÉVIA dos Livros Fiscais (OCR da tela cheia).

    Só é usada quando `validar_livro` não confirma a prévia: o OCR de tela
    cheia pode ler o cabeçalho em outra ordem e perder rótulos. Mantém as
    exigências de identidade: título de um dos livros, exatamente o par de
    datas pedido, um único CNPJ e o nome da empresa conferida. O PDF
    exportado continua passando pela conferência rígida.
    """
    compacto = _compactar(texto)[:2500]
    titulos = ("REGISTRODEENTRADAS", "REGISTRODESAIDAS")
    icms = "ICMS" in compacto and any(m in compacto for m in ("REGISTRODEICMS", "APURACAODOICMS", "REGISTRODEAPURACAODOICMS"))
    if not (any(t in compacto for t in titulos) or icms):
        raise ValueError("A prévia não confirma o título de um livro fiscal.")
    datas = set(re.findall(r"([0-9]{2}/[0-9]{2}/[0-9]{4})(?:ATE|A|[-–])([0-9]{2}/[0-9]{2}/[0-9]{4})", compacto))
    if datas != {(inicio, fim)}:
        raise ValueError("A prévia do livro não confirma o período solicitado.")
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto.upper()) if not unicodedata.combining(c))
    espacado = " ".join(sem_acento.split())[:2500]
    encontrados = re.findall(r"(?<![0-9])([0-9]{2}[.,]?[0-9]{3}[.,]?[0-9]{3}/?[0-9]{4}-?[0-9]{2})(?![0-9])", espacado)
    cnpjs = {re.sub(r"\D", "", valor) for valor in encontrados}
    if len(cnpjs) != 1:
        raise ValueError("CNPJ da prévia do livro ausente ou ambíguo.")
    cnpj = cnpjs.pop()
    if cnpj_esperado is not None and re.sub(r"\D", "", str(cnpj_esperado)) != cnpj:
        raise ValueError("O CNPJ da prévia não corresponde à empresa esperada.")
    if nome_empresa and not _nome_confere(nome_empresa, compacto):
        raise ValueError("O nome da empresa na prévia não confere com a empresa conferida.")
    return cnpj


def finalizar_pdf(caminho, tipo, inicio, fim, cnpj_esperado=None, nome_empresa=None):
    """Lê um PDF novo e completo; publica sem sobrescrever arquivos prévios."""
    from pypdf import PdfReader

    caminho = Path(caminho)
    with caminho.open("rb") as arquivo:
        if arquivo.read(5) != b"%PDF-":
            raise ValueError("O arquivo exportado não é PDF.")
        arquivo.seek(0)
        leitor = PdfReader(arquivo, strict=True)
        if not leitor.pages:
            raise ValueError("PDF sem páginas.")
        texto = leitor.pages[0].extract_text() or ""
        if tipo == "resumo_acumulador":
            cnpj = validar_resumo_acumulador(texto, inicio, fim, cnpj_esperado)
        else:
            cnpj = validar_livro(texto, tipo, inicio, fim, cnpj_esperado)
        # Força leitura de todas as páginas antes de declarar o arquivo pronto.
        for pagina in leitor.pages[1:]:
            pagina.extract_text()
    if tipo == "resumo_acumulador":
        if nome_empresa is None:
            raise ValueError("Informe o nome da empresa para nomear o Resumo.")
        datas = [datetime.datetime.strptime(v, "%d/%m/%Y").date().isoformat() for v in (inicio, fim)]
        nome = nome_relatorio(tipo, nome_empresa, *datas)
    else:
        nome = nome_livro(tipo, cnpj, inicio, fim, nome_empresa=nome_empresa)
    destino = caminho.with_name(nome)
    numero = 1
    while True:
        criado = False
        try:
            # Reserva exclusiva: uma execução concorrente também não substitui.
            with destino.open("xb") as saida:
                criado = True
                with caminho.open("rb") as entrada:
                    shutil.copyfileobj(entrada, saida)
            break
        except FileExistsError:
            numero += 1
            destino = caminho.with_name(f"{Path(nome).stem}_{numero}.pdf")
        except Exception:
            if criado and destino.exists():
                destino.unlink()
            raise
    try:
        caminho.unlink()
    except OSError:
        pass  # A cópia final é válida; o temporário pode estar preso pelo exportador.
    return destino
