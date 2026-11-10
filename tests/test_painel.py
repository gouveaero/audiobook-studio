"""T18 (R14, R18, R30 a R32): painel com controles reais e tela final com player."""
import json
import time
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.test_servidor_base import Servidor

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "ui"


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-painel", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def test_dashboard_e_ready_sem_travessao_nem_google():
    for nome in ("dashboard.html", "ready.html"):
        html = (UI / nome).read_text(encoding="utf8")
        assert "—" not in html
        assert "fonts.googleapis.com" not in html
        assert "fonts.css" in html
        assert "studio.js" in html
        assert "Claude Code" not in html


def test_dashboard_tem_pausar_continuar_cancelar_e_eta():
    html = (UI / "dashboard.html").read_text(encoding="utf8")
    assert "Pausar" in html
    assert "Continuar" in html
    assert "Cancelar" in html
    assert "eta" in html.lower() or "restam" in html
    assert "/api/projects/" in html
    assert "studio.post" in html


def test_ready_tem_player_salvar_finder_e_ia():
    html = (UI / "ready.html").read_text(encoding="utf8")
    assert "Salvar M4B" in html
    assert "Finder" in html
    assert "<audio" in html
    assert "inteligência artificial" in html.lower() or "inteligencia artificial" in html.lower()
    assert "Refazer" in html or "refazer" in html


def test_state_expoe_eta_e_chars_do_job(api, casa):
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto."]),
    ], config={"motor": FAKE_ENGINE})
    (proj / "work").mkdir(parents=True, exist_ok=True)
    (proj / "work" / "job.json").write_text(json.dumps({
        "pid": 1, "status": "gerando", "motor": FAKE_ENGINE, "model": "fake",
        "started": time.time(), "chars_total": 100, "chars_done": 40,
        "chars_per_second": 10.0, "eta_seconds": 6.0,
    }), encoding="utf8")
    data = json.loads(api.req("GET", f"/api/projects/{proj.name}/state")[2])
    assert data["status"] == "gerando"
    assert data["eta_seconds"] == 6.0
    assert data["chars_done"] == 40
    assert data["chars_total"] == 100
    assert abs(data["total"] - 0.4) < 0.01


def test_pause_resume_cancel_arquivos_reais(api, casa, ambiente_fake):
    """R14: pause/resume/cancel via API criam os arquivos que o generate lê."""
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Trecho um longo o bastante.", "Mais um.", "E outro."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name
    (proj / "work").mkdir(exist_ok=True)
    (proj / "work" / "job.json").write_text(json.dumps({
        "pid": 1, "status": "gerando", "motor": FAKE_ENGINE, "started": time.time(),
    }), encoding="utf8")

    assert api.req("POST", f"/api/projects/{pid}/pause", headers=auth(api))[0] == 200
    assert (proj / "work" / "pause").is_file()
    st = json.loads(api.req("GET", f"/api/projects/{pid}/state")[2])
    assert st["status"] == "pausado"

    assert api.req("POST", f"/api/projects/{pid}/resume", headers=auth(api))[0] == 200
    assert not (proj / "work" / "pause").exists()

    assert api.req("POST", f"/api/projects/{pid}/cancel", headers=auth(api))[0] == 200
    assert (proj / "work" / "cancel").is_file()


def test_audio_multi_projeto_com_range(api, casa):
    """R30: /api/projects/<id>/file/chapters/... serve com Range."""
    from tests.test_servidor_base import _wav_bytes
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Oi."]),
    ], config={"motor": FAKE_ENGINE})
    cap = proj / "chapters"
    cap.mkdir(parents=True, exist_ok=True)
    # usa wav curto com extensão .m4a só para o tipo; Range olha bytes
    wav = _wav_bytes(0.3)
    (cap / "01.m4a").write_bytes(wav)
    path = f"/api/projects/{proj.name}/file/chapters/01.m4a"
    st, headers, body = api.req("GET", path)
    assert st == 200
    assert body == wav
    st, headers, body = api.req("GET", path, headers={"Range": "bytes=0-3"})
    assert st == 206
    assert body == wav[:4]
    assert "bytes" in (headers.get("Content-Range") or headers.get("content-range") or "").lower()


def test_ready_html_serve(api):
    st, _, body = api.req("GET", "/ready.html")
    assert st == 200
    assert "Salvar M4B" in body.decode("utf8")
