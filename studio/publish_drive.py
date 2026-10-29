"""Envia o audiolivro pronto (M4B, vídeo e capa) para o Google Drive com rclone e confere o resultado.

  python -m studio publish --project projects/meu-livro [--dest "remote:Pasta/Audiolivros"] [--with-chapters]

O destino vem de --dest, da variável AUDIOBOOK_DRIVE_DEST ou de config.local.json ({"drive_dest": "remote:Pasta"}) na raiz do
repositório. Dentro dele cria-se uma pasta com o título do livro. Pré-requisito: `rclone config` com um remote do Google Drive.
"""
import argparse, json, os, re, subprocess, sys


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True); ap.add_argument("--dest")
    ap.add_argument("--with-chapters", action="store_true", help="envia também um M4A por capítulo")
    a = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = json.load(open(f"{root}/config.local.json")) if os.path.exists(f"{root}/config.local.json") else {}
    dest = a.dest or os.environ.get("AUDIOBOOK_DRIVE_DEST") or cfg.get("drive_dest")
    if not dest:
        sys.exit("Defina o destino: --dest remote:Pasta, AUDIOBOOK_DRIVE_DEST ou config.local.json {\"drive_dest\": ...}")
    out = f"{a.project}/audiobook"
    if not os.path.isdir(out):
        sys.exit(f"Rode antes: python -m studio assemble --project {a.project}")
    title = (json.load(open(f"{a.project}/book.json")).get("title") or "Audiolivro").replace("/", "-")
    target = f"{dest.rstrip('/')}/{title}"
    cover = f"{a.project}/cover.jpg"
    if os.path.exists(cover):
        subprocess.run(["cp", cover, f"{out}/capa.jpg"], check=True)
    flt = ["--include", "*.m4b", "--include", "*.mp4", "--include", "capa.jpg"] + (["--include", "capitulos/**"] if a.with_chapters else [])
    subprocess.run(["rclone", "copy", out, target, *flt, "--drive-chunk-size", "128M", "--transfers", "2", "--stats", "30s", "-v"], check=True)
    chk = subprocess.run(["rclone", "check", out, target, *flt, "--size-only", "--one-way"], capture_output=True, text=True)
    if chk.returncode:
        sys.exit("Conferência falhou (arquivos faltando ou de tamanho diferente):\n" + chk.stderr[-600:])
    print("Enviado e conferido em", target)
    link = subprocess.run(["rclone", "link", target], capture_output=True, text=True)
    print("Link:", re.sub(r"\s+", "", link.stdout) if link.returncode == 0 else "(sem link: abra a pasta no Drive)")


if __name__ == "__main__":
    main()
