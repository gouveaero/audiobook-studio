"""Guia 6 (R30–R32): flagged pelo último done; Salvar M4B sem caminho absoluto."""
import json
from pathlib import Path

from tests.conftest import FAKE_ENGINE, make_project
from tests.test_servidor_base import Servidor

UI = Path(__file__).resolve().parent.parent / "ui"


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


def test_ready_salvar_sem_caminho_absoluto():
    html = (UI / "ready.html").read_text(encoding="utf8")
    assert "showSaveFilePicker" in html or "download" in html
    assert "j.out" not in html or "basename" in html or "pasta" in html.lower() or "nome" in html.lower()
    # não deve concatenar o caminho cru na mensagem
    assert 'M4B salvo: " + j.out' not in html
    assert "Downloads" in html or "showSaveFilePicker" in html
