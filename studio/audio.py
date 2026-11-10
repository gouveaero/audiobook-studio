"""Tratamento de áudio ao juntar os trechos de um capítulo (virada, EQ e volume).

Valores de design.md, seção Áudio. Não gera voz de novo: só processa os WAV em cache.
"""
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
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", filt, dst])
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
            ["ffmpeg", "-i", path, "-af", "ebur128=framelog=verbose", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        m = re.search(r"I:\s*([-\d.]+)\s*LUFS", r.stderr)
        if not m:
            # silêncio total ou áudio curto demais: ebur128 pode não reportar
            return None
        return float(m.group(1))


def normalizar_volume(samples, sr):
    """Ganho fixo até -21 LUFS, depois alimiter (sem compressor)."""
    lufs = medir_lufs(samples, sr)
    if lufs is None:
        gain = 0.0
    else:
        gain = TARGET_LUFS - lufs
    filt = f"volume={gain}dB,{LIMITER_FILTER}"
    return _ffmpeg_filter(samples, sr, filt)


def tratar(samples, sr, *, eq=False):
    if eq:
        samples = aplicar_eq(samples, sr)
    return normalizar_volume(samples, sr)


def montar_capitulo(chunks, pauses, head, sr, *, eq=False, prev_trailing=0.0):
    """Junta os trechos de um capítulo com virada, EQ e volume.

    `chunks` é lista de arrays float32. `head` é o conjunto/lista de índices de título.
    Devolve (amostras, silêncio_final_em_segundos) para a virada do próximo capítulo.
    Projetos sem head não recebem tratamento de título (R50).
    """
    heads = set(head or [])
    parts = []
    trailing = 0.0

    if heads:
        lead = max(0.0, SILENCE_BEFORE_TITLE - float(prev_trailing or 0.0))
        if lead > 0:
            parts.append(np.zeros(int(round(sr * lead)), dtype=np.float32))

    for i, w in enumerate(chunks):
        w = np.asarray(w, dtype=np.float32).reshape(-1)
        if i in heads:
            w = aplicar_titulo(w, sr)
        parts.append(w)
        if i < len(chunks) - 1:
            if i in heads:
                pz = SILENCE_AFTER_TITLE
            else:
                pz = float(pauses[i]) if i < len(pauses) else 0.7
            parts.append(np.zeros(int(round(sr * pz)), dtype=np.float32))
            trailing = 0.0
        else:
            # último trecho: a pausa do livro vira o "fim do capítulo" da próxima virada
            if i in heads:
                # capítulo só com título: depois dele ainda vale o silêncio pós-título
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

    joined = np.concatenate(parts)
    return tratar(joined, sr, eq=eq), trailing


def eq_do_projeto(P):
    """EQ ligado pelo manifest da voz ou por config.json (`"eq": true`)."""
    for rel in ("voice/manifest.json", "config.json"):
        path = os.path.join(P, rel)
        try:
            import json
            cfg = json.load(open(path, encoding="utf8"))
        except (OSError, ValueError):
            continue
        if "eq" in cfg:
            return bool(cfg["eq"])
    return False
