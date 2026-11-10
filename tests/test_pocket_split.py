"""T5 (R10): pré-corte por tokens do motor Pocket. Nenhum pedaço enviado ao modelo passa do alvo de 40 tokens.

Os testes sem modelo usam um contador de tokens falso (uma palavra = um token). O teste @model usa o tokenizador
do próprio modelo e confere que o Pocket não emite "generation may skip words" em nenhum trecho do capítulo de referência.
"""
import json
import logging
import os
import re

import pytest

from tests.conftest import local_paths

palavras = lambda s: len(s.split())  # contador falso: um token por palavra


def junta(pedacos):
    return " ".join(pedacos).split()


def test_texto_curto_fica_inteiro():
    from studio.engines.pocket import cortar
    t = "Uma frase curta. Outra frase curta."
    assert cortar(t, palavras, 40) == [t]


def test_paragrafo_corta_em_frases_sem_passar_do_alvo():
    from studio.engines.pocket import cortar
    frases = [f"Esta é a frase número {i} do parágrafo de teste." for i in range(12)]  # 10 palavras cada
    t = " ".join(frases)
    p = cortar(t, palavras, 20)
    assert len(p) > 1
    assert all(palavras(x) <= 20 for x in p)
    assert junta(p) == t.split()
    assert all(x.endswith(".") for x in p), "corte entre frases mantém a frase inteira"
    assert len(p) == 6 and all(palavras(x) == 20 for x in p), "agrupa duas frases por pedaço, o máximo que cabe"


def test_frase_longa_corta_na_virgula_ponto_e_virgula_ou_dois_pontos():
    from studio.engines.pocket import cortar
    t = ("Winston subiu a escada, parou no patamar, olhou o cartaz enorme; " +
         "o rosto o fitava de todos os ângulos: era o Grande Irmão quem vigiava, " +
         "e ninguém escapava do olhar, nem de dia, nem de noite, nem nunca.")
    p = cortar(t, palavras, 8)
    assert len(p) >= 4
    assert all(palavras(x) <= 8 for x in p)
    assert junta(p) == t.split()
    assert all(re.search(r"[,;:.]$", x) for x in p), "cada parte termina numa pausa natural"


def test_frase_sem_pontuacao_corta_na_fronteira_de_palavra():
    from studio.engines.pocket import cortar
    t = " ".join(f"palavra{i}" for i in range(50)) + "."
    p = cortar(t, palavras, 12)
    assert all(palavras(x) <= 12 for x in p)
    assert junta(p) == t.split()
    assert not any(x == "" for x in p)


def test_nao_corta_numero_decimal_nem_dentro_de_palavra():
    from studio.engines.pocket import cortar
    t = "O valor era 3.5 por cento, disse ele. E depois 12.75 por cento, acrescentou."
    p = cortar(t, palavras, 6)
    assert junta(p) == t.split()
    assert any("3.5" in x for x in p) and any("12.75" in x for x in p)


def test_motor_pocket_split_usa_o_contador_do_modelo():
    from studio.engines.pocket import PocketEngine, TARGET_TOKENS
    e = PocketEngine()
    e.n_tokens = palavras  # sem modelo carregado, o teste injeta o contador
    assert TARGET_TOKENS == 40
    t = " ".join(f"Frase número {i} para o teste de corte do motor." for i in range(10))
    p = e.split(t)
    assert len(p) > 1 and all(palavras(x) <= TARGET_TOKENS for x in p) and junta(p) == t.split()


@pytest.mark.model
def test_capitulo_de_referencia_sem_aviso_de_corte(caplog, tmp_path):
    """R10: com o tokenizador real, nenhum pedaço do capítulo 03 faz o Pocket avisar que pode pular palavras."""
    from pocket_tts.models.text_chunking import split_into_best_sentences
    from studio.engines.pocket import PocketEngine, TARGET_TOKENS
    p = local_paths()
    caps = json.load(open(p["book.json corrigido à mão (lista de conferência)"]))["chapters"]
    trechos = [c for c in caps if c["id"] == "03"][0]["chunks"]
    e = PocketEngine(device="cpu")
    e.load({"model": "portuguese_24l", "name": "rafael"})
    m = e.model
    n_pedacos, n_tokens_max = 0, 0
    with caplog.at_level(logging.WARNING, logger="pocket_tts.models.text_chunking"):
        for t in trechos:
            for pedaco in e.split(t):
                n_pedacos += 1
                n_tokens_max = max(n_tokens_max, e.n_tokens(pedaco))
                chunks = split_into_best_sentences(m.flow_lm.conditioner.tokenizer, pedaco, 50, m.pad_with_spaces_for_short_inputs,
                                                   remove_semicolons=m.remove_semicolons, append_terminal_punctuation=m.append_terminal_punctuation,
                                                   capitalize_first_letter=m.capitalize_first_letter, replace_characters=m.replace_characters)
                assert len(chunks) == 1, (pedaco, chunks)
    avisos = [r for r in caplog.records if "may skip words" in r.getMessage()]
    print(f"\n{len(trechos)} trechos, {n_pedacos} pedaços, máximo {n_tokens_max} tokens por pedaço")
    assert avisos == []
    assert n_tokens_max <= TARGET_TOKENS
    # sem diferenciar maiúsculas: palavras em caixa alta vão em minúsculas para o Pocket (T6)
    assert " ".join(e.split(" ".join(trechos))).lower().split() == " ".join(trechos).lower().split()


def test_palavras_em_maiusculas_vao_em_minusculas():
    """Medido no capítulo de referência: "GUERRA É PAZ" e "ABAIXO O GRANDE IRMÃO" saem lentos e perdem palavras."""
    from studio.engines.pocket import cortar
    assert cortar("GUERRA É PAZ", palavras, 40) == ["Guerra é paz"]
    assert cortar("O GRANDE IRMÃO ESTÁ DE OLHO EM VOCÊ, dizia o letreiro.", palavras, 40) == \
        ["O grande irmão está de olho em você, dizia o letreiro."]
    assert cortar("Winston Smith viu a ONU e o Partido.", palavras, 40) == ["Winston Smith viu a onu e o Partido."]
    assert cortar("A letra A e o pronome É ficam.", palavras, 40) == ["A letra A e o pronome É ficam."]


def test_faixa_de_ritmo_calibrada_no_capitulo_de_referencia():
    """Calibrada nos 328 pedaços de 60+ caracteres do capítulo 03 (T6): perdas apareceram acima de 20 car/s;
    12 a 19,5 refaz cerca de 6% dos pedaços."""
    from studio.engines.pocket import PocketEngine
    assert PocketEngine.rate_range == (12.0, 19.5)


def test_carga_liga_o_preenchimento_de_frases_curtas(monkeypatch):
    """Medido na T6: sem o preenchimento do próprio Pocket, "Guerra é paz" sai como "e é rapaz"."""
    import sys, types
    class Modelo:
        sample_rate = 24000
        pad_with_spaces_for_short_inputs = False
        has_voice_cloning = False
        @classmethod
        def load_model(cls, language):
            return cls()
        def get_state_for_audio_prompt(self, fonte):
            return {"fonte": fonte}
    falso = types.ModuleType("pocket_tts"); falso.TTSModel = Modelo
    monkeypatch.setitem(sys.modules, "pocket_tts", falso)
    from studio.engines.pocket import PocketEngine
    e = PocketEngine(); e.load({"model": "portuguese_24l", "name": "rafael"})
    assert e.model.pad_with_spaces_for_short_inputs is True
