"""T12 (R19 a R21): virada de capítulo, EQ e volume ao juntar os trechos."""
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import FAKE_ENGINE, make_project


def gerar(P, *extra):
    from studio import generate
    generate.main(["--project", str(P), *extra])


def ffprobe_dur(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def medir_lufs_e_pico(path):
    r = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "ebur128=framelog=verbose,astats=metadata=1:reset=0", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    err = r.stderr
    m_i = re.search(r"I:\s*([-\d.]+)\s*LUFS", err)
    m_p = re.search(r"Peak level dB:\s*([-\d.]+)", err)
    assert m_i and m_p, err[-800:]
    return float(m_i.group(1)), float(m_p.group(1))


def silêncios(path, ruido="-40dB", min_dur=0.2):
    r = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", f"silencedetect=noise={ruido}:d={min_dur}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start:\s*([-\d.]+)", r.stderr)]
    durs = [float(x) for x in re.findall(r"silence_duration:\s*([-\d.]+)", r.stderr)]
    # silencedetect omite o último silence_end se o arquivo termina em silêncio
    if len(durs) == len(starts) - 1:
        durs.append(ffprobe_dur(path) - starts[-1])
    return list(zip(starts, durs))


def projeto_com_titulos(tmp_path, eq=True):
    """Dois capítulos com head[0]; textos longos o bastante para o silêncio sobressair."""
    P = make_project(tmp_path, [
        ("01", "Capítulo um", [
            "Capítulo um.",
            "Corpo do primeiro capítulo com texto suficiente para medir volume e silêncio com segurança.",
        ]),
        ("02", "Capítulo dois", [
            "Capítulo dois.",
            "Corpo do segundo capítulo, também longo o bastante para a medição no arquivo final.",
        ]),
    ], config={"motor": FAKE_ENGINE, "eq": eq})
    book = json.loads((P / "book.json").read_text(encoding="utf8"))
    for c in book["chapters"]:
        c["head"] = [0]
        c["pauses"] = [0.7, 0.7]  # pausas do livro; a virada usa as constantes de design
    (P / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf8")
    return P


def montar_m4b(P, out):
    """Concatena os capítulos num M4B mínimo para medir a virada (R20)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    lst = out / "list.txt"
    caps = sorted((P / "chapters").glob("*.m4a"))
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in caps), encoding="utf8")
    m4b = out / "livro.m4b"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", "-f", "ipod", str(m4b)],
        check=True,
    )
    return m4b


def test_volume_do_capitulo_em_lufs_e_pico(tmp_path, ambiente_fake):
    """R19: cada capítulo sai a -21 LUFS (±1) com pico ≤ -2,5 dBFS."""
    P = projeto_com_titulos(tmp_path, eq=False)
    gerar(P)
    for cid in ("01", "02"):
        lufs, pico = medir_lufs_e_pico(P / "chapters" / f"{cid}.m4a")
        assert abs(lufs - (-21.0)) <= 1.0, f"capítulo {cid}: LUFS={lufs}"
        assert pico <= -2.5 + 0.05, f"capítulo {cid}: pico={pico}"


def test_virada_de_capitulo_no_m4b(tmp_path, ambiente_fake):
    """R20: 1,5 s antes do título e 1 s depois (±0,15), medidos no M4B; título mais lento e alto."""
    from studio import audio as A

    P = projeto_com_titulos(tmp_path, eq=False)
    gerar(P)
    m4b = montar_m4b(P, tmp_path / "saida")

    # Duração do título gerado (sem tratamento) vs no capítulo: atempo=0,92 alonga ~8%.
    from studio.wavio import read_wav
    titulo_wav, sr = read_wav(str(P / "work" / "chunks" / "01_0000.wav"))
    dur_titulo_bruto = len(titulo_wav) / sr
    esperado_titulo = dur_titulo_bruto / A.TITLE_ATEMPO

    gaps = silêncios(m4b)
    # No M4B: silêncio inicial (antes do 1º título) ≈ 1,5 s; depois do 1º título ≈ 1,0 s;
    # entre fim do corpo do cap.1 e título do cap.2 o total antes do 2º título ≈ 1,5 s.
    assert gaps, "nenhum silêncio detectado no M4B"
    assert abs(gaps[0][1] - A.SILENCE_BEFORE_TITLE) <= 0.15

    # Segundo silêncio do primeiro capítulo: depois do título
    assert abs(gaps[1][1] - A.SILENCE_AFTER_TITLE) <= 0.15

    # Silêncio imediatamente antes do título do capítulo 2 (último gap entre falas do cap.1 e título do 2)
    # Estrutura: [1.5 sil][título1][1.0 sil][corpo1][trailing][leading][título2]...
    # O gap antes do título 2 é gaps[2] se o corpo não tiver silêncio interno (tom contínuo do fake).
    assert abs(gaps[2][1] - A.SILENCE_BEFORE_TITLE) <= 0.15

    # Título mais lento: o bloco sonoro após o primeiro silêncio dura ~esperado_titulo
    inicio_titulo = gaps[0][0] + gaps[0][1]
    fim_titulo = gaps[1][0]
    assert abs((fim_titulo - inicio_titulo) - esperado_titulo) <= 0.15


def test_eq_sem_gerar_voz_de_novo(tmp_path, ambiente_fake):
    """R21: EQ conforme a regra; juntar de novo não chama o motor."""
    from studio import audio as A
    from studio.wavio import read_wav, write_wav

    P = projeto_com_titulos(tmp_path, eq=True)
    registro = tmp_path / "synth.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    gerar(P, "--only", "01")
    n = len(registro.read_text().splitlines())
    assert n >= 2

    # Remonta o capítulo a partir dos WAV em cache, com EQ, sem synth.
    book = json.loads((P / "book.json").read_text(encoding="utf8"))
    cap = book["chapters"][0]
    chunks = []
    for k in range(len(cap["chunks"])):
        w, sr = read_wav(str(P / "work" / "chunks" / f"01_{k:04d}.wav"))
        chunks.append(w)
    tratado, trailing = A.montar_capitulo(
        chunks, cap["pauses"], cap["head"], sr, eq=True, prev_trailing=0.0,
    )
    assert len(tratado) > sr  # pelo menos 1 s
    assert trailing >= 0
    assert len(registro.read_text().splitlines()) == n, "não deveria gerar voz de novo"

    # Com EQ, um grave forte abaixo de 80 Hz cai frente ao mesmo áudio sem EQ (antes do volume).
    t = np.arange(sr * 2, dtype=np.float32) / sr
    grave = (0.8 * np.sin(2 * np.pi * 50.0 * t)).astype(np.float32)
    com_eq = A.aplicar_eq(grave, sr)
    sem_eq = grave
    # energia na banda < 80 Hz (aproximação por RMS do sinal todo, dominado pelo 50 Hz)
    assert float(np.sqrt(np.mean(com_eq ** 2))) < 0.7 * float(np.sqrt(np.mean(sem_eq ** 2)))


def test_sem_head_nao_aplica_virada_de_titulo(tmp_path, ambiente_fake):
    """R50: projeto sem head junta só com as pausas do livro, sem alongar título."""
    from studio import audio as A

    P = make_project(tmp_path, [
        ("01", "Um", ["Titulo curto.", "Frase do corpo do capítulo sem campo head."]),
    ], config={"motor": FAKE_ENGINE, "eq": False})
    gerar(P)
    # Sem head: sem silêncio inicial de 1,5 s imposto pela virada
    gaps = silêncios(P / "chapters" / "01.m4a")
    if gaps and gaps[0][0] < 0.05:
        assert gaps[0][1] < A.SILENCE_BEFORE_TITLE - 0.3


def test_constantes_batem_com_o_design():
    from studio import audio as A
    assert A.SILENCE_BEFORE_TITLE == 1.5
    assert A.SILENCE_AFTER_TITLE == 1.0
    assert A.TITLE_ATEMPO == 0.92
    assert A.TITLE_VOLUME_DB == 2.5
    assert A.TARGET_LUFS == -21.0
    assert A.EQ_FILTER == (
        "highpass=f=80,"
        "equalizer=f=220:width_type=o:w=1.2:g=-2.5,"
        "equalizer=f=3500:width_type=o:w=1.5:g=2"
    )
    assert A.LIMITER_FILTER == "alimiter=limit=0.7:level=false:attack=5:release=80"
