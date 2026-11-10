"""T6 (R11): o fim de cada pedaço do Pocket sai inteiro; a última palavra não é cortada.

Medido no capítulo de referência (10/11/2026): 1 em cada 4 dos 425 pedaços terminava com a voz ainda no nível de pico
na última amostra (cauda de silêncio 0 ms), e nesses o Whisper ouvia "torno" por "tornozelo", "desamp" por
"desamparo", "automa" por "automaticamente medo e ira". A causa é o sinal de fim de fala (EOS) do Pocket: com o
limiar padrão (-4,0, que o modelo português não redefine) ele dispara enquanto a última palavra ainda está sendo
dita, e só 2 quadros (160 ms) são gerados depois. Regerar os mesmos pedaços com a mesma semente reproduz o corte
bit a bit; com o limiar ajustado o fim cai no lugar certo e os pedaços bons ficam idênticos.

O teste @model roda o Pocket real num processo filho (um por vez na máquina) e depois o Whisper (sozinho) com o
Python de LOCAL_MD. Os textos vêm do book.json de LOCAL_MD, nunca do repositório.
"""
import json
import os
import re
import subprocess
import sys
import types

import numpy as np
import pytest

from tests.conftest import RAIZ, hf_home_sem_login, local_paths

# (trecho, pedaço) do capítulo 03 que saíram cortados no áudio de referência, todos na tentativa 0 (semente 1000)
PEDACOS = [(28, 0), (25, 0), (61, 1), (47, 3)]
CAUDA_MINIMA_MS = 120    # pedaços inteiros medidos: 280 a 460 ms de silêncio no fim; cortados: 0 ms
FIM_MAXIMO_DB = -25.0    # últimos 80 ms em relação ao pico: inteiros abaixo de -37 dB; cortados acima de -8 dB

PROGRAMA = r"""
import json, sys
from studio.engines import load_engine
from studio.wavio import write_wav
voz, book_json, pasta = sys.argv[1], sys.argv[2], sys.argv[3]
pedacos = json.loads(sys.argv[4])
e = load_engine("pocket", device="cpu")
e.load({"model": "portuguese_24l", "file": voz})
cap = [c for c in json.load(open(book_json, encoding="utf8"))["chapters"] if c["id"] == "03"][0]
saida = []
for k, s in pedacos:
    texto = e.split(cap["chunks"][k])[s]
    w = e.synth(texto, 0)
    f = f"{pasta}/k{k:02d}s{s}.wav"
    write_wav(f, w, e.sample_rate)
    saida.append({"k": k, "s": s, "texto": texto, "arquivo": f, "secs": round(len(w) / e.sample_rate, 3)})
print("@@" + json.dumps(saida, ensure_ascii=False))
"""

WHISPER = r"""
import json, sys
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
saida = {}
for f in sys.argv[1:]:
    segs, _ = m.transcribe(f, language="pt", beam_size=1, vad_filter=False, word_timestamps=True)
    saida[f] = " ".join(w.word for s in segs for w in s.words)
print("@@" + json.dumps(saida, ensure_ascii=False))
"""


def normalizar(texto):
    return re.findall(r"\w+", texto.lower())


