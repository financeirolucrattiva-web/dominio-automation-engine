"""Os testes antigos do seletor exercitam o percurso por setas; a busca por digitação
(modo padrão em produção) é testada à parte, ligando `MODO_DIGITACAO` explicitamente."""
import pytest


@pytest.fixture(autouse=True)
def seletor_percurso_por_setas(monkeypatch):
    from app import seletor_pasta
    monkeypatch.setattr(seletor_pasta, "MODO_DIGITACAO", False)


@pytest.fixture(autouse=True)
def geometria_dos_campos_limpa():
    from app import leitura_resumo
    leitura_resumo.esquecer_geometria()
    yield
    leitura_resumo.esquecer_geometria()


@pytest.fixture(autouse=True)
def otimizacoes_desligadas_nos_testes_antigos(monkeypatch):
    """As simulações antigas de OCR dependem da ORDEM das chamadas e do caminho clássico; os testes
    das otimizações as ligam explicitamente (`otimizacoes._forcado = True`)."""
    from app import otimizacoes
    otimizacoes.restaurar_para_testes()
    monkeypatch.setattr(otimizacoes, "_forcado", False)
    yield
    otimizacoes.restaurar_para_testes()
