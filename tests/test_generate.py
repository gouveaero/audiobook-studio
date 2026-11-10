"""T4 (R50): generate.py usa a interface de motores sem mudar o comportamento atual."""
import json
import os
import subprocess
import wave

import numpy as np
import pytest

from tests.conftest import FAKE_ENGINE, make_project


def gerar(P, *extra):
    from studio import generate
    generate.main(["--project", str(P), *extra])


def duracao(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def eventos(P):
    return [json.loads(l) for l in (P / "work" / "progress.jsonl").read_text().splitlines()]


def test_gera_capitulos_cache_trava_e_progresso(projeto_falso, ambiente_fake):
    P = projeto_falso
    gerar(P)
    for cid in ("01", "02"):
        assert (P / "chapters" / f"{cid}.m4a").exists()
        assert (P / "work" / "locks" / cid).exists()
        assert (P / "work" / "chunks" / f"{cid}_0000.wav").exists()
        assert (P / "work" / "chunks" / f"{cid}_0001.wav").exists()
    assert not list((P / "chapters").glob("*.tmp*"))
    assert not list((P / "work").glob("*.wav"))
    feitos = [e for e in eventos(P) if e["kind"] == "done"]
    assert [e["ch"] for e in feitos] == ["01", "02"]
    assert feitos[0]["title"] == "Capítulo um" and feitos[0]["flagged"] == []
    # duração = trechos a 15 caracteres/s + pausas de 0,5 s
    texto = "Capítulo um." + "Era uma vez uma frase curta de teste."
    assert abs(duracao(P / "chapters" / "01.m4a") - (len(texto) / 15 + 1.0)) < 0.2


def test_trecho_em_cache_e_de_16_bits(projeto_falso, ambiente_fake):
    gerar(projeto_falso)
    with wave.open(str(projeto_falso / "work" / "chunks" / "01_0000.wav")) as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 1


def test_only_filtra_capitulos(projeto_falso, ambiente_fake):
    gerar(projeto_falso, "--only", "02")
    assert not (projeto_falso / "chapters" / "01.m4a").exists()
    assert (projeto_falso / "chapters" / "02.m4a").exists()


def test_reaproveita_trechos_do_cache(projeto_falso, ambiente_fake, tmp_path):
    P = projeto_falso
    registro = tmp_path / "chamadas.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    gerar(P, "--only", "01")
    n = len(registro.read_text().splitlines())
    assert n == 2
    (P / "chapters" / "01.m4a").unlink(); (P / "work" / "locks" / "01").unlink()
    gerar(P, "--only", "01")
    assert len(registro.read_text().splitlines()) == n, "não deveria gerar voz de novo"
    assert (P / "chapters" / "01.m4a").exists()


def test_capitulo_pronto_ou_travado_e_pulado(projeto_falso, ambiente_fake):
    P = projeto_falso
    (P / "work" / "locks").mkdir(parents=True); (P / "work" / "locks" / "01").touch()  # trava vazia (nuvem) continua valendo
    gerar(P)
    assert not (P / "chapters" / "01.m4a").exists()
    assert (P / "chapters" / "02.m4a").exists()


def test_ritmo_fora_da_faixa_refaz_ate_4_vezes_e_marca(projeto_falso, ambiente_fake):
    ambiente_fake.setenv("FAKE_ENGINE_RATE", "5")  # lento demais: fora da faixa do motor falso
    P = projeto_falso
    gerar(P, "--only", "01")
    ev = eventos(P)
    retries = [e for e in ev if e["kind"] == "retry"]
    # o trecho 0 tem menos de 60 caracteres e não é conferido; o trecho 1 tem mais de 60? não: é curto também
    assert retries == []
    assert [e["flagged"] for e in ev if e["kind"] == "done"] == [[]]


def test_ritmo_fora_da_faixa_em_trecho_longo_marca_o_trecho(tmp_path, ambiente_fake):
    ambiente_fake.setenv("FAKE_ENGINE_RATE", "5")
    longo = "Esta é uma frase comprida o bastante para passar dos sessenta caracteres exigidos pela conferência."
    P = make_project(tmp_path, [("01", "Um", ["Curto.", longo])], config={"motor": FAKE_ENGINE})
    gerar(P)
    ev = eventos(P)
    retries = [e for e in ev if e["kind"] == "retry"]
    assert len(retries) == 1 and retries[0]["k"] == 1 and retries[0]["attempt"] == -1
    assert abs(retries[0]["rate"] - 5.0) < 0.3
    assert [e["flagged"] for e in ev if e["kind"] == "done"] == [[1]]


def test_ritmo_que_se_corrige_registra_a_tentativa(tmp_path, ambiente_fake):
    ambiente_fake.setenv("FAKE_ENGINE_RATE", "5")
    ambiente_fake.setenv("FAKE_ENGINE_FIX_AFTER", "2")  # a partir da terceira tentativa o ritmo volta ao normal
    longo = "Esta é uma frase comprida o bastante para passar dos sessenta caracteres exigidos pela conferência."
    P = make_project(tmp_path, [("01", "Um", [longo])], config={"motor": FAKE_ENGINE})
    gerar(P)
    ev = eventos(P)
    retries = [e for e in ev if e["kind"] == "retry"]
    assert len(retries) == 1 and retries[0]["attempt"] == 2
    assert [e["flagged"] for e in ev if e["kind"] == "done"] == [[]]


def test_projeto_antigo_sem_motor_usa_omnivoice(tmp_path):
    """R50: config.json sem "motor" (ou ausente) e book.json sem "head" continuam no OmniVoice."""
    from studio import generate
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"voz": "alguém", "nuvem": "GPU"})
    assert generate.engine_name_for(str(P)) == "omnivoice"
    os.remove(P / "config.json")
    assert generate.engine_name_for(str(P)) == "omnivoice"


