"""T8 (R14 a R18): work/job.json, pausar, continuar, cancelar, caffeinate, espaço em disco e tempo restante."""
import json
import os
import signal
import stat
import subprocess
import sys
import time

import pytest

from tests.conftest import FAKE_ENGINE, RAIZ, make_project

LONGO = ["Trecho número %d, com texto suficiente para dar uns três segundos de áudio no motor falso." % i for i in range(6)]


def gerar(P, *extra):
    from studio import generate
    generate.main(["--project", str(P), *extra])


def job(P):
    return json.loads((P / "work" / "job.json").read_text())


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


def n_chunks(P):
    d = P / "work" / "chunks"
    return len([f for f in os.listdir(d) if f.endswith(".wav")]) if d.is_dir() else 0


def status(P):
    try:
        return job(P).get("status")
    except (OSError, ValueError):
        return None


def test_job_json_registra_a_tarefa_e_termina_pronto_com_o_m4b(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi, tudo bem?"]), ("02", "Dois", ["Até logo."])], config={"motor": FAKE_ENGINE})
    gerar(P)
    j = job(P)
    assert j["status"] == "pronto"
    assert j["pid"] == os.getpid()
    assert j["motor"] == FAKE_ENGINE and j["model"]
    assert isinstance(j["started"], float) and j["started"] <= time.time()
    assert j["chars_total"] == len("Oi, tudo bem?") + len("Até logo.") and j["chars_done"] == j["chars_total"]
    assert j["eta_seconds"] == 0
    assert os.path.isfile(j["m4b"]) and j["m4b"].endswith(".m4b")


def test_job_json_preserva_campos_de_quem_iniciou(tmp_path, ambiente_fake):
    """A interface escreve job.json antes de abrir o processo; o gerador acrescenta, não apaga."""
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    (P / "work").mkdir()
    (P / "work" / "job.json").write_text(json.dumps({"pid": 1, "status": "rodando", "only": "01", "redo": {"chapter": "01", "chunk": 0}, "started": 123.0}))
    gerar(P)
    j = job(P)
    assert j["only"] == "01" and j["redo"] == {"chapter": "01", "chunk": 0} and j["started"] == 123.0
    assert j["status"] == "pronto" and j["pid"] == os.getpid()


def test_capitulo_excluido_fica_fora_da_conta(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."]), ("02", "Dois", ["x" * 500])], config={"motor": FAKE_ENGINE})
    book = json.loads((P / "book.json").read_text()); book["chapters"][1]["include"] = False
    (P / "book.json").write_text(json.dumps(book))
    gerar(P)
    assert job(P)["chars_total"] == 3 and job(P)["status"] == "pronto"


def test_so_alguns_capitulos_termina_concluido_sem_montar(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi."]), ("02", "Dois", ["Olá."])], config={"motor": FAKE_ENGINE})
    gerar(P, "--only", "01")
    assert job(P)["status"] == "concluido" and "m4b" not in job(P)
    assert not (P / "audiobook").exists()


def test_pausar_e_continuar(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", LONGO)], config={"motor": FAKE_ENGINE})
    p = processo(P, {"FAKE_ENGINE_DELAY": "0.3"})
    assert espera(lambda: n_chunks(P) >= 2), p.stderr.read().decode()[-2000:]
    assert status(P) == "gerando"
    (P / "work" / "pause").write_text("1")
    assert espera(lambda: status(P) == "pausado")
    n = n_chunks(P); time.sleep(1.2)
    assert n_chunks(P) == n, "pausado não gera"
    assert p.poll() is None, "pausar não encerra o processo"
    (P / "work" / "pause").unlink()
    assert espera(lambda: status(P) == "gerando")
    assert p.wait(60) == 0, p.stderr.read().decode()[-2000:]
    assert status(P) == "pronto" and (P / "chapters" / "01.m4a").exists()


def test_cancelar_nao_apaga_o_pronto_e_permite_retomar(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", LONGO)], config={"motor": FAKE_ENGINE})
    p = processo(P, {"FAKE_ENGINE_DELAY": "0.3"})
    assert espera(lambda: n_chunks(P) >= 2), p.stderr.read().decode()[-2000:]
    (P / "work" / "cancel").write_text("1")
    assert p.wait(30) == 0, p.stderr.read().decode()[-2000:]
    assert status(P) == "cancelado"
    n = n_chunks(P)
    assert 2 <= n < len(LONGO)
    assert not (P / "chapters" / "01.m4a").exists()
    assert not (P / "work" / "locks" / "01").exists(), "cancelar solta a trava para a retomada"
    (P / "work" / "cancel").unlink()
    gerar(P)
    assert status(P) == "pronto" and (P / "chapters" / "01.m4a").exists()


def caffeinate_de(pid):
    r = subprocess.run(["pgrep", "-f", f"caffeinate -i -w {pid}"], capture_output=True, text=True)
    return [l for l in r.stdout.split() if l.strip()]


def test_caffeinate_so_durante_a_geracao(tmp_path, ambiente_fake):
    """R16: o Mac não dorme durante a geração, e a proteção termina junto com ela (caffeinate real, observado por pgrep)."""
    import shutil, threading
    if not shutil.which("caffeinate"):
        pytest.skip("sem caffeinate nesta máquina")
    ambiente_fake.setenv("FAKE_ENGINE_DELAY", "1.5")
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    vistos = []
    parar = threading.Event()

    def observa():
        while not parar.is_set():
            vistos.extend(caffeinate_de(os.getpid())); time.sleep(0.1)
    t = threading.Thread(target=observa, daemon=True); t.start()
    try:
        gerar(P)
    finally:
        parar.set(); t.join()
    assert vistos, "caffeinate -i -w <pid da geração> devia estar rodando durante a geração"
    assert espera(lambda: not caffeinate_de(os.getpid()), 5), "a proteção contra dormir termina junto com a geração"


def test_espaco_necessario_e_250mb_por_hora_mais_500mb():
    from studio.generate import espaco_necessario
    assert espaco_necessario(chars=3600 * 15, chars_per_second=15.0) == 250_000_000 + 500_000_000
    assert espaco_necessario(chars=0, chars_per_second=15.0) == 500_000_000


def test_sem_espaco_avisa_antes_de_comecar(tmp_path, ambiente_fake):
    from studio import generate
    ambiente_fake.setattr(generate, "espaco_livre", lambda path: 100_000_000)
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": FAKE_ENGINE})
    with pytest.raises(SystemExit) as e:
        gerar(P)
    assert e.value.code != 0
    j = job(P)
    assert j["status"] == "erro" and "espaço" in j["error"].lower() and "Traceback" not in j["error"]
    assert n_chunks(P) == 0 and not (P / "work" / "locks" / "01").exists()


def test_tempo_restante_vem_da_velocidade_medida(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", LONGO)], config={"motor": FAKE_ENGINE})
    p = processo(P, {"FAKE_ENGINE_DELAY": "0.5"})
    assert espera(lambda: n_chunks(P) >= 3), p.stderr.read().decode()[-2000:]
    j = job(P)
    total = sum(len(t) for t in LONGO)
    assert j["chars_done"] >= 3 * len(LONGO[0]) and j["chars_total"] == total
    assert j["chars_per_second"] > 0
    # cada trecho leva 0,5 s de espera no motor falso, mais um pouco de escrita: a velocidade medida fica perto de len/0,5
    assert 0.3 * len(LONGO[0]) / 0.5 < j["chars_per_second"] < 1.2 * len(LONGO[0]) / 0.5, j
    assert abs(j["eta_seconds"] - (total - j["chars_done"]) / j["chars_per_second"]) < 0.06  # eta arredondado a 0,1 s
    assert p.wait(60) == 0
    assert job(P)["eta_seconds"] == 0 and job(P)["status"] == "pronto"


def test_erro_vira_estado_erro_em_portugues_e_o_detalhe_vai_para_o_log(tmp_path, ambiente_fake):
    P = make_project(tmp_path, [("01", "Um", ["Oi.", "Trecho que explode."])], config={"motor": FAKE_ENGINE})
    p = processo(P, {"FAKE_ENGINE_FAIL": "explode"})
    assert p.wait(30) != 0
    err = p.stderr.read().decode()
    assert "Traceback" in err, "o detalhe vai para o log"
    j = job(P)
    assert j["status"] == "erro" and "Traceback" not in j["error"] and j["error"]
    assert not (P / "work" / "locks" / "01").exists(), "trava solta para tentar de novo"
