#!/usr/bin/env python3
"""Monta o audiolivro final a partir dos capítulos gerados.

Produz, em --out:
  capitulos/NN - Título.m4a   um arquivo por capítulo, com capa e metadados
  <album>.m4b                 audiolivro único, capítulos marcados, capa embutida
  <album>.mp4                 vídeo (capa ampliada com fundo desfocado + áudio, capítulos marcados)

Uso:
  assemble.py --book book.json --chapters capitulos --cover capa.jpeg --out saida \
      --album "Título do Livro" --author "Autor" --narrator "Nome da Voz" \
      --year 2011 --lang por [--pre prefacio.wav:Prefácio] [--limit N] [--no-video]
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--project", help="pasta do projeto: usa book.json, chapters/, cover.jpg e config.json dela")
ap.add_argument("--book"); ap.add_argument("--chapters"); ap.add_argument("--cover"); ap.add_argument("--out")
ap.add_argument("--album"); ap.add_argument("--author"); ap.add_argument("--narrator")
ap.add_argument("--year", default="")
ap.add_argument("--lang", default="por")
ap.add_argument("--pre", action="append", default=[], help="arquivo.wav:Título, entra antes dos capítulos")
ap.add_argument("--limit", type=int, default=0, help="só os N primeiros (teste)")
ap.add_argument("--no-video", action="store_true")
a = ap.parse_args()
if a.project:
    P = a.project
    bk = json.load(open(f"{P}/book.json")); cf = json.load(open(f"{P}/config.json")) if os.path.exists(f"{P}/config.json") else {}
    a.book = a.book or f"{P}/book.json"; a.chapters = a.chapters or f"{P}/chapters"; a.cover = a.cover or f"{P}/cover.jpg"
    a.out = a.out or f"{P}/audiobook"; a.album = a.album or bk.get("title", "Audiobook")
    a.author = a.author or bk.get("author", ""); a.narrator = a.narrator or cf.get("voz", "voz clonada")
for k in ("book", "chapters", "cover", "out", "album", "author", "narrator"):
    if not getattr(a, k):
        sys.exit(f"falta --{k} (ou use --project)")


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ERRO: " + " ".join(cmd[:4]) + "...\n" + r.stderr[-800:])
    return r.stdout


def dur(f):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f).strip())


ROMAN = {"I": "I", "II": "II", "III": "III", "IV": "IV", "V": "V", "VI": "VI", "VII": "VII", "VIII": "VIII", "IX": "IX"}


def titulo(t):
    t = re.sub(r"\s+", " ", t).strip()   # títulos do EPUB às vezes trazem quebra de linha
    m = re.match(r"^([IVX]+)\.\s+(.+)$", t)          # "I. JUDAÍSMO" -> "Parte I: Judaísmo"
    if m and m.group(1) in ROMAN:
        return f"Parte {m.group(1)}: {m.group(2).capitalize()}"
    return t


def safe(s):
    return re.sub(r"[\\/:*?\"<>|]", "-", s).strip()


os.makedirs(f"{a.out}/capitulos", exist_ok=True)
tmp = tempfile.mkdtemp(prefix="assemble_")
book = json.load(open(a.book))
book = book["chapters"] if isinstance(book, dict) else book

tracks = []  # (arquivo, título)
for spec in a.pre:
    f, t = spec.rsplit(":", 1)
    if f.endswith(".m4a"):
        tracks.append((f, t))
    else:
        o = f"{tmp}/pre_{len(tracks)}.m4a"
        run("ffmpeg", "-y", "-loglevel", "error", "-i", f, "-ac", "1", "-b:a", "64k", o)
        tracks.append((o, t))
for c in book:
    f = f"{a.chapters}/{c['id']}.m4a"
    if os.path.exists(f):
        tracks.append((f, titulo(c["title"])))
    else:
        print("aviso: falta", f)
if a.limit:
    tracks = tracks[:a.limit]
N = len(tracks)
print(N, "faixas")

# 1) um arquivo por capítulo, com capa e metadados
for i, (f, t) in enumerate(tracks, 1):
    out = f"{a.out}/capitulos/{i:02d} - {safe(t)}.m4a"
    run("ffmpeg", "-y", "-loglevel", "error", "-i", f, "-i", a.cover, "-map", "0:a", "-map", "1:v", "-c", "copy",
        "-disposition:v:0", "attached_pic", "-metadata", f"title={t}", "-metadata", f"artist={a.author}",
        "-metadata", f"album_artist={a.author}", "-metadata", f"album={a.album}", "-metadata", f"composer={a.narrator}",
        "-metadata", f"comment=Narração: {a.narrator} (voz clonada por IA)", "-metadata", "genre=Audiobook",
        "-metadata", f"track={i}/{N}", "-metadata", f"date={a.year}", "-metadata:s:a:0", f"language={a.lang}",
        "-f", "ipod", out)

# 2) M4B único com capítulos
lst = f"{tmp}/list.txt"
with open(lst, "w") as fh:
    for f, _ in tracks:
        fh.write("file '" + os.path.abspath(f).replace("'", "'\\''") + "'\n")
joined = f"{tmp}/joined.m4a"
run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined)
meta = f"{tmp}/meta.txt"
t0 = 0
with open(meta, "w") as fh:
    fh.write(";FFMETADATA1\n")
    for k, v in (("title", a.album), ("artist", a.author), ("album_artist", a.author), ("album", a.album),
                 ("composer", a.narrator), ("genre", "Audiobook"), ("date", a.year),
                 ("comment", f"Narração: {a.narrator} (voz clonada por IA)")):
        fh.write(f"{k}={v}\n")
    for f, t in tracks:
        d = dur(f); s, e = int(t0 * 1000), int((t0 + d) * 1000)
        fh.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={s}\nEND={e}\ntitle={t}\n")
        t0 += d
m4b = f"{a.out}/{safe(a.album)}.m4b"
run("ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", meta, "-i", a.cover, "-map", "0:a", "-map", "2:v",
    "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", "-disposition:v:0", "attached_pic",
    "-metadata:s:a:0", f"language={a.lang}", "-f", "ipod", m4b)
print("M4B:", m4b, round(os.path.getsize(m4b) / 1e6), "MB,", round(t0 / 3600, 2), "h")

# 3) vídeo: capa ampliada sobre fundo desfocado
if not a.no_video:
    mp4 = f"{a.out}/{safe(a.album)}.mp4"
    flt = ("[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=45:6,eq=brightness=-0.18[bg];"
           "[b]scale=-2:920:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "1", "-i", a.cover, "-i", joined, "-i", meta,
        "-filter_complex", flt, "-map", "[v]", "-map", "1:a", "-map_metadata", "2", "-map_chapters", "2",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "22", "-r", "1", "-g", "60",
        "-c:a", "copy", "-shortest", "-movflags", "+faststart", mp4)
    print("MP4:", mp4, round(os.path.getsize(mp4) / 1e6), "MB")
shutil.rmtree(tmp, ignore_errors=True)
print("pronto")
