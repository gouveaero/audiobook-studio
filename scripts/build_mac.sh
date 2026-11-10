#!/usr/bin/env bash
# Constrói o .app + .dmg do Audiobook Studio (chip Apple) a partir de um clone limpo.
# R40, R42, R43. Não inclui o modelo Pocket.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x "$RAIZ/.venv/bin/python" ]; then
    PYTHON="$RAIZ/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

echo "== build_mac: raiz $RAIZ =="

# --- ambiente ---
if [ ! -x "$RAIZ/.venv/bin/python" ]; then
  echo "== uv venv =="
  uv venv --python 3.12 "$RAIZ/.venv"
fi
PYTHON="$RAIZ/.venv/bin/python"
echo "== dependências (CPU torch) =="
uv pip install -r "$RAIZ/requirements-dev.txt" --python "$PYTHON"
# reforça torch CPU no Mac arm64 (já vem com pocket-tts; garante índice oficial)
uv pip install --python "$PYTHON" "torch" --index-url https://download.pytorch.org/whl/cpu || true

# --- pacote de voz (opcional) ---
echo "== voice-pack =="
set +e
LOCAL_MD="${LOCAL_MD:-}" "$PYTHON" "$RAIZ/scripts/build_voice_pack.py"
vp=$?
set -e
if [ "$vp" -ne 0 ]; then
  echo "build_mac: sem pacote de voz (código $vp); o app usará a voz de reserva."
fi

# --- ffmpeg / ffprobe LGPL embutidos ---
BIN="$RAIZ/build/bin"
mkdir -p "$BIN"
FFMPEG_VER="8.1.2"
FFMPEG_URL="https://github.com/livefantasia/ffmpeg-macos-build/releases/download/autobuild-2026-08-30/ffmpeg-${FFMPEG_VER}-aarch64-apple-darwin-lgpl.zip"
FFMPEG_SHA_EXPECTED=""  # preenchido após download na primeira execução e documentado em THIRD_PARTY.md
META="$BIN/ffmpeg-source.txt"
if [ ! -x "$BIN/ffmpeg" ] || [ ! -x "$BIN/ffprobe" ]; then
  echo "== baixar ffmpeg LGPL arm64 =="
  TMP="$(mktemp -d -t abs-ffmpeg)"
  curl -fsSL -o "$TMP/ffmpeg.zip" "$FFMPEG_URL"
  SUM="$(shasum -a 256 "$TMP/ffmpeg.zip" | awk '{print $1}')"
  echo "sha256 zip: $SUM"
  unzip -q -o "$TMP/ffmpeg.zip" -d "$TMP/out"
  # achar binários no zip
  FF="$(find "$TMP/out" -type f -name ffmpeg | head -1)"
  FP="$(find "$TMP/out" -type f -name ffprobe | head -1)"
  if [ -z "$FF" ] || [ -z "$FP" ]; then
    echo "build_mac: zip do ffmpeg sem ffmpeg/ffprobe" >&2
    ls -laR "$TMP/out" >&2 || true
    exit 1
  fi
  cp "$FF" "$BIN/ffmpeg"
  cp "$FP" "$BIN/ffprobe"
  chmod +x "$BIN/ffmpeg" "$BIN/ffprobe"
  {
    echo "url=$FFMPEG_URL"
    echo "version=$FFMPEG_VER"
    echo "zip_sha256=$SUM"
    echo "ffmpeg_sha256=$(shasum -a 256 "$BIN/ffmpeg" | awk '{print $1}')"
    echo "ffprobe_sha256=$(shasum -a 256 "$BIN/ffprobe" | awk '{print $1}')"
    echo "license=LGPL-2.1-or-later"
    echo "notes=Build sem --enable-gpl/--enable-nonfree (livefantasia/ffmpeg-macos-build)."
  } > "$META"
  rm -rf "$TMP"
else
  echo "== ffmpeg já em build/bin =="
fi

# --- PyInstaller ---
echo "== PyInstaller =="
rm -rf "$RAIZ/build/pyi" "$RAIZ/dist"
"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$RAIZ/dist" \
  --workpath "$RAIZ/build/pyi" \
  "$RAIZ/scripts/audiobook_studio.spec"

APP="$RAIZ/dist/Audiobook Studio.app"
if [ ! -d "$APP" ]; then
  # às vezes o BUNDLE fica em dist/Audiobook Studio/Audiobook Studio.app
  ALT="$(find "$RAIZ/dist" -maxdepth 2 -type d -name 'Audiobook Studio.app' | head -1)"
  if [ -n "$ALT" ]; then
    APP="$ALT"
  else
    echo "build_mac: .app não encontrado em dist/" >&2
    ls -la "$RAIZ/dist" >&2
    exit 1
  fi
fi

# --- codesign ad hoc ---
echo "== codesign ad hoc =="
codesign --force --deep -s - "$APP"

# --- DMG ---
echo "== dmg =="
STAGE="$(mktemp -d -t abs-dmg)"
cp -R "$APP" "$STAGE/"
DMG="$RAIZ/dist/Audiobook-Studio.dmg"
rm -f "$DMG"
hdiutil create -volname "Audiobook Studio" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

SIZE="$(stat -f%z "$DMG" 2>/dev/null || stat -c%s "$DMG")"
echo "DMG=$DMG"
echo "DMG_BYTES=$SIZE"
python3 - <<PY
b=int("$SIZE")
gb=b/(1024**3)
print(f"DMG_SIZE_GB={gb:.3f}")
if b > int(1.5 * 1024**3):
    print("AVISO: .dmg acima de 1,5 GB (R42)")
PY

# --- autoteste (R43) ---
echo "== self-test =="
export AUDIOBOOK_STUDIO_HOME="${AUDIOBOOK_STUDIO_HOME:-$(mktemp -d -t abs-selfhome)}"
EXE="$APP/Contents/MacOS/Audiobook Studio"
if [ -x "$EXE" ]; then
  set +e
  "$EXE" --self-test | tee "$RAIZ/dist/self-test.json"
  st=${PIPESTATUS[0]}
  set -e
  echo "self-test exit=$st"
else
  echo "build_mac: executável não encontrado em $EXE" >&2
  ls -la "$APP/Contents/MacOS" >&2 || true
  exit 1
fi

echo "build_mac: ok"
