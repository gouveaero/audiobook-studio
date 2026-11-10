"""T7 (R13, R9): trechos atômicos, travas com PID, descarte de .wav ilegível, retomada e capítulos excluídos."""
import json
import os
import signal
import subprocess
import sys
import time

import pytest

from tests.conftest import FAKE_ENGINE, RAIZ, make_project
from studio.wavio import read_wav

LONGO = ["Trecho número %d, com texto suficiente para dar uns três segundos de áudio no motor falso." % i for i in range(6)]


def gerar(P, *extra):
    from studio import generate
    generate.main(["--project", str(P), *extra])


def processo(P, env_extra, *extra):
    env = dict(os.environ, **env_extra)
    return subprocess.Popen([sys.executable, "-m", "studio.generate", "--project", str(P), *extra], cwd=RAIZ, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def espera(cond, limite=30):
    t0 = time.time()
    while time.time() - t0 < limite:
        if cond():
            return True
        time.sleep(0.05)
    return False


def chunks(P):
    return sorted(f for f in os.listdir(P / "work" / "chunks") if f.endswith(".wav"))


def test_matar_no_meio_e_retomar_continua_do_ultimo_trecho_integro(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", LONGO)], config={"motor": FAKE_ENGINE})
    registro = tmp_path / "chamadas.log"
    env = {"FAKE_ENGINE_DELAY": "0.4", "FAKE_ENGINE_LOG": str(registro)}
    p = processo(P, env)
    assert espera(lambda: (P / "work" / "chunks").is_dir() and len(chunks(P)) >= 2), p.stderr.read().decode()[-2000:]
    time.sleep(0.1)  # no meio de um trecho
    p.send_signal(signal.SIGKILL); p.wait()
    prontos = chunks(P)
    assert 2 <= len(prontos) < len(LONGO)
    for f in prontos:  # tudo que tem o nome final é íntegro
        w, sr = read_wav(str(P / "work" / "chunks" / f))
        assert len(w) > sr
    assert not (P / "chapters" / "01.m4a").exists()
    assert (P / "work" / "locks" / "01").exists(), "a trava velha ficou para trás"
    antes = len(registro.read_text().splitlines())
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    gerar(P)  # retomada no mesmo projeto, com a trava velha de um processo morto
    assert (P / "chapters" / "01.m4a").exists()
    depois = registro.read_text().splitlines()
    assert len(depois) - antes == len(LONGO) - len(prontos), "refez só o que faltava"
    assert not list((P / "work" / "chunks").glob("*.tmp*"))


def test_trecho_e_escrito_em_tmp_e_renomeado(tmp_path, ambiente_fake):
    """Se a escrita do WAV for interrompida, sobra um .tmp, nunca um .wav parcial."""
    from studio import generate
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    nomes = []
    original = generate.write_wav

    def espiao(path, samples, sr):
        nomes.append(os.path.basename(path)); original(path, samples, sr)
    ambiente_fake.setattr(generate, "write_wav", espiao)
    gerar(P)
    assert nomes[0].startswith("01_0000.wav.") and nomes[0].endswith(".tmp"), nomes


def test_trava_de_processo_morto_e_liberada(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    (P / "work" / "locks").mkdir(parents=True)
    morto = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True).stdout.strip()
    (P / "work" / "locks" / "01").write_text(morto)
    gerar(P)
    assert (P / "chapters" / "01.m4a").exists()
    assert (P / "work" / "locks" / "01").read_text().strip() == str(os.getpid())


def test_trava_de_processo_vivo_continua_valendo(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    (P / "work" / "locks").mkdir(parents=True)
    vivo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (P / "work" / "locks" / "01").write_text(str(vivo.pid))
        gerar(P)
        assert not (P / "chapters" / "01.m4a").exists()
        assert (P / "work" / "locks" / "01").read_text().strip() == str(vivo.pid)
    finally:
        vivo.kill(); vivo.wait()


def test_trava_vazia_da_nuvem_continua_valendo(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    (P / "work" / "locks").mkdir(parents=True); (P / "work" / "locks" / "01").touch()
    gerar(P)
    assert not (P / "chapters" / "01.m4a").exists()


def test_trava_nova_guarda_o_pid(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    gerar(P)
    assert (P / "work" / "locks" / "01").read_text().strip() == str(os.getpid())


def test_wav_ilegivel_no_cache_e_refeito(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Primeiro trecho.", "Segundo trecho."])], config={"motor": FAKE_ENGINE})
    registro = tmp_path / "chamadas.log"
    ambiente_fake.setenv("FAKE_ENGINE_LOG", str(registro))
    (P / "work" / "chunks").mkdir(parents=True)
    (P / "work" / "chunks" / "01_0000.wav").write_bytes(b"RIFF lixo truncado")
    (P / "work" / "chunks" / "01_0001.wav").write_bytes(b"")
    gerar(P)
    assert [l.split("\t", 1)[1] for l in registro.read_text().splitlines()] == ["Primeiro trecho.", "Segundo trecho."]
    assert (P / "chapters" / "01.m4a").exists()


def test_capitulo_com_include_false_nao_e_gerado(tmp_path, ambiente_fake):
    """R9: capítulo tirado pela pessoa não gera, não trava e não entra no progresso."""
    P = make_project(tmp_path, [("01", "Um", ["Oi."]), ("02", "Dois", ["Olá."]), ("03", "Três", ["Tchau."])],
                     config={"motor": FAKE_ENGINE})
    book = json.loads((P / "book.json").read_text())
    book["chapters"][1]["include"] = False
    (P / "book.json").write_text(json.dumps(book, ensure_ascii=False))
    gerar(P)
    assert (P / "chapters" / "01.m4a").exists() and (P / "chapters" / "03.m4a").exists()
    assert not (P / "chapters" / "02.m4a").exists()
    assert not (P / "work" / "locks" / "02").exists()
    feitos = [json.loads(l)["ch"] for l in (P / "work" / "progress.jsonl").read_text().splitlines()]
    assert feitos == ["01", "03"]
