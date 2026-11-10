"""T14 (R33, R34, R30): pastas do app, brand, abrir sem --project, token, Host e Range."""
import io
import json
import socket
import struct
import threading
import wave
from http.client import HTTPConnection
from pathlib import Path

import pytest


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wav_bytes(segundos=1.0, rate=16000) -> bytes:
    n = int(rate * segundos)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
    return buf.getvalue()


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


def test_brand_centraliza_nome_e_urls_vazias():
    from studio import brand

    assert brand.APP_NAME == "Audiobook Studio"
    assert brand.VOICE_FALLBACK == "rafael"
    assert brand.DONATION_URL == ""
    assert brand.ANDROID_WAITLIST_URL == ""


def test_pastas_do_app_sob_audio_book_studio_home(casa):
    from studio.brand import ensure_dirs, app_home

    assert app_home() == casa
    ensure_dirs()
    assert (casa / "hf").is_dir()
    assert (casa / "voices").is_dir()
    assert (casa / "projects").is_dir()
    assert (casa / "settings.json").is_file()


class Servidor:
    """Sobe studio.server numa thread com token conhecido."""

    def __init__(self, token="tok-teste", project=None, port=None):
        from studio import server as srv

        self.port = port or _porta_livre()
        self.token = token
        self.srv = srv
        srv.P = str(project) if project else ""
        srv.SESSION_TOKEN = token
        srv.PORT = self.port
        srv.JOBS.clear()
        srv.HIST.clear()
        self.httpd = srv.ThreadingHTTPServer(("127.0.0.1", self.port), srv.H)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def req(self, method, path, body=None, headers=None, host=None):
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if headers:
            h.update(headers)
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, dict(r.getheaders()), data


@pytest.fixture
def servidor(casa, projeto_falso):
    from studio.brand import ensure_dirs

    ensure_dirs()
    s = Servidor(project=projeto_falso)
    yield s
    s.close()


def test_servidor_recusa_host_errado_em_get(servidor):
    status, _, _ = servidor.req("GET", "/api/state", host="evil.example")
    assert status == 403


def test_servidor_recusa_post_sem_token(servidor):
    status, _, body = servidor.req(
        "POST", "/api/config",
        body=json.dumps({"voz": "x"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert status == 403
    assert b"traceback" not in body.lower()


def test_servidor_aceita_post_com_token_e_host(servidor):
    status, _, body = servidor.req(
        "POST", "/api/config",
        body=json.dumps({"voz": "teste"}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Studio-Token": servidor.token,
        },
    )
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_get_nao_exige_token(servidor):
    status, _, body = servidor.req("GET", "/api/state")
    assert status == 200
    assert "total" in json.loads(body)


def test_range_em_audio_devolve_206(servidor, projeto_falso):
    audio = _wav_bytes(0.5)
    wav = Path(projeto_falso) / "voice" / "ref.wav"
    wav.write_bytes(audio)
    status, headers, body = servidor.req(
        "GET", "/voice/ref.wav",
        headers={"Range": "bytes=0-99"},
    )
    assert status == 206
    assert headers.get("Content-Range", headers.get("content-range", "")).startswith("bytes 0-99/")
    assert len(body) == 100
    assert headers.get("Accept-Ranges", headers.get("accept-ranges")) == "bytes"


def test_abrir_sem_project_cria_pastas_e_responde(casa, monkeypatch):
    from studio.brand import ensure_dirs
    from studio import server as srv

    ensure_dirs()
    port = _porta_livre()
    srv.P = ""
    srv.SESSION_TOKEN = "tok-livre"
    srv.PORT = port
    srv.JOBS.clear()
    httpd = srv.ThreadingHTTPServer(("127.0.0.1", port), srv.H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/projects", headers={"Host": f"127.0.0.1:{port}"})
        r = conn.getresponse()
        body = r.read()
        conn.close()
        # T14: a rota pode ainda ser 404 até T15; o importante é o servidor subir sem --project
        # e escutar só em 127.0.0.1. Aqui conferimos que o bind local responde.
        assert r.status in (200, 404)
        assert isinstance(body, (bytes, bytearray))
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_app_aceita_abrir_sem_project(monkeypatch):
    """app.main não exige --project (R35 / design)."""
    import argparse
    from studio import app as appmod

    ap = argparse.ArgumentParser()
    # Reusa a mesma definição que main() usará: --project opcional
    ap.add_argument("--project", default=None)
    ap.add_argument("--page", choices=["setup", "dashboard", "home", "review", "voice", "ready"], default="home")
    ap.add_argument("--port", type=int, default=8791)
    ns = ap.parse_args([])
    assert ns.project is None

    # Confirma que o argparse real do módulo também aceita
    parser = appmod.build_parser()
    ns2 = parser.parse_args([])
    assert ns2.project is None


def test_servidor_escuta_somente_loopback():
    from studio import server as srv
    import inspect
    src = inspect.getsource(srv)
    assert '("127.0.0.1"' in src or "('127.0.0.1'" in src
    assert "0.0.0.0" not in src
