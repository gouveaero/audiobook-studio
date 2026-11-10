"""Apoio comum dos testes: raiz do repositório no sys.path e projetos sintéticos."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

FAKE_ENGINE = "tests.fake_engine:FakeEngine"


def make_project(raiz: Path, chapters, config=None, book_extra=None) -> Path:
    """Cria um projeto no formato atual. `chapters` é uma lista de (id, title, [trechos])."""
    P = raiz / "projeto"
    (P / "voice").mkdir(parents=True)
    (P / "voice" / "ref.wav").write_bytes(b"RIFF")  # só precisa existir; o motor falso não o lê
    (P / "voice" / "ref.txt").write_text("Texto da referência.", encoding="utf8")
    book = {"title": "Livro de teste", "author": "Autora", "language": "pt", "chapters": []}
    for cid, title, chunks in chapters:
        book["chapters"].append({"id": cid, "title": title, "chunks": list(chunks), "pauses": [0.5] * len(chunks)})
    book.update(book_extra or {})
    (P / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf8")
    if config is not None:
        (P / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x334455:s=128x128",
                    "-frames:v", "1", str(P / "cover.jpg")], check=True)  # a montagem automática precisa da capa
    return P


@pytest.fixture
def projeto_falso(tmp_path):
    """Projeto de dois capítulos curtos usando o motor falso."""
    return make_project(tmp_path, [
        ("01", "Capítulo um", ["Capítulo um.", "Era uma vez uma frase curta de teste."]),
        ("02", "Capítulo dois", ["Capítulo dois.", "Outra frase, igualmente curta, para o segundo capítulo."]),
    ], config={"motor": FAKE_ENGINE})


@pytest.fixture
def ambiente_fake(monkeypatch):
    """Limpa as variáveis que controlam o motor falso, para um teste não vazar no outro."""
    for v in list(os.environ):
        if v.startswith("FAKE_ENGINE_"):
            monkeypatch.delenv(v)
    return monkeypatch


def local_md() -> str:
    """Conteúdo de LOCAL_MD (caminhos desta máquina, fora do git). Pula o teste se não houver."""
    caminho = os.environ.get("LOCAL_MD")
    if not caminho or not Path(caminho).expanduser().is_file():
        pytest.skip("LOCAL_MD não definido; os testes com modelo precisam dos caminhos desta máquina")
    return Path(caminho).expanduser().read_text(encoding="utf-8")


def local_paths() -> dict:
    """Mapeia o rótulo de cada linha de LOCAL_MD ("Exportada", "Livro 1", ...) para o caminho entre crases, expandido.
    O Python do Whisper, numa linha só com o caminho, entra como "whisper_python"."""
    import re
    paths = {}
    for linha in local_md().splitlines():
        linha = linha.strip().lstrip("- ").strip()
        m = re.match(r"^(?P<rotulo>.*?\S):\s*`(?P<valor>[^`]+)`", linha)
        if m:
            paths[m["rotulo"].replace("`", "").strip()] = os.path.expanduser(m["valor"])
        elif linha.startswith("`") and linha.rstrip("`").endswith("/bin/python"):
            paths["whisper_python"] = os.path.expanduser(linha.strip("`"))
    return paths


def hf_home_sem_login(tmp_path) -> dict:
    """Ambiente para um processo do Pocket sem login: HF_HOME vazio (ou o cache de HF_HOME_SEM_LOGIN, que
    não pode ter token) e sem HF_TOKEN. Nunca imprime nem copia o token do Hugging Face."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HF_") and k != "HUGGING_FACE_HUB_TOKEN"}
    home = Path(os.environ.get("HF_HOME_SEM_LOGIN") or tmp_path / "hf-vazio")
    home.mkdir(parents=True, exist_ok=True)
    assert not (home / "token").exists(), "HF_HOME_SEM_LOGIN não pode conter token"
    env["HF_HOME"] = str(home)
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["PYTHONPATH"] = str(RAIZ)
    return env
