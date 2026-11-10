#!/usr/bin/env python3
"""Monta o audiolivro final a partir dos capítulos gerados.

Produz, em --out:
  capitulos/NN - Título.m4a   um arquivo por capítulo, com capa e metadados
  <album>.m4b                 audiolivro único, capítulos marcados, capa embutida
  <album>.mp4                 vídeo (só se pedido com --video)

Entrada para generate/servidor (montagem automática após a geração):
  from studio.assemble import montar_projeto
  montar_projeto(pasta_do_projeto, video=False)

Uso na linha de comando:
  python -m studio.assemble --project projects/meu-livro [--video]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

COMENTARIO_IA = "Narração gerada por IA."

ROMAN = {"I": "I", "II": "II", "III": "III", "IV": "IV", "V": "V", "VI": "VI", "VII": "VII", "VIII": "VIII", "IX": "IX"}


def run(*cmd):
    from studio.paths import ffmpeg_bin, ffprobe_bin
    cmd = list(cmd)
    if cmd and cmd[0] == "ffmpeg":
        cmd[0] = ffmpeg_bin()
    elif cmd and cmd[0] == "ffprobe":
        cmd[0] = ffprobe_bin()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ERRO: " + " ".join(cmd[:4]) + "...\n" + (r.stderr or "")[-800:])
    return r.stdout


def dur(f):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f).strip())


def titulo(t):
    t = re.sub(r"\s+", " ", t).strip()
    m = re.match(r"^([IVX]+)\.\s+(.+)$", t)
    if m and m.group(1) in ROMAN:
        return f"Parte {m.group(1)}: {m.group(2).capitalize()}"
    return t


def safe(s):
    return re.sub(r'[\\/:*?"<>|]', "-", s).strip()


def _meta_escape(s):
    """Escapa valores do FFMETADATA1."""
    return (s or "").replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", " ")


def _comentario(narrator):
    narr = (narrator or "").strip()
    if narr:
        return f"{COMENTARIO_IA} Narrador: {narr}."
    return COMENTARIO_IA


def montar(*, book, chapters_dir, cover, out, album, author, narrator, year="", lang="por",
           pre=None, limit=0, video=False):
    """Monta M4B (e opcionalmente MP4). Devolve o caminho do M4B.

    Capítulos com include false ficam de fora. Sem o campo include, entram (projetos antigos).
    """
    os.makedirs(f"{out}/capitulos", exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="assemble_")
    try:
        raw = book["chapters"] if isinstance(book, dict) else book
        tracks = []
        for spec in pre or []:
            f, t = spec.rsplit(":", 1)
            if f.endswith(".m4a"):
                tracks.append((f, t))
            else:
                o = f"{tmp}/pre_{len(tracks)}.m4a"
                run("ffmpeg", "-y", "-loglevel", "error", "-i", f, "-ac", "1", "-b:a", "64k", o)
                tracks.append((o, t))
        for c in raw:
            if not c.get("include", True):
                continue
            f = f"{chapters_dir}/{c['id']}.m4a"
            if os.path.exists(f):
                tracks.append((f, titulo(c["title"])))
            else:
                print("aviso: falta", f)
        if limit:
            tracks = tracks[:limit]
        n = len(tracks)
        print(n, "faixas")
        if not tracks:
            raise RuntimeError("nenhum capítulo para montar")

        comment = _comentario(narrator)
        for i, (f, t) in enumerate(tracks, 1):
            dest = f"{out}/capitulos/{i:02d} - {safe(t)}.m4a"
            run("ffmpeg", "-y", "-loglevel", "error", "-i", f, "-i", cover, "-map", "0:a", "-map", "1:v", "-c", "copy",
                "-disposition:v:0", "attached_pic", "-metadata", f"title={t}", "-metadata", f"artist={author}",
                "-metadata", f"album_artist={author}", "-metadata", f"album={album}", "-metadata", f"composer={narrator}",
                "-metadata", f"comment={comment}", "-metadata", "genre=Audiobook",
                "-metadata", f"track={i}/{n}", "-metadata", f"date={year}", "-metadata:s:a:0", f"language={lang}",
                "-f", "ipod", dest)

        lst = f"{tmp}/list.txt"
        with open(lst, "w", encoding="utf8") as fh:
            for f, _ in tracks:
                fh.write("file '" + os.path.abspath(f).replace("'", "'\\''") + "'\n")
        joined = f"{tmp}/joined.m4a"
        run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined)

        meta = f"{tmp}/meta.txt"
        t0 = 0.0
        with open(meta, "w", encoding="utf8") as fh:
            fh.write(";FFMETADATA1\n")
            for k, v in (("title", album), ("artist", author), ("album_artist", author), ("album", album),
                         ("composer", narrator), ("genre", "Audiobook"), ("date", year),
                         ("comment", comment)):
                fh.write(f"{k}={_meta_escape(v)}\n")
            for f, t in tracks:
                d = dur(f)
                s, e = int(t0 * 1000), int((t0 + d) * 1000)
                fh.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={s}\nEND={e}\ntitle={_meta_escape(t)}\n")
                t0 += d

        m4b = f"{out}/{safe(album)}.m4b"
        run("ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", meta, "-i", cover, "-map", "0:a", "-map", "2:v",
            "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", "-disposition:v:0", "attached_pic",
            "-metadata:s:a:0", f"language={lang}", "-f", "ipod", m4b)
        print("M4B:", m4b, round(os.path.getsize(m4b) / 1e6), "MB,", round(t0 / 3600, 2), "h")

        if video:
            mp4 = f"{out}/{safe(album)}.mp4"
            flt = ("[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=45:6,eq=brightness=-0.18[bg];"
                   "[b]scale=-2:920:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
            run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "1", "-i", cover, "-i", joined, "-i", meta,
                "-filter_complex", flt, "-map", "[v]", "-map", "1:a", "-map_metadata", "2", "-map_chapters", "2",
                "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "22", "-r", "1", "-g", "60",
                "-c:a", "copy", "-shortest", "-movflags", "+faststart", mp4)
            print("MP4:", mp4, round(os.path.getsize(mp4) / 1e6), "MB")

        print("pronto")
        return m4b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def montar_projeto(P, *, video=False, limit=0, pre=None, out=None):
    """Monta o audiolivro de um projeto. Entrada para generate/servidor (R28, R29).

    Lê book.json, chapters/, cover.jpg e config.json. Vídeo só se video=True.
    Devolve o caminho do M4B.
    """
    P = os.path.abspath(P)
    bk = json.load(open(f"{P}/book.json", encoding="utf8"))
    cf = json.load(open(f"{P}/config.json", encoding="utf8")) if os.path.exists(f"{P}/config.json") else {}
    cover = f"{P}/cover.jpg"
    if not os.path.exists(cover):
        raise FileNotFoundError(f"falta capa: {cover}")
    return montar(
        book=bk,
        chapters_dir=f"{P}/chapters",
        cover=cover,
        out=out or f"{P}/audiobook",
        album=bk.get("title", "Audiobook"),
        author=bk.get("author", ""),
        narrator=cf.get("voz") or cf.get("narrator") or "voz clonada",
        year=str(bk.get("year") or cf.get("year") or ""),
        lang=bk.get("language") or "por",
        pre=pre,
        limit=limit,
        video=video,
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="pasta do projeto: usa book.json, chapters/, cover.jpg e config.json dela")
    ap.add_argument("--book")
    ap.add_argument("--chapters")
    ap.add_argument("--cover")
    ap.add_argument("--out")
    ap.add_argument("--album")
    ap.add_argument("--author")
    ap.add_argument("--narrator")
    ap.add_argument("--year", default="")
    ap.add_argument("--lang", default="por")
    ap.add_argument("--pre", action="append", default=[], help="arquivo.wav:Título, entra antes dos capítulos")
    ap.add_argument("--limit", type=int, default=0, help="só os N primeiros (teste)")
    ap.add_argument("--video", action="store_true", help="também gera o MP4 (só se a pessoa pedir)")
    ap.add_argument("--no-video", action="store_true", help=argparse.SUPPRESS)  # legado: padrão já é sem vídeo
    a = ap.parse_args(argv)

    if a.project:
        try:
            montar_projeto(a.project, video=a.video and not a.no_video, limit=a.limit, pre=a.pre or None, out=a.out)
        except (RuntimeError, FileNotFoundError, OSError, ValueError) as e:
            sys.exit(str(e))
        return

    for k in ("book", "chapters", "cover", "out", "album", "author", "narrator"):
        if not getattr(a, k):
            sys.exit(f"falta --{k} (ou use --project)")
    book = json.load(open(a.book, encoding="utf8"))
    try:
        montar(
            book=book, chapters_dir=a.chapters, cover=a.cover, out=a.out,
            album=a.album, author=a.author, narrator=a.narrator, year=a.year, lang=a.lang,
            pre=a.pre, limit=a.limit, video=a.video and not a.no_video,
        )
    except (RuntimeError, OSError, ValueError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
