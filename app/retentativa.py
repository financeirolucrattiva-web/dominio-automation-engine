"""Segunda chance da rotina no caminho clássico (sem otimizações), quando a primeira falha cedo.

As otimizações de velocidade (OCR em paralelo, geometria lembrada, OCR do centro do seletor...) têm o
caminho clássico, já provado, ao lado. Se uma rotina falha ANTES de gerar algo, o executor volta à tela
azul e repete a rotina uma vez com todas as otimizações desligadas: o pior caso fica igual ao tempo antigo
e uma falha de otimização não derruba o lote.

Regras (puras, testáveis aqui; a execução fica em `executor_servidor`):
- nunca repete depois de a geração ser sinalizada (EFD: etapa `gerar_documento` iniciada; Resumo/Livros:
  PDFs já aceitos em `conferir_pdf`) nem quando o operador interferiu (foco perdido) ou parou a rotina;
- no máximo uma repetição por tarefa;
- só quando alguma otimização estava ligada (senão repetir não muda nada).
"""

ROTINAS_DE_GERACAO_UNICA = ("efd_contribuicoes", "sped_fiscal", "geracao_fiscal")


def _etapas(eventos, status=None):
    return {e.get("step") for e in eventos if isinstance(e, dict) and (status is None or e.get("status") == status)}


def foi_sucesso(resultado):
    """True para `True` ou `(True, ...)` (os geradores devolvem os dois formatos)."""
    if isinstance(resultado, tuple) and resultado:
        resultado = resultado[0]
    return resultado is True


def pode_retentar(capacidade, eventos, *, foco_perdido=False, ja_retentou=False, otimizacoes_ativas=True):
    """Decide se a falha de `capacidade` pode ser repetida em modo seguro. `eventos` = os desta tarefa."""
    if ja_retentou or foco_perdido or not otimizacoes_ativas:
        return False
    if capacidade in ROTINAS_DE_GERACAO_UNICA:
        return "gerar_documento" not in _etapas(eventos)
    # Resumo / Livros (e livros individuais): só antes de o PDF ser aceito.
    return "conferir_pdf" not in _etapas(eventos, "confirmado")
