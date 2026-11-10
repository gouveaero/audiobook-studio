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
    if len(durs) == len(starts) - 1:
        durs.append(ffprobe_dur(path) - starts[-1])
    return list(zip(starts, durs))


def rms_db(samples):
    s = np.asarray(samples, dtype=np.float32).reshape(-1)
    e = float(np.mean(s ** 2))
    assert e > 0, "bloco sem sinal"
    return 10.0 * np.log10(e)


def projeto_com_titulos(tmp_path, eq=True, pauses=None):
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
        c["pauses"] = list(pauses) if pauses is not None else [0.7, 0.7]
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
    """R20: 1,5 s antes do título e 1 s depois (±0,15), medidos no M4B; título mais lento."""
    from studio import audio as A

    P = projeto_com_titulos(tmp_path, eq=False)
    gerar(P)
    m4b = montar_m4b(P, tmp_path / "saida")

    from studio.wavio import read_wav
    titulo_wav, sr = read_wav(str(P / "work" / "chunks" / "01_0000.wav"))
    esperado_titulo = (len(titulo_wav) / sr) / A.TITLE_ATEMPO

    gaps = silêncios(m4b)
    assert gaps, "nenhum silêncio detectado no M4B"
    assert abs(gaps[0][1] - A.SILENCE_BEFORE_TITLE) <= 0.15
    assert abs(gaps[1][1] - A.SILENCE_AFTER_TITLE) <= 0.15
    assert abs(gaps[2][1] - A.SILENCE_BEFORE_TITLE) <= 0.15

    inicio_titulo = gaps[0][0] + gaps[0][1]
    fim_titulo = gaps[1][0]
    assert abs((fim_titulo - inicio_titulo) - esperado_titulo) <= 0.15


def test_virada_independe_da_ordem_de_geracao(tmp_path, ambiente_fake):
    """R20: silêncio antes do título vem do book.json, não da ordem de execução."""
    from studio import audio as A

    P = projeto_com_titulos(tmp_path, eq=False, pauses=[0.7, 0.7])
    gerar(P, "--only", "02")
    gerar(P, "--only", "01")
    m4b = montar_m4b(P, tmp_path / "saida-ordem")
    gaps = silêncios(m4b)
    assert len(gaps) >= 3, gaps
    # gaps[2] = silêncio total antes do título do capítulo 02 (trailing do 01 + leading do 02)
    assert abs(gaps[2][1] - A.SILENCE_BEFORE_TITLE) <= 0.15, gaps


def test_titulo_fica_2_5_db_mais_alto_que_o_corpo(tmp_path, ambiente_fake):
    """R20: no capítulo final, o bloco do título fica 2,5 dB (±0,5) acima do corpo."""
    from studio import audio as A
    from studio.wavio import read_wav, write_wav

    P = projeto_com_titulos(tmp_path, eq=False)
    # Amplitude baixa o bastante para o alimiter não comprimir o título após +2,5 dB.
    (P / "work" / "chunks").mkdir(parents=True)
    sr = 16000
    book = json.loads((P / "book.json").read_text(encoding="utf8"))
    cap = book["chapters"][0]
    for k, txt in enumerate(cap["chunks"]):
        n = max(sr, int(round(len(txt) / 15 * sr)))
        t = np.arange(n, dtype=np.float32) / sr
        write_wav(str(P / "work" / "chunks" / f"01_{k:04d}.wav"),
                  (0.05 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32), sr)
    gerar(P, "--only", "01")

    # Decodifica o capítulo para WAV e mede RMS do título e do corpo pelos silêncios.
    cap_m4a = P / "chapters" / "01.m4a"
    wav_out = tmp_path / "cap01.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(cap_m4a), str(wav_out)], check=True,
    )
    audio, sr = read_wav(str(wav_out))
    gaps = silêncios(wav_out)
    assert len(gaps) >= 2
    # [silêncio inicial][título][silêncio pós-título][corpo...]
    t0 = gaps[0][0] + gaps[0][1]
    t1 = gaps[1][0]
    c0 = gaps[1][0] + gaps[1][1]
    # corpo até o silêncio final (se houver) ou o fim
    c1 = gaps[2][0] if len(gaps) >= 3 else len(audio) / sr
    titulo = audio[int(t0 * sr):int(t1 * sr)]
    corpo = audio[int(c0 * sr):int(c1 * sr)]
    # corta bordas para evitar vazamento do silencedetect
    margem = int(0.05 * sr)
    titulo, corpo = titulo[margem:-margem or None], corpo[margem:-margem or None]
    diff = rms_db(titulo) - rms_db(corpo)
    assert abs(diff - A.TITLE_VOLUME_DB) <= 0.5, f"diff={diff:.2f} dB"


def test_remonta_capitulo_sem_gerar_voz_de_novo(tmp_path, ambiente_fake):
    """R21 pelo caminho real: apaga o m4a, mantém chunks, generate remonta sem synth."""
    P = projeto_com_titulos(tmp_path, eq=True)
    registro = tmp_path / "synth.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    gerar(P, "--only", "01")
    n = len(registro.read_text().splitlines())
    assert n >= 2
    (P / "chapters" / "01.m4a").unlink()
    (P / "work" / "locks" / "01").unlink()  # trava da 1ª execução; sem isso o generate pula o capítulo
    gerar(P, "--only", "01")
    assert (P / "chapters" / "01.m4a").exists()
    assert len(registro.read_text().splitlines()) == n, "não deveria gerar voz de novo"


