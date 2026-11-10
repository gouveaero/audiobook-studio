#!/usr/bin/env python3
"""Monta build/voice-pack/ a partir da origem em LOCAL_MD (fora do git).

Uso:
  LOCAL_MD=docs/specs/beta-desktop/local.md python scripts/build_voice_pack.py

Sem LOCAL_MD ou sem a origem: sai com mensagem clara (código 2). O instalador
pode seguir sem o pacote; o app usa a voz de reserva.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEST_PADRAO = RAIZ / "build" / "voice-pack"
ARQUIVO_VOZ = "voz_portuguese_24l.safetensors"
MODEL_ID = "portuguese_24l"


def ler_local_md(texto: str) -> dict:
    """Extrai rótulo e caminhos da seção de voz padrão. Sem caminhos no código."""
    label = None
    exportada = None
    referencia = None
    in_voz = False
    for linha in texto.splitlines():
        if re.match(r"^##\s+Voz\s+padr", linha, re.I):
            in_voz = True
            m = re.search(r'rótulo\s+no\s+app:\s*"([^"]+)"', linha, re.I)
            if not m:
                m = re.search(r"rótulo\s+no\s+app:\s*'([^']+)'", linha, re.I)
            if m:
                label = m.group(1).strip()
            continue
        if in_voz and linha.startswith("## "):
            break
        if not in_voz:
            continue
        m = re.match(r"^-\s*(?P<rotulo>.*?):\s*`(?P<path>[^`]+)`", linha.strip())
        if not m:
            continue
        rot = m.group("rotulo").strip().lower()
        path = os.path.expanduser(m.group("path").strip())
        if rot.startswith("exportada"):
            exportada = path
        elif "refer" in rot:
            referencia = path
    return {"label": label, "exportada": exportada, "referencia": referencia}


def montar(origem: dict, dest: Path) -> Path:
    exportada = Path(origem["exportada"])
    if not exportada.is_file():
        raise FileNotFoundError(f"Arquivo da voz exportada não encontrado: {exportada}")
    label = (origem.get("label") or "").strip()
    if not label:
        raise ValueError('LOCAL_MD sem rótulo no cabeçalho (rótulo no app: "...").')
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    alvo = dest / ARQUIVO_VOZ
    shutil.copy2(exportada, alvo)
    ref = origem.get("referencia")
    if ref and Path(ref).is_file():
        shutil.copy2(ref, dest / "ref.wav")
    man = {
        "id": "padrao",
        "label": label,
        "engine": "pocket",
        "model": MODEL_ID,
        "file": ARQUIVO_VOZ,
        "eq": True,
    }
    (dest / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=1) + "\n",
        encoding="utf8",
    )
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=DEST_PADRAO,
        help=f"pasta de saída (padrão: {DEST_PADRAO})",
    )
    ap.add_argument(
        "--local-md",
        default=os.environ.get("LOCAL_MD", ""),
        help="caminho de LOCAL_MD (ou variável LOCAL_MD)",
    )
    a = ap.parse_args(argv)
    if not a.local_md:
        print(
            "build_voice_pack: defina LOCAL_MD com o arquivo de caminhos desta máquina "
            "(ex.: docs/specs/beta-desktop/local.md). Sem isso o instalador segue sem "
            "o pacote e o app usa a voz de reserva.",
            file=sys.stderr,
        )
        return 2
    path = Path(a.local_md).expanduser()
    if not path.is_file():
        print(f"build_voice_pack: LOCAL_MD não é um arquivo: {path}", file=sys.stderr)
        return 2
    info = ler_local_md(path.read_text(encoding="utf8"))
    if not info.get("exportada"):
        print(
            "build_voice_pack: LOCAL_MD sem linha 'Exportada: `...`' na seção Voz padrão. "
            "O instalador pode seguir sem o pacote.",
            file=sys.stderr,
        )
        return 2
    try:
        out = montar(info, a.out)
    except (OSError, ValueError, FileNotFoundError) as e:
        print(f"build_voice_pack: {e}", file=sys.stderr)
        return 2
    print(f"build_voice_pack: ok → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
