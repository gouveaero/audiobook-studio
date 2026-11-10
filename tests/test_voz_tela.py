"""T17 (R22 a R26): tela de voz, padrão, prontas, clonagem guiada e checagem da gravação."""
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.test_servidor_base import Servidor, _wav_bytes

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "ui"


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    monkeypatch.setenv("AUDIOBOOK_PREVIEW_MOTOR", FAKE_ENGINE)
    monkeypatch.delenv("VOICE_PACK_DIR", raising=False)
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-voz", project=None)
    yield s
    s.close()


def auth(s, extra=None):
    h = {"X-Studio-Token": s.token}
    if extra:
        h.update(extra)
    return h


def _wav_tom(segundos=8.0, rate=16000, freq=440.0, amp=0.25) -> bytes:
    """WAV com tom audível (passa na checagem de volume/duração)."""
    n = int(rate * segundos)
    t = np.arange(n, dtype=np.float64) / rate
    samples = (np.sin(2 * np.pi * freq * t) * amp * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def _wav_graves(segundos=8.0, rate=16000) -> bytes:
    """Quase só graves (EQ liga; sem aviso de regravação por graves)."""
    n = int(rate * segundos)
    t = np.arange(n, dtype=np.float64) / rate
    samples = (np.sin(2 * np.pi * 80.0 * t) * 0.35 * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def test_voice_html_sem_travessao_nem_google_fonts():
    html = (UI / "voice.html").read_text(encoding="utf8")
    assert "—" not in html
    assert "fonts.googleapis.com" not in html
    assert "fonts.css" in html
    assert "studio.js" in html
    assert "Claude Code" not in html


def test_r22_voz_padrao_ou_fallback_selecionada_sem_login(api, casa, monkeypatch, tmp_path):
    # Sem pacote: VOICE_PACK_DIR sem manifest desliga também o build/voice-pack local
    monkeypatch.setenv("VOICE_PACK_DIR", str(tmp_path / "sem-pacote"))
    (tmp_path / "sem-pacote").mkdir()
    data = json.loads(api.req("GET", "/api/voices")[2])
    assert data["selected"] == "rafael"
    assert data["hf_logged_in"] is False
    assert any(v["id"] == "rafael" for v in data["voices"])

    pack = tmp_path / "voice-pack"
    pack.mkdir()
    (pack / "manifest.json").write_text(json.dumps({
        "id": "padrao", "label": "Voz do teste", "engine": "pocket",
        "model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors", "eq": True,
    }), encoding="utf8")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    data = json.loads(api.req("GET", "/api/voices")[2])
    assert data["selected"] == "padrao"
    assert data["hf_logged_in"] is False


def test_r23_ouvir_voz_pronta_com_motor_falso(api, casa):
    st, headers, body = api.req(
        "POST", "/api/voices/preview",
        body=json.dumps({"voice_id": "rafael"}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, body[:500]
    assert "audio" in (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    assert body[:4] == b"RIFF"
    assert len(body) > 1000


@pytest.mark.model
def test_r23_ouvir_voz_pronta_com_pocket_real(tmp_path, monkeypatch):
    """Preview com Pocket real; o Maestro roda na fila de modelo."""
    import os
    import subprocess
    import sys

    casa = tmp_path / "app-home"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HF_") and k not in ("HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE")}
    env["AUDIOBOOK_STUDIO_HOME"] = str(casa)
    env["PYTHONPATH"] = str(RAIZ)
    # sem AUDIOBOOK_PREVIEW_MOTOR → pocket
    prog = r"""
import os, sys
from pathlib import Path
from studio.brand import ensure_dirs, VOICE_FALLBACK
from studio import local_api as la
ensure_dirs()
# garante embedding (pode usar rede nesta camada model)
la.garantir_embedding_voz(VOICE_FALLBACK)
p = la.preview_voice(VOICE_FALLBACK)
assert p.is_file() and p.stat().st_size > 1000
print("ok", p)
"""
    r = subprocess.run([sys.executable, "-c", prog], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:] + r.stdout[-500:]


def test_select_voz_pronta_persiste_e_baixa_ou_aviso(api, casa, monkeypatch):
    from studio import local_api as la

    # já "local": não chama rede
    monkeypatch.setattr(la, "embedding_local", lambda nome: Path("/tmp/fake.safetensors") if nome == "rafael" else None)
    monkeypatch.setattr(la, "garantir_embedding_voz", lambda nome, on_progress=None: Path("/tmp/fake.safetensors"))
    st, _, b = api.req(
        "POST", "/api/voices/select",
        body=json.dumps({"voice_id": "rafael"}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    data = json.loads(b)
    assert data["selected"] == "rafael"
    settings = json.loads((casa / "settings.json").read_text(encoding="utf8"))
    assert settings["voice_id"] == "rafael"

    def falha(_nome, on_progress=None):
        raise ConnectionError(la.MSG_SEM_CONEXAO_VOZ)

    monkeypatch.setattr(la, "embedding_local", lambda nome: None)
    monkeypatch.setattr(la, "garantir_embedding_voz", falha)
    st, _, b = api.req(
        "POST", "/api/voices/select",
        body=json.dumps({"voice_id": "cosette"}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 503
    err = json.loads(b)["error"]
    assert "internet" in err.lower() or "conexão" in err.lower() or "conecte" in err.lower()
    assert "Traceback" not in err


def test_r24_clonagem_exige_declaracao_e_guia_hf(api, casa):
    html = (UI / "voice.html").read_text(encoding="utf8")
    assert "Declaro que esta voz é minha" in html or "autorização" in html
    assert "Hugging Face" in html
    assert "token" in html.lower()
    assert "Gravar" in html
    assert "Enviar arquivo" in html or "arquivo" in html.lower()

    st, _, b = api.req(
        "POST", "/api/voices", body=_wav_tom(6),
        headers=auth(api, {"Content-Type": "audio/wav", "X-Consent": "false"}),
    )
    assert st == 400
    assert "declaração" in json.loads(b)["error"].lower() or "autorização" in json.loads(b)["error"].lower()

    data = json.loads(api.req("GET", "/api/voices")[2])
    assert data["terms_guide"]
    assert any("Pocket" in t or "termos" in t.lower() for t in data["terms_guide"])
    assert "clone_blocked" in data


def test_r25_aviso_curta_baixa_e_graves_so_eq(api, casa):
    # curta + baixa (silêncio 0,5 s)
    st, _, b = api.req(
        "POST", "/api/voices", body=_wav_bytes(0.5),
        headers=auth(api, {
            "Content-Type": "audio/wav", "X-Consent": "true",
            "X-Voice-Label": "Curta", "X-Voice-Text": "teste",
        }),
    )
    assert st == 200, b
    data = json.loads(b)
    warns = " ".join(data.get("warnings") or []).lower()
    assert "curta" in warns
    assert "baixa" in warns

    # graves: EQ ligado, sem aviso de graves/regravar por graves
    st, _, b = api.req(
        "POST", "/api/voices", body=_wav_graves(8),
        headers=auth(api, {
            "Content-Type": "audio/wav", "X-Consent": "true",
            "X-Voice-Label": "Graves", "X-Voice-Text": "teste graves",
        }),
    )
    assert st == 200, b
    data = json.loads(b)
    assert data["eq"] is True
    # excesso de graves não gera aviso de regravação (R25)
    assert not (data.get("warnings") or [])


def test_voice_html_serve_e_fluxo_anexa_ao_projeto(api, casa, monkeypatch):
    from studio import local_api as la

    monkeypatch.setattr(la, "garantir_embedding_voz", lambda nome, on_progress=None: Path("/tmp/x.safetensors"))

    st, _, body = api.req("GET", "/voice.html")
    assert st == 200
    html = body.decode("utf8")
    assert "Escolher a voz" in html
    assert "Usar a minha voz" in html
    assert "Ouvir" in html

    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto."]),
    ], config={"motor": FAKE_ENGINE})
    st, _, b = api.req(
        "POST", "/api/voices/select",
        body=json.dumps({"voice_id": "rafael"}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    st, _, b = api.req(
        "POST", f"/api/projects/{proj.name}/voice",
        body=json.dumps({"voice_id": "rafael"}).encode(),
        headers=auth(api, {"Content-Type": "application/json"}),
    )
    assert st == 200, b
    man = json.loads((proj / "voice" / "manifest.json").read_text(encoding="utf8"))
    assert man.get("name") == "rafael" or man.get("id") == "rafael"


def test_checar_gravacao_unitario(casa, tmp_path):
    from studio.local_api import (
        AVISO_GRAVACAO_BAIXA, AVISO_GRAVACAO_CURTA, checar_gravacao,
    )
    from studio.wavio import write_wav

    curto = tmp_path / "curto.wav"
    write_wav(str(curto), np.zeros(8000, dtype=np.float32), 16000)  # 0,5 s silêncio
    w = checar_gravacao(curto)
    assert AVISO_GRAVACAO_CURTA in w
    assert AVISO_GRAVACAO_BAIXA in w

    bom = tmp_path / "bom.wav"
    t = np.arange(16000 * 8, dtype=np.float32) / 16000
    write_wav(str(bom), (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), 16000)
    assert checar_gravacao(bom) == []
