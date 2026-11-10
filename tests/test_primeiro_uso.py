"""Guia 1 (R36): tela de primeiro uso e download do modelo (com AUDIOBOOK_FAKE_DOWNLOAD)."""
import json
import time
from pathlib import Path

import pytest

from tests.test_servidor_base import Servidor

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "ui"


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    monkeypatch.setenv("AUDIOBOOK_FAKE_DOWNLOAD", "1")
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-dl", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def test_home_consulta_models_e_tem_painel_download():
    html = (UI / "home.html").read_text(encoding="utf8")
    assert "/api/models" in html
    assert "/api/models/download" in html
    assert "Baixar modelo" in html or "Tentar de novo" in html
    assert "total_bytes" in html or "tamanho" in html.lower() or "MB" in html


def test_fake_download_falha_na_primeira_e_passa_na_segunda(api, casa):
    from studio import local_api as la

    antes = json.loads(api.req("GET", "/api/models")[2])
    assert antes["status"] in ("ausente", "erro")
    assert antes["total_bytes"] > 0

    assert api.req("POST", "/api/models/download", headers=auth(api))[0] == 200
    info = None
    for _ in range(80):
        info = json.loads(api.req("GET", "/api/models")[2])
        if info["status"] == "erro":
            break
        time.sleep(0.05)
    assert info["status"] == "erro", info
    assert "download" in (info.get("error") or "").lower() or "conexão" in (info.get("error") or "").lower()
    assert "Traceback" not in (info.get("error") or "")

    assert api.req("POST", "/api/models/download", headers=auth(api))[0] == 200
    for _ in range(80):
        info = json.loads(api.req("GET", "/api/models")[2])
        if info["status"] == "pronto":
            break
        time.sleep(0.05)
    assert info["status"] == "pronto", info
    assert info["bytes"] == info["total_bytes"]


def test_criar_projeto_sem_modelo_recusa(api, casa, tmp_path):
    from tests.epub_sintetico import make_epub, paras
    epub = tmp_path / "a.epub"
    make_epub(epub, [("c1.xhtml", "<h1>1.</h1>" + paras(2))], toc=[("Um", "c1.xhtml")], title="Livro")
    st, _, body = api.req("POST", "/api/projects", body=epub.read_bytes(), headers=auth(api))
    assert st == 400
    data = json.loads(body)
    assert "modelo" in data["error"].lower() or "baix" in data["error"].lower()
