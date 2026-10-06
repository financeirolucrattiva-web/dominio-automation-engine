"""Validação e nomes dos livros exportados, somente em disco local."""

import datetime
from pathlib import Path
import re
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


def validar_livro(texto, tipo, inicio, fim, cnpj_esperado=None):
    """Confirma tipo/período e devolve CNPJ inequívoco do cabeçalho.

    Aceita letras e datas espaçadas pelo posicionamento do texto no PDF.
    Não consulta serviços externos nem infere identidade por OCR.
    """
    titulos = {"registro_saidas": "REGISTRODESAIDAS", "registro_entradas": "REGISTRODEENTRADAS"}
    if tipo not in titulos:
        raise ValueError("Tipo de livro não reconhecido.")
    compacto = _compactar(texto)
    titulo = titulos[tipo]
    if titulo not in compacto:
        raise ValueError("O PDF não contém o título do livro solicitado.")
    # O período precisa estar no cabeçalho, antes das linhas de movimentos.
    cabecalho = compacto[compacto.index(titulo):]
    limites = [cabecalho.find(m) for m in ("CODIFICACAO", "VALORESFISCAIS") if m in cabecalho]
    if limites:
        cabecalho = cabecalho[:min(limites)]
    else:
        cabecalho = cabecalho[:2500]
    periodo = re.search(re.escape(_compactar(inicio)) + r"(?:A|ATE|[-–])" + re.escape(_compactar(fim)), cabecalho)
    if periodo is None:
        raise ValueError("O cabeçalho do PDF não confirma o período solicitado.")
    cabecalho = cabecalho[:periodo.end()]
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
    if tipo not in ("registro_saidas", "registro_entradas") or not re.fullmatch(r"\d{14}", cnpj):
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
        cnpj = validar_livro(texto, tipo, inicio, fim, cnpj_esperado)
        # Força leitura de todas as páginas antes de declarar o arquivo pronto.
        for pagina in leitor.pages[1:]:
            pagina.extract_text()
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
                    import shutil
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