def test_eq_true_e_false_produzem_capitulos_diferentes(tmp_path, ambiente_fake):
    """R21: mesmos trechos, eq true e eq false geram arquivos de capítulo diferentes."""
    from studio import audio as A
    from studio.wavio import read_wav, write_wav

    P = projeto_com_titulos(tmp_path, eq=False)
    gerar(P, "--only", "01")
    book = json.loads((P / "book.json").read_text(encoding="utf8"))
    cap = book["chapters"][0]
    chunks = [read_wav(str(P / "work" / "chunks" / f"01_{k:04d}.wav"))[0] for k in range(len(cap["chunks"]))]
    sr = read_wav(str(P / "work" / "chunks" / "01_0000.wav"))[1]
    lead = A.silencio_antes_do_titulo(book["chapters"], 0)
    com = A.montar_capitulo(chunks, cap["pauses"], cap["head"], sr, eq=True, silencio_antes=lead)[0]
    sem = A.montar_capitulo(chunks, cap["pauses"], cap["head"], sr, eq=False, silencio_antes=lead)[0]
    assert com.shape == sem.shape
    assert not np.allclose(com, sem, atol=1e-4)


def test_eq_atenua_graves_fortes():
    """Filtro de EQ do design reduz energia de um tom a 50 Hz."""
    from studio import audio as A
    sr = 16000
    t = np.arange(sr * 2, dtype=np.float32) / sr
    grave = (0.8 * np.sin(2 * np.pi * 50.0 * t)).astype(np.float32)
    com_eq = A.aplicar_eq(grave, sr)
    assert float(np.sqrt(np.mean(com_eq ** 2))) < 0.7 * float(np.sqrt(np.mean(grave ** 2)))


def test_sem_head_nao_aplica_virada_de_titulo(tmp_path, ambiente_fake):
    """R50: sem head, o capítulo não começa com 1,5 s de silêncio e o 1º trecho não leva atempo."""
    from studio import audio as A
    from studio.wavio import read_wav

    P = make_project(tmp_path, [
        ("01", "Um", ["Titulo curto.", "Frase do corpo do capítulo sem campo head."]),
    ], config={"motor": FAKE_ENGINE, "eq": False})
    gerar(P)

    wav_out = tmp_path / "sem_head.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(P / "chapters" / "01.m4a"), str(wav_out)],
        check=True,
    )
    gaps = silêncios(wav_out)
    silencio_inicial = gaps[0][1] if gaps and abs(gaps[0][0]) < 0.05 else 0.0
    assert silencio_inicial < A.SILENCE_BEFORE_TITLE - 0.3, gaps

    bruto, sr = read_wav(str(P / "work" / "chunks" / "01_0000.wav"))
    dur_bruto = len(bruto) / sr
    # primeiro bloco sonoro: do fim do silêncio inicial (se houver) até o próximo silêncio
    if gaps and abs(gaps[0][0]) < 0.05:
        inicio = gaps[0][0] + gaps[0][1]
        fim = gaps[1][0] if len(gaps) > 1 else ffprobe_dur(wav_out)
    else:
        inicio = 0.0
        fim = gaps[0][0] if gaps else ffprobe_dur(wav_out)
    dur_primeiro = fim - inicio
    assert abs(dur_primeiro - dur_bruto) <= 0.12, (dur_primeiro, dur_bruto)
    assert abs(dur_primeiro - dur_bruto / A.TITLE_ATEMPO) > 0.05


def test_eq_por_graves_da_referencia(tmp_path):
    """Regra do design: >60% da energia abaixo de 350 Hz => True; caso contrário False."""
    from studio import audio as A
    from studio.wavio import write_wav

    sr = 16000
    t = np.arange(sr * 2, dtype=np.float32) / sr
    grave = (0.5 * np.sin(2 * np.pi * 100.0 * t)).astype(np.float32)
    agudo = (0.5 * np.sin(2 * np.pi * 2000.0 * t)).astype(np.float32)
    p_grave = tmp_path / "grave.wav"
    p_agudo = tmp_path / "agudo.wav"
    write_wav(str(p_grave), grave, sr)
    write_wav(str(p_agudo), agudo, sr)
    assert A.eq_por_graves(str(p_grave)) is True
    assert A.eq_por_graves(str(p_agudo)) is False


def test_silencio_antes_do_titulo_pelo_book():
    """Silêncio antes do título = 1,5 s menos a última pausa do capítulo anterior incluído."""
    from studio import audio as A

    caps = [
        {"id": "01", "include": True, "head": [0], "pauses": [1.0, 0.7], "chunks": ["a", "b"]},
        {"id": "02", "include": False, "head": [0], "pauses": [1.0, 9.0], "chunks": ["x", "y"]},
        {"id": "03", "include": True, "head": [0], "pauses": [1.0, 0.5], "chunks": ["c", "d"]},
        {"id": "04", "include": True, "head": [], "pauses": [0.4], "chunks": ["só corpo"]},
        {"id": "05", "include": True, "head": [0], "pauses": [1.0, 0.2], "chunks": ["e", "f"]},
    ]
    assert A.silencio_antes_do_titulo(caps, 0) == pytest.approx(1.5)
    # anterior incluído é 01 (02 está fora): trailing 0,7 → lead 0,8
    assert A.silencio_antes_do_titulo(caps, 2) == pytest.approx(0.8)
    # 04 sem head: sem virada
    assert A.silencio_antes_do_titulo(caps, 3) == 0.0
    # anterior incluído é 04 (sem head): trailing = última pausa 0,4 → lead 1,1
    assert A.silencio_antes_do_titulo(caps, 4) == pytest.approx(1.1)


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
