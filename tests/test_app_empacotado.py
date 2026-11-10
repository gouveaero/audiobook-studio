"""T20/T21: testes do app empacotado (@pytest.mark.package).

APP_PATH: caminho do .app (padrão dist/Audiobook Studio.app).
A T21 (livro curto em env limpo) é para a fila do modelo do Maestro.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _app_path() -> Path:
    env = os.environ.get("APP_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return RAIZ / "dist" / "Audiobook Studio.app"


def _exe(app: Path) -> Path:
    return app / "Contents" / "MacOS" / "Audiobook Studio"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.package
def test_app_declara_microfone_no_info_plist():
    app = _app_path()
    if not app.is_dir():
        pytest.skip(f"APP_PATH/app ausente: {app}")
    plist = (app / "Contents" / "Info.plist").read_text(encoding="utf8", errors="replace")
    assert "NSMicrophoneUsageDescription" in plist


@pytest.mark.package
def test_self_test_janela_real():
    app = _app_path()
    exe = _exe(app)
    if not exe.is_file():
        pytest.skip(f"executável ausente: {exe}")
    home = Path(os.environ.get("AUDIOBOOK_STUDIO_HOME") or (RAIZ / "build" / "selftest-home"))
    home.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(exe), "--self-test"],
        capture_output=True, text=True,
        env={**os.environ, "AUDIOBOOK_STUDIO_HOME": str(home)},
        timeout=120,
    )
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip().startswith("{")]
    assert lines, f"sem JSON: out={r.stdout!r} err={r.stderr!r} code={r.returncode}"
    data = json.loads(lines[-1])
    assert data.get("getUserMedia") == "presente", data
    assert data.get("audio_range") is True, data
    assert data.get("microphone_permission") is not None, data


@pytest.mark.package
def test_livro_curto_ambiente_limpo(tmp_path):
    """R41: env limpo (HOME vazio, PATH mínimo) gera um livro curto até o M4B."""
    app = _app_path()
    exe = _exe(app)
    if not exe.is_file():
        pytest.skip(f"executável ausente: {exe}")

    from tests.epub_sintetico import make_epub, paras

    home = tmp_path / "home"
    home.mkdir()
    studio_home = home / "Library" / "Application Support" / "Audiobook Studio"
    studio_home.mkdir(parents=True)

    hf_seed = os.environ.get("AUDIOBOOK_HF_SEED", "").strip()
    if hf_seed and Path(hf_seed).is_dir():
        import shutil
        shutil.copytree(hf_seed, studio_home / "hf", dirs_exist_ok=True)

    epub = tmp_path / "curto.epub"
    make_epub(
        epub,
        [("c1.xhtml", "<h1>1.</h1>" + paras(2))],
        toc=[("Um", "c1.xhtml")],
        title="Livro Curto Pacote",
        cover=True,
    )

    port = _free_port()
    token = "tok-package-t21"
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "AUDIOBOOK_STUDIO_HOME": str(studio_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }

    def req(method, path, body=None, headers=None):
        h = dict(headers or {})
        if method not in ("GET", "HEAD"):
            h["X-Studio-Token"] = token
        r = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=body, method=method, headers=h,
        )
        try:
            with urllib.request.urlopen(r, timeout=180) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    proc = subprocess.Popen(
        [str(exe), "_worker", "server", "--port", str(port), "--token", token],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                if proc.poll() is not None:
                    err = (proc.stderr.read() or b"").decode()[:800]
                    pytest.fail(f"servidor do app saiu cedo: {err}")
                time.sleep(0.2)
        else:
            pytest.fail("servidor do app não abriu a porta")

        st, body = req("GET", "/api/models")
        assert st == 200, body
        models = json.loads(body)
        if models.get("status") != "pronto":
            if not hf_seed and not os.environ.get("PACKAGE_ALLOW_MODEL_DOWNLOAD"):
                pytest.skip("sem modelo no HOME limpo; Maestro usa AUDIOBOOK_HF_SEED")
            st, body = req("POST", "/api/models/download", body=b"")
            assert st == 200, body
            for _ in range(600):
                st, body = req("GET", "/api/models")
                info = json.loads(body)
                if info.get("status") == "pronto":
                    break
                if info.get("status") == "erro":
                    pytest.fail(info.get("error"))
                time.sleep(1)
            else:
                pytest.fail("timeout download modelo")

        st, body = req("POST", "/api/projects", body=epub.read_bytes())
        assert st == 200, body
        pid = json.loads(body)["id"]

        st, body = req("GET", "/api/voices")
        assert st == 200
        voices = json.loads(body)
        vid = voices.get("selected") or "rafael"
        req(
            "POST", f"/api/projects/{pid}/voice",
            body=json.dumps({"voice_id": vid}).encode(),
            headers={"Content-Type": "application/json"},
        )

        st, body = req("POST", f"/api/projects/{pid}/start", body=b"{}")
        assert st == 200, body

        final = None
        for _ in range(900):
            st, body = req("GET", f"/api/projects/{pid}/state")
            assert st == 200
            final = json.loads(body)
            if final.get("status") in ("pronto", "concluido", "erro", "cancelado"):
                break
            time.sleep(1)
        assert final and final.get("status") in ("pronto", "concluido"), final
        m4b = list((studio_home / "projects" / pid / "audiobook").glob("*.m4b"))
        assert m4b or final.get("m4b"), "sem M4B"

        dmg = RAIZ / "dist" / "Audiobook-Studio.dmg"
        if dmg.is_file():
            assert dmg.stat().st_size > 1024
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
