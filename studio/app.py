"""Abre a interface como um app (janela própria, sem abas nem barra de endereço).

  python -m studio.app [--project projects/meu-livro] [--page dashboard] [--port 8791]
  python -m studio.boot --self-test   # R43: JSON com getUserMedia e Range no WebKit

Sobe o studio.server em segundo plano e abre a janela:
  1. pywebview (`pip install pywebview`): janela nativa do sistema (WebKit no macOS, WebView2 no Windows);
  2. sem ele, Chrome, Edge, Brave ou Chromium em modo app (`--app=`), com perfil próprio;
  3. em último caso, o navegador padrão.
Fechar a janela encerra o servidor. A geração em andamento (nuvem ou local) continua: é outro processo.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser

from studio.brand import APP_NAME, ensure_dirs

BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def free_port(p):
    while True:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)):
                return p
        p += 1


def wait_up(url, secs=20):
    for _ in range(secs * 4):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=None, help="projeto único (modo skill); omitido abre a lista de livros")
    ap.add_argument(
        "--page",
        choices=["setup", "dashboard", "home", "review", "voice", "ready", "about"],
        default="home",
    )
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    return ap


def page_path(page: str) -> str:
    if page == "dashboard":
        return "dashboard.html"
    if page == "setup":
        return ""
    return f"{page}.html"


def _start_server(port: int, token: str, project: str | None = None):
    from studio.boot import worker_cmd
    cmd = worker_cmd("server", ["--port", str(port), "--token", token, "--exit-with-parent"])
    if project:
        cmd.extend(["--project", os.path.abspath(project)])
    # cwd: repo ou pasta de recursos no bundle
    try:
        from studio.paths import repo_root
        cwd = str(repo_root())
    except Exception:
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_self_test(argv=None) -> int:
    """Autoteste na janela real (R43): guias 2/4/5/6 + getUserMedia/Range. Ver studio.selftest."""
    from studio.selftest import run_self_test as _run
    return _run(argv)


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.self_test:
        raise SystemExit(run_self_test())
    ensure_dirs()
    port = free_port(a.port)
    token = secrets.token_urlsafe(24)
    srv = _start_server(port, token, a.project)
    base = f"http://127.0.0.1:{port}"
    path = page_path(a.page)
    url = f"{base}/{path}?token={token}" if path else f"{base}/?token={token}"
    if not wait_up(f"{base}/config.json"):
        srv.terminate()
        sys.exit("O servidor da interface não subiu.")
    try:
        try:
            import webview
            from studio.webview_patch import patch_cocoa_media_capture
            patch_cocoa_media_capture()
            if sys.platform == "darwin":
                try:
                    from Foundation import NSBundle
                    from AppKit import NSApplication, NSImage
                    NSBundle.mainBundle().infoDictionary()["CFBundleName"] = APP_NAME
                    logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.png")
                    try:
                        from studio.paths import resource_dir
                        alt = resource_dir() / "assets" / "logo.png"
                        if alt.is_file():
                            logo = str(alt)
                    except Exception:
                        pass
                    NSApplication.sharedApplication().setApplicationIconImage_(
                        NSImage.alloc().initWithContentsOfFile_(logo))
                except Exception:
                    pass
            webview.create_window(APP_NAME, url, width=1600, height=900, background_color="#02070c")
            webview.start()
            return
        except ImportError:
            pass
        exe = next((b for b in BROWSERS if os.path.exists(b) or shutil.which(b)), None)
        if exe:
            prof = os.path.join(os.path.expanduser("~"), ".audiobook-studio", "app-profile")
            subprocess.run([shutil.which(exe) or exe, f"--app={url}", f"--user-data-dir={prof}", "--window-size=1600,900",
                            "--no-first-run", "--no-default-browser-check"])
        else:
            webbrowser.open(url)
            print(url, "(Ctrl+C encerra)")
            srv.wait()
    except KeyboardInterrupt:
        pass
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
