"""Apoio comum dos testes: raiz do repositório no sys.path e projetos sintéticos."""
import json
import os
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
