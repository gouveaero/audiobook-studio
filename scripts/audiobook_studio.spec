# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: pasta + .app (chip Apple). Sem modelo Pocket e sem OmniVoice.
import os
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.osx import BUNDLE
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all

block_cipher = None
# SPECPATH pode ser a pasta do .spec (scripts/) ou o cwd (raiz do repo).
_sp = Path(SPECPATH).resolve()
if (_sp / "studio" / "boot.py").is_file():
    RAIZ = _sp
elif (_sp.parent / "studio" / "boot.py").is_file():
    RAIZ = _sp.parent
else:
    raise SystemExit(f"audiobook_studio.spec: studio/boot.py não encontrado a partir de SPECPATH={SPECPATH!r}")

datas = [
    (str(RAIZ / "ui"), "ui"),
    (str(RAIZ / "assets"), "assets"),
]
voice = RAIZ / "build" / "voice-pack"
if voice.is_dir() and (voice / "manifest.json").is_file():
    datas.append((str(voice), "voice-pack"))

binaries = []
bin_dir = RAIZ / "build" / "bin"
for nome in ("ffmpeg", "ffprobe"):
    p = bin_dir / nome
    if p.is_file():
        binaries.append((str(p), "."))

hiddenimports = [
    "studio", "studio.app", "studio.server", "studio.generate", "studio.assemble",
    "studio.prepare_book", "studio.prepare_voice", "studio.local_api", "studio.audio",
    "studio.engines", "studio.engines.pocket", "studio.normalize_pt", "studio.boot",
    "studio.paths", "studio.webview_patch", "studio.brand", "studio.wavio",
    "studio.selftest_engine", "studio.selftest",
    "pocket_tts", "num2words", "webview",
]

# scipy: o Pocket importa scipy.io.wavfile → sparse → array_api_compat.numpy.fft;
# sem collect_all o .app quebra na geração com ModuleNotFoundError.
for pkg in ("pocket_tts", "webview", "num2words", "scipy"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass
try:
    from PyInstaller.utils.hooks import collect_submodules
    hiddenimports += collect_submodules("scipy._external")
except Exception:
    pass
hiddenimports += [
    "scipy._external.array_api_compat.numpy",
    "scipy._external.array_api_compat.numpy.fft",
    "scipy._external.array_api_compat.numpy.linalg",
]

a = Analysis(
    [str(RAIZ / "studio" / "boot.py")],
    pathex=[str(RAIZ)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["omnivoice", "torchvision", "torchaudio"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Modelo e OmniVoice fora do instalador
a.datas = [
    d for d in a.datas
    if "omnivoice" not in str(d[0]).lower()
    and "model.safetensors" not in str(d[0]).replace("\\", "/").lower()
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Audiobook Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Audiobook Studio",
)

_icns_env = os.environ.get("AUDIOBOOK_ICNS", "").strip()
_icns = Path(_icns_env) if _icns_env else (RAIZ / "build" / "AppIcon.icns")
_icon = str(_icns) if _icns.is_file() else None

app = BUNDLE(
    coll,
    name="Audiobook Studio.app",
    icon=_icon,
    bundle_identifier="studio.audiobook.app",
    info_plist={
        "CFBundleName": "Audiobook Studio",
        "CFBundleDisplayName": "Audiobook Studio",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": (
            "O Audiobook Studio usa o microfone só quando você grava a sua voz "
            "para narrar o audiolivro."
        ),
        "LSMinimumSystemVersion": "12.0",
    },
)
