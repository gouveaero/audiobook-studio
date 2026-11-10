"""T20 / R37, R43: auxiliar HTTP do selftest só fala com 127.0.0.1; autoteste sem som."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from studio import selftest

RAIZ = Path(__file__).resolve().parent.parent


def test_api_recusa_host_que_nao_e_loopback(monkeypatch):
    """Erro antes de abrir conexão: urlopen não é chamado (R37)."""
    chamado = {"n": 0}

    def _falso_urlopen(*_a, **_k):
        chamado["n"] += 1
        raise AssertionError("urlopen não deveria ser chamado")

    monkeypatch.setattr(selftest.urllib.request, "urlopen", _falso_urlopen)

    with pytest.raises(ValueError, match=r"127\.0\.0\.1"):
        selftest._api("http://example.com:8795", "tok", "GET", "/health")

    assert chamado["n"] == 0


def test_api_recusa_localhost_literal(monkeypatch):
    """Só 127.0.0.1 vale; localhost também é recusado antes de conectar."""
    chamado = {"n": 0}

    def _falso_urlopen(*_a, **_k):
        chamado["n"] += 1
        raise AssertionError("urlopen não deveria ser chamado")

    monkeypatch.setattr(selftest.urllib.request, "urlopen", _falso_urlopen)

    with pytest.raises(ValueError, match=r"127\.0\.0\.1"):
        selftest._api("http://localhost:8795", "tok", "GET", "/health")

    assert chamado["n"] == 0


def test_selftest_js_aplica_mudo_antes_de_tocar_ou_avancar_audio():
    """R43: todo <audio> do autoteste fica muted/volume 0 antes de play ou seek."""
    src = (RAIZ / "studio" / "selftest.py").read_text(encoding="utf8")
    assert "muted" in src and "volume" in src, "autoteste precisa silenciar <audio>"
    # Helper ou patch instalado no modo autoteste (não no app normal).
    assert re.search(r"__absMudo|muted\s*=\s*true", src), "falta aplicar muted = true"

    # Passos que mexem em áudio: mudo tem de aparecer no mesmo bloco JS.
    blocos = {
        "smoke_r43": _bloco_js_apos(src, "smoke_r43"),
        "guia4_voz": _bloco_js_apos(src, "guia4_voz"),
        "guia6_seek": _bloco_js_apos(src, "guia6_seek"),
    }
    for nome, bloco in blocos.items():
        assert bloco, f"bloco JS de {nome} não encontrado"
        assert re.search(r"muted\s*=\s*true", bloco), f"{nome}: falta muted = true"
        assert re.search(r"volume\s*=\s*0", bloco), f"{nome}: falta volume = 0"
        # Se chama play(), o mudo vem antes.
        play = re.search(r"\.play\s*\(", bloco)
        if play:
            antes = bloco[: play.start()]
            assert re.search(r"muted\s*=\s*true", antes), f"{nome}: play() sem mudo antes"
        # guia4: clique em Ouvir (play no app) exige mudo no player antes do click.
        if nome == "guia4_voz":
            click = re.search(r"btn\.click\s*\(", bloco)
            assert click, "guia4_voz deve clicar no botão Ouvir"
            antes = bloco[: click.start()]
            assert re.search(r"muted\s*=\s*true", antes), "guia4: mudo antes do click Ouvir"


def _bloco_js_apos(src: str, token: str) -> str:
    """Extrai o corpo JS passado a _run_js_step para o token dado."""
    # _run_js_step(window, "token", """ ... """) ou f""" ... """
    m = re.search(
        rf'_run_js_step\(\s*window\s*,\s*"{re.escape(token)}"\s*,\s*(f?)"""(.*?)"""',
        src,
        re.S,
    )
    return m.group(2) if m else ""
