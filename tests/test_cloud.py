"""T9 (R51): cloud.py envia studio/engines/, o necessário para o motor certo e mantém as reservas de capítulo.
Usa o `colab` simulado de tests/fake_colab.py, sem rede e sem GPU."""
import json
import os
import stat
import subprocess
import sys

import pytest

from tests.conftest import RAIZ, make_project

sys.path.insert(0, str(RAIZ))


def faixa(path, segundos=1.0):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={segundos}",
                    "-ac", "1", "-b:a", "48k", str(path)], check=True)
    return path


@pytest.fixture
def colab_falso(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    (bin_dir / "colab").write_text(f"#!/bin/sh\nexec '{sys.executable}' '{RAIZ / 'tests' / 'fake_colab.py'}' \"$@\"\n")
    (bin_dir / "colab").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    log, vm = tmp_path / "colab.jsonl", tmp_path / "vm"
    vm.mkdir()
    monkeypatch.setenv("FAKE_COLAB_LOG", str(log)); monkeypatch.setenv("FAKE_COLAB_VM", str(vm))
    monkeypatch.setenv("FAKE_COLAB_M4A", str(faixa(tmp_path / "pronto.m4a")))
    monkeypatch.setattr("time.sleep", lambda s: None)

    def chamadas():
        return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return {"log": chamadas, "vm": vm}


def rodar(P, *extra):
    from studio import cloud
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("--project", required=True); ap.add_argument("--gpu", default="A100")
    ap.add_argument("--only", default=""); ap.add_argument("--keep", action="store_true"); ap.add_argument("--leave", default="")
    cloud.run(ap.parse_args(["run", "--project", str(P), *extra]))


def comando(c):
    return [a for a in c["args"] if not a.startswith("-") and a != "adc"][0]


def uploads(colab):
    return {c["args"][-1]: c["args"][-2] for c in colab["log"]() if comando(c) == "upload"}


def execs(colab):
    return [c["code"] for c in colab["log"]() if comando(c) == "exec"]


def test_envia_o_pacote_studio_com_engines(tmp_path, colab_falso):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    rodar(P)
    up = uploads(colab_falso)
    for f in os.listdir(RAIZ / "studio"):
        if f.endswith(".py"):
            assert f"/content/studio/{f}" in up
    for f in os.listdir(RAIZ / "studio" / "engines"):
        if f.endswith(".py"):
            assert f"/content/studio/engines/{f}" in up, f
    assert (colab_falso["vm"] / "studio" / "engines" / "pocket.py").is_file()


def test_projeto_omnivoice_envia_referencia_e_instala_omnivoice(tmp_path, colab_falso):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])  # sem config.json nem manifesto: OmniVoice (R50)
    rodar(P)
    up = uploads(colab_falso)
    assert "/content/project/voice/ref.wav" in up and "/content/project/voice/ref.txt" in up
    pip = [c for c in execs(colab_falso) if "pip install" in c]
    assert pip and "omnivoice" in pip[0] and "pocket-tts" not in pip[0]
    lanc = [c for c in execs(colab_falso) if "studio.generate" in c][0]
    assert "--motor omnivoice" in lanc


def test_projeto_pocket_envia_manifesto_e_voz_e_instala_pocket(tmp_path, colab_falso, monkeypatch):
    P = make_project(tmp_path, [("01", "Um", ["Oi."])], config={"motor": "pocket"})
    (P / "voice" / "ref.wav").unlink(); (P / "voice" / "ref.txt").unlink()
    pack = tmp_path / "pack"; pack.mkdir(); (pack / "voz_portuguese_24l.safetensors").write_bytes(b"pesos")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    (P / "voice" / "manifest.json").write_text(json.dumps({"id": "padrao", "engine": "pocket", "model": "portuguese_24l",
                                                           "file": "voz_portuguese_24l.safetensors", "eq": True}))
    rodar(P)
    up = uploads(colab_falso)
    assert "/content/project/voice/manifest.json" in up
    assert up["/content/project/voice/voz_portuguese_24l.safetensors"] == str(pack / "voz_portuguese_24l.safetensors")
    assert "/content/project/config.json" in up
    assert not any(k.endswith("ref.wav") for k in up)
    pip = [c for c in execs(colab_falso) if "pip install" in c]
    assert pip and "pocket-tts==4.0.1" in pip[0] and "omnivoice" not in pip[0]
    assert "--motor pocket" in [c for c in execs(colab_falso) if "studio.generate" in c][0]


def test_reservas_de_capitulo_na_vm(tmp_path, colab_falso):
    """Capítulo pronto aqui, pedido com --leave para este computador, ou tirado pela pessoa (include false) fica travado na VM."""
    P = make_project(tmp_path, [("01", "Um", ["Oi."]), ("02", "Dois", ["Olá."]), ("03", "Três", ["Tchau."]),
                                ("04", "Quatro", ["Fim."])])
    book = json.loads((P / "book.json").read_text()); book["chapters"][2]["include"] = False
    (P / "book.json").write_text(json.dumps(book))
    (P / "chapters").mkdir(); faixa(P / "chapters" / "01.m4a")
    rodar(P, "--leave", "04")
    lanc = [c for c in execs(colab_falso) if "studio.generate" in c][0]
    import re
    travados = json.loads(re.search(r"for i in (\[.*?\]):", lanc).group(1).replace("'", '"'))
    assert sorted(travados) == ["01", "03", "04"]
    assert (P / "chapters" / "02.m4a").exists(), "só o capítulo 02 foi gerado e baixado"
    assert not (P / "chapters" / "03.m4a").exists() and not (P / "chapters" / "04.m4a").exists()
    assert any(comando(c) == "stop" for c in colab_falso["log"]()), "VM encerrada depois de baixar tudo"


def test_vm_nao_monta_o_livro(tmp_path, colab_falso):
    """A montagem é feita aqui, com a capa; na VM o gerador só gera (sem cover.jpg ela falharia e sujaria o gen.log)."""
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    rodar(P)
    assert "--no-assemble" in [c for c in execs(colab_falso) if "studio.generate" in c][0]
