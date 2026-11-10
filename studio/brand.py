"""Constantes de marca e pastas do app. Nome e URLs mudam sem espalhar strings."""
import os
from pathlib import Path

APP_NAME = "Audiobook Studio"
# Voz pronta do Pocket quando o pacote padrão não está instalado (escolha técnica provisória).
VOICE_FALLBACK = "rafael"
# Releases e aviso de versão (R44). Sem barra no fim.
GITHUB_REPO = "https://github.com/gouveaero/audiobook-studio"
# Só aparecem na interface quando preenchidos (R48).
DONATION_URL = ""
ANDROID_WAITLIST_URL = ""


def app_home() -> Path:
    env = os.environ.get("AUDIOBOOK_STUDIO_HOME")
    if env:
        return Path(env)
    return Path.home() / "Library" / "Application Support" / APP_NAME


def ensure_dirs() -> Path:
    """Cria a árvore do app e settings.json vazio se faltar. Devolve a pasta raiz."""
    home = app_home()
    for sub in ("hf", "voices", "projects"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    settings = home / "settings.json"
    if not settings.exists():
        settings.write_text("{}", encoding="utf8")
    return home
