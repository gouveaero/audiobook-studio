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
    """Autoteste na janela real (R43). Imprime JSON em stdout. Não trava no diálogo do microfone (H6)."""
    ensure_dirs()
    port = free_port(8795)
    token = secrets.token_urlsafe(24)
    srv = _start_server(port, token)
    base = f"http://127.0.0.1:{port}"
    url = f"{base}/home.html?token={token}"
    result = {
        "ok": False,
        "getUserMedia": "indisponivel",
        "audio_range": False,
        "error": None,
        "microphone_permission": None,
    }
    try:
        if not wait_up(f"{base}/config.json", secs=30):
            result["error"] = "servidor não subiu"
            print(json.dumps(result, ensure_ascii=False))
            return 1
        try:
            import webview
        except ImportError:
            result["error"] = "pywebview não instalado"
            print(json.dumps(result, ensure_ascii=False))
            return 1
        from studio.webview_patch import patch_cocoa_media_capture
        patch_cocoa_media_capture()

        # Áudio curto no servidor para provar Range (arquivo de projeto falso via /favicon não serve).
        # Usa um WAV mínimo servido como página? Melhor: POST não. Servimos via /api — cria projeto fake?
        # Simples: evaluate_js busca um .m4a se existir; senão gera data URI e só testa getUserMedia.
        # Para Range de verdade: cria projeto mínimo em AUDIOBOOK_STUDIO_HOME.
        home = ensure_dirs()
        proj = home / "projects" / "_selftest"
        chap = proj / "chapters"
        chap.mkdir(parents=True, exist_ok=True)
        import wave
        from io import BytesIO
        buf = BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        (chap / "01.m4a").write_bytes(buf.getvalue())
        (proj / "book.json").write_text(
            json.dumps({
                "title": "Selftest", "author": "",
                "chapters": [{"id": "01", "title": "1", "include": True, "chunks": ["oi"]}],
            }),
            encoding="utf8",
        )
        (proj / "config.json").write_text("{}", encoding="utf8")

        audio_url = f"{base}/api/projects/_selftest/file/chapters/01.m4a?token={token}"
        done = {"v": None}

        def on_loaded():
            kick = r"""
window.__absSelf = null;
(async function() {
  const out = {getUserMedia: "ausente", microphone_permission: null, audio_range: false, seek_ok: false};
  try {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      out.getUserMedia = "presente";
    } else {
      out.getUserMedia = "ausente";
    }
  } catch (e) {
    out.getUserMedia = "erro";
  }
  // Áudio / Range primeiro (não depende do diálogo do microfone, H6).
  try {
    const a = document.createElement("audio");
    a.preload = "auto";
    a.src = %AUDIO%;
    document.body.appendChild(a);
    await new Promise((resolve, reject) => {
      a.onloadedmetadata = () => resolve();
      a.onerror = () => reject(new Error("audio"));
      setTimeout(() => reject(new Error("timeout")), 8000);
    });
    const mid = Math.max(0.05, (a.duration || 0.5) / 2);
    a.currentTime = mid;
    await new Promise(r => setTimeout(r, 400));
    out.seek_ok = a.currentTime > 0.02;
    out.audio_range = out.seek_ok;
  } catch (e) {
    out.audio_range = false;
  }
  // Microfone: tenta, mas não bloqueia o resultado se o sistema ficar no diálogo.
  if (out.getUserMedia === "presente") {
    out.microphone_permission = "esperando";
    window.__absSelf = Object.assign({}, out);
    try {
      const mic = navigator.mediaDevices.getUserMedia({ audio: true, video: false }).then(function(stream) {
        try { stream.getTracks().forEach(function(tr) { tr.stop(); }); } catch (e) {}
        return "concedida";
      }).catch(function(e) {
        var name = (e && e.name) ? e.name : "";
        if (name === "NotAllowedError" || name === "PermissionDeniedError") return "negada";
        return "erro:" + name;
      });
      const timed = new Promise(function(resolve) { setTimeout(function() { resolve("esperando"); }, 2000); });
      out.microphone_permission = await Promise.race([mic, timed]);
    } catch (e) {
      out.microphone_permission = "esperando";
    }
  }
  window.__absSelf = out;
})();
true
""".replace("%AUDIO%", json.dumps(audio_url))
            try:
                window.evaluate_js(kick)
            except Exception as e:
                done["v"] = {"error": str(e)}
                try:
                    window.destroy()
                except Exception:
                    pass
                return

            def poll():
                for _ in range(80):
                    time.sleep(0.25)
                    try:
                        raw = window.evaluate_js(
                            "window.__absSelf ? JSON.stringify(window.__absSelf) : null"
                        )
                    except Exception:
                        raw = None
                    if raw and raw != "null":
                        try:
                            done["v"] = json.loads(raw) if isinstance(raw, str) else raw
                        except Exception:
                            done["v"] = {"error": "json", "raw": str(raw)}
                        break
                if done["v"] is None:
                    done["v"] = {
                        "error": "timeout js",
                        "getUserMedia": "timeout",
                        "microphone_permission": "esperando",
                    }
                try:
                    window.destroy()
                except Exception:
                    pass

            threading.Thread(target=poll, daemon=True).start()

        window = webview.create_window(APP_NAME + " autoteste", url, width=800, height=600, background_color="#02070c")
        window.events.loaded += on_loaded

        def watchdog():
            time.sleep(25)
            if done["v"] is None:
                done["v"] = {"error": "timeout janela", "getUserMedia": "timeout", "microphone_permission": "esperando"}
                try:
                    window.destroy()
                except Exception:
                    pass

        threading.Thread(target=watchdog, daemon=True).start()
        webview.start()
        out = done["v"] or {}
        result["getUserMedia"] = out.get("getUserMedia") or result["getUserMedia"]
        result["microphone_permission"] = out.get("microphone_permission")
        result["audio_range"] = bool(out.get("audio_range") or out.get("seek_ok"))
        result["error"] = out.get("error")
        result["ok"] = (
            result["getUserMedia"] in ("presente",)
            and result["audio_range"] is True
        )
        # H6: permissão esperando/negada não falha o autoteste sozinha se a API existe e o Range ok
        if result["getUserMedia"] == "presente" and result["audio_range"]:
            result["ok"] = True
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=3)
        except Exception:
            srv.kill()


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
