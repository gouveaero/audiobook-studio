"""T20: checagens estáticas do instalador (sem build completo)."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SPEC = (RAIZ / "scripts" / "audiobook_studio.spec").read_text(encoding="utf8")
BUILD_SH = (RAIZ / "scripts" / "build_mac.sh").read_text(encoding="utf8")
REQ = (RAIZ / "requirements-dev.txt").read_text(encoding="utf8")


def test_pyinstaller_fixado_em_requirements_dev():
    assert re.search(r"pyinstaller==\d+\.\d+", REQ)


def test_spec_sem_modelo_nem_omnivoice():
    assert "omnivoice" in SPEC  # aparece em excludes
    assert "excludes" in SPEC
    assert "model.safetensors" in SPEC  # filtrado dos datas
    assert "BUNDLE" in SPEC
    assert "NSMicrophoneUsageDescription" in SPEC
    assert "Audiobook Studio" in SPEC
    assert "arm64" in SPEC
    # não embute o download do modelo
    assert "pocket-tts-without-voice-cloning" not in SPEC


def test_build_mac_usa_codesign_adhoc_e_ffmpeg_lgpl():
    assert "codesign" in BUILD_SH and '-s -' in BUILD_SH
    assert "ffmpeg" in BUILD_SH and "ffprobe" in BUILD_SH
    assert "LGPL" in BUILD_SH or "lgpl" in BUILD_SH.lower()
    assert "self-test" in BUILD_SH
    assert "uv venv" in BUILD_SH or "uv pip" in BUILD_SH
    assert "FFMPEG_SHA_EXPECTED=" in BUILD_SH
    assert "iconutil" in BUILD_SH and "sips" in BUILD_SH
    assert "buildconf" in BUILD_SH


def test_build_mac_falha_se_self_test_falhar():
    """O .dmg pode ficar em dist/, mas o script não pode sair 0 com self-test exit≠0."""
    assert "self-test exit=" in BUILD_SH
    assert re.search(r'\[ "\$st" -ne 0 \]', BUILD_SH) or 'st" -ne 0' in BUILD_SH
    assert re.search(r'exit "\$st"|exit \$st', BUILD_SH)


def test_spec_coleta_scipy_para_pocket():
    assert "scipy" in SPEC
    assert "array_api_compat" in SPEC or "collect_all" in SPEC


def test_third_party_menciona_ffmpeg_embutido():
    tp = (RAIZ / "THIRD_PARTY.md").read_text(encoding="utf8")
    assert "ffmpeg" in tp.lower()
    assert "LGPL" in tp or "GPL" in tp


def test_boot_e_paths_existem():
    assert (RAIZ / "studio" / "boot.py").is_file()
    assert (RAIZ / "studio" / "paths.py").is_file()
    assert (RAIZ / "studio" / "webview_patch.py").is_file()
    assert (RAIZ / "studio" / "selftest.py").is_file()
    assert (RAIZ / "studio" / "selftest_engine.py").is_file()
    boot = (RAIZ / "studio" / "boot.py").read_text(encoding="utf8")
    assert "_worker" in boot
    assert "self-test" in boot or "self_test" in boot
    app = (RAIZ / "studio" / "app.py").read_text(encoding="utf8")
    assert "studio.selftest" in app
