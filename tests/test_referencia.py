"""T6 (R10, R11, R12): o capítulo de referência gerado com o Pocket e a voz padrão.

- R10: zero avisos "generation may skip words" na geração.
- R11: perda de palavras (trechos de 3+, Whisper small) no máximo 0,5 ponto percentual acima da do OmniVoice no
  mesmo capítulo, medida com o mesmo método. O teste imprime os dois números.
- R12: pedaço com ritmo fora da faixa é refeito até 4 vezes; o que continuar fora fica marcado em `flagged`.

A geração leva cerca de 1 hora na CPU e o Whisper cerca de 10 minutos por áudio. Ela fica em
REFERENCIA_DIR (padrão ~/.cache/audiobook-studio/referencia/<código do motor>), fora do git, e é retomada;
mudar studio/engines/pocket.py ou studio/generate.py gera de novo do zero.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

from tests.conftest import RAIZ, hf_home_sem_login, local_paths

pytestmark = pytest.mark.model

sys.path.insert(0, str(RAIZ / "scripts"))

R11_MARGEM_PP = 0.5


def codigo_do_motor():
    h = hashlib.sha256()
    for f in ("studio/engines/pocket.py", "studio/generate.py", "studio/engines/__init__.py"):
        h.update((RAIZ / f).read_bytes())
    return h.hexdigest()[:12]


def preparar(P, book_json, voz):
    os.makedirs(f"{P}/voice", exist_ok=True)
    b = json.load(open(book_json, encoding="utf8"))
    b["chapters"] = [c for c in b["chapters"] if c["id"] == "03"]
    json.dump(b, open(f"{P}/book.json", "w", encoding="utf8"), ensure_ascii=False)
    json.dump({"motor": "pocket"}, open(f"{P}/config.json", "w"))
    json.dump({"id": "padrao", "engine": "pocket", "model": "portuguese_24l", "file": os.path.basename(voz), "eq": True},
              open(f"{P}/voice/manifest.json", "w"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x334455:s=128x128",
                    "-frames:v", "1", f"{P}/cover.jpg"], check=True)


def test_capitulo_de_referencia_com_pocket(tmp_path):
    from medir_perda import medir_com_cache
    p = local_paths()
    book_json, voz = p["book.json corrigido à mão (lista de conferência)"], p["Exportada"]
    base = os.environ.get("REFERENCIA_DIR") or os.path.expanduser("~/.cache/audiobook-studio/referencia")
    P = os.path.join(base, codigo_do_motor())
    if not os.path.exists(f"{P}/book.json"):
        preparar(P, book_json, voz)
    env = hf_home_sem_login(tmp_path)
    env["VOICE_PACK_DIR"] = os.path.dirname(voz)
    cap = f"{P}/chapters/03.m4a"
    if not os.path.exists(cap):
        r = subprocess.run([sys.executable, "-m", "studio.generate", "--project", P, "--device", "cpu"], cwd=RAIZ, env=env,
                           capture_output=True, text=True, timeout=4 * 3600)
        open(f"{P}/generate.stderr.log", "a", encoding="utf8").write(r.stderr)
        assert r.returncode == 0, r.stderr[-3000:]
    log = open(f"{P}/generate.stderr.log", encoding="utf8").read() if os.path.exists(f"{P}/generate.stderr.log") else ""

    # R10
    avisos = len(re.findall(r"generation may skip words", log))
    # R12
    ev = [json.loads(l) for l in open(f"{P}/work/progress.jsonl", encoding="utf8")]
    pedacos = [e for e in ev if e["kind"] == "piece"]
    refeitos = [e for e in pedacos if e["attempt"] != 0]
    marcados = [k for e in ev if e["kind"] == "done" for k in e["flagged"]]
    # R11
    omni = medir_com_cache(p["whisper_python"], book_json, "03", p["Áudio OmniVoice desse capítulo, para R11"])
    pocket = medir_com_cache(p["whisper_python"], book_json, "03", cap)
    teto = omni["perdidas_pct"] + R11_MARGEM_PP
    print(f"\nR10: {avisos} avisos 'generation may skip words' em {len(pedacos)} pedaços")
    print(f"R12: {len(refeitos)} pedaços refeitos, {len([e for e in refeitos if e['attempt'] == -1])} fora da faixa depois de 4 tentativas; trechos marcados: {marcados}")
    print(f"R11: OmniVoice perdeu {omni['perdidas']} de {omni['total']} ({omni['perdidas_pct']}%); "
          f"Pocket perdeu {pocket['perdidas']} de {pocket['total']} ({pocket['perdidas_pct']}%); teto {teto:.3f}%")
    print("Pocket perdeu:", pocket["exemplos_perdidos"])
    assert avisos == 0
    assert pocket["total"] == omni["total"]
    assert pocket["perdidas_pct"] <= teto, (pocket["perdidas"], pocket["perdidas_pct"], teto)
