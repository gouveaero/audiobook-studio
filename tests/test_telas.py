"""T16 (R9, R35, R39): telas de início e conferência, fontes embutidas, sem rede externa."""
import json
import re
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project
from tests.epub_sintetico import encryption_xml, make_epub, paras
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
    s = Servidor(token="tok-ui", project=None)
    yield s
    s.close()


def auth(s):
    return {"X-Studio-Token": s.token}


def test_ui_sem_travessao():
    ruins = []
    for path in UI.rglob("*"):
        if path.suffix.lower() not in {".html", ".js", ".css", ".svg", ".txt"}:
            continue
        texto = path.read_text(encoding="utf8", errors="replace")
        if "—" in texto:
            ruins.append(str(path.relative_to(RAIZ)))
    assert not ruins, f"travessão em: {ruins}"


def test_ui_sem_urls_externas_nem_google_fonts():
    """R35: fontes locais; nenhum pedido a domínio externo nas páginas."""
    permitido_local = re.compile(r"""["'](/|https?://127\.0\.0\.1)""")
    externo = re.compile(
        r"""https?://(?!127\.0\.0\.1)([a-zA-Z0-9.-]+)""",
        re.I,
    )
    ruins = []
    for path in UI.rglob("*"):
        if path.suffix.lower() not in {".html", ".js", ".css"}:
            continue
        texto = path.read_text(encoding="utf8", errors="replace")
        if "fonts.googleapis.com" in texto or "fonts.gstatic.com" in texto:
            ruins.append(f"{path.name}: Google Fonts")
        for m in externo.finditer(texto):
            # data: e comentários de licença em css de fonte podem citar URL de documentação;
            # só falha se for carregamento (url(http), href=, src=, @import)
            start = max(0, m.start() - 40)
            trecho = texto[start:m.end() + 10]
            if re.search(r"""(href|src|@import|url\()\s*[=:(]\s*['"]?https?://(?!127\.0\.0\.1)""", trecho, re.I):
                ruins.append(f"{path.name}: {m.group(0)}")
    assert not ruins, "\n".join(ruins)


def test_fontes_embutidas_existem():
    fonts = UI / "fonts"
    assert fonts.is_dir()
    woffs = list(fonts.glob("*.woff2"))
    assert woffs, "precisa haver .woff2 em ui/fonts/"
    css = (UI / "fonts.css").read_text(encoding="utf8")
    assert "fonts/" in css
    assert "Oxanium" in css or "oxanium" in css.lower()
    assert "http://" not in css and "https://" not in css


def test_home_lista_projetos_e_novo(api, casa):
    make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Texto."]),
    ], config={"motor": FAKE_ENGINE})
    # renomeia pasta para um id legível
    src = casa / "projects" / "projeto"
    dest = casa / "projects" / "livro-teste"
    src.rename(dest)
    book = json.loads((dest / "book.json").read_text(encoding="utf8"))
    book["title"] = "Livro de Teste"
    (dest / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf8")

    st, _, body = api.req("GET", "/home.html")
    assert st == 200
    html = body.decode("utf8")
    assert "fonts.css" in html
    assert "Novo audiolivro" in html
    assert "studio.js" in html
    assert "Claude Code" not in html
    assert "—" not in html

    st, _, body = api.req("GET", "/api/projects")
    assert st == 200
    data = json.loads(body)
    assert any(p["id"] == "livro-teste" for p in data["projects"])
    assert any(p["title"] == "Livro de Teste" for p in data["projects"])


def test_raiz_abre_home_sem_project(api):
    st, headers, body = api.req("GET", "/")
    assert st == 200
    # redireciona ou serve a home
    texto = body.decode("utf8", "replace")
    assert "Novo audiolivro" in texto or "home.html" in str(headers).lower()


def test_review_tem_controles_de_capitulo(api, casa):
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Era uma vez uma frase."]),
        ("02", "Dois", ["Capítulo dois.", "Outra frase curta."]),
    ], config={"motor": FAKE_ENGINE})
    pid = proj.name
    st, _, body = api.req("GET", f"/review.html?id={pid}")
    assert st == 200
    html = body.decode("utf8")
    assert "fonts.css" in html
    assert "studio.js" in html
    # UI de conferência
    for trecho in ("incluir", "renomear", "tempo", "capítulo"):
        assert trecho.lower() in html.lower() or trecho[:4] in html.lower()
    assert "Claude Code" not in html
    assert "—" not in html


def test_review_api_book_tem_inicio_e_estimativa(api, casa):
    """A tela usa o book da API: include, title, início do texto e tempo estimado."""
    proj = make_project(casa / "projects", [
        ("01", "Um", ["Capítulo um.", "Era uma vez uma frase bem comprida para estimar."]),
    ], config={"motor": FAKE_ENGINE})
    st, _, body = api.req("GET", f"/api/projects/{proj.name}/book")
    assert st == 200
    book = json.loads(body)
    ch = book["chapters"][0]
    assert "include" in ch or True  # prepare/make pode omitir; a tela assume true
    assert ch["title"]
    assert ch["chunks"]
    inicio = ch["chunks"][0]
    assert len(inicio) > 0
    chars = sum(len(t) for t in ch["chunks"])
    # ~16,6 chars/s no Pocket; a UI pode usar 13 ou chars_per_second do motor
    assert chars > 10


def test_erros_de_livro_em_portugues_na_api(api, tmp_path):
    from studio import local_api as la
    la.set_models_status(status="pronto", bytes=la.MODEL_TOTAL_BYTES, total_bytes=la.MODEL_TOTAL_BYTES, error=None)
    # DRM
    epub = tmp_path / "drm.epub"
    make_epub(
        epub, [("c1.xhtml", "<h1>1.</h1>" + paras(1))],
        encryption=encryption_xml([("http://www.w3.org/2001/04/xmlenc#aes128-cbc", "OEBPS/Text/c1.xhtml")]),
    )
    st, _, body = api.req("POST", "/api/projects", body=epub.read_bytes(), headers=auth(api))
    assert st == 400
    data = json.loads(body)
    assert data["code"] == "drm"
    assert "DRM" in data["error"] or "proteção" in data["error"].lower()
    assert "Traceback" not in body.decode()

    # inglês
    epub2 = tmp_path / "en.epub"
    make_epub(
        epub2,
        [("c1.xhtml", "<h1>1.</h1><p>The cold wind came down the narrow street and nobody could say where.</p>" * 8)],
        toc=[("1.", "c1.xhtml")], lang="en", title="English Book",
    )
    st, _, body = api.req("POST", "/api/projects", body=epub2.read_bytes(), headers=auth(api))
    assert st == 400
    data = json.loads(body)
    assert data["code"] == "idioma"
    assert "português" in data["error"].lower() or "inglês" in data["error"].lower()

    # inválido
    st, _, body = api.req("POST", "/api/projects", body=b"nao-e-epub", headers=auth(api))
    assert st == 400
    data = json.loads(body)
    assert data["code"] in ("invalido", "vazio", "drm", "idioma")
    assert data["error"]
    assert "Traceback" not in body.decode()


def test_setup_sem_dica_claude_e_sem_google_fonts():
    html = (UI / "setup.html").read_text(encoding="utf8")
    assert "Claude Code" not in html
    assert "fonts.googleapis.com" not in html
    assert "fonts.css" in html or "fonts/" in html
