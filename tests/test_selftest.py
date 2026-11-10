"""T20 / R37, R43: auxiliar HTTP do selftest só fala com 127.0.0.1."""
from __future__ import annotations

import pytest

from studio import selftest


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
