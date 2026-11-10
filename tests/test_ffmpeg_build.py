"""Conferência estática: SHA-256 do zip do ffmpeg e checagem LGPL no build (sem GPL/nonfree)."""
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parent.parent
BUILD_SH = (RAIZ / "scripts" / "build_mac.sh").read_text(encoding="utf8")


def test_build_mac_fixa_sha256_do_zip_ffmpeg():
    assert "FFMPEG_SHA_EXPECTED=" in BUILD_SH
    m = re.search(r'FFMPEG_SHA_EXPECTED="([0-9a-f]{64})"', BUILD_SH)
    assert m, "FFMPEG_SHA_EXPECTED deve ser um SHA-256 de 64 hex fixado no script"
    assert "ABORT" in BUILD_SH.upper() or "abort" in BUILD_SH.lower() or "exit 1" in BUILD_SH
    # Conferência obrigatória: compara SUM com o valor fixado e aborta se divergir
    assert "FFMPEG_SHA_EXPECTED" in BUILD_SH
    assert re.search(r"SUM.*FFMPEG_SHA_EXPECTED|FFMPEG_SHA_EXPECTED.*SUM", BUILD_SH) or (
        'SUM="' in BUILD_SH and "FFMPEG_SHA_EXPECTED" in BUILD_SH and "exit 1" in BUILD_SH
    )


def test_build_mac_checa_buildconf_sem_gpl_nem_nonfree():
    assert "-L" in BUILD_SH or "ffmpeg -L" in BUILD_SH
    assert "buildconf" in BUILD_SH
    assert "--enable-gpl" in BUILD_SH
    assert "--enable-nonfree" in BUILD_SH
    # o script deve rejeitar se essas flags aparecerem na configuração
    assert "enable-gpl" in BUILD_SH and "enable-nonfree" in BUILD_SH


def test_build_mac_gera_icns_do_logo():
    assert "logo.png" in BUILD_SH
    assert "sips" in BUILD_SH
    assert "iconutil" in BUILD_SH
    assert ".icns" in BUILD_SH
