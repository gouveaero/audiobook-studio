"""T22 (R44): aviso de versão nova pelas releases do GitHub; sem rede não causa erro."""
import json
from pathlib import Path

import pytest

from studio import local_api as la
from tests.test_servidor_base import Servidor

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-upd", project=None)
    yield s
    s.close()


def test_github_repo_em_brand():
    from studio import brand
    assert brand.GITHUB_REPO.startswith("https://github.com/")
    assert "gouveaero/audiobook-studio" in brand.GITHUB_REPO
    assert not brand.GITHUB_REPO.endswith("/")
    assert la.releases_api_url() == (
        "https://api.github.com/repos/gouveaero/audiobook-studio/releases/latest"
    )


def test_versao_mais_nova_comparacao():
    assert la.versao_mais_nova("0.1.0-beta", "0.2.0") is True
    assert la.versao_mais_nova("0.1.0", "v0.1.0") is False
    assert la.versao_mais_nova("0.2.0", "0.1.9") is False
    assert la.versao_mais_nova("0.1.0", "0.1.0.1") is True


def test_update_versao_maior_simulada(api, monkeypatch):
    def fake(_url):
        return {
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/gouveaero/audiobook-studio/releases/tag/v9.9.9",
        }

    monkeypatch.setattr(la, "_http_get_json", fake)
    st, _, body = api.req("GET", "/api/updates")
    assert st == 200
    data = json.loads(body)
    assert data["update_available"] is True
    assert data["latest"] == "v9.9.9"
    assert data["current"] == la.APP_VERSION
    assert "releases" in (data.get("release_url") or "")


def test_update_versao_igual_simulada(api, monkeypatch):
    def fake(_url):
        return {"tag_name": la.APP_VERSION, "html_url": "https://example.invalid/x"}

    monkeypatch.setattr(la, "_http_get_json", fake)
    data = json.loads(api.req("GET", "/api/updates")[2])
    assert data["update_available"] is False
    assert data["latest"] == la.APP_VERSION


def test_update_sem_rede_nao_erra(api, monkeypatch):
    def fake(_url):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(la, "_http_get_json", fake)
    st, _, body = api.req("GET", "/api/updates")
    assert st == 200
    data = json.loads(body)
    assert data["update_available"] is False
    assert data.get("offline") is True
    assert "error" not in data or not data.get("error")


def test_update_resposta_invalida(api, monkeypatch):
    monkeypatch.setattr(la, "_http_get_json", lambda url: "nao-e-json-objeto")
    data = json.loads(api.req("GET", "/api/updates")[2])
    assert data["update_available"] is False
    assert data["latest"] is None

    monkeypatch.setattr(la, "_http_get_json", lambda url: {"tag_name": ""})
    data = json.loads(api.req("GET", "/api/updates")[2])
    assert data["update_available"] is False


def test_nenhum_teste_deste_arquivo_chama_rede_real(monkeypatch):
    """Guarda: se _http_get_json real for chamado neste módulo de testes, falha."""
    def banido(url):
        raise AssertionError(f"teste acessou a rede: {url}")

    monkeypatch.setattr(la, "_http_get_json", banido)
    # chamada direta com buscar injetado não usa _http_get_json
    out = la.verificar_versao_nova(buscar=lambda u: {"tag_name": "v1.0.0"})
    assert "update_available" in out


def test_home_consulta_updates():
    html = (RAIZ / "ui" / "home.html").read_text(encoding="utf8")
    assert "/api/updates" in html
    assert "update_available" in html
