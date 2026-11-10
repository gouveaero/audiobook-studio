"""R48: atributo hidden não pode ser vencido por display: inline-block (Doar/Android etc.)."""
import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "ui"

# Páginas HTML da interface (não CSS).
HTMLS = sorted(UI.glob("*.html"))


def _usa_atributo_hidden(html: str) -> bool:
    # atributo HTML hidden (não overflow:hidden no CSS)
    return bool(re.search(r"(?:^|>|\s)hidden(?:\s|=|/|>)", html))


def _tem_regra_hidden_none(texto: str) -> bool:
    # [hidden] { ... display: none !important ... }
    return bool(
        re.search(
            r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important",
            texto,
            re.IGNORECASE | re.DOTALL,
        )
    )


def _css_incluidos(html: str) -> list[Path]:
    out = []
    for m in re.finditer(r'href=["\'](/?[\w./-]+\.css)["\']', html):
        nome = m.group(1).lstrip("/")
        cand = UI / Path(nome).name
        if cand.is_file():
            out.append(cand)
    return out


def test_paginas_com_hidden_carregam_regra_display_none_important():
    faltando = []
    for path in HTMLS:
        html = path.read_text(encoding="utf8")
        if not _usa_atributo_hidden(html):
            continue
        ok = _tem_regra_hidden_none(html)
        if not ok:
            for css in _css_incluidos(html):
                if _tem_regra_hidden_none(css.read_text(encoding="utf8")):
                    ok = True
                    break
        if not ok:
            faltando.append(path.name)
    assert not faltando, (
        "páginas com atributo hidden sem [hidden]{display:none!important} "
        f"(na página ou CSS incluído): {faltando}"
    )
