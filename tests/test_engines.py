"""T4 (R50): interface de motores em studio/engines/ e o motor OmniVoice por trás dela."""
import sys
import types

import numpy as np
import pytest

from tests.conftest import FAKE_ENGINE


def test_interface_define_os_campos_do_design():
    from studio.engines import Engine
    e = Engine
    for campo in ("id", "sample_rate", "chars_per_second", "rate_range"):
        assert hasattr(e, campo), campo
    for metodo in ("load", "split", "synth"):
        assert callable(getattr(e, metodo)), metodo


def test_motor_padrao_e_omnivoice_sem_importar_o_modelo():
    from studio.engines import engine_name
    assert engine_name({}) == "omnivoice"
    assert engine_name({"voz": "alguém"}) == "omnivoice"
    assert engine_name({"motor": "OmniVoice"}) == "omnivoice"  # rótulo antigo do painel
    assert engine_name({"motor": "pocket"}) == "pocket"
    assert "omnivoice" not in sys.modules
    assert "torch" not in sys.modules


def test_carrega_omnivoice_sem_tocar_no_modelo():
    from studio.engines import load_engine
    e = load_engine("omnivoice", device="cpu", steps=32)
    assert e.id == "omnivoice"
    assert e.rate_range == (10.0, 17.0)
    assert e.split("Uma frase. Outra frase.") == ["Uma frase. Outra frase."]
    assert "omnivoice" not in sys.modules
    assert "torch" not in sys.modules


def test_carrega_motor_por_caminho_pontilhado():
    from studio.engines import load_engine
    e = load_engine(FAKE_ENGINE)
    assert e.id == "fake"
    assert e.split("Texto qualquer.") == ["Texto qualquer."]


def test_motor_desconhecido_da_erro_claro():
    from studio.engines import load_engine
    with pytest.raises(ValueError, match="[Mm]otor"):
        load_engine("inexistente")


def test_motor_falso_gera_audio_proporcional_ao_texto(ambiente_fake):
    from tests.fake_engine import FakeEngine
    e = FakeEngine()
    e.load({"ref_wav": "nao-existe.wav", "ref_txt": "x", "language": "pt"})
    curto, longo = e.synth("Oi.", 0), e.synth("Uma frase bem mais comprida do que a outra.", 0)
    assert curto.dtype == np.float32 and curto.ndim == 1
    assert len(longo) > len(curto)
    assert abs(len(longo) / e.sample_rate - len("Uma frase bem mais comprida do que a outra.") / e.chars_per_second) < 0.05


def test_motor_falso_obedece_ritmo_e_corte_do_ambiente(ambiente_fake):
    ambiente_fake.setenv("FAKE_ENGINE_RATE", "5")
    ambiente_fake.setenv("FAKE_ENGINE_MAX_CHARS", "12")
    from tests.fake_engine import FakeEngine
    e = FakeEngine()
    e.load({})
    w = e.synth("x" * 50, 0)
    assert abs(len(w) / e.sample_rate - 10.0) < 0.05
    pedacos = e.split("Uma frase, com vírgula, e mais palavras no fim.")
    assert len(pedacos) > 1 and all(len(p) <= 12 for p in pedacos)
    assert " ".join(pedacos).split() == "Uma frase, com vírgula, e mais palavras no fim.".split()


def test_omnivoice_chama_o_modelo_como_antes(monkeypatch):
    """Sem mudar o comportamento (R50): mesmos argumentos de carga e de geração do generate.py antigo."""
    torch = pytest.importorskip("torch")
    chamadas = {}

    class ModeloFalso:
        sampling_rate = 24000

        @classmethod
        def from_pretrained(cls, name, **kw):
            chamadas["load"] = (name, kw)
            return cls()

        def generate(self, **kw):
            chamadas["gen"] = kw
            chamadas["seed"] = torch.initial_seed()
            return [torch.zeros(1, 2400, dtype=torch.float16)]

    pacote = types.ModuleType("omnivoice"); modelos = types.ModuleType("omnivoice.models")
    mod = types.ModuleType("omnivoice.models.omnivoice"); mod.OmniVoice = ModeloFalso
    for nome, m in (("omnivoice", pacote), ("omnivoice.models", modelos), ("omnivoice.models.omnivoice", mod)):
        monkeypatch.setitem(sys.modules, nome, m)

    from studio.engines import load_engine
    e = load_engine("omnivoice", device="cpu", steps=32)
    e.load({"ref_wav": "/tmp/ref.wav", "ref_txt": "Referência.", "language": "pt"})
    assert chamadas["load"] == ("k2-fsa/OmniVoice", {"device_map": "cpu", "dtype": torch.float16})
    assert e.sample_rate == 24000
    w = e.synth("Um texto.", 2)
    assert chamadas["gen"] == {"text": "Um texto.", "language": "pt", "ref_audio": "/tmp/ref.wav",
                               "ref_text": "Referência.", "num_step": 32, "guidance_scale": 2.0}
    assert chamadas["seed"] == 1002
    assert w.dtype == np.float32 and w.shape == (2400,)
