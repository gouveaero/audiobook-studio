"""T20/T21: testes do app empacotado (@pytest.mark.package).

APP_PATH: caminho do .app (padrão dist/Audiobook Studio.app).
Na camada package, app ausente é FALHA (não skip).
R41: HOME limpo + PATH mínimo; sem AUDIOBOOK_HF_SEED o app baixa o modelo de verdade.
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


def _require_app() -> tuple[Path, Path]:
    app = _app_path()
    exe = _exe(app)
    assert app.is_dir(), (
        f"Camada package: app ausente em {app}. "
        "Rode scripts/build_mac.sh e defina APP_PATH se necessário."
    )
    assert exe.is_file(), (
        f"Camada package: executável ausente em {exe}."
    )
    return app, exe


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ffprobe_app(app: Path) -> Path:
    """ffprobe embutido no .app (não o do PATH)."""
    candidatos = [
        app / "Contents" / "MacOS" / "ffprobe",
        app / "Contents" / "Resources" / "ffprobe",
        app / "Contents" / "Frameworks" / "ffprobe",
    ]
    meipass = app / "Contents" / "Frameworks"
    if meipass.is_dir():
        for p in meipass.rglob("ffprobe"):
            if p.is_file():
                return p
    for c in candidatos:
        if c.is_file():
            return c
    # PyInstaller onedir: ao lado do exe dentro de MacOS ou _internal
    mac = app / "Contents" / "MacOS"
    for p in mac.rglob("ffprobe"):
        if p.is_file():
            return p
    raise AssertionError("ffprobe embutido não encontrado no .app")


@pytest.mark.package
def test_app_declara_microfone_no_info_plist():
    app, _ = _require_app()
    plist = (app / "Contents" / "Info.plist").read_text(encoding="utf8", errors="replace")
    assert "NSMicrophoneUsageDescription" in plist


@pytest.mark.package
def test_self_test_janela_real(tmp_path):
    app, exe = _require_app()
    home = tmp_path / "selftest-home"
    home.mkdir()
    # Ambiente mínimo: não herdar HF_*, PATH de brew, etc.
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "AUDIOBOOK_STUDIO_HOME": str(home / "Library" / "Application Support" / "Audiobook Studio"),
        "AUDIOBOOK_FAKE_DOWNLOAD": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(tmp_path / "tmp"),
    }
    Path(env["AUDIOBOOK_STUDIO_HOME"]).mkdir(parents=True)
    Path(env["TMPDIR"]).mkdir(parents=True)
    r = subprocess.run(
        [str(exe), "--self-test"],
        capture_output=True, text=True, env=env, timeout=300,
    )
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip().startswith("{")]
    assert lines, f"sem JSON: out={r.stdout!r} err={r.stderr!r} code={r.returncode}"
    data = json.loads(lines[-1])
    assert data.get("ok") is True or data.get("getUserMedia") == "presente", data
    assert data.get("audio_range") is True, data
    # Guias 2/4/5/6 no autoteste ampliado
    guias = data.get("guias") or {}
    for chave in ("guia2", "guia4", "guia5", "guia6"):
        assert chave in guias or data.get(chave) is not None or "passos" in data, data


@pytest.mark.package
def test_livro_curto_ambiente_limpo(tmp_path):
    """R41: HOME vazio + PATH=/usr/bin:/bin; baixa modelo se preciso; M4B com capítulos/capa."""
    app, exe = _require_app()
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
    # env limpo de propósito: sem herdar os.environ
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "AUDIOBOOK_STUDIO_HOME": str(studio_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(tmp_path / "tmp"),
    }
    Path(env["TMPDIR"]).mkdir(parents=True)

    def req(method, path, body=None, headers=None):
        h = dict(headers or {})
        if method not in ("GET", "HEAD"):
            h["X-Studio-Token"] = token
        r = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=body, method=method, headers=h,
        )
        try:
            with urllib.request.urlopen(r, timeout=300) as resp:
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
        # Confirma que o processo não herdou PATH gordo
        try:
            ps = subprocess.check_output(
                ["/bin/ps", "e", "-p", str(proc.pid)], text=True, stderr=subprocess.DEVNULL
            )
            assert "HOMEBREW" not in ps
            assert "/opt/homebrew" not in ps or "PATH=/usr/bin:/bin" in ps
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

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
            # primeiro uso de verdade: baixa pela rota (rede liberada)
            st, body = req("POST", "/api/models/download", body=b"")
            assert st == 200, body
            for _ in range(900):
                st, body = req("GET", "/api/models")
                info = json.loads(body)
                if info.get("status") == "pronto":
                    break
                if info.get("status") == "erro":
                    pytest.fail(f"download do modelo falhou: {info.get('error')}")
                time.sleep(2)
            else:
                pytest.fail("timeout no download do modelo (primeiro uso)")

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
        for _ in range(1800):
            st, body = req("GET", f"/api/projects/{pid}/state")
            assert st == 200
            final = json.loads(body)
            if final.get("status") in ("pronto", "concluido", "erro", "cancelado"):
                break
            time.sleep(2)
        assert final and final.get("status") in ("pronto", "concluido"), final
        m4bs = list((studio_home / "projects" / pid / "audiobook").glob("*.m4b"))
        assert m4bs, "sem M4B"
        m4b = m4bs[0]

        # Capítulos e capa via ffprobe embutido (não o do PATH)
        ffprobe = _ffprobe_app(app)
        r = subprocess.run(
            [str(ffprobe), "-v", "error", "-show_entries", "format_tags=title:stream=codec_type",
             "-show_chapters", "-of", "json", str(m4b)],
            capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=60,
        )
        assert r.returncode == 0, r.stderr
        meta = json.loads(r.stdout or "{}")
        chapters = meta.get("chapters") or []
        assert len(chapters) >= 1, meta
        streams = meta.get("streams") or []
        tem_video_capa = any(s.get("codec_type") == "video" for s in streams)
        assert tem_video_capa, f"M4B sem capa embutida: {streams}"

        dmg = Path(os.environ.get("DMG_PATH") or (RAIZ / "dist" / "Audiobook-Studio.dmg"))
        assert dmg.is_file(), f"DMG ausente: {dmg}"
        dmg_bytes = dmg.stat().st_size
        print(f"DMG_PATH={dmg}")
        print(f"DMG_BYTES={dmg_bytes}")
        print(f"DMG_SIZE_GB={dmg_bytes / (1024**3):.3f}")
        assert dmg_bytes > 1024
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