def fim_do_pedaco(w, sr):
    """(cauda_ms, fim80_db): silêncio depois do último quadro de 20 ms com voz (acima do pico menos 30 dB) e nível
    dos últimos 80 ms em relação ao pico. Um pedaço cortado termina com a voz no pico: cauda 0 e fim80 perto de 0."""
    w = np.asarray(w, dtype=np.float64).reshape(-1)
    rms_db = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    fr = int(sr * 0.02)
    env = np.array([rms_db(w[i * fr:(i + 1) * fr]) for i in range(len(w) // fr)])
    pico = env.max()
    ultimo_com_voz = np.where(env > pico - 30)[0][-1]
    return int((len(env) - 1 - ultimo_com_voz) * 20), float(rms_db(w[-int(sr * 0.08):]) - pico)


def test_medida_do_fim_distingue_corte_de_silencio():
    sr = 24000
    voz = np.sin(np.arange(sr) * 2 * np.pi * 200 / sr) * 0.5
    cortado = voz
    inteiro = np.concatenate([voz, np.zeros(int(sr * 0.3))])
    assert fim_do_pedaco(cortado, sr) == (0, pytest.approx(0.0, abs=0.5))
    cauda, fim = fim_do_pedaco(inteiro, sr)
    assert cauda >= 280 and fim < -60


def test_carga_ajusta_o_limiar_de_fim_de_fala(monkeypatch):
    """O modelo português não redefine o limiar do EOS e fica com o padrão (-4,0), medido cedo demais."""
    class Modelo:
        sample_rate = 24000
        pad_with_spaces_for_short_inputs = False
        eos_threshold = -4.0
        has_voice_cloning = False
        @classmethod
        def load_model(cls, language):
            return cls()
        def get_state_for_audio_prompt(self, fonte):
            return {"fonte": fonte}
    falso = types.ModuleType("pocket_tts"); falso.TTSModel = Modelo
    monkeypatch.setitem(sys.modules, "pocket_tts", falso)
    from studio.engines.pocket import EOS_THRESHOLD, PocketEngine
    e = PocketEngine(); e.load({"model": "portuguese_24l", "name": "rafael"})
    assert EOS_THRESHOLD > -4.0
    assert e.model.eos_threshold == EOS_THRESHOLD


@pytest.mark.model
def test_fim_dos_pedacos_sai_inteiro(tmp_path):
    from studio.wavio import read_wav
    p = local_paths()
    voz, book_json = p["Exportada"], p["book.json corrigido à mão (lista de conferência)"]
    env = hf_home_sem_login(tmp_path)
    pasta = tmp_path / "pedacos"; pasta.mkdir()
    r = subprocess.run([sys.executable, "-c", PROGRAMA, voz, book_json, str(pasta), json.dumps(PEDACOS)],
                       cwd=RAIZ, env=env, capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stderr[-3000:]
    pedacos = json.loads(r.stdout.split("@@", 1)[1])
    assert len(pedacos) == len(PEDACOS)

    medidas = {}
    for x in pedacos:
        w, sr = read_wav(x["arquivo"])
        medidas[x["arquivo"]] = fim_do_pedaco(w, sr)
        x["cauda_ms"], x["fim80_db"] = medidas[x["arquivo"]]
        # não gera além da conta: ritmo abaixo de 10 caracteres por segundo seria repetição ou silêncio longo
        assert x["secs"] < len(x["texto"]) / 10.0 + 1.0, x

    # Whisper sozinho, depois do Pocket, com o Python de LOCAL_MD
    r = subprocess.run([p["whisper_python"], "-c", WHISPER] + [x["arquivo"] for x in pedacos],
                       capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stderr[-3000:]
    ouvido = json.loads(r.stdout.split("@@", 1)[1])
    for x in pedacos:
        x["ouvido"] = ouvido[x["arquivo"]]
        print(f"\nk{x['k']:02d}s{x['s']}: {x['secs']} s, cauda {x['cauda_ms']} ms, fim {x['fim80_db']:.1f} dB; "
              f"texto ...{x['texto'][-40:]!r}; ouviu ...{x['ouvido'][-40:]!r}")

    cortados = [x for x in pedacos if x["cauda_ms"] < CAUDA_MINIMA_MS or x["fim80_db"] > FIM_MAXIMO_DB]
    assert cortados == [], "fim abrupto: " + "; ".join(f"k{x['k']:02d}s{x['s']} cauda {x['cauda_ms']} ms, {x['fim80_db']:.1f} dB" for x in cortados)
    sem_ultima = [x for x in pedacos if normalizar(x["ouvido"])[-1:] != normalizar(x["texto"])[-1:]]
    assert sem_ultima == [], "última palavra perdida: " + "; ".join(
        f"k{x['k']:02d}s{x['s']} {normalizar(x['texto'])[-1]!r} -> {normalizar(x['ouvido'])[-1:]}" for x in sem_ultima)
