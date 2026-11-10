"""T3 e R11: medição de palavras perdidas (trechos de 3+), com o método de LOCAL_MD portado para scripts/medir_perda.py."""
import json
import os
import subprocess
import sys

import pytest

from tests.conftest import RAIZ, local_paths

sys.path.insert(0, str(RAIZ / "scripts"))


def test_normaliza_palavras_sem_pontuacao_nem_maiusculas():
    from medir_perda import normalizar
    assert normalizar("Olá, Mundo! Era 1984.") == ["olá", "mundo", "era", "1984"]


def test_compara_conta_so_trechos_de_tres_ou_mais_palavras():
    from medir_perda import comparar
    ref = "um dois três quatro cinco seis sete oito nove dez onze doze".split()
    # perdeu "quatro cinco seis" (3) e "onze" (1, não conta); extra "aa bb cc dd" (4)
    ouvido = "um dois três sete oito nove dez aa bb cc dd doze".split()
    r = comparar(ref, ouvido)
    assert r["total"] == 12 and r["ouvidas"] == 12
    assert r["perdidas"] == 3 and r["trechos_perdidos"] == 1
    assert r["extras"] == 4 and r["trechos_extras"] == 1
    assert r["exemplos_perdidos"] == ["quatro cinco seis"]
    assert abs(r["perdidas_pct"] - 25.0) < 0.01


def test_compara_sem_diferenca_da_zero():
    from medir_perda import comparar
    r = comparar(["a", "b", "c"], ["a", "b", "c"])
    assert r["perdidas"] == 0 and r["extras"] == 0 and r["perdidas_pct"] == 0.0


def test_texto_do_capitulo_junta_os_trechos(tmp_path):
    from medir_perda import texto_do_capitulo
    book = {"chapters": [{"id": "03", "chunks": ["Capítulo um.", "Era um dia."]}]}
    (tmp_path / "book.json").write_text(json.dumps(book))
    assert texto_do_capitulo(str(tmp_path / "book.json"), "03") == "Capítulo um. Era um dia."


@pytest.mark.model
def test_referencia_omnivoice_medida_com_whisper(tmp_path):
    """T3: Whisper `small` no áudio OmniVoice do capítulo de referência, com o Python indicado em LOCAL_MD.
    O número fica em cache fora do git (MEDICAO_CACHE_DIR) para a R11 não repetir os 10 minutos."""
    from medir_perda import medir_com_cache
    p = local_paths()
    r = medir_com_cache(p["whisper_python"], p["book.json corrigido à mão (lista de conferência)"],
                        "03", p["Áudio OmniVoice desse capítulo, para R11"])
    print("\nReferência OmniVoice:", json.dumps(r, ensure_ascii=False))
    assert r["total"] > 6000
    assert 0 <= r["perdidas"] < r["total"] * 0.05, r


def test_compara_devolve_a_posicao_dos_trechos_perdidos():
    """Para calibrar o ritmo: as posições (no texto de referência) permitem achar o pedaço que perdeu palavras."""
    from medir_perda import comparar
    ref = "um dois três quatro cinco seis sete oito nove dez onze doze".split()
    ouvido = "um dois três sete oito nove dez aa bb cc dd doze".split()
    assert comparar(ref, ouvido)["posicoes_perdidas"] == [[3, 6]]


def test_pedaco_de_cada_palavra():
    from medir_perda import pedaco_de_cada_palavra
    pedacos = [("01", 0, 0, "Era um dia,"), ("01", 0, 1, "frio e luminoso."), ("01", 1, 0, "Fim.")]
    assert pedaco_de_cada_palavra(pedacos) == [(0, 0)] * 3 + [(0, 1)] * 3 + [(1, 0)]
