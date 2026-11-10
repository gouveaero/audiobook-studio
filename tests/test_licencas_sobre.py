"""T23 (R45 a R48): LICENSE, THIRD_PARTY, Sobre, README e botões de doação/Android."""
import json
import re
from pathlib import Path

import pytest

from tests.test_servidor_base import Servidor

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "ui"


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "app-home"
    monkeypatch.setenv("AUDIOBOOK_STUDIO_HOME", str(home))
    return home


@pytest.fixture
def api(casa):
    s = Servidor(token="tok-lic", project=None)
    yield s
    s.close()


def test_license_mit_titular_sem_email():
    texto = (RAIZ / "LICENSE").read_text(encoding="utf8")
    assert "MIT License" in texto
    assert "Gabriel Gouvea" in texto
    assert "@" not in texto
    assert "Permission is hereby granted" in texto


def test_third_party_registra_pacotes_e_omnivoice():
    texto = (RAIZ / "THIRD_PARTY.md").read_text(encoding="utf8")
    for trecho in (
        "pocket-tts", "torch", "pywebview", "num2words", "huggingface_hub",
        "ffmpeg", "Oxanium", "JetBrains Mono", "OFL",
        "Apache-2.0", "AGPL-3.0", "OmniVoice", "não entra no instalador",
        "cc-by-4.0",
    ):
        assert trecho in texto, trecho
    # fatos distintos do omnivoice
    assert "model card" in texto.lower() or "Model card" in texto
    assert "AGPL" in texto


def test_about_html_termos_e_sem_travessao():
    html = (UI / "about.html").read_text(encoding="utf8")
    assert "—" not in html
    assert "fonts.css" in html
    assert "studio.js" in html
    assert "consentimento" in html.lower() or "autorizou" in html.lower()
    assert "DRM" in html
    assert "passar por outra pessoa" in html.lower() or "passe por outra" in html.lower()
    assert "inteligência artificial" in html.lower() or "inteligencia artificial" in html.lower()


def test_readme_portugues_e_abre_sem_assinatura():
    readme = (RAIZ / "README.md").read_text(encoding="utf8")
    assert "Privacidade e Segurança" in readme or "Abrir mesmo assim" in readme
    assert "chip Apple" in readme or "Mac" in readme
    assert "docs/linha-de-comando.md" in readme
    assert (RAIZ / "docs" / "linha-de-comando.md").is_file()
    cli = (RAIZ / "docs" / "linha-de-comando.md").read_text(encoding="utf8")
    assert "OmniVoice" in cli or "omnivoice" in cli.lower()
    assert "Colab" in cli or "colab" in cli.lower()


def test_version_urls_vazias_por_padrao(api):
    from studio import brand
    assert brand.DONATION_URL == ""
    assert brand.ANDROID_WAITLIST_URL == ""
    data = json.loads(api.req("GET", "/api/version")[2])
    assert data.get("donation_url") == ""
    assert data.get("android_waitlist_url") == ""


def test_botoes_doacao_android_so_com_url(api, monkeypatch):
    """R48: com URL vazia o botão fica hidden; com URL preenchida, aparece no JSON e a home usa isso."""
    from studio import brand
    from studio import local_api as la

    monkeypatch.setattr(brand, "DONATION_URL", "")
    monkeypatch.setattr(brand, "ANDROID_WAITLIST_URL", "")
    monkeypatch.setattr(la, "DONATION_URL", "")
    monkeypatch.setattr(la, "ANDROID_WAITLIST_URL", "")
    vazio = json.loads(api.req("GET", "/api/version")[2])
    assert not vazio["donation_url"]
    assert not vazio["android_waitlist_url"]

    monkeypatch.setattr(la, "DONATION_URL", "https://example.com/doar")
    monkeypatch.setattr(la, "ANDROID_WAITLIST_URL", "https://example.com/android")
    cheio = json.loads(api.req("GET", "/api/version")[2])
    assert cheio["donation_url"] == "https://example.com/doar"
    assert cheio["android_waitlist_url"] == "https://example.com/android"

    home = (UI / "home.html").read_text(encoding="utf8")
    assert 'id="doar"' in home and "hidden" in home
    assert 'id="android"' in home
    assert "donation_url" in home and "android_waitlist_url" in home


def test_about_serve(api):
    st, _, body = api.req("GET", "/about.html")
    assert st == 200
    assert "Termos de uso" in body.decode("utf8")


def test_home_tem_sobre(api):
    st, _, body = api.req("GET", "/home.html")
    assert st == 200
    assert "Sobre" in body.decode("utf8")
    assert "about.html" in body.decode("utf8")
