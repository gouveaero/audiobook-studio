"""T15 (R9, R26, R31, R36, R38): rotas de projetos, voz, modelos, estado e refazer."""
import hashlib
import json
import os
import re
import time
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.epub_sintetico import make_epub, paras, encryption_xml
from tests.test_servidor_base import Servidor, _wav_bytes


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-api", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def wait_final(api, pid, timeout=90):
    finais = {"concluido", "erro", "cancelado"}
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        st, _, body = api.req("GET", f"/api/projects/{pid}/state")
        assert st == 200, body
        last = json.loads(body)
        if last.get("status") in finais:
            return last
        time.sleep(0.2)
    raise AssertionError(f"timeout esperando estado final; último={last}")


def capa_minima(path: Path):
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64",
         "-frames:v", "1", str(path)],
        check=True,
    )


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- projetos / book ----------

def test_post_projects_cria_projeto_de_epub(api, casa, tmp_path):
    epub = tmp_path / "livro.epub"
    make_epub(epub, [("c1.xhtml", "<h1>1.</h1>" + paras(2))], toc=[("1.", "c1.xhtml")], title="Casa Nova")
    status, _, body = api.req("POST", "/api/projects", body=epub.read_bytes(), headers=auth(api))
    assert status == 200, body
    data = json.loads(body)
    assert data["title"] == "Casa Nova"
    assert (casa / "projects" / data["id"] / "book.json").is_file()


def test_post_projects_drm_devolve_code_sem_traceback(api, tmp_path):
    epub = tmp_path / "drm.epub"
    make_epub(
        epub, [("c1.xhtml", "<h1>1.</h1>" + paras(1))],
        encryption=encryption_xml([("http://www.w3.org/2001/04/xmlenc#aes128-cbc", "OEBPS/Text/c1.xhtml")]),
    )
    status, _, body = api.req("POST", "/api/projects", body=epub.read_bytes(), headers=auth(api))
    assert status == 400
    data = json.loads(body)
    assert data["code"] == "drm"
    assert "Traceback" not in body.decode()


def test_put_book_respeita_include_e_titulo(api, casa, tmp_path):
    epub = tmp_path / "a.epub"
    make_epub(epub, [("c1.xhtml", "<h1>1.</h1>" + paras(2)), ("c2.xhtml", "<h1>2.</h1>" + paras(2))],
              toc=[("Um", "c1.xhtml"), ("Dois", "c2.xhtml")], title="Dois Caps")
    status, _, body = api.req("POST", "/api/projects", body=epub.read_bytes(), headers=auth(api))
    pid = json.loads(body)["id"]
    book = json.loads(api.req("GET", f"/api/projects/{pid}/book")[2])
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


def _projeto_r9(casa):
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto do primeiro."]),
        ("02", "Dois", ["Capítulo dois.", "Texto do segundo."]),
    ], config={"motor": FAKE_ENGINE, "voz": "teste"})
    book = json.loads((proj / "book.json").read_text(encoding="utf8"))
    for ch in book["chapters"]:
        ch["include"] = True
    book["chapters"][0]["include"] = False
    book["chapters"][1]["title"] = "Capítulo renomeado"
    (proj / "book.json").write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf8")
    capa_minima(proj / "cover.jpg")
    return proj


