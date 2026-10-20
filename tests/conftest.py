"""Os testes antigos do seletor exercitam o percurso por setas; a busca por digitação
(modo padrão em produção) é testada à parte, ligando `MODO_DIGITACAO` explicitamente."""
import pytest


@pytest.fixture(autouse=True)
def seletor_percurso_por_setas(monkeypatch):
    from app import seletor_pasta
    monkeypatch.setattr(seletor_pasta, "MODO_DIGITACAO", False)
