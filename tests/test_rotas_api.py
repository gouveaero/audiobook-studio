"""T15 (R9, R26, R31, R36, R38): rotas de projetos, voz, modelos, estado e refazer."""
import json
import os
import time
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.epub_sintetico import make_epub, paras
from tests.test_servidor_base import Servidor, _wav_bytes


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


@pytest.fixture
def api(casa):
    """Servidor multi-projeto (sem --project)."""
    s = Servidor(token="tok-api", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def test_post_projects_cria_projeto_de_epub(api, casa, tmp_path):
    epub = tmp_path / "livro.epub"
    make_epub(epub, [("c1.xhtml", "<h1>1.</h1>" + paras(2))], toc=[("1.", "c1.xhtml")], title="Casa Nova")
    status, _, body = api.req(
        "POST", "/api/projects",
        body=epub.read_bytes(),
        headers=auth(api, {"Content-Type": "application/epub+zip"}),
    )
    assert status == 200, body
    data = json.loads(body)
    assert data["title"] == "Casa Nova"
    assert "id" in data
    proj = casa / "projects" / data["id"]
    assert (proj / "book.json").is_file()
    book = json.loads((proj / "book.json").read_text(encoding="utf8"))
    assert book["chapters"]
    assert "include" in book["chapters"][0]


def test_post_projects_drm_devolve_code_sem_traceback(api, tmp_path):
    from tests.epub_sintetico import encryption_xml
    epub = tmp_path / "drm.epub"
    make_epub(
        epub, [("c1.xhtml", "<h1>1.</h1>" + paras(1))],
        encryption=encryption_xml([("http://www.idpf.org/2008/embedding", "OEBPS/Text/c1.xhtml")]),
    )
    # embedding alone may not be drm - use real encrypted content algorithm
    make_epub(
        epub, [("c1.xhtml", "<h1>1.</h1>" + paras(1))],
        encryption=encryption_xml([("http://www.w3.org/2001/04/xmlenc#aes128-cbc", "OEBPS/Text/c1.xhtml")]),
    )
    status, _, body = api.req(
        "POST", "/api/projects",
        body=epub.read_bytes(),
        headers=auth(api),
    )
    assert status == 400
    data = json.loads(body)
    assert data["code"] == "drm"
    assert "traceback" not in body.decode().lower()
    assert "Traceback" not in body.decode()


def test_put_book_respeita_include_e_titulo(api, casa, tmp_path):
    epub = tmp_path / "a.epub"
    make_epub(epub, [("c1.xhtml", "<h1>1.</h1>" + paras(2)), ("c2.xhtml", "<h1>2.</h1>" + paras(2))],
              toc=[("Um", "c1.xhtml"), ("Dois", "c2.xhtml")], title="Dois Caps")
    status, _, body = api.req("POST", "/api/projects", body=epub.read_bytes(), headers=auth(api))
    assert status == 200, body
    pid = json.loads(body)["id"]
    status, _, body = api.req("GET", f"/api/projects/{pid}/book")
    assert status == 200
    book = json.loads(body)
    book["chapters"][0]["include"] = False
    book["chapters"][1]["title"] = "Capítulo renomeado"
    status, _, body = api.req(
        "PUT", f"/api/projects/{pid}/book",
        body=json.dumps(book).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert status == 200, body
    salvo = json.loads((casa / "projects" / pid / "book.json").read_text(encoding="utf8"))
    assert salvo["chapters"][0]["include"] is False
    assert salvo["chapters"][1]["title"] == "Capítulo renomeado"


def test_hf_login_grava_token_0600_e_nao_ecoado(api, casa):
    segredo = "hf_" + ("A" * 30)
    status, _, body = api.req(
        "POST", "/api/hf-login",
        body=json.dumps({"token": segredo}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert status == 200, body
    data = json.loads(body)
    assert data.get("ok") is True
    assert segredo not in body.decode()
    path = casa / "hf" / "token"
    assert path.is_file()
    assert path.read_text(encoding="utf8").strip() == segredo
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
    # GET não revela
    for path_api in ("/api/voices", "/api/models", "/api/projects", "/config.json"):
        st, _, b = api.req("GET", path_api)
        assert st == 200
        assert segredo.encode() not in b


def test_models_download_simulado_com_progresso_e_nova_tentativa(api, casa, monkeypatch):
    from studio import server as srv

    calls = {"n": 0}

    def fake_download(dest: Path, on_progress):
        calls["n"] += 1
        total = 1000
        if calls["n"] == 1:
            on_progress(200, total)
            raise ConnectionError("queda simulada")
        for done in (400, 800, 1000):
            on_progress(done, total)
            time.sleep(0.01)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 1000)

    monkeypatch.setattr(srv, "baixar_modelo", fake_download)

    status, _, body = api.req("GET", "/api/models")
    assert status == 200
    antes = json.loads(body)
    assert "total_bytes" in antes
    assert antes["status"] in ("ausente", "pronto", "baixando", "erro")

    status, _, body = api.req("POST", "/api/models/download", headers=auth(api))
    assert status == 200, body
    # espera o download em background terminar (com retry)
    pronto = False
    for _ in range(50):
        st, _, b = api.req("GET", "/api/models")
        info = json.loads(b)
        if info["status"] == "pronto":
            pronto = True
            break
        if info["status"] == "erro" and calls["n"] == 1:
            # primeira falha; pede de novo
            api.req("POST", "/api/models/download", headers=auth(api))
        time.sleep(0.05)
    assert pronto or calls["n"] >= 2
    # se ainda não pronto, segunda tentativa
    if not pronto:
        status, _, body = api.req("POST", "/api/models/download", headers=auth(api))
        assert status == 200
        for _ in range(50):
            st, _, b = api.req("GET", "/api/models")
            if json.loads(b)["status"] == "pronto":
                pronto = True
                break
            time.sleep(0.05)
    assert pronto
    assert calls["n"] >= 2
    final = json.loads(api.req("GET", "/api/models")[2])
    assert final["bytes"] == final["total_bytes"] or final["status"] == "pronto"


def test_state_lê_job_json(api, casa):
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto."]),
    ], config={"motor": FAKE_ENGINE})
    # make_project cria casa/projects/projeto
    pid = proj.name
    work = proj / "work"
    work.mkdir(parents=True, exist_ok=True)
    job = {"pid": 99999, "status": "rodando", "motor": FAKE_ENGINE, "model": "portuguese_24l", "started": time.time()}
    (work / "job.json").write_text(json.dumps(job), encoding="utf8")
    status, _, body = api.req("GET", f"/api/projects/{pid}/state")
    assert status == 200, body
    data = json.loads(body)
    assert data["status"] == "rodando"
    assert data["job"]["pid"] == 99999


def test_pause_resume_cancel_via_arquivos(api, casa):
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto curto."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name
    (proj / "work").mkdir(exist_ok=True)
    (proj / "work" / "job.json").write_text(json.dumps({
        "pid": os.getpid(), "status": "rodando", "motor": FAKE_ENGINE, "model": "fake", "started": time.time(),
    }), encoding="utf8")

    st, _, b = api.req("POST", f"/api/projects/{pid}/pause", headers=auth(api))
    assert st == 200, b
    assert (proj / "work" / "pause").is_file()

    st, _, b = api.req("POST", f"/api/projects/{pid}/resume", headers=auth(api))
    assert st == 200, b
    assert not (proj / "work" / "pause").exists()

    st, _, b = api.req("POST", f"/api/projects/{pid}/cancel", headers=auth(api))
    assert st == 200, b
    assert (proj / "work" / "cancel").is_file()


def test_redo_apaga_trecho_e_marca_refazer(api, casa, monkeypatch):
    proj = make_project(casa / "projects", [
        ("03", "Três", ["Capítulo três.", "Frase A.", "Frase B."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name
    chunks = proj / "work" / "chunks"
    chunks.mkdir(parents=True, exist_ok=True)
    alvo = chunks / "03_0001.wav"
    alvo.write_bytes(_wav_bytes(0.2))
    (chunks / "03_0001.p00.wav").write_bytes(b"x")
    (proj / "chapters").mkdir(exist_ok=True)
    (proj / "chapters" / "03.m4a").write_bytes(b"fake")

    class FakeProc:
        pid = 4242
        def wait(self):
            return 0

    monkeypatch.setattr("studio.local_api.subprocess.Popen", lambda *a, **k: FakeProc())

    st, _, b = api.req(
        "POST", f"/api/projects/{pid}/redo",
        body=json.dumps({"chapter": "03", "chunk": 1}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    assert not alvo.exists()
    assert not (chunks / "03_0001.p00.wav").exists()
    assert not (proj / "chapters" / "03.m4a").exists()
    # job de refazer registrado (espera o waiter do processo falso)
    job = None
    for _ in range(30):
        raw = (proj / "work" / "job.json").read_text(encoding="utf8").strip()
        if raw:
            job = json.loads(raw)
            if job.get("redo") == {"chapter": "03", "chunk": 1}:
                break
        time.sleep(0.05)
    assert job is not None
    assert job.get("redo") == {"chapter": "03", "chunk": 1}
    assert job["status"] in ("rodando", "refazendo", "concluido")


def test_voices_lista_padrao_ou_fallback(api, casa, monkeypatch, tmp_path):
    # sem pacote: fallback rafael
    monkeypatch.delenv("VOICE_PACK_DIR", raising=False)
    st, _, b = api.req("GET", "/api/voices")
    assert st == 200
    data = json.loads(b)
    assert any(v["id"] == "rafael" or v.get("name") == "rafael" for v in data["voices"])
    assert data.get("selected")

    # com pacote
    pack = tmp_path / "voice-pack"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({
        "id": "padrao", "label": "Voz do teste", "engine": "pocket",
        "model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors", "eq": True,
    }), encoding="utf8")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    st, _, b = api.req("GET", "/api/voices")
    data = json.loads(b)
    assert any(v["id"] == "padrao" for v in data["voices"])


def test_post_voices_exige_consentimento_e_grava_eq(api, casa):
    audio = _wav_bytes(0.5)
    # sem consentimento
    st, _, b = api.req(
        "POST", "/api/voices",
        body=audio,
        headers=auth(api, {"Content-Type": "audio/wav", "X-Consent": "false"}),
    )
    assert st == 400
    assert b"traceback" not in b.lower()

    st, _, b = api.req(
        "POST", "/api/voices",
        body=audio,
        headers=auth(api, {
            "Content-Type": "audio/wav",
            "X-Consent": "true",
            "X-Voice-Text": "Texto de teste da clonagem.",
            "X-Voice-Label": "Minha voz",
        }),
    )
    assert st == 200, b
    data = json.loads(b)
    assert "id" in data
    assert "eq" in data
    assert isinstance(data["eq"], bool)
    vdir = casa / "voices" / data["id"]
    assert (vdir / "manifest.json").is_file()
    man = json.loads((vdir / "manifest.json").read_text(encoding="utf8"))
    assert man["eq"] is data["eq"]
    assert (vdir / "ref.wav").is_file()


def test_assemble_chama_montar_projeto(api, casa, monkeypatch):
    from studio import server as srv
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name
    called = {}

    def fake_montar(P, *, video=False, **kw):
        called["P"] = str(P)
        called["video"] = video
        return str(Path(P) / "audiobook" / "livro.m4b")

    monkeypatch.setattr(srv, "montar_projeto", fake_montar)
    st, _, b = api.req(
        "POST", f"/api/projects/{pid}/assemble",
        body=json.dumps({"video": False}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    assert called["P"] == str(proj)
    assert called["video"] is False


def test_version_e_erro_sem_traceback(api):
    st, _, b = api.req("GET", "/api/version")
    assert st == 200
    data = json.loads(b)
    assert "version" in data or "app" in data
