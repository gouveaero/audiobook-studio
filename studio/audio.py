"""Tratamento de áudio ao juntar os trechos de um capítulo (virada, EQ e volume).

Valores de design.md, seção Áudio. Não gera voz de novo: só processa os WAV em cache.
"""
import json
import os
import re
import subprocess
import tempfile

import numpy as np

from studio.wavio import read_wav, write_wav

SILENCE_BEFORE_TITLE = 1.5
SILENCE_AFTER_TITLE = 1.0
TITLE_ATEMPO = 0.92
TITLE_VOLUME_DB = 2.5
TARGET_LUFS = -21.0
EQ_FILTER = (
    "highpass=f=80,"
    "equalizer=f=220:width_type=o:w=1.2:g=-2.5,"
    "equalizer=f=3500:width_type=o:w=1.5:g=2"
)
LIMITER_FILTER = "alimiter=limit=0.7:level=false:attack=5:release=80"
EQ_GRAVES_HZ = 350.0
EQ_GRAVES_FRACAO = 0.60


def _ffmpeg():
    from studio.paths import ffmpeg_bin
    return ffmpeg_bin()


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + (r.stderr or r.stdout)[-800:])
    return r


def _ffmpeg_filter(samples, sr, filt):
    """Aplica um filtro de áudio do ffmpeg e devolve float32 mono."""
    with tempfile.TemporaryDirectory(prefix="studio_audio_") as tmp:
        src = os.path.join(tmp, "in.wav")
        dst = os.path.join(tmp, "out.wav")
        write_wav(src, samples, sr)
        _run([_ffmpeg(), "-y", "-loglevel", "error", "-i", src, "-af", filt, dst])
        out, out_sr = read_wav(dst)
        if out_sr != sr:
            raise RuntimeError(f"taxa mudou de {sr} para {out_sr}")
        return out


def aplicar_titulo(samples, sr):
    """Título 8% mais lento e 2,5 dB mais alto, antes do EQ e do volume."""
    return _ffmpeg_filter(samples, sr, f"atempo={TITLE_ATEMPO},volume={TITLE_VOLUME_DB}dB")


def aplicar_eq(samples, sr):
    return _ffmpeg_filter(samples, sr, EQ_FILTER)


def medir_lufs(samples, sr):
    with tempfile.TemporaryDirectory(prefix="studio_lufs_") as tmp:
        path = os.path.join(tmp, "a.wav")
        write_wav(path, samples, sr)
        r = subprocess.run(
            [_ffmpeg(), "-i", path, "-af", "ebur128=framelog=verbose", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        m = re.search(r"I:\s*([-\d.]+)\s*LUFS", r.stderr)
        if not m:
            return None
        return float(m.group(1))


def normalizar_volume(samples, sr):
    """Ganho fixo até -21 LUFS, depois alimiter (sem compressor)."""
    lufs = medir_lufs(samples, sr)
    gain = 0.0 if lufs is None else TARGET_LUFS - lufs
    return _ffmpeg_filter(samples, sr, f"volume={gain}dB,{LIMITER_FILTER}")


def tratar(samples, sr, *, eq=False):
    if eq:
        samples = aplicar_eq(samples, sr)
    return normalizar_volume(samples, sr)


def pausa_final_do_capitulo(cap):
    """Silêncio no fim do capítulo montado, segundo o book.json (para a próxima virada)."""
    pauses = cap.get("pauses") or []
    if not pauses:
        return 0.0
    last = len(pauses) - 1
    if last in set(cap.get("head") or []):
        return SILENCE_AFTER_TITLE
    return float(pauses[last])


def silencio_antes_do_titulo(chapters, idx):
    """Silêncio a colocar antes do título, só a partir do book.json (R20).

    Total desejado: 1,5 s, somando a pausa final do capítulo anterior incluído.
    Capítulos com include false são ignorados. Sem head: sem virada (0).
    """
    cap = chapters[idx]
    if not (cap.get("head") or []):
        return 0.0
    trailing = 0.0
    for i in range(idx - 1, -1, -1):
        prev = chapters[i]
        if prev.get("include", True):
            trailing = pausa_final_do_capitulo(prev)
            break
    return max(0.0, SILENCE_BEFORE_TITLE - trailing)


def montar_capitulo(chunks, pauses, head, sr, *, eq=False, silencio_antes=0.0):
    """Junta os trechos de um capítulo com virada, EQ e volume.

    `silencio_antes` deve vir de `silencio_antes_do_titulo` (book.json), não do estado
    da execução. Devolve (amostras, silêncio_final_em_segundos).
    """
    heads = set(head or [])
    parts = []
    trailing = 0.0

    if heads and silencio_antes > 0:
        parts.append(np.zeros(int(round(sr * float(silencio_antes))), dtype=np.float32))

    for i, w in enumerate(chunks):
        w = np.asarray(w, dtype=np.float32).reshape(-1)
        if i in heads:
            w = aplicar_titulo(w, sr)
        parts.append(w)
        if i < len(chunks) - 1:
            pz = SILENCE_AFTER_TITLE if i in heads else float(pauses[i]) if i < len(pauses) else 0.7
            parts.append(np.zeros(int(round(sr * pz)), dtype=np.float32))
            trailing = 0.0
        else:
            if i in heads:
                pz = SILENCE_AFTER_TITLE
                parts.append(np.zeros(int(round(sr * pz)), dtype=np.float32))
                trailing = pz
            else:
                pz = float(pauses[i]) if i < len(pauses) else 0.0
                if pz > 0:
                    parts.append(np.zeros(int(round(sr * pz)), dtype=np.float32))
                trailing = pz

    if not parts:
        return np.zeros(0, dtype=np.float32), 0.0
    return tratar(np.concatenate(parts), sr, eq=eq), trailing


def eq_por_graves(ref_wav, limiar_hz=EQ_GRAVES_HZ, fracao=EQ_GRAVES_FRACAO):
    """True se mais de `fracao` da energia do WAV de referência está abaixo de `limiar_hz`.

    Regra de design.md para voz clonada; a Interface grava o resultado em manifest.json.
    """
    samples, sr = read_wav(ref_wav)
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if len(samples) < 2:
        return False
    espec = np.fft.rfft(samples)
    pot = (espec.real ** 2 + espec.imag ** 2)
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sr)
    total = float(pot.sum())
    if total <= 0:
        return False
    graves = float(pot[freqs < limiar_hz].sum())
    return (graves / total) > fracao


def eq_do_projeto(P):
    """Lê a decisão já gravada: voice/manifest.json do projeto ou config.json.

    A pasta de vozes do app (voices/<id>/manifest.json) é cuidada pela Interface (T17);
    no projeto, o manifest da voz usada fica em voice/manifest.json quando existir.
    """
    for rel in ("voice/manifest.json", "config.json"):
        path = os.path.join(P, rel)
        try:
            cfg = json.load(open(path, encoding="utf8"))
        except (OSError, ValueError):
            continue
        if "eq" in cfg:
            return bool(cfg["eq"])
    return False
