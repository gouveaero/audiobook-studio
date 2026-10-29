"""Gera o áudio dos capítulos a partir de book.json, clonando a voz de referência. Roda igual em CUDA, Apple (MPS) e CPU.

  python -m studio.generate --project projects/meu-livro [--only 06,14] [--workers 3] [--device auto]

Estrutura do projeto:
  book.json            (studio.prepare_book)
  voice/ref.wav        referência de 3 a 15 s     voice/ref.txt  transcrição exata dela     (studio.prepare_voice)
  work/chunks/NN_KKKK.wav   cache por trecho (retomável; apagar o arquivo refaz o trecho)
  work/locks/NN             trava de capítulo, para vários processos dividirem a fila
  chapters/NN.m4a           saída; só aparece com o arquivo completo (escrita em .tmp e renomeada)
  work/progress.jsonl       eventos: retry, done, flagged

Checagem de qualidade: cada trecho tem o ritmo (caracteres por segundo) conferido. Fora de 10 a 17 é provável corte ou
repetição; o trecho é regenerado com outra semente (até 4 tentativas) e, se falhar, fica marcado em `flagged`.
"""
import argparse, json, os, subprocess, sys, time, warnings


def pick_device(name):
    import torch
    if name != "auto":
        return name
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--only", default="", help="ids de capítulo separados por vírgula")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--workers", type=int, default=0, help="processos em paralelo (padrão: 3 em CUDA, 1 no resto)")
    ap.add_argument("--steps", type=int, default=32)
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
    device = pick_device(a.device)

    if not a.worker_child:  # processo pai: abre N filhos que dividem a fila por trava
        n = a.workers or (3 if device == "cuda" else 1)
        if n > 1:
            kids = [subprocess.Popen([sys.executable, "-m", "studio.generate", "--project", P, "--only", a.only,
                                      "--device", device, "--steps", str(a.steps), "--worker-child"]) for _ in range(n)]
            sys.exit(max(k.wait() for k in kids))

    warnings.filterwarnings("ignore")
    import torch, torchaudio
    from omnivoice.models.omnivoice import OmniVoice
    ref, ref_txt = f"{P}/voice/ref.wav", open(f"{P}/voice/ref.txt", encoding="utf8").read().strip()
    lang = book.get("language", "pt")
    model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=torch.float16)
    sr = model.sampling_rate

    def log(**kw):
        with open(f"{P}/work/progress.jsonl", "a") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")

    def synth(text):
        for attempt in range(4):
            torch.manual_seed(1000 + attempt)
            w = torch.as_tensor(model.generate(text=text, language=lang, ref_audio=ref, ref_text=ref_txt,
                                               num_step=a.steps, guidance_scale=2.0)[0]).float()
            w = w if w.dim() == 2 else w[None]
            rate = len(text) / (w.shape[1] / sr)
            if len(text) < 60 or 10.0 <= rate <= 17.0:
                return w, rate, attempt
        return w, rate, -1

    def claim(c):
        if os.path.exists(f"{P}/chapters/{c['id']}.m4a"):
            return False
        try:
            os.close(os.open(f"{P}/work/locks/{c['id']}", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            return False

    t0 = time.time()
    for c in chapters:
        if not claim(c):
            continue
        parts, flagged = [], []
        for k, (txt, pz) in enumerate(zip(c["chunks"], c["pauses"])):
            f = f"{P}/work/chunks/{c['id']}_{k:04d}.wav"
            if not os.path.exists(f):
                w, rate, att = synth(txt)
                torchaudio.save(f, w.cpu(), sr)
                if att != 0:
                    log(kind="retry", ch=c["id"], k=k, rate=round(rate, 1), attempt=att)
                if att == -1:
                    flagged.append(k)
            w, _ = torchaudio.load(f)
            parts += [w, torch.zeros(1, int(sr * pz))]
        wav, tmp, out = f"{P}/work/{c['id']}.{os.getpid()}.wav", f"{P}/chapters/{c['id']}.{os.getpid()}.tmp.m4a", f"{P}/chapters/{c['id']}.m4a"
        torchaudio.save(wav, torch.cat(parts, 1), sr)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-b:a", "64k", tmp], check=True)
        os.remove(wav)
        os.rename(tmp, out)  # só existe como NN.m4a quando está completo
        log(kind="done", ch=c["id"], title=c["title"], secs=round(time.time() - t0), flagged=flagged)


if __name__ == "__main__":
    main()
