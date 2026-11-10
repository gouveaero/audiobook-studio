"""T14 (R33, R34, R30, R38): pastas do app, brand, token, Host, Range e UI com token."""
import io
import json
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import wave
from http.client import HTTPConnection
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


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


def _hdr(headers, name):
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return ""


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
        from studio.brand import ensure_dirs

        ensure_dirs()
        self.port = port or _porta_livre()
        self.token = token
        self.srv = srv
        srv.P = str(project) if project else ""
        srv.SESSION_TOKEN = token
        srv.PORT = self.port
        srv.JOBS.clear()
        srv.HIST.clear()
        self.httpd = srv.make_server(self.port)
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


def test_sem_token_configurado_escrita_e_403(casa, projeto_falso):
    s = Servidor(token="", project=projeto_falso)
    try:
        status, _, _ = s.req(
            "POST", "/api/config",
            body=json.dumps({"voz": "x"}).encode(),
            headers={"Content-Type": "application/json", "X-Studio-Token": ""},
        )
        assert status == 403
    finally:
        s.close()


def test_put_e_delete_sem_token_sao_403(servidor):
    for method in ("PUT", "DELETE"):
        status, _, _ = servidor.req(method, "/api/projects/x/book", body=b"{}")
        assert status == 403, method


def test_put_e_delete_com_host_errado_sao_403(servidor):
    for method in ("PUT", "DELETE"):
        status, _, _ = servidor.req(
            method, "/api/projects/x/book",
            body=b"{}",
            headers={"X-Studio-Token": servidor.token},
            host="evil.example",
        )
        assert status == 403, method


def test_post_com_token_certo_e_host_errado_e_403(servidor):
    status, _, _ = servidor.req(
        "POST", "/api/config",
        body=json.dumps({"voz": "x"}).encode(),
        headers={"Content-Type": "application/json", "X-Studio-Token": servidor.token},
        host="evil.example",
    )
    assert status == 403


def test_get_nunca_devolve_token_de_sessao(servidor):
    for path in ("/config.json", "/api/projects", "/api/state"):
        status, _, body = servidor.req("GET", path)
        assert status == 200, path
        assert servidor.token.encode() not in body
        assert b"X-Studio-Token" not in body


def test_make_server_liga_em_loopback():
    from studio import server as srv

    port = _porta_livre()
    httpd = srv.make_server(port)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
        assert httpd.server_address[1] == port
    finally:
        httpd.server_close()


