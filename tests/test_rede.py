"""T24 / R37: destinos de rede no código (studio/ e ui/).

Permitidos: Hugging Face, GitHub Releases e o endereço opcional do formulário
(DONATION_URL / ANDROID_WAITLIST_URL em brand.py). Nenhum outro domínio.
Chamadas de rede só nos pontos previstos (download do modelo e checagem de versão).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
STUDIO = RAIZ / "studio"
UI = RAIZ / "ui"

# Domínios/hosts de rede permitidos em strings do app (R37).
PERMITIDOS = (
    "huggingface.co",
    "hf.co",
    "github.com",
    "api.github.com",
    "127.0.0.1",
    "localhost",
)

# URLs que não são chamadas de rede (namespaces XML, docs).
IGNORAR_SUBSTRING = (
    "w3.org",
    "idpf.org",
    "daisy.org",
    "purl.org",
    "oasis-open.org",
    "ns.adobe.com",  # namespace de ofuscação de fonte no EPUB, não é chamada de rede
    "xmlns",
    "opendocument",
)

URL_RE = re.compile(r"https?://[^\s\"'`<>\)]+", re.I)


def _textos_codigo() -> list[tuple[Path, str]]:
    out = []
    for base in (STUDIO, UI):
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".py", ".js", ".html", ".css", ".json"}:
                continue
            if p.name.endswith(".woff2"):
                continue
            out.append((p, p.read_text(encoding="utf8", errors="replace")))
    return out


def _brand_opcionais() -> set[str]:
    """Endereços opcionais do formulário (doação / Android) quando preenchidos."""
    brand = (STUDIO / "brand.py").read_text(encoding="utf8")
    urls = set()
    for nome in ("DONATION_URL", "ANDROID_WAITLIST_URL"):
        m = re.search(rf'{nome}\s*=\s*"([^"]*)"', brand)
        if m and m.group(1).strip():
            urls.add(m.group(1).strip())
    return urls


def _host_ok(url: str, opcionais: set[str]) -> bool:
    if url in opcionais:
        return True
    low = url.lower()
    if any(x in low for x in IGNORAR_SUBSTRING):
        return True
    if any(d in low for d in PERMITIDOS):
        return True
    return False


def test_nenhum_dominio_fora_da_lista_em_studio_e_ui():
    opcionais = _brand_opcionais()
    problemas = []
    for path, texto in _textos_codigo():
        for m in URL_RE.finditer(texto):
            url = m.group(0).rstrip(".,);]")
            if not _host_ok(url, opcionais):
                rel = path.relative_to(RAIZ)
                problemas.append(f"{rel}: destino não permitido")
    assert not problemas, "\n".join(problemas)


def test_chamadas_de_rede_so_nos_pontos_previstos():
    """urlopen / Request / hf_hub_* só em local_api (modelo/versão) e app (loopback)."""
    permitidos_modulos = {
        "studio/local_api.py",
        "studio/app.py",  # wait_up em 127.0.0.1
        "studio/server.py",  # só docstring/print local
        "studio/selftest.py",  # só loopback
    }
    # cloud.py / publish_drive.py usam CLIs (colab, rclone), não URLs HTTP do app beta.
    problemas = []
    for path in STUDIO.rglob("*.py"):
        rel = str(path.relative_to(RAIZ)).replace("\\", "/")
        src = path.read_text(encoding="utf8", errors="replace")
        usa = bool(re.search(
            r"\b(urlopen|urllib\.request\.Request|hf_hub_download|hf_hub_url|get_hf_file_metadata)\b",
            src,
        ))
        if not usa:
            continue
        if rel not in permitidos_modulos:
            problemas.append(f"{rel}: chamada de rede fora dos pontos previstos")
    assert not problemas, "\n".join(problemas)


def test_brand_expoe_urls_opcionais_do_formulario():
    brand = (STUDIO / "brand.py").read_text(encoding="utf8")
    assert "DONATION_URL" in brand
    assert "ANDROID_WAITLIST_URL" in brand
    assert "GITHUB_REPO" in brand
