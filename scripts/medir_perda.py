#!/usr/bin/env python
"""Mede palavras perdidas e extras num áudio de capítulo, comparando a transcrição do Whisper `small` com o texto.

  python scripts/medir_perda.py --book projects/x/book.json --chapter 03 audio1.m4a [audio2.wav ...] [--json saida.json]

Método (o mesmo da medição de referência do projeto): faster-whisper `small`, CPU, int8, beam 1, VAD; palavras
normalizadas (minúsculas, só letras e números); `difflib.SequenceMatcher` sem autojunk; conta só os trechos
perdidos ou extras com 3 ou mais palavras, porque trocas de uma ou duas palavras costumam ser erro do Whisper.

Este arquivo roda com o Python que tem o faster-whisper (ver local.md), por isso só importa o Whisper em `transcrever`.
As funções puras (`normalizar`, `comparar`) são usadas pelos testes sem modelo.
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

MIN_TRECHO = 3


def normalizar(texto):
    return re.findall(r"\w+", texto.lower())


def texto_do_capitulo(book_json, chapter_id):
    caps = json.load(open(book_json, encoding="utf8"))["chapters"]
    c = [x for x in caps if x["id"] == chapter_id][0]
    return " ".join(c["chunks"])


def comparar(ref, ouvido):
    """`ref` e `ouvido` são listas de palavras normalizadas."""
    sm = difflib.SequenceMatcher(None, ref, ouvido, autojunk=False)
    perdidos, extras = [], []
    for op, a, b, c, d in sm.get_opcodes():
        if op in ("delete", "replace") and (b - a) - (d - c) >= MIN_TRECHO:
            perdidos.append((a, b))
        if op in ("insert", "replace") and (d - c) - (b - a) >= MIN_TRECHO:
            extras.append((c, d))
    total = len(ref)
    n_perdidas = sum(b - a for a, b in perdidos)
    return {
        "total": total, "ouvidas": len(ouvido), "semelhanca": round(sm.ratio(), 4),
        "perdidas": n_perdidas, "trechos_perdidos": len(perdidos),
        "perdidas_pct": round(100.0 * n_perdidas / total, 3) if total else 0.0,
        "extras": sum(d - c for c, d in extras), "trechos_extras": len(extras),
        "posicoes_perdidas": [[a, b] for a, b in perdidos],
        "exemplos_perdidos": [" ".join(ref[a:b])[:110] for a, b in sorted(perdidos, key=lambda t: t[0] - t[1])[:8]],
        "exemplos_extras": [" ".join(ouvido[c:d])[:110] for c, d in sorted(extras, key=lambda t: t[0] - t[1])[:5]],
    }


def pedaco_de_cada_palavra(pedacos):
    """`pedacos` em ordem: (capítulo, trecho, pedaço, texto). Devolve (trecho, pedaço) de cada palavra normalizada
    do texto juntado, na mesma ordem das palavras de referência usadas em `comparar`."""
    saida = []
    for _, k, s, texto in pedacos:
        saida += [(k, s)] * len(normalizar(texto))
    return saida


def transcrever(audio):
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(audio, language="pt", beam_size=1, vad_filter=True)
    return " ".join(s.text for s in segs)


def medir(book_json, chapter_id, audios):
    ref = normalizar(texto_do_capitulo(book_json, chapter_id))
    saida = {}
    for f in audios:
        r = comparar(ref, normalizar(transcrever(f)))
        r["audio"] = os.path.basename(f)
        saida[f] = r
        print(f"\n== {os.path.basename(f)}: ouvidas {r['ouvidas']} de {r['total']} palavras; semelhança {r['semelhanca']:.3f}; "
              f"trechos perdidos (3+) {r['trechos_perdidos']} = {r['perdidas']} palavras ({r['perdidas_pct']}%); "
              f"extras (3+) {r['trechos_extras']} = {r['extras']} palavras", flush=True)
        for ex in r["exemplos_perdidos"]:
            print("  perdeu:", ex, flush=True)
        for ex in r["exemplos_extras"]:
            print("  extra:", ex, flush=True)
    return saida


def _chave_cache(book_json, chapter_id, audio):
    st = os.stat(audio)
    h = hashlib.sha256(f"{os.path.abspath(audio)}|{st.st_size}|{int(st.st_mtime)}|{chapter_id}".encode()).hexdigest()[:24]
    return h


def medir_com_cache(python, book_json, chapter_id, audio, cache_dir=None):
    """Roda este script com `python` (o que tem o faster-whisper) e guarda o resultado fora do git.

    O cache fica em MEDICAO_CACHE_DIR (padrão ~/.cache/audiobook-studio/medicoes) e vale enquanto o áudio não mudar."""
    cache_dir = cache_dir or os.environ.get("MEDICAO_CACHE_DIR") or os.path.expanduser("~/.cache/audiobook-studio/medicoes")
    os.makedirs(cache_dir, exist_ok=True)
    arq = os.path.join(cache_dir, _chave_cache(book_json, chapter_id, audio) + ".json")
    if os.path.exists(arq):
        return json.load(open(arq, encoding="utf8"))
    saida = arq + ".tmp"
    subprocess.run([python, os.path.abspath(__file__), "--book", book_json, "--chapter", chapter_id, audio, "--json", saida],
                   check=True, timeout=3600)
    r = json.load(open(saida, encoding="utf8"))[audio]
    json.dump(r, open(arq, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    os.remove(saida)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--json", default="", help="grava o resultado neste arquivo")
    ap.add_argument("audios", nargs="+")
    a = ap.parse_args(argv)
    r = medir(a.book, a.chapter, a.audios)
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
