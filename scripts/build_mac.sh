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

# --- ícone .icns a partir de assets/logo.png (sips + iconutil) ---
echo "== icns =="
LOGO="$RAIZ/assets/logo.png"
ICNS_DIR="$RAIZ/build/AppIcon.iconset"
ICNS_OUT="$RAIZ/build/AppIcon.icns"
if [ ! -f "$LOGO" ]; then
  echo "build_mac: assets/logo.png ausente" >&2
  exit 1
fi
rm -rf "$ICNS_DIR"
mkdir -p "$ICNS_DIR"
for sz in 16 32 128 256 512; do
  sips -z "$sz" "$sz" "$LOGO" --out "$ICNS_DIR/icon_${sz}x${sz}.png" >/dev/null
  sips -z $((sz * 2)) $((sz * 2)) "$LOGO" --out "$ICNS_DIR/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$ICNS_DIR" -o "$ICNS_OUT"
test -f "$ICNS_OUT"
export AUDIOBOOK_ICNS="$ICNS_OUT"

# --- ffmpeg / ffprobe LGPL embutidos ---
BIN="$RAIZ/build/bin"
mkdir -p "$BIN"
FFMPEG_VER="8.1.2"
FFMPEG_URL="https://github.com/livefantasia/ffmpeg-macos-build/releases/download/autobuild-2026-08-30/ffmpeg-${FFMPEG_VER}-aarch64-apple-darwin-lgpl.zip"
# SHA-256 do zip (origem não oficial: livefantasia/ffmpeg-macos-build). Abortar se não bater.
FFMPEG_SHA_EXPECTED="61163696da382f2c5aa7a7babe4abeb1ff7636e364db6a165e93059adfb13cd2"
META="$BIN/ffmpeg-source.txt"
NEED_FF=0
if [ ! -x "$BIN/ffmpeg" ] || [ ! -x "$BIN/ffprobe" ]; then
  NEED_FF=1
fi
if [ "$NEED_FF" -eq 1 ]; then
  echo "== baixar ffmpeg LGPL arm64 =="
  TMP="$(mktemp -d -t abs-ffmpeg)"
  curl -fsSL -o "$TMP/ffmpeg.zip" "$FFMPEG_URL"
  SUM="$(shasum -a 256 "$TMP/ffmpeg.zip" | awk '{print $1}')"
  echo "sha256 zip: $SUM"
  if [ "$SUM" != "$FFMPEG_SHA_EXPECTED" ]; then
    echo "build_mac: ABORT — SHA-256 do zip do ffmpeg não confere." >&2
    echo "  esperado: $FFMPEG_SHA_EXPECTED" >&2
    echo "  obtido:   $SUM" >&2
    rm -rf "$TMP"
    exit 1
  fi
  unzip -q -o "$TMP/ffmpeg.zip" -d "$TMP/out"
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

# Conferência LGPL do binário embutido (ffmpeg -L e -buildconf)
echo "== ffmpeg -L / -buildconf (sem --enable-gpl/--enable-nonfree) =="
"$BIN/ffmpeg" -L >"$BIN/ffmpeg-L.txt" 2>&1 || true
"$BIN/ffmpeg" -buildconf >"$BIN/ffmpeg-buildconf.txt" 2>&1 || true
if grep -E -- '--enable-gpl|--enable-nonfree' "$BIN/ffmpeg-buildconf.txt" >/dev/null; then
  echo "build_mac: ABORT — ffmpeg embutido declara --enable-gpl ou --enable-nonfree" >&2
  cat "$BIN/ffmpeg-buildconf.txt" >&2
  exit 1
fi
if ! grep -qi 'Lesser General Public License\|LGPL' "$BIN/ffmpeg-L.txt"; then
  echo "build_mac: ABORT — ffmpeg -L não indica LGPL" >&2
  cat "$BIN/ffmpeg-L.txt" >&2
  exit 1
fi
echo "ffmpeg LGPL ok"

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
export AUDIOBOOK_FAKE_DOWNLOAD=1
export AUDIOBOOK_PREVIEW_MOTOR="${AUDIOBOOK_PREVIEW_MOTOR:-studio.selftest_engine:SelftestEngine}"
export FAKE_ENGINE_DELAY="${FAKE_ENGINE_DELAY:-0.05}"
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
