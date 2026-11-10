"""T6 (apoio): a geração resolve a voz pelo voice/manifest.json do projeto e registra o ritmo de cada pedaço."""
import json

from tests.conftest import FAKE_ENGINE, make_project


def test_projeto_antigo_sem_manifesto_usa_ref_wav_e_ref_txt(tmp_path):
    from studio.generate import voice_for
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    v = voice_for(str(P), {"language": "pt"})
    assert v["ref_wav"] == f"{P}/voice/ref.wav" and v["ref_txt"] == "Texto da referência." and v["language"] == "pt"
    assert "file" not in v and "name" not in v


def test_manifesto_com_arquivo_no_pacote_de_voz(tmp_path, monkeypatch):
    from studio.generate import voice_for
    pack = tmp_path / "voice-pack"; pack.mkdir()
    (pack / "voz_portuguese_24l.safetensors").write_bytes(b"x")
    monkeypatch.setenv("VOICE_PACK_DIR", str(pack))
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    man = {"id": "padrao", "label": "Voz padrão", "engine": "pocket", "model": "portuguese_24l",
           "file": "voz_portuguese_24l.safetensors", "eq": True}
    (P / "voice" / "manifest.json").write_text(json.dumps(man))
    v = voice_for(str(P), {})
    assert v["model"] == "portuguese_24l" and v["file"] == str(pack / "voz_portuguese_24l.safetensors")
    assert v["eq"] is True


def test_manifesto_com_arquivo_na_pasta_do_projeto_ou_das_vozes(tmp_path, monkeypatch):
    from studio.generate import voice_for
    home = tmp_path / "home"; (home / "voices" / "minha").mkdir(parents=True)
    (home / "voices" / "minha" / "voz.safetensors").write_bytes(b"x")
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home)); monkeypatch.delenv("VOICE_PACK_DIR", raising=False)
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    (P / "voice" / "manifest.json").write_text(json.dumps({"id": "minha", "engine": "pocket", "model": "portuguese_24l", "file": "voz.safetensors"}))
    assert voice_for(str(P), {})["file"] == str(home / "voices" / "minha" / "voz.safetensors")
    (P / "voice" / "voz.safetensors").write_bytes(b"y")  # na pasta do projeto, tem prioridade
    assert voice_for(str(P), {})["file"] == f"{P}/voice/voz.safetensors"


def test_manifesto_de_voz_pronta(tmp_path):
    from studio.generate import voice_for
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    (P / "voice" / "manifest.json").write_text(json.dumps({"id": "rafael", "engine": "pocket", "model": "portuguese_24l", "name": "rafael"}))
    v = voice_for(str(P), {})
    assert v["name"] == "rafael" and "file" not in v


def test_manifesto_sem_arquivo_nem_nome_cai_na_voz_pronta_configurada(tmp_path):
    from studio.brand import VOICE_FALLBACK
    from studio.generate import voice_for
    P = make_project(tmp_path, [("01", "Um", ["Oi."])])
    (P / "voice" / "ref.wav").unlink()
    (P / "voice" / "manifest.json").write_text(json.dumps({"engine": "pocket", "model": "portuguese_24l"}))
    assert voice_for(str(P), {})["name"] == VOICE_FALLBACK


def test_ritmo_de_cada_pedaco_vai_para_o_progresso(tmp_path, ambiente_fake):
    """Dados para calibrar rate_range: um evento por pedaço gerado, com caracteres, segundos e ritmo."""
    from studio import generate
    ambiente_fake.setenv("FAKE_ENGINE_MAX_CHARS", "30")
    texto = "Primeira parte da frase, segunda parte da frase, terceira parte da frase."
    P = make_project(tmp_path, [("01", "Um", [texto, "Curto."])], config={"motor": FAKE_ENGINE})
    generate.main(["--project", str(P)])
    ev = [json.loads(l) for l in (P / "work" / "progress.jsonl").read_text().splitlines()]
    pedacos = [e for e in ev if e["kind"] == "piece"]
    assert [(e["ch"], e["k"], e["s"]) for e in pedacos] == [("01", 0, 0), ("01", 0, 1), ("01", 0, 2), ("01", 1, 0)]
    assert all(e["chars"] > 0 and e["secs"] > 0 and abs(e["rate"] - 15.0) < 0.5 and e["attempt"] == 0 for e in pedacos)
