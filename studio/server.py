"""Interface local: assistente de configuração (livro, voz, onde gerar) e painel ao vivo.

  python -m studio.server --project projects/meu-livro [--port 8791]
  python -m studio.server [--port 8791]   # multi-projeto sob AUDIOBOOK_STUDIO_HOME
  abre http://127.0.0.1:8791/  (assistente)   e   /dashboard.html  (painel; ?demo=1 simula)

Escuta só em 127.0.0.1. POST/PUT/DELETE exigem X-Studio-Token. Todo pedido exige Host local.
Os uploads vão para o projeto; a geração roda em subprocessos (studio.generate / studio.cloud).
"""
import argparse, hmac, json, os, re, secrets, subprocess, sys, threading, time, traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

from studio.assemble import montar_projeto
from studio.brand import APP_NAME, ensure_dirs, app_home
from studio import local_api
from studio.local_api import baixar_modelo  # monkeypatchável nos testes
from studio.prepare_book import BookError

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    from studio.paths import resource_dir, repo_root
    UI = str(resource_dir() / "ui")
    REPO = str(repo_root())
except Exception:
    UI = os.path.join(os.path.dirname(HERE), "ui")
    REPO = os.path.dirname(HERE)
P = ""
JOBS = {}
HIST = []
SESSION_TOKEN = ""
PORT = 8791

AUDIO_TYPES = {".wav": "audio/wav", ".m4a": "audio/mp4", ".m4b": "audio/mp4"}
AUDIO_ROOTS = ("voice", "chapters", "audiobook")
PROJ_RE = re.compile(r"^/api/projects/([^/]+)(/.*)?$")
# Áudio multi-projeto: /api/projects/<id>/file/chapters/01.m4a (Range, R30)
PROJ_FILE_RE = re.compile(r"^/api/projects/([^/]+)/file/(voice|chapters|audiobook)/(.+)$")


def pj(*a):
    return os.path.join(P, *a)


