"""Gera o áudio dos capítulos a partir de book.json. Roda igual em CUDA, Apple (MPS) e CPU.

  python -m studio.generate --project projects/meu-livro [--only 06,14] [--workers 3] [--device auto] [--motor omnivoice]

Estrutura do projeto:
  book.json            (studio.prepare_book)
  config.json          "motor": omnivoice (padrão, projetos antigos) ou pocket
  voice/ref.wav        referência de 3 a 15 s     voice/ref.txt  transcrição exata dela     (studio.prepare_voice)
  work/chunks/NN_KKKK.wav   cache por trecho (retomável; apagar o arquivo refaz o trecho)
  work/chunks/NN_KKKK.pSS.wav  pedaços de um trecho, quando o motor corta o trecho (Pocket); somem no trecho pronto
  work/locks/NN             trava de capítulo, para vários processos dividirem a fila
  chapters/NN.m4a           saída; só aparece com o arquivo completo (escrita em .tmp e renomeada)
  work/progress.jsonl       eventos: retry, done, flagged

Checagem de qualidade: cada pedaço tem o ritmo (caracteres por segundo) conferido na faixa do motor. Fora dela é
provável corte ou repetição; o pedaço é regenerado com outra semente (até 4 tentativas) e, se falhar, o trecho fica
marcado em `flagged`.
"""
import argparse, json, os, subprocess, sys, time, warnings

import numpy as np

from studio.audio import eq_do_projeto, montar_capitulo, silencio_antes_do_titulo
from studio.engines import engine_name, load_engine
from studio.wavio import read_wav, write_wav

PIECE_PAUSE = 0.25   # segundos entre pedaços de um mesmo trecho
MIN_CHECK_CHARS = 60  # pedaços mais curtos não têm o ritmo conferido
MAX_ATTEMPTS = 4


def pick_device(name):
    import torch
    if name != "auto":
        return name
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def engine_name_for(P):
    try:
        cfg = json.load(open(f"{P}/config.json"))
    except (OSError, ValueError):
        cfg = {}
    return engine_name(cfg)


def voice_for(P, book):
    ref_txt = f"{P}/voice/ref.txt"
    return {"ref_wav": f"{P}/voice/ref.wav", "language": book.get("language", "pt"),
            "ref_txt": open(ref_txt, encoding="utf8").read().strip() if os.path.exists(ref_txt) else ""}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--only", default="", help="ids de capítulo separados por vírgula")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--workers", type=int, default=0, help="processos em paralelo (padrão: 3 em CUDA, 1 no resto)")
    ap.add_argument("--steps", type=int, default=32)
    ap.add_argument("--motor", default="", help="motor (padrão: o de config.json, senão omnivoice)")
    ap.add_argument("--worker-child", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    P = a.project
    for d in ("work/chunks", "work/locks", "chapters"):
        os.makedirs(f"{P}/{d}", exist_ok=True)
    book = json.load(open(f"{P}/book.json"))
    chapters = book["chapters"]
    if a.only:
        keep = set(a.only.split(","))
        chapters = [c for c in chapters if c["id"] in keep]
    motor = a.motor or engine_name_for(P)
    device = pick_device(a.device) if motor in ("omnivoice", "pocket") else a.device

    if not a.worker_child:  # processo pai: abre N filhos que dividem a fila por trava
        n = a.workers or (3 if device == "cuda" else 1)
        if n > 1:
            kids = [subprocess.Popen([sys.executable, "-m", "studio.generate", "--project", P, "--only", a.only,
                                      "--device", device, "--steps", str(a.steps), "--motor", motor, "--worker-child"])
                    for _ in range(n)]
            sys.exit(max(k.wait() for k in kids))

    warnings.filterwarnings("ignore")
    engine = load_engine(motor, device=device, steps=a.steps)
    engine.load(voice_for(P, book))
    sr = engine.sample_rate
    lo, hi = engine.rate_range

    def log(**kw):
        with open(f"{P}/work/progress.jsonl", "a") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")

    def synth(text):
        for attempt in range(MAX_ATTEMPTS):
            w = np.asarray(engine.synth(text, attempt), dtype=np.float32).reshape(-1)
            rate = len(text) / (len(w) / sr)
            if len(text) < MIN_CHECK_CHARS or lo <= rate <= hi:
                return w, rate, attempt
        return w, rate, -1

    def synth_chunk(c, k, txt):
        """Gera o trecho k (em pedaços, se o motor cortar). Devolve (ritmo, tentativa) da pior parte."""
        f = f"{P}/work/chunks/{c['id']}_{k:04d}.wav"
        pieces = engine.split(txt)
        if len(pieces) == 1:
            w, rate, att = synth(txt)
            write_wav(f, w, sr)
            return rate, att
        parts, worst = [], (None, 0)
        for s, piece in enumerate(pieces):
            pf = f"{P}/work/chunks/{c['id']}_{k:04d}.p{s:02d}.wav"
            if not os.path.exists(pf):
                w, rate, att = synth(piece)
                write_wav(pf, w, sr)
                if att != 0 and (worst[0] is None or att == -1 or (worst[1] != -1 and att > worst[1])):
                    worst = (rate, att)
            w, _ = read_wav(pf)
            parts += [w, np.zeros(int(sr * PIECE_PAUSE), dtype=np.float32)]
        write_wav(f, np.concatenate(parts[:-1]), sr)
        for s in range(len(pieces)):
            os.remove(f"{P}/work/chunks/{c['id']}_{k:04d}.p{s:02d}.wav")
        return worst

    def claim(c):
        if os.path.exists(f"{P}/chapters/{c['id']}.m4a"):
            return False
        try:
            os.close(os.open(f"{P}/work/locks/{c['id']}", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            return False

    t0 = time.time()
    usar_eq = eq_do_projeto(P)
    livro = book["chapters"]
    por_id = {c["id"]: i for i, c in enumerate(livro)}
    for c in chapters:
        if not claim(c):
            continue
        parts, flagged = [], []
        wsr = sr
        for k, (txt, pz) in enumerate(zip(c["chunks"], c["pauses"])):
            f = f"{P}/work/chunks/{c['id']}_{k:04d}.wav"
            if not os.path.exists(f):
                rate, att = synth_chunk(c, k, txt)
                if att != 0:
                    log(kind="retry", ch=c["id"], k=k, rate=round(rate, 1), attempt=att)
                if att == -1:
                    flagged.append(k)
            w, wsr = read_wav(f)
            parts.append(w)
        lead = silencio_antes_do_titulo(livro, por_id[c["id"]])
        audio, _ = montar_capitulo(
            parts, c["pauses"], c.get("head") or [], wsr, eq=usar_eq, silencio_antes=lead,
        )
        wav, tmp, out = f"{P}/work/{c['id']}.{os.getpid()}.wav", f"{P}/chapters/{c['id']}.{os.getpid()}.tmp.m4a", f"{P}/chapters/{c['id']}.m4a"
        write_wav(wav, audio, wsr)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-b:a", "64k", tmp], check=True)
        os.remove(wav)
        os.rename(tmp, out)  # só existe como NN.m4a quando está completo
        log(kind="done", ch=c["id"], title=c["title"], secs=round(time.time() - t0), flagged=flagged)


if __name__ == "__main__":
    main()
