"""Prepara a voz de referência: recorta um trecho limpo de até 15 s que termina no fim de uma frase, transcreve e salva.

  python -m studio.prepare_voice gravacao.m4a --project projects/meu-livro [--text "transcrição exata"] [--lang pt]

Saída em <project>/voice/: ref.wav (mono 24 kHz), ref.txt (transcrição), peaks.json (para a interface).
O modelo aceita de 3 a 20 s com transcrição; entre 8 e 15 s dá o melhor resultado. A transcrição precisa ser exata:
confira ref.txt e corrija à mão se o Whisper errou alguma palavra.
"""
import argparse, json, os, struct, subprocess, wave

LIMIT = 15.0


def to_wav(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "24000", dst], check=True)


def peaks(wav_path, bins=180):
    w = wave.open(wav_path); n = w.getnframes(); d = struct.unpack("<%dh" % n, w.readframes(n)); step = max(1, n // bins)
    return [round(min(1, max(abs(x) for x in d[i * step:(i + 1) * step]) / 20000), 3) for i in range(bins)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio"); ap.add_argument("--project", required=True)
    ap.add_argument("--text", help="transcrição exata do trecho (pula o Whisper e usa o áudio inteiro até 20 s)")
    ap.add_argument("--lang", default="pt")
    ap.add_argument("--start", type=float, default=0.0, help="começa o recorte neste segundo")
    a = ap.parse_args(argv)
    out = f"{a.project}/voice"; os.makedirs(out, exist_ok=True)
    full = f"{out}/_full.wav"; to_wav(a.audio, full)
    if a.text:
        cut, text = 20.0, a.text.strip()
    else:
        from faster_whisper import WhisperModel
        segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(full, language=a.lang)
        segs = [s for s in segs if s.start >= a.start - 0.2]
        if not segs:
            raise SystemExit("Não encontrei fala no áudio.")
        t0, picked = segs[0].start, []
        for s in segs:
            if s.end - t0 > LIMIT and picked:
                break
            picked.append(s)
        cut, text = picked[-1].end - t0, " ".join(s.text.strip() for s in picked)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", full, "-t", f"{cut:.2f}", f"{out}/ref.wav"], check=True)
    if a.text:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(a.start), "-i", full, "-t", str(cut), f"{out}/ref.wav"], check=True)
    os.remove(full)
    open(f"{out}/ref.txt", "w", encoding="utf8").write(text + "\n")
    json.dump(peaks(f"{out}/ref.wav"), open(f"{out}/peaks.json", "w"))
    print(f"referência: {out}/ref.wav ({cut:.1f} s)\ntranscrição: {text}\nConfira {out}/ref.txt: precisa estar exata.")


if __name__ == "__main__":
    main()