def test_processo_server_responde_e_nao_imprime_token(casa, tmp_path):
    port = _porta_livre()
    token = "segredo-processo-xyz"
    env = os.environ.copy()
    env["AUDIOBOOK_STUDIO_HOME"] = str(casa)
    proc = subprocess.Popen(
        [sys.executable, "-m", "studio.server", "--port", str(port), "--token", token],
        cwd=RAIZ,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        ok = False
        for _ in range(40):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/api/projects", headers={"Host": f"127.0.0.1:{port}"})
                r = conn.getresponse()
                body = r.read()
                conn.close()
                if r.status == 200:
                    ok = True
                    assert json.loads(body) == {"projects": []}
                    break
            except OSError:
                time.sleep(0.1)
        assert ok, "servidor não respondeu em 127.0.0.1"
    finally:
        proc.terminate()
        out, err = proc.communicate(timeout=5)
    texto = (out or b"").decode("utf-8", "replace") + (err or b"").decode("utf-8", "replace")
    assert token not in texto


def test_abrir_sem_project_lista_vazia(casa):
    s = Servidor(token="tok-livre", project=None)
    try:
        status, _, body = s.req("GET", "/api/projects")
        assert status == 200
        assert json.loads(body) == {"projects": []}
    finally:
        s.close()


def test_app_aceita_abrir_sem_project():
    from studio import app as appmod

    ns = appmod.build_parser().parse_args([])
    assert ns.project is None


# ---------- Range e áudio (R30) ----------

def test_range_variantes_e_sem_range(servidor, projeto_falso):
    audio = _wav_bytes(1.0)  # ~32 KB
    assert len(audio) > 250
    wav = Path(projeto_falso) / "voice" / "ref.wav"
    wav.write_bytes(audio)
    size = len(audio)

    status, headers, body = servidor.req("GET", "/voice/ref.wav", headers={"Range": "bytes=100-199"})
    assert status == 206
    assert _hdr(headers, "Content-Range") == f"bytes 100-199/{size}"
    assert body == audio[100:200]

    status, headers, body = servidor.req("GET", "/voice/ref.wav", headers={"Range": "bytes=100-"})
    assert status == 206
    assert _hdr(headers, "Content-Range") == f"bytes 100-{size - 1}/{size}"
    assert body == audio[100:]

    status, headers, body = servidor.req("GET", "/voice/ref.wav", headers={"Range": "bytes=-50"})
    assert status == 206
    assert _hdr(headers, "Content-Range") == f"bytes {size - 50}-{size - 1}/{size}"
    assert body == audio[-50:]

    status, headers, body = servidor.req("GET", "/voice/ref.wav", headers={"Range": f"bytes={size + 10}-{size + 20}"})
    assert status == 416

    status, headers, body = servidor.req("GET", "/voice/ref.wav")
    assert status == 200
    assert _hdr(headers, "Accept-Ranges") == "bytes"
    assert body == audio


def test_range_em_m4a_do_projeto(servidor, projeto_falso):
    data = b"fake-m4a-header" + os.urandom(400)
    path = Path(projeto_falso) / "chapters" / "01.m4a"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    status, headers, body = servidor.req("GET", "/chapters/01.m4a", headers={"Range": "bytes=10-19"})
    assert status == 206
    assert body == data[10:20]
    assert _hdr(headers, "Content-Type").startswith("audio/")


def test_caminho_com_ponto_ponto_nao_escapa(servidor, projeto_falso, tmp_path):
    segredo = RAIZ / "ui" / "favicon.png"
    assert segredo.is_file()
    # tentativa de sair do projeto
    status, _, _ = servidor.req("GET", "/voice/../../ui/favicon.png")
    assert status in (403, 404)
    status, _, _ = servidor.req("GET", "/chapters/../../../studio/server.py")
    assert status in (403, 404)


# ---------- UI: token nas escritas ----------

def test_excecao_grava_log_sem_tokens(casa, projeto_falso, monkeypatch):
    """R38: detalhe no log sob AUDIOBOOK_STUDIO_HOME; tokens não aparecem."""
    from studio import server as srv

    s = Servidor(token="tok-secreto-sessao", project=projeto_falso)
    try:
        def boom(*a, **k):
            raise RuntimeError("falha com tok-secreto-sessao e hf_" + ("x" * 24))

        monkeypatch.setattr(srv, "jload", boom)
        status, _, body = s.req(
            "POST", "/api/config",
            body=json.dumps({"voz": "x"}).encode(),
            headers={"Content-Type": "application/json", "X-Studio-Token": s.token},
        )
        assert status == 500
        assert b"traceback" not in body.lower()
        assert b"tok-secreto" not in body
        log = casa / "logs" / "server.log"
        assert log.is_file()
        texto = log.read_text(encoding="utf8")
        assert "RuntimeError" in texto
        assert "tok-secreto-sessao" not in texto
        assert "hf_" + ("x" * 24) not in texto
        assert "[sessao]" in texto or "[hf]" in texto
    finally:
        s.close()


def test_ui_tem_ajudante_de_token():
    helper = (RAIZ / "ui" / "studio.js").read_text(encoding="utf-8")
    assert "X-Studio-Token" in helper
    assert "sessionStorage" in helper
    assert "studioWrite" in helper or "studioFetch" in helper


def test_paginas_ui_nao_fazem_escrita_fora_do_ajudante():
    """Toda fetch/XMLHttpRequest de escrita em ui/ passa pelo ajudante com token."""
    helper_names = ("studioWrite", "studioFetch", "studio.post", "studio.put", "studio.del", "studio.delete")
    # fetch(url, { method: "POST" ... }) direto é proibido; post() local que não usa o ajudante também
    direto = re.compile(
        r"""fetch\s*\([^)]*\{[^}]*method\s*:\s*['"](POST|PUT|DELETE)['"]""",
        re.IGNORECASE | re.DOTALL,
    )
    xhr = re.compile(r"""\.open\s*\(\s*['"](POST|PUT|DELETE)['"]""", re.IGNORECASE)
    problemas = []
    for path in sorted((RAIZ / "ui").glob("*.html")):
        texto = path.read_text(encoding="utf-8")
        if "studio.js" not in texto and ("fetch(" in texto or "XMLHttpRequest" in texto):
            # páginas com script próprio precisam incluir o ajudante se tiverem escrita
            if direto.search(texto) or xhr.search(texto) or re.search(r"""method:\s*["']POST""", texto):
                problemas.append(f"{path.name}: escrita sem incluir studio.js")
                continue
        if direto.search(texto):
            problemas.append(f"{path.name}: fetch de escrita direto, use o ajudante")
        if xhr.search(texto):
            problemas.append(f"{path.name}: XHR de escrita direto, use o ajudante")
        # função post local que chama fetch sem studio
        if re.search(r"""async function post\s*\([^)]*\)\s*\{[^}]*fetch\s*\([^)]*method:\s*["']POST["']""", texto, re.DOTALL):
            if not any(h in texto for h in helper_names):
                problemas.append(f"{path.name}: post() local sem ajudante de token")
    assert not problemas, "\n".join(problemas)