def jload(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default


def config():
    book = jload(pj("book.json"), {}) or {}
    c = {"livro": book.get("title", "Livro"), "autor": book.get("author", ""), "voz": "minha voz", "segundos": 15,
         "motor": "OmniVoice", "nuvem": "GPU na nuvem", "mac": "este computador", "capitulos": len(book.get("chapters", [])) or 1}
    c.update(jload(pj("config.json"), {}) or {})
    return c


def state():
    book = (jload(pj("book.json"), {}) or {}).get("chapters", [])
    chars = {(c["id"], k): len(t) for c in book for k, t in enumerate(c["chunks"])}
    tot = sum(chars.values()) or 1
    done_ids = sorted(f[:-4] for f in os.listdir(pj("chapters")) if re.fullmatch(r"\w+\.m4a", f)) if os.path.isdir(pj("chapters")) else []
    local = set(os.listdir(pj("work", "chunks"))) if os.path.isdir(pj("work", "chunks")) else set()
    cloud = jload(pj("work", "cloud_status.json"), {}) or {}
    remote = set(cloud.get("chunks", []))
    got = {"cloud": 0, "local": 0}; active = {}; local_ch = set()
    for f in local | remote:  # nuvem e este computador podem rodar juntos; cada trecho conta para quem o gerou
        m = re.fullmatch(r"(\w+)_(\d+)\.wav", f)
        if m and (m.group(1), int(m.group(2))) in chars:
            who = "cloud" if f in remote else "local"
            got[who] += chars[(m.group(1), int(m.group(2)))]
            if who == "local":
                local_ch.add(m.group(1))
            if m.group(1) not in done_ids:
                k0 = active.get(m.group(1), (who, -1))[1]
                active[m.group(1)] = (who, max(k0, int(m.group(2))))
    done_chars = got["cloud"] + got["local"]
    now = time.time(); HIST.append((now, got["cloud"], got["local"]))
    while HIST and now - HIST[0][0] > 120:
        HIST.pop(0)
    dt = now - HIST[0][0]
    rate_c = (got["cloud"] - HIST[0][1]) / dt / 13 if dt > 10 else 0
    rate_l = (got["local"] - HIST[0][2]) / dt / 13 if dt > 10 else 0
    by = {c["id"]: c for c in book}
    live = [{"who": who, "ch": i, "title": by[i]["title"], "text": by[i]["chunks"][k + 1]}
            for i, (who, k) in active.items() if k + 1 < len(by[i]["chunks"])]
    return {"total": done_chars / tot, "cloud": got["cloud"] / tot, "mac": got["local"] / tot,
            "gpu": cloud.get("gpu", 0), "rateCloud": round(rate_c, 1), "rateMac": round(rate_l, 1),
            "hours": round(done_chars / 13 / 3600, 1), "done": done_ids, "macIds": sorted(local_ch & set(done_ids)),
            "titles": {c["id"]: c["title"] for c in book}, "live": live[:4], "jobs": {k: v["status"] for k, v in JOBS.items()}}


def spawn(name, cmd, cwd):
    log = open(pj("work", f"{name}.log"), "ab") if os.path.isdir(pj("work")) else subprocess.DEVNULL
    p = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
    JOBS[name] = {"proc": p, "status": "rodando"}
    def waiter():
        JOBS[name]["status"] = "concluído" if p.wait() == 0 else f"erro (veja work/{name}.log)"
    threading.Thread(target=waiter, daemon=True).start()
    return p


def redact_secrets(text: str) -> str:
    if SESSION_TOKEN:
        text = text.replace(SESSION_TOKEN, "[sessao]")
    text = re.sub(r"hf_[A-Za-z0-9]{20,}", "[hf]", text)
    return text


def log_exception():
    """Grava traceback em AUDIOBOOK_STUDIO_HOME/logs/server.log, sem tokens (R38)."""
    try:
        ensure_dirs()
        log_dir = app_home() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        body = redact_secrets(traceback.format_exc())
        with open(log_dir / "server.log", "a", encoding="utf8") as f:
            f.write(f"\n--- {stamp} ---\n{body}\n")
    except Exception:
        pass


def erro_publico(msg: str = "Algo deu errado. Veja o log.") -> str:
    """Mensagem para a tela: português, sem traceback, caminho ou nome de exceção (R38)."""
    texto = (msg or "").strip() or "Algo deu errado. Veja o log."
    if "Traceback" in texto or re.search(r"/Users/|/home/|\\\\", texto):
        return "Algo deu errado. Veja o log."
    if re.search(r"\b(Error|Exception|KeyError|TypeError|ValueError|RuntimeError|OSError)\b", texto):
        return "Algo deu errado. Veja o log."
    return texto


def resolve_audio_under(root: Path, rel_parts: tuple[str, ...]):
    """Resolve arquivo de áudio sob root. None = inexistente; False = pedido inválido."""
    if not rel_parts or rel_parts[0] not in AUDIO_ROOTS:
        return None
    if any(p in (".", "..") or "/" in p or "\\" in p for p in rel_parts):
        return False
    suffix = Path(rel_parts[-1]).suffix.lower()
    if suffix not in AUDIO_TYPES:
        return None
    root = root.resolve()
    full = (root.joinpath(*rel_parts)).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        return False
    if not full.is_file():
        return None
    return str(full), AUDIO_TYPES[suffix]


def resolve_project_audio(url_path: str):
    """Resolve /voice|chapters|audiobook/... para um arquivo sob P. None = não é áudio; False = inválido."""
    if not P:
        return None
    raw = unquote(url_path.split("?", 1)[0])
    if ".." in raw or "\\" in raw:
        return False
    parts = Path(raw.lstrip("/")).parts
    return resolve_audio_under(Path(P), parts)


def resolve_multi_project_audio(url_path: str):
    """Resolve /api/projects/<id>/file/{voice|chapters|audiobook}/... com Range (R30)."""
    raw = unquote(url_path.split("?", 1)[0])
    m = PROJ_FILE_RE.match(raw)
    if not m:
        return None
    pid, root_name, rest = m.group(1), m.group(2), m.group(3)
    if ".." in rest or "\\" in rest:
        return False
    proj = local_api.project_path(pid)
    if not proj:
        return False
    parts = (root_name,) + Path(rest).parts
    return resolve_audio_under(proj, parts)


def make_server(port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), H)


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=UI, **k)

    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").strip().lower()
        return host == f"127.0.0.1:{PORT}"

    def _token_ok(self):
        if not SESSION_TOKEN:
            return False
        got = self.headers.get("X-Studio-Token") or ""
        return hmac.compare_digest(got, SESSION_TOKEN)

    def _guard(self, mutating):
        if not self._host_ok():
            self.send_json({"error": "Pedido recusado."}, 403)
            return False
        if mutating and not self._token_ok():
            self.send_json({"error": "Pedido recusado."}, 403)
            return False
        return True

    def send_file_range(self, path, content_type):
        """Serve arquivo com suporte a Range (206), exigido pelo WebKit no player."""
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            spec = rng[6:].strip()
            if "," in spec:
                self.send_error(416)
                return
            start_s, _, end_s = spec.partition("-")
            try:
                if start_s == "":
                    length = int(end_s)
                    start = max(0, size - length)
                    end = size - 1
                else:
                    start = int(start_s)
                    end = int(end_s) if end_s else size - 1
            except ValueError:
                self.send_error(416)
                return
            if start < 0 or start >= size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            length = end - start + 1
            with open(path, "rb") as f:
                f.seek(start)
                data = f.read(length)
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            self.wfile.write(data)
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._guard(False):
            return
        p = urlparse(self.path).path
        audio = resolve_multi_project_audio(p)
        if audio is None:
            audio = resolve_project_audio(p)
        if audio is False:
            return self.send_json({"error": "Pedido recusado."}, 403)
        if audio:
            return self.send_file_range(audio[0], audio[1])
        try:
            if p == "/api/state":
                if not P:
                    return self.send_json({"error": "Nenhum projeto aberto."}, 400)
                return self.send_json(state())
            if p == "/api/projects":
                return self.send_json({"projects": local_api.list_projects()})
            if p == "/api/voices":
                return self.send_json(local_api.list_voices())
            if p == "/api/models":
                return self.send_json(local_api.get_models_status())
            if p == "/api/version":
                return self.send_json(local_api.version_info())
            if p == "/api/updates":
                # R44: falta de internet não vira 500
                return self.send_json(local_api.verificar_versao_nova())
            m = PROJ_RE.match(p)
            if m:
                pid, rest = m.group(1), m.group(2) or ""
                if rest == "/book":
                    return self.send_json(local_api.load_book(pid))
                if rest == "/state":
                    return self.send_json(local_api.project_state(pid))
                if rest == "/config":
                    proj = local_api.project_path(pid)
                    if not proj:
                        raise FileNotFoundError(pid)
                    book = jload(str(proj / "book.json"), {}) or {}
                    cfg = jload(str(proj / "config.json"), {}) or {}
                    voz = cfg.get("voz_label") or cfg.get("voz") or ""
                    if not voz:
                        man_path = proj / "voice" / "manifest.json"
                        if man_path.is_file():
                            try:
                                voz = (json.loads(man_path.read_text(encoding="utf8")).get("label") or "")
                            except (OSError, ValueError):
                                voz = ""
                    out = {
                        "livro": book.get("title", "Livro"),
                        "autor": book.get("author", ""),
                        "voz": voz or "voz",
                        "voz_label": voz or "voz",
                        "motor": cfg.get("motor") or "pocket",
                        "capitulos": len([c for c in book.get("chapters", []) if c.get("include", True)]) or 1,
                    }
                    out.update(cfg)
                    out["voz"] = voz or out.get("voz") or "voz"
                    out["voz_label"] = out["voz"]
                    return self.send_json(out)
            if p == "/config.json":
                if not P:
                    return self.send_json({"app": APP_NAME})
                return self.send_json(config())
            if p == "/voice_peaks.json":
                return self.send_json(jload(pj("voice", "peaks.json"), [.3] * 180) if P else [.3] * 180)
            if p == "/api/voice":
                if not P:
                    return self.send_json({"text": ""})
                return self.send_json({"text": open(pj("voice", "ref.txt"), encoding="utf8").read().strip() if os.path.exists(pj("voice", "ref.txt")) else ""})
        except FileNotFoundError:
            return self.send_json({"error": "Projeto não encontrado."}, 404)
        except Exception:
            log_exception()
            return self.send_json({"error": erro_publico()}, 500)
        if p == "/":
            self.path = "/home.html" if not P else "/setup.html"
        super().do_GET()

    def body(self):
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def do_POST(self):
        if not self._guard(True):
            return
        p = urlparse(self.path).path
        if P:
            os.makedirs(pj("work"), exist_ok=True)
        try:
            if p == "/api/projects":
                try:
                    return self.send_json(local_api.create_project_from_epub(self.body()))
                except BookError as e:
                    return self.send_json({"error": erro_publico(str(e)), "code": e.code}, 400)
                except FileNotFoundError as e:
                    # não confundir com "projeto ausente" do GET (ex.: ffmpeg/capa)
                    log_exception()
                    return self.send_json({"error": erro_publico(str(e) or "Falha ao criar o livro.")}, 500)
            if p == "/api/hf-login":
                data = json.loads(self.body() or b"{}")
                try:
                    local_api.save_hf_token(data.get("token", ""))
                except ValueError as e:
                    return self.send_json({"error": erro_publico(str(e))}, 400)
                return self.send_json({"ok": True, "hf_logged_in": True})
            if p == "/api/models/download":
                return self.send_json(local_api.start_model_download(baixar=baixar_modelo))
            if p == "/api/voices/select":
                o = json.loads(self.body() or b"{}")
                try:
                    return self.send_json(local_api.select_voice(o.get("voice_id") or ""))
                except FileNotFoundError:
                    return self.send_json({"error": "Voz não encontrada."}, 404)
                except ConnectionError as e:
                    return self.send_json({"error": erro_publico(str(e))}, 503)
            if p == "/api/voices/preview":
                o = json.loads(self.body() or b"{}")
                try:
                    wav = local_api.preview_voice(o.get("voice_id") or "")
                except FileNotFoundError:
                    return self.send_json({"error": "Voz não encontrada."}, 404)
                except ConnectionError as e:
                    return self.send_json({"error": erro_publico(str(e))}, 503)
                except Exception:
                    log_exception()
                    return self.send_json({"error": erro_publico()}, 500)
                return self.send_file_range(str(wav), "audio/wav")
            if p == "/api/voices":
                consent = (self.headers.get("X-Consent") or "").lower() in ("1", "true", "yes", "sim")
                label = self.headers.get("X-Voice-Label") or "Minha voz"
                text = self.headers.get("X-Voice-Text") or ""
                try:
                    return self.send_json(local_api.save_cloned_voice(
                        self.body(), label=label, text=text, consent=consent))
                except PermissionError as e:
                    return self.send_json({"error": erro_publico(str(e))}, 400)
                except ValueError as e:
                    return self.send_json({"error": erro_publico(str(e))}, 400)
            m = PROJ_RE.match(p)
            if m:
                pid, rest = m.group(1), m.group(2) or ""
                if rest == "/start":
                    return self.send_json(local_api.start_generate(pid))
                if rest == "/pause":
                    local_api.set_pause(pid, True); return self.send_json({"ok": True})
                if rest == "/resume":
                    local_api.set_pause(pid, False); return self.send_json({"ok": True})
                if rest == "/cancel":
                    local_api.set_cancel(pid); return self.send_json({"ok": True})
                if rest == "/redo":
                    o = json.loads(self.body() or b"{}")
                    return self.send_json(local_api.redo_chunk(pid, o["chapter"], int(o["chunk"])))
                if rest == "/assemble":
                    o = json.loads(self.body() or b"{}")
                    out = montar_projeto(str(local_api.project_path(pid)), video=bool(o.get("video")))
                    return self.send_json({"ok": True, "out": out})
                if rest == "/reveal":
                    proj = local_api.project_path(pid)
                    if not proj:
                        raise FileNotFoundError(pid)
                    m4b = next((proj / "audiobook").glob("*.m4b"), None) if (proj / "audiobook").is_dir() else None
                    alvo = m4b or (proj / "audiobook")
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", "-R", str(alvo)])
                    return self.send_json({"ok": True, "path": str(alvo)})
                if rest == "/voice":
                    o = json.loads(self.body() or b"{}")
                    local_api.attach_voice_to_project(pid, o["voice_id"])
                    return self.send_json({"ok": True})
            # --- rotas legadas do modo --project (skill) ---
            if p == "/api/book":
                if not P:
                    return self.send_json({"error": "Abra um projeto antes."}, 400)
                open(pj("book.epub"), "wb").write(self.body())
                r = subprocess.run([sys.executable, "-m", "studio.prepare_book", pj("book.epub"), pj("book.json")], cwd=os.path.dirname(HERE), capture_output=True, text=True)
                if r.returncode: return self.send_json({"error": r.stderr[-400:]}, 400)
                b = jload(pj("book.json")); return self.send_json({"title": b["title"], "author": b["author"], "chapters": len(b["chapters"]), "summary": r.stdout.strip()})
            if p == "/api/voice":
                if not P:
                    return self.send_json({"error": "Abra um projeto antes."}, 400)
                os.makedirs(pj("voice"), exist_ok=True)
                open(pj("voice", "_upload"), "wb").write(self.body())
                lang = (jload(pj("book.json"), {}) or {}).get("language", "pt")
                r = subprocess.run([sys.executable, "-m", "studio.prepare_voice", pj("voice", "_upload"), "--project", P, "--lang", lang], cwd=os.path.dirname(HERE), capture_output=True, text=True)
                if r.returncode: return self.send_json({"error": r.stderr[-400:]}, 400)
                return self.send_json({"text": open(pj("voice", "ref.txt"), encoding="utf8").read().strip()})
            if p == "/api/voice-text":
                if not P:
                    return self.send_json({"error": "Abra um projeto antes."}, 400)
                open(pj("voice", "ref.txt"), "w", encoding="utf8").write(json.loads(self.body())["text"].strip() + "\n"); return self.send_json({"ok": True})
            if p == "/api/config":
                if not P:
                    return self.send_json({"error": "Abra um projeto antes."}, 400)
                c = jload(pj("config.json"), {}) or {}; c.update(json.loads(self.body())); json.dump(c, open(pj("config.json"), "w"), ensure_ascii=False, indent=1); return self.send_json({"ok": True})
            if p == "/api/start":
                if not P:
                    return self.send_json({"error": "Abra um projeto antes."}, 400)
                o = json.loads(self.body() or b"{}")
                if not (os.path.exists(pj("book.json")) and os.path.exists(pj("voice", "ref.wav"))):
                    return self.send_json({"error": "Falta o livro ou a voz."}, 400)
                if o.get("mode") == "cloud":
                    spawn("cloud", [sys.executable, "-m", "studio.cloud", "run", "--project", P, "--gpu", o.get("gpu", "A100")], os.path.dirname(HERE))
                else:
                    spawn("generate", [sys.executable, "-m", "studio.generate", "--project", P], os.path.dirname(HERE))
                return self.send_json({"ok": True})
            if p == "/api/assemble":
                if not P:
                    return self.send_json({"error": "Abra um projeto antes."}, 400)
                spawn("assemble", [sys.executable, "-m", "studio.assemble", "--project", P], os.path.dirname(HERE)); return self.send_json({"ok": True})
        except BookError as e:
            return self.send_json({"error": erro_publico(str(e)), "code": e.code}, 400)
        except FileNotFoundError:
            return self.send_json({"error": "Projeto não encontrado."}, 404)
        except ValueError as e:
            return self.send_json({"error": erro_publico(str(e))}, 400)
        except Exception:
            log_exception()
            return self.send_json({"error": erro_publico()}, 500)
        self.send_json({"error": "rota desconhecida"}, 404)

    def do_PUT(self):
        if not self._guard(True):
            return
        p = urlparse(self.path).path
        try:
            m = PROJ_RE.match(p)
            if m and (m.group(2) or "") == "/book":
                book = json.loads(self.body())
                return self.send_json(local_api.save_book(m.group(1), book))
        except FileNotFoundError:
            return self.send_json({"error": "Projeto não encontrado."}, 404)
        except ValueError as e:
            return self.send_json({"error": erro_publico(str(e))}, 400)
        except Exception:
            log_exception()
            return self.send_json({"error": erro_publico()}, 500)
        self.send_json({"error": "rota desconhecida"}, 404)

    def do_DELETE(self):
        if not self._guard(True):
            return
        self.send_json({"error": "rota desconhecida"}, 404)

    def log_message(self, *a):
        pass


def main(argv=None):
    global P, SESSION_TOKEN, PORT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=None)
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--token", default=None, help="token de sessão (gerado se omitido)")
    ap.add_argument("--exit-with-parent", action="store_true", help="encerra quando o processo pai (o app) sair")
    a = ap.parse_args(argv)
    ensure_dirs()
    PORT = a.port
    SESSION_TOKEN = a.token or secrets.token_urlsafe(24)
    P = os.path.abspath(a.project) if a.project else ""
    if a.exit_with_parent:
        ppid = os.getppid()
        def watch():
            while os.getppid() == ppid:
                time.sleep(2)
            os._exit(0)
        threading.Thread(target=watch, daemon=True).start()
    if P:
        for d in ("work/chunks", "chapters", "voice"):
            os.makedirs(pj(d), exist_ok=True)
    print(f"http://127.0.0.1:{PORT}/  (projeto: {P or 'nenhum'}; app: {APP_NAME})", flush=True)
    # Token nunca vai para stdout/stderr.
    make_server(PORT).serve_forever()


if __name__ == "__main__":
    main()
