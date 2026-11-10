"""Raiz de recursos e binários embutidos (dev vs app empacotado)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Pasta com ui/, fonts, ffmpeg embutido e voice-pack no app empacotado."""
    env = os.environ.get("AUDIOBOOK_RESOURCE_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        candidatos = []
        if meipass:
            candidatos.append(Path(meipass))
        mac_os = Path(sys.executable).resolve().parent
        contents = mac_os.parent
        candidatos.extend([
            mac_os,
            contents / "Resources",
            contents / "Frameworks",
            contents / "Frameworks" / "Audiobook Studio",
        ])
        for cand in candidatos:
            if cand and (cand / "ui").is_dir():
                return cand
        return Path(meipass) if meipass else mac_os
    return repo_root()


def voice_pack_bundled() -> Path | None:
    """Pacote no app empacotado, ou build/voice-pack no desenvolvimento."""
    if getattr(sys, "frozen", False):
        for base in (resource_dir(),):
            for cand in (base / "voice-pack", base / "build" / "voice-pack"):
                if cand.is_dir() and (cand / "manifest.json").is_file():
                    return cand
        return None
    # Desenvolvimento: só se VOICE_PACK_DIR não estiver forçando outro lugar;
    # build/voice-pack existe após build_voice_pack.py (fora do git).
    if os.environ.get("VOICE_PACK_DIR", "").strip() == "":
        cand = repo_root() / "build" / "voice-pack"
        if cand.is_dir() and (cand / "manifest.json").is_file():
            return cand
    return None


def _bin(nome: str) -> str:
    """No app empacotado, preferir binário embutido; no dev, o PATH (Homebrew)."""
    bases = []
    if getattr(sys, "frozen", False) or os.environ.get("AUDIOBOOK_BUNDLED_FFMPEG", "").strip():
        bases.extend([resource_dir(), resource_dir() / "bin", repo_root() / "build" / "bin"])
    for base in bases:
        cand = base / nome
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    found = shutil.which(nome)
    if found:
        return found
    return nome


def ffmpeg_bin() -> str:
    return _bin("ffmpeg")


def ffprobe_bin() -> str:
    return _bin("ffprobe")
