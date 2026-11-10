"""Guia 6 (R30–R32): flagged pelo último done; Salvar M4B sem caminho absoluto."""
import json
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.test_servidor_base import Servidor

UI = Path(__file__).resolve().parent.parent / "ui"


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    # Downloads do usuário = HOME limpo do teste (não o da máquina).
    user = tmp_path / "user-home"
    (user / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(user))
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-save", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def _projeto_com_m4b(casa: Path, nome="Livro Teste.m4b", conteudo=b"m4b-fake-bytes"):
    proj = make_project(casa / "projects", [
        ("01", "Um", ["a", "b"]),
    ], config={"motor": FAKE_ENGINE})
    audiobook = proj / "audiobook"
    audiobook.mkdir(parents=True, exist_ok=True)
    (audiobook / nome).write_bytes(conteudo)
    return proj


def test_flagged_usa_ultimo_done_por_capitulo(tmp_path, monkeypatch):
    from studio import local_api as la

    home = tmp_path / "home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    proj = make_project(home / "projects", [
        ("01", "Um", ["a", "b"]),
    ], config={"motor": FAKE_ENGINE})
    work = proj / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "progress.jsonl").write_text(
        "\n".join([
            json.dumps({"kind": "flagged", "ch": "01", "chunk": 0}),
            json.dumps({"kind": "done", "ch": "01", "flagged": [0]}),
            json.dumps({"kind": "done", "ch": "01", "flagged": []}),
        ]) + "\n",
        encoding="utf8",
    )
    assert la._flagged_from_progress(proj) == []

    (work / "progress.jsonl").write_text(
        "\n".join([
            json.dumps({"kind": "flagged", "ch": "01", "chunk": 1}),
            json.dumps({"kind": "done", "ch": "01", "flagged": [0, 1]}),
        ]) + "\n",
        encoding="utf8",
    )
    got = la._flagged_from_progress(proj)
    assert sorted((g["chapter"], g["chunk"]) for g in got) == [("01", 0), ("01", 1)]


def test_ready_salvar_usa_rota_save_sem_caminho_absoluto():
    """R32/R38: a tela confirma via /save e não mostra caminho completo."""
    html = (UI / "ready.html").read_text(encoding="utf8")
    assert '/save"' in html or "/save'" in html or "/save`" in html or "/save" in html
    assert "showSaveFilePicker" not in html
    assert 'M4B salvo: " + j.out' not in html
    assert "salvo.nome" in html or "j.nome" in html or "data.nome" in html


def test_save_copia_m4b_para_downloads_sem_sobrescrever(api, casa, tmp_path):
    """POST /save copia o M4B para ~/Downloads e devolve só nome e pasta (R32, R38)."""
    proj = _projeto_com_m4b(casa, "Cronica.m4b", b"abc123")
    user_dl = Path.home() / "Downloads"
    assert user_dl.is_dir()

    st, _, b = api.req(
        "POST", f"/api/projects/{proj.name}/save",
        body=b"{}",
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    data = json.loads(b)
    assert data.get("ok") is True
    assert data.get("nome") == "Cronica.m4b"
    assert data.get("pasta") == "Downloads"
    assert "path" not in data
    assert "/" not in data.get("nome", "")
    dest = user_dl / "Cronica.m4b"
    assert dest.is_file()
    assert dest.read_bytes() == b"abc123"
    assert dest.stat().st_size == (proj / "audiobook" / "Cronica.m4b").stat().st_size

    # Segunda chamada não sobrescreve: acrescente " 2".
    st2, _, b2 = api.req(
        "POST", f"/api/projects/{proj.name}/save",
        body=b"{}",
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st2 == 200, b2
    data2 = json.loads(b2)
    assert data2.get("nome") == "Cronica 2.m4b"
    assert (user_dl / "Cronica.m4b").read_bytes() == b"abc123"
    assert (user_dl / "Cronica 2.m4b").read_bytes() == b"abc123"


def test_save_exige_token(api, casa):
    """R33: POST /save sem token é 403."""
    proj = _projeto_com_m4b(casa)
    st, _, _ = api.req(
        "POST", f"/api/projects/{proj.name}/save",
        body=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert st == 403
