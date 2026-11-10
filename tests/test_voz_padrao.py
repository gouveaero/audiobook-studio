"""T2 (R22): a voz padrão exportada de `portuguese_24l` fala sem login, e clonar voz nova continua bloqueado.

Roda o Pocket real num processo filho com HF_HOME vazio e sem HF_TOKEN (um processo por vez na máquina).
Os caminhos vêm de LOCAL_MD, nunca do repositório.
"""
import json
import os
import subprocess
import sys

import pytest

from tests.conftest import RAIZ, hf_home_sem_login, local_paths

pytestmark = pytest.mark.model

FRASE = "Esta é uma frase curta para provar a voz padrão do audiolivro."

PROGRAMA = r"""
import json, os, sys
from studio.engines import load_engine
voz, ref, saida = sys.argv[1], sys.argv[2], sys.argv[3]
e = load_engine("pocket", device="cpu")
e.load({"model": "portuguese_24l", "file": voz})
w = e.synth(%r, 0)
from studio.wavio import write_wav
write_wav(saida, w, e.sample_rate)
r = {"sample_rate": e.sample_rate, "secs": len(w) / e.sample_rate, "cloning": bool(e.model.has_voice_cloning),
     "clone_error": None, "pronta_secs": None}
try:
    e.load({"model": "portuguese_24l", "ref_wav": ref})
except Exception as ex:
    r["clone_error"] = str(ex)
e.load({"model": "portuguese_24l", "name": "rafael"})
r["pronta_secs"] = len(e.synth("Oi, tudo bem com você?", 0)) / e.sample_rate
print("@@" + json.dumps(r, ensure_ascii=False))
""" % FRASE


def test_voz_padrao_fala_sem_login_e_clonagem_continua_bloqueada(tmp_path):
    p = local_paths()
    voz, ref = p["Exportada"], p["Referência original"]
    assert os.path.isfile(voz) and os.path.isfile(ref)
    env = hf_home_sem_login(tmp_path)
    saida = tmp_path / "voz_padrao.wav"
    r = subprocess.run([sys.executable, "-c", PROGRAMA, voz, ref, str(saida)], cwd=RAIZ, env=env,
                       capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stderr[-3000:]
    res = json.loads(r.stdout.split("@@", 1)[1])
    assert not os.path.exists(os.path.join(env["HF_HOME"], "token"))
    assert res["sample_rate"] == 24000
    assert res["cloning"] is False, "sem login tem de carregar os pesos sem clonagem"
    # fala de verdade: a 16,6 caracteres/s a frase leva uns 4 s; aceitamos uma folga larga
    assert 2.0 < res["secs"] < 10.0, res
    assert res["clone_error"], "clonar voz nova devia ser recusado sem login"
    from studio.engines.pocket import CLONAGEM_BLOQUEADA
    assert res["clone_error"] == CLONAGEM_BLOQUEADA, "a pessoa recebe a mensagem em português, sem traceback"
    assert res["pronta_secs"] and 0.8 < res["pronta_secs"] < 6.0, res
    assert "hf_" not in r.stdout and "hf_" not in r.stderr.replace("hf_hub", "")
    assert saida.stat().st_size > 1000


def test_erro_de_clonagem_sem_login_em_portugues():
    """A mensagem que chega à pessoa é em português e não traz traceback (R38)."""
    from studio.engines.pocket import CLONAGEM_BLOQUEADA
    assert "Hugging Face" in CLONAGEM_BLOQUEADA and "—" not in CLONAGEM_BLOQUEADA
