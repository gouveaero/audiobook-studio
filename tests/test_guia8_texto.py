"""Guia 8 (R7, R38, R39): textos, erro de montagem, voz no config, capa."""
import json
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.epub_sintetico import make_epub, paras
from tests.test_servidor_base import Servidor

UI = Path(__file__).resolve().parent.parent / "ui"


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-g8", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def test_dashboard_log_sem_ingles_tecnico():
    html = (UI / "dashboard.html").read_text(encoding="utf8")
    assert "clone_voice --ref" not in html
    assert "synth cloud" not in html
    assert "gerando capítulo" in html or "geração local" in html


def test_home_sem_slug_interno():
    html = (UI / "home.html").read_text(encoding="utf8")
    assert "+ p.id" not in html
    assert 'p.author || ""' in html or "p.author ?" in html


def test_voice_copy_amigavel():
    html = (UI / "voice.html").read_text(encoding="utf8")
    assert "A voz padrão já vem escolhida" in html
    assert "Precisa de internet na primeira vez" in html
    assert "sem login" not in html.lower()
    assert "baixa ao escolher ou ouvir" not in html


def test_voice_pack_mostra_label_selecionado_no_topo(api, casa, tmp_path, monkeypatch):
    pack = tmp_path / "voice-pack"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({
        "id": "padrao", "label": "Voz Rafael", "engine": "pocket",
        "model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors", "eq": True,
    }), encoding="utf8")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    data = json.loads(api.req("GET", "/api/voices")[2])
    assert data["selected"] == "padrao"
    sel = next(v for v in data["voices"] if v["id"] == data["selected"])
    assert sel["label"] == "Voz Rafael"
    html = (UI / "voice.html").read_text(encoding="utf8")
    assert "selectedLabel" in html or "rótulo" in html or "vozEscolhida" in html or "labelSel" in html


def test_generate_erro_montagem_sem_excecao_nem_caminho():
    src = (Path(__file__).resolve().parent.parent / "studio" / "generate.py").read_text(encoding="utf8")
    assert "O detalhe está em work/generate.log" not in src
    assert "type(e).__name__" not in src


def test_project_state_filtra_erro_tecnico(api, casa):
    from studio import local_api as la
    proj = make_project(casa / "projects", [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    (proj / "work").mkdir(parents=True, exist_ok=True)
    (proj / "work" / "job.json").write_text(json.dumps({
        "pid": 1, "status": "erro",
        "error": "A montagem do audiolivro falhou (RuntimeError). O detalhe está em work/generate.log.",
    }), encoding="utf8")
    data = json.loads(api.req("GET", f"/api/projects/{proj.name}/state")[2])
    assert data["status"] == "erro"
    assert "RuntimeError" not in (data.get("error") or "")
    assert "generate.log" not in (data.get("error") or "")
    assert "montagem" in (data.get("error") or "").lower() or "audiolivro" in (data.get("error") or "").lower()


def test_attach_voice_grava_rotulo_no_config(api, casa, tmp_path, monkeypatch):
    pack = tmp_path / "voice-pack"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({
        "id": "padrao", "label": "voz Rafael", "engine": "pocket",
        "model": "portuguese_24l", "eq": True,
    }), encoding="utf8")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    proj = make_project(casa / "projects", [("01", "Um", ["Oi."])], config={"motor": "pocket"})
    from studio import local_api as la
    la.attach_voice_to_project(proj.name, "padrao")
    cfg = json.loads((proj / "config.json").read_text(encoding="utf8"))
    assert cfg.get("voz") == "voz Rafael" or cfg.get("voz_label") == "voz Rafael"
    assert cfg.get("motor") == "pocket"  # motor interno ok no arquivo
    # endpoint de config para o painel expõe o rótulo, não "pocket" no subtítulo
    out = json.loads(api.req("GET", f"/api/projects/{proj.name}/config")[2])
    assert "Rafael" in (out.get("voz_label") or out.get("voz") or "")


def test_r7_criar_projeto_garante_capa_valida(api, casa, tmp_path):
    """Livro criado pela tela não pode chegar à montagem sem capa usável (R7)."""
    from studio import local_api as la
    la.set_models_status(status="pronto", bytes=la.MODEL_TOTAL_BYTES, total_bytes=la.MODEL_TOTAL_BYTES, error=None)
    epub = tmp_path / "c.epub"
    # capa sintética inválida para ffmpeg (bytes de mentira)
    make_epub(
        epub,
        [("c1.xhtml", "<h1>1.</h1>" + paras(2))],
        toc=[("Um", "c1.xhtml")],
        title="Com Capa Falsa",
        cover=True,
    )
    st, _, body = api.req(
        "POST", "/api/projects",
        body=epub.read_bytes(),
        headers=auth(api),
    )
    assert st == 200, body
    pid = json.loads(body)["id"]
    capa = casa / "projects" / pid / "cover.jpg"
    assert capa.is_file() and capa.stat().st_size > 500
    import subprocess
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(capa), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
