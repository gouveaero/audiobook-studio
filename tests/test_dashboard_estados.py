"""Guia 5 (R14, R15, R18): painel local sem nuvem/GPU e estados coerentes."""
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "ui"


def test_dashboard_local_sem_nuvem_nem_gpu_no_hud():
    html = (UI / "dashboard.html").read_text(encoding="utf8")
    assert "modoLocal" in html
    assert "geração local pronta" in html
    assert "clone_voice --ref" not in html
    assert "synth cloud" not in html
    assert "Continuar a geração" in html
    assert "Voltar ao início" in html
    assert 'rotuloStatus' in html or 'cancelado' in html
    # nuvem/GPU só no fluxo antigo (mode cloud), não no HUD local padrão
    assert 'modoLocal ? ""' in html or "$(\"gc\").hidden" in html or 'gc").hidden' in html


def test_dashboard_sync_trata_estados_finais():
    html = (UI / "dashboard.html").read_text(encoding="utf8")
    for st in ("cancelado", "pausado", "montando", "pronto", "erro"):
        assert st in html
    assert "btnHome" in html or "Voltar ao início" in html
    assert "etaTxt" in html