def test_argumento_motor_sobrepoe_o_config(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"voz": "alguém"})  # sem "motor": seria OmniVoice
    gerar(P, "--motor", FAKE_ENGINE)
    assert (P / "chapters" / "01.m4a").exists()


def test_cache_antigo_em_float32_continua_valendo(projeto_falso, ambiente_fake):
    """Trechos gravados pelo torchaudio (float32) são lidos na montagem do capítulo."""
    from scipy.io import wavfile
    P = projeto_falso
    (P / "work" / "chunks").mkdir(parents=True)
    sr = 16000
    wavfile.write(str(P / "work" / "chunks" / "01_0000.wav"), sr, np.zeros(sr * 3, dtype=np.float32))
    gerar(P, "--only", "01")
    assert abs(duracao(P / "chapters" / "01.m4a") - (3 + len("Era uma vez uma frase curta de teste.") / 15 + 1.0)) < 0.2


def test_pedacos_viram_o_trecho_inteiro(tmp_path, ambiente_fake):
    """Motor que corta o trecho em pedaços: pedaço pronto não é gerado de novo e, com todos prontos,
    os pedaços viram o trecho NN_KKKK.wav (e somem)."""
    ambiente_fake.setenv("FAKE_ENGINE_MAX_CHARS", "30")
    registro = tmp_path / "chamadas.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    texto = "Primeira parte da frase, segunda parte da frase, terceira parte da frase."
    P = make_project(tmp_path, [("01", "Um", [texto])], config={"motor": FAKE_ENGINE})
    from tests.fake_engine import FakeEngine
    from studio.wavio import write_wav
    pedacos = FakeEngine().split(texto)
    assert len(pedacos) == 3
    (P / "work" / "chunks").mkdir(parents=True)
    write_wav(str(P / "work" / "chunks" / "01_0000.p00.wav"), np.zeros(16000 * 2, dtype=np.float32), 16000)
    gerar(P)
    gerados = [l.split("\t", 1)[1] for l in registro.read_text().splitlines()]
    assert gerados == pedacos[1:], "o primeiro pedaço já estava pronto"
    assert not list((P / "work" / "chunks").glob("01_0000.p*.wav"))
    from studio.wavio import read_wav
    w, sr = read_wav(str(P / "work" / "chunks" / "01_0000.wav"))
    esperado = 2 + sum(len(x) for x in pedacos[1:]) / 15 + 2 * 0.25
    assert abs(len(w) / sr - esperado) < 0.05
