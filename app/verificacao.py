"""Verificação de conteúdo de arquivo exportado do Domínio — confirma
que o arquivo gerado é realmente o que se espera (empresa, período),
não só que ele existe (ver `dominio.gerar_registro_saidas()`, passo
11, que já confirma existência/tamanho).

Separado de `dominio.py` de propósito: não interage com a tela, só lê
um arquivo já salvo em disco — nenhuma das funções aqui chama
`pyautogui`/`pytesseract`.
"""

from pathlib import Path


def verificar_livro_fiscal_pdf(
    caminho, texto_cabecalho_esperado="REGISTRO DE SA",
    cnpj_esperado=None, data_inicial_esperada=None, data_final_esperada=None,
):
    """Lê o `.pdf` gerado por `dominio.gerar_registro_saidas()` /
    `dominio.gerar_registro_entradas()` e confere, no conteúdo de
    verdade (não só no nome do arquivo), que é a empresa e o período
    esperados — pedido explícito do usuário (passo 8 da rotina
    original: "verificar empresa e período no conteúdo, quando o
    formato permitir").

    `texto_cabecalho_esperado`: trecho que deve aparecer no corpo do
    PDF confirmando que é o livro certo — "REGISTRO DE SA" (bate com
    "REGISTRO DE SAÍDAS") por padrão; passe "REGISTRO DE ENTRADAS" pra
    conferir o livro de entradas.

    Formato trocado de `.xls` pra `.pdf` na seção 0.57 (o ícone que a
    rotina usa abre "Salvar em PDF", não Excel — achado real, a
    suposição inicial de qual ícone era qual estava errada). Extração
    de texto via `pypdf`; se falhar (PDF escaneado sem camada de
    texto, por exemplo), cai pro plano B de ler como texto bruto —
    **nenhum dos dois caminhos foi confirmado contra um PDF real
    gerado por esta rotina ainda**, a própria geração do arquivo nunca
    completou numa execução real até agora.

    Devolve um dict com:
    - `"ok"`: True/False — achou tudo que foi pedido pra conferir.
    - `"metodo"`: `"pypdf"`, `"texto_bruto"` ou `None` (não conseguiu
      ler de jeito nenhum).
    - `"detalhes"`: lista de strings, uma por item conferido (achado
      ou não), pra log/diagnóstico — não só um True/False seco.
    """
    caminho = Path(caminho)
    detalhes = []

    texto_completo, metodo, erro_leitura = _ler_conteudo(caminho, detalhes)
    if texto_completo is None:
        detalhes.append(f"Não consegui ler o arquivo de nenhum jeito: {erro_leitura!r}")
        return {"ok": False, "metodo": None, "detalhes": detalhes}

    tudo_ok = True

    if texto_cabecalho_esperado.upper() not in texto_completo.upper():
        tudo_ok = False
        detalhes.append(f"Não achei '{texto_cabecalho_esperado}' no conteúdo — é mesmo o arquivo certo?")
    else:
        detalhes.append(f"Achei '{texto_cabecalho_esperado}' no conteúdo.")

    if cnpj_esperado:
        so_digitos_esperado = "".join(c for c in cnpj_esperado if c.isdigit())
        so_digitos_arquivo = "".join(c for c in texto_completo if c.isdigit())
        if so_digitos_esperado not in so_digitos_arquivo:
            tudo_ok = False
            detalhes.append(f"Não achei o CNPJ esperado ({cnpj_esperado}) no conteúdo.")
        else:
            detalhes.append(f"CNPJ esperado ({cnpj_esperado}) confirmado no conteúdo.")

    for rotulo, valor_esperado in (
        ("Data inicial", data_inicial_esperada),
        ("Data final", data_final_esperada),
    ):
        if not valor_esperado:
            continue
        if valor_esperado not in texto_completo:
            tudo_ok = False
            detalhes.append(f"Não achei {rotulo} esperada ({valor_esperado}) no conteúdo.")
        else:
            detalhes.append(f"{rotulo} esperada ({valor_esperado}) confirmada no conteúdo.")

    return {"ok": tudo_ok, "metodo": metodo, "detalhes": detalhes}


def verificar_registro_saidas_pdf(
    caminho, cnpj_esperado=None, data_inicial_esperada=None, data_final_esperada=None,
):
    """Wrapper fino de compatibilidade — mesmo que chamar
    `verificar_livro_fiscal_pdf()` com o padrão de "Registro de
    Saídas"."""
    return verificar_livro_fiscal_pdf(
        caminho, texto_cabecalho_esperado="REGISTRO DE SA",
        cnpj_esperado=cnpj_esperado,
        data_inicial_esperada=data_inicial_esperada, data_final_esperada=data_final_esperada,
    )


def _ler_conteudo(caminho, detalhes):
    """Devolve `(texto_completo, metodo, erro)` — `texto_completo` é
    `None` só se os dois jeitos de ler falharem."""
    try:
        import pypdf

        leitor = pypdf.PdfReader(str(caminho))
        partes = [pagina.extract_text() or "" for pagina in leitor.pages]
        texto = "\n".join(partes)
        if texto.strip():
            return texto, "pypdf", None
        detalhes.append("pypdf abriu o PDF mas não achou texto nenhum (PDF escaneado/imagem?) — tentando como texto bruto.")
    except Exception as erro_pypdf:
        detalhes.append(f"pypdf não conseguiu abrir ({erro_pypdf!r}) — tentando como texto bruto.")

    try:
        return caminho.read_text(encoding="latin-1", errors="ignore"), "texto_bruto", None
    except Exception as erro_texto:
        return None, None, erro_texto