def test_put_include_e_titulo_respeitados_na_montagem(api, casa, ambiente_fake):
    """R9: capítulo tirado fica fora do M4B; título renomeado aparece no marcador."""
    proj = _projeto_r9(casa)
    pid = proj.name
    st, _, b = api.req("POST", f"/api/projects/{pid}/start", headers=auth(api))
    assert st == 200, b
    state = wait_final(api, pid, timeout=120)
    assert state["status"] == "concluido", state

    st, _, b = api.req(
        "POST", f"/api/projects/{pid}/assemble",
        body=json.dumps({"video": False}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    m4bs = list((proj / "audiobook").glob("*.m4b"))
    assert m4bs
    meta = __import__("subprocess").run(
        ["ffprobe", "-v", "error", "-show_chapters", "-print_format", "json", str(m4bs[0])],
        capture_output=True, text=True, check=True,
    ).stdout
    caps = json.loads(meta).get("chapters", [])
    titulos = [c.get("tags", {}).get("title", "") for c in caps]
    assert not any(t == "Um" for t in titulos)
    assert any("renomeado" in t.lower() for t in titulos)


@pytest.mark.xfail(strict=True, reason="aguarda Motor T8: generate.py ainda não lê include")
def test_generate_respeita_include_aguarda_motor(api, casa, ambiente_fake):
    """Quando o Motor passar a ler include, o capítulo tirado não deve ser gerado."""
    proj = _projeto_r9(casa)
    pid = proj.name
    st, _, b = api.req("POST", f"/api/projects/{pid}/start", headers=auth(api))
    assert st == 200, b
    state = wait_final(api, pid, timeout=120)
    assert state["status"] == "concluido", state
    assert not (proj / "chapters" / "01.m4a").exists()


# ---------- R26 HF token ----------

def test_hf_login_0600_sem_eco_em_get_nem_log(api, casa, monkeypatch):
    segredo = "hf_" + ("B" * 32)
    status, _, body = api.req(
        "POST", "/api/hf-login",
        body=json.dumps({"token": segredo}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert status == 200, body
    assert segredo not in body.decode()
    path = casa / "hf" / "token"
    assert path.read_text(encoding="utf8").strip() == segredo
    assert (path.stat().st_mode & 0o777) == 0o600

    for path_api in ("/api/voices", "/api/models", "/api/version", "/api/projects"):
        st, _, b = api.req("GET", path_api)
        assert st == 200
        assert segredo.encode() not in b

    # provoca 500 depois do login e confere logs
    from studio import local_api as la
    monkeypatch.setattr(la, "list_projects", lambda: (_ for _ in ()).throw(RuntimeError(f"boom {segredo}")))
    st, _, b = api.req("GET", "/api/projects")
    assert st == 500
    assert segredo.encode() not in b
    log = (casa / "logs" / "server.log").read_text(encoding="utf8")
    assert segredo not in log
    assert "hf_" + ("B" * 32) not in log
    for wlog in (casa / "projects").rglob("*.log"):
        assert segredo not in wlog.read_text(encoding="utf8", errors="replace")


# ---------- R36 modelos ----------

def test_models_download_simulado_falha_e_completa(api, casa, monkeypatch):
    from studio import server as srv

    calls = {"n": 0}
    progressos = []

    def fake_download(on_progress):
        calls["n"] += 1
        total = 1000
        if calls["n"] == 1:
            on_progress(200, total)
            progressos.append((200, total))
            raise ConnectionError("queda simulada")
        for done in (300, 700, 1000):
            on_progress(done, total)
            progressos.append((done, total))
            time.sleep(0.01)

    monkeypatch.setattr(srv, "baixar_modelo", fake_download)

    antes = json.loads(api.req("GET", "/api/models")[2])
    assert antes["status"] == "ausente"
    assert antes["total_bytes"] > 0

    assert api.req("POST", "/api/models/download", headers=auth(api))[0] == 200
    # espera erro da 1ª tentativa
    info = None
    for _ in range(50):
        info = json.loads(api.req("GET", "/api/models")[2])
        if info["status"] == "erro":
            break
        time.sleep(0.05)
    assert info["status"] == "erro"
    assert calls["n"] == 1
    assert "download" in (info.get("error") or "").lower()
    assert "descarga" not in (info.get("error") or "").lower()

    assert api.req("POST", "/api/models/download", headers=auth(api))[0] == 200
    for _ in range(50):
        info = json.loads(api.req("GET", "/api/models")[2])
        if info["status"] == "pronto":
            break
        time.sleep(0.05)
    assert info["status"] == "pronto"
    assert calls["n"] == 2
    assert info["bytes"] == info["total_bytes"]
    assert info["bytes"] == 1000
    # progresso crescente na 2ª tentativa
    segundos = [p for p in progressos if p[0] >= 300]
    assert [p[0] for p in segundos] == sorted(p[0] for p in segundos)


# Processo filho: download sem HF_TOKEN/HF_HOME herdados; progresso em JSONL.
_DOWNLOAD_FILHO = r"""
import json, os, sys
from pathlib import Path
casa, prog = Path(sys.argv[1]), Path(sys.argv[2])
os.environ["AUDIOBOOK_STUDIO_HOME"] = str(casa)
# ambiente limpo de Hugging Face (sem login nem cache global)
for k in list(os.environ):
    if k.startswith("HF_") or k in ("HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
        del os.environ[k]
from studio import local_api as la
from studio.brand import ensure_dirs
ensure_dirs()
assert not (casa / "hf" / "token").exists()
visto = []
def on_progress(done, total):
    visto.append((int(done), int(total)))
    prog.write_text(json.dumps(visto), encoding="utf8")
la.baixar_modelo(on_progress)
paths = [str(p) for p in la.caminhos_modelo_no_app()]
sizes = [p.stat().st_size for p in la.caminhos_modelo_no_app()]
print("@@" + json.dumps({"visto": visto, "paths": paths, "sizes": sizes, "hub_bytes": la.bytes_no_hub()}, ensure_ascii=False))
"""


@pytest.mark.model
def test_models_download_real_e_motor_offline(tmp_path):
    """Download real dos pesos sem clonagem no hf/ do app; depois Pocket offline sem token.

    O Maestro roda o teste completo (um processo Pocket por vez). A parte de download
    pode ser depurada sozinha (ver tests/test_rotas_api.py docstring do helper).
    """
    import subprocess
    import sys

    from tests.conftest import RAIZ

    casa = tmp_path / "app-home"
    prog = tmp_path / "progress.json"
    # sem herdar HF_HOME/HF_TOKEN do ambiente do desenvolvedor
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HF_") and k not in ("HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE")}
    env["AUDIOBOOK_STUDIO_HOME"] = str(casa)
    env["PYTHONPATH"] = str(RAIZ)
    r = subprocess.run(
        [sys.executable, "-c", _DOWNLOAD_FILHO, str(casa), str(prog)],
        cwd=RAIZ, env=env, capture_output=True, text=True, timeout=3600,
    )
    assert r.returncode == 0, r.stderr[-3000:] + r.stdout[-1000:]
    res = json.loads(r.stdout.split("@@", 1)[1])
    visto = res["visto"]
    assert visto and visto[0][0] == 0
    assert visto[-1][0] == visto[-1][1]
    assert visto[-1][1] > 100_000_000
    assert any(0 < d < visto[-1][1] for d, _ in visto), visto[:20]
    # arquivos só dentro do app, com tamanho real
    assert res["paths"], "modelo não ficou em AUDIOBOOK_STUDIO_HOME/hf"
    for p in res["paths"]:
        assert p.startswith(str(casa / "hf")), p
        assert Path(p).is_file()
    from studio.brand import VOICE_FALLBACK
    assert any(
        "embeddings" in p and f"{VOICE_FALLBACK}.safetensors" in p for p in res["paths"]
    ), res["paths"]
    assert sum(res["sizes"]) > 100_000_000
    assert sum(res["sizes"]) == visto[-1][0] or abs(sum(res["sizes"]) - visto[-1][1]) < 1024 * 1024
    assert not (casa / "hf" / "token").exists()

    # carrega o motor offline a partir do hf/ do app (Maestro / fila de modelo)
    from studio.engines import load_engine
    env_off = dict(env)
    env_off["HF_HOME"] = str(casa / "hf")
    env_off["HF_HUB_CACHE"] = str(casa / "hf" / "hub")
    env_off["HF_HUB_OFFLINE"] = "1"
    prog_motor = r"""
import os, sys
from studio.engines import load_engine
e = load_engine("pocket", device="cpu")
e.load({"model": "portuguese_24l", "name": "rafael"})
w = e.synth("Olá, tudo bem?", 0)
print("@@", len(w))
assert not os.path.exists(os.path.join(os.environ["HF_HOME"], "token"))
"""
    r2 = subprocess.run(
        [sys.executable, "-c", prog_motor],
        cwd=RAIZ, env=env_off, capture_output=True, text=True, timeout=1800,
    )
    assert r2.returncode == 0, r2.stderr[-3000:]
    assert int(r2.stdout.split("@@")[1].strip()) > 1000


# ---------- R31 start / redo reais ----------

def test_start_gera_capitulo_com_motor_falso(api, casa, ambiente_fake, tmp_path):
    registro = tmp_path / "synth.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Frase curta de teste."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name
    st, _, b = api.req("POST", f"/api/projects/{pid}/start", headers=auth(api))
    assert st == 200, b
    state = wait_final(api, pid)
    assert state["status"] == "concluido", state
    assert (proj / "chapters" / "01.m4a").is_file()
    assert len(registro.read_text(encoding="utf8").splitlines()) == 2


def test_redo_refaz_so_o_trecho_com_motor_falso(api, casa, ambiente_fake, tmp_path):
    registro = tmp_path / "synth.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    proj = make_project(casa / "projects", [
        ("03", "Três", ["Capítulo três.", "Frase A do meio.", "Frase B do fim."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name

    st, _, b = api.req("POST", f"/api/projects/{pid}/start", headers=auth(api))
    assert st == 200, b
    state = wait_final(api, pid)
    assert state["status"] == "concluido", state
    assert len(registro.read_text(encoding="utf8").splitlines()) == 3

    chunks = proj / "work" / "chunks"
    outros = {
        "03_0000.wav": (file_sha(chunks / "03_0000.wav"), (chunks / "03_0000.wav").stat().st_mtime_ns),
        "03_0002.wav": (file_sha(chunks / "03_0002.wav"), (chunks / "03_0002.wav").stat().st_mtime_ns),
    }
    m4a = proj / "chapters" / "03.m4a"
    m4a_antes = m4a.stat().st_mtime_ns
    time.sleep(0.05)

    n_antes = len(registro.read_text(encoding="utf8").splitlines())
    st, _, b = api.req(
        "POST", f"/api/projects/{pid}/redo",
        body=json.dumps({"chapter": "03", "chunk": 1}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    state = wait_final(api, pid)
    assert state["status"] == "concluido", state

    linhas = registro.read_text(encoding="utf8").splitlines()
    novas = linhas[n_antes:]
    assert len(novas) == 1, novas
    assert "Frase A do meio." in novas[0]
    assert m4a.is_file()
    assert m4a.stat().st_mtime_ns > m4a_antes
    for nome, (sha, mtime) in outros.items():
        p = chunks / nome
        assert file_sha(p) == sha
        assert p.stat().st_mtime_ns == mtime


# ---------- R38 ----------

def _assert_erro_limpo(body: bytes):
    texto = body.decode("utf8", "replace")
    assert "Traceback" not in texto
    assert not re.search(r"/Users/|/home/|\\\\", texto)
    assert not re.search(r"\b(Error|Exception|KeyError|TypeError|RuntimeError|OSError)\b", texto)
    data = json.loads(body)
    assert isinstance(data.get("error"), str) and data["error"]
    # português: letras acentuadas ou palavras comuns
    assert re.search(r"[áàâãéêíóôõúçÁÉÍÓÚ]|errado|falhou|recusado|projeto|voz|conexão|conexão|tente", data["error"], re.I) or "log" in data["error"].lower()


def test_r38_projetos_voz_modelos_sem_traceback(api, casa, monkeypatch):
    from studio import local_api as la
    from studio import server as srv

    # projetos
    monkeypatch.setattr(la, "create_project_from_epub", lambda b: (_ for _ in ()).throw(RuntimeError("/Users/x/boom")))
    st, _, body = api.req("POST", "/api/projects", body=b"x", headers=auth(api))
    assert st == 500
    _assert_erro_limpo(body)
    assert "RuntimeError" not in (casa / "logs" / "server.log").read_text(encoding="utf8") or True
    assert "RuntimeError" in (casa / "logs" / "server.log").read_text(encoding="utf8")

    # voz
    monkeypatch.setattr(la, "save_cloned_voice", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("TypeError path /tmp/x")))
    st, _, body = api.req(
        "POST", "/api/voices", body=_wav_bytes(0.2),
        headers=auth(api, {"Content-Type": "audio/wav", "X-Consent": "true"}),
    )
    assert st == 500
    _assert_erro_limpo(body)

    # modelos: força exceção no start
    def boom_start(baixar=None):
        raise RuntimeError("falha /home/secret")
    monkeypatch.setattr(la, "start_model_download", boom_start)
    # a rota chama local_api.start_model_download via servidor — precisa patch no ponto de uso
    monkeypatch.setattr(srv.local_api, "start_model_download", boom_start)
    st, _, body = api.req("POST", "/api/models/download", headers=auth(api))
    assert st == 500
    _assert_erro_limpo(body)


# ---------- vozes / assemble / version ----------

def test_voices_lista_padrao_ou_fallback(api, casa, monkeypatch, tmp_path):
    monkeypatch.delenv("VOICE_PACK_DIR", raising=False)
    data = json.loads(api.req("GET", "/api/voices")[2])
    assert any(v["id"] == "rafael" or v.get("name") == "rafael" for v in data["voices"])
    pack = tmp_path / "voice-pack"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({
        "id": "padrao", "label": "Voz do teste", "engine": "pocket",
        "model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors", "eq": True,
    }), encoding="utf8")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    data = json.loads(api.req("GET", "/api/voices")[2])
    assert any(v["id"] == "padrao" for v in data["voices"])


def test_post_voices_exige_consentimento_e_grava_eq(api, casa):
    st, _, b = api.req(
        "POST", "/api/voices", body=_wav_bytes(0.5),
        headers=auth(api, {"Content-Type": "audio/wav", "X-Consent": "false"}),
    )
    assert st == 400
    st, _, b = api.req(
        "POST", "/api/voices", body=_wav_bytes(0.5),
        headers=auth(api, {
            "Content-Type": "audio/wav", "X-Consent": "true",
            "X-Voice-Text": "Texto de teste da clonagem.", "X-Voice-Label": "Minha voz",
        }),
    )
    assert st == 200, b
    data = json.loads(b)
    assert isinstance(data["eq"], bool)
    assert (casa / "voices" / data["id"] / "manifest.json").is_file()


def test_assemble_chama_montar_projeto(api, casa, monkeypatch):
    from studio import server as srv
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto."]),
    ], config={"motor": FAKE_ENGINE})
    called = {}

    def fake_montar(P, *, video=False, **kw):
        called["P"] = str(P)
        called["video"] = video
        return str(Path(P) / "audiobook" / "livro.m4b")

    monkeypatch.setattr(srv, "montar_projeto", fake_montar)
    st, _, b = api.req(
        "POST", f"/api/projects/{proj.name}/assemble",
        body=json.dumps({"video": False}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    assert called["P"] == str(proj)


def test_version_ok(api):
    st, _, b = api.req("GET", "/api/version")
    assert st == 200
    assert "version" in json.loads(b) or "app" in json.loads(b)


def test_state_lê_job_json(api, casa):
    proj = make_project(casa / "projects", [("01", "Um", ["Capítulo um.", "Texto."])], config={"motor": FAKE_ENGINE})
    (proj / "work").mkdir(parents=True, exist_ok=True)
    (proj / "work" / "job.json").write_text(json.dumps({
        "pid": 99999, "status": "rodando", "motor": FAKE_ENGINE, "model": "portuguese_24l", "started": time.time(),
    }), encoding="utf8")
    data = json.loads(api.req("GET", f"/api/projects/{proj.name}/state")[2])
    assert data["status"] == "rodando"
    assert data["job"]["pid"] == 99999


def test_pause_resume_cancel_via_arquivos(api, casa):
    proj = make_project(casa / "projects", [("01", "Um", ["Capítulo um.", "Texto."])], config={"motor": FAKE_ENGINE})
    (proj / "work").mkdir(exist_ok=True)
    (proj / "work" / "job.json").write_text(json.dumps({
        "pid": os.getpid(), "status": "rodando", "motor": FAKE_ENGINE, "model": "fake", "started": time.time(),
    }), encoding="utf8")
    assert api.req("POST", f"/api/projects/{proj.name}/pause", headers=auth(api))[0] == 200
    assert (proj / "work" / "pause").is_file()
    assert api.req("POST", f"/api/projects/{proj.name}/resume", headers=auth(api))[0] == 200
    assert not (proj / "work" / "pause").exists()
    assert api.req("POST", f"/api/projects/{proj.name}/cancel", headers=auth(api))[0] == 200
    assert (proj / "work" / "cancel").is_file()
