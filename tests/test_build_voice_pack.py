"""T20: build_voice_pack com LOCAL_MD sintético (sem package)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "build_voice_pack.py"


def test_build_voice_pack_sem_local_md_sai_claro(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCAL_MD", raising=False)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(tmp_path / "vp")],
        capture_output=True, text=True, cwd=str(RAIZ),
    )
    assert r.returncode == 2
    assert "LOCAL_MD" in r.stderr


def test_build_voice_pack_com_local_md_sintetico(tmp_path, monkeypatch):
    safetensors = tmp_path / "voz.safetensors"
    safetensors.write_bytes(b"fake-weights")
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFF....")
    local = tmp_path / "local.md"
    local.write_text(
        "# x\n\n"
        '## Voz padrão (dono da voz: Teste; rótulo no app: "Voz do Teste")\n\n'
        f"- Exportada: `{safetensors}`\n"
        f"- Referência original: `{ref}`\n",
        encoding="utf8",
    )
    dest = tmp_path / "voice-pack"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--local-md", str(local), "--out", str(dest)],
        capture_output=True, text=True, cwd=str(RAIZ),
    )
    assert r.returncode == 0, r.stderr
    man = json.loads((dest / "manifest.json").read_text(encoding="utf8"))
    assert man == {
        "id": "padrao",
        "label": "Voz do Teste",
        "engine": "pocket",
        "model": "portuguese_24l",
        "file": "voz_portuguese_24l.safetensors",
        "eq": True,
    }
    assert (dest / "voz_portuguese_24l.safetensors").read_bytes() == b"fake-weights"
    assert (dest / "ref.wav").is_file()
    # nenhum caminho pessoal no script
    src = SCRIPT.read_text(encoding="utf8")
    assert "/Users/" not in src
    assert "gabriel" not in src.lower()
