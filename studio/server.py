"""Interface local: assistente de configuração (livro, voz, onde gerar) e painel ao vivo.

  python -m studio.server --project projects/meu-livro [--port 8791]
  abre http://localhost:8791/  (assistente)   e   /dashboard.html  (painel; ?demo=1 simula)

Escuta só em 127.0.0.1. Os uploads vão para o projeto; a geração roda em subprocessos (studio.generate / studio.cloud).
"""
import argparse, json, os, re, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(os.path.dirname(HERE), "ui")
P = ""
JOBS = {}
HIST = []


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
    names = set(os.listdir(pj("work", "chunks"))) if os.path.isdir(pj("work", "chunks")) else set()
    cloud = jload(pj("work", "cloud_status.json"), {}) or {}
    names |= set(cloud.get("chunks", []))
    done_chars = 0; active = {}
    for f in names:
        m = re.fullmatch(r"(\w+)_(\d+)\.wav", f)
        if m and (m.group(1), int(m.group(2))) in chars:
            done_chars += chars[(m.group(1), int(m.group(2)))]
            if m.group(1) not in done_ids:
                active[m.group(1)] = max(active.get(m.group(1), -1), int(m.group(2)))
    now = time.time(); HIST.append((now, done_chars))
    while HIST and now - HIST[0][0] > 120:
        HIST.pop(0)
    rate = (done_chars - HIST[0][1]) / (now - HIST[0][0]) / 13 if now - HIST[0][0] > 10 else 0
    by = {c["id"]: c for c in book}
    live = [{"who": "cloud" if cloud.get("chunks") else "local", "ch": i, "title": by[i]["title"],
             "text": by[i]["chunks"][k + 1]} for i, k in active.items() if k + 1 < len(by[i]["chunks"])]
    mode = "cloud" if cloud.get("chunks") else "local"
    return {"total": done_chars / tot, "cloud": done_chars / tot if mode == "cloud" else 0, "mac": done_chars / tot if mode == "local" else 0,
            "gpu": cloud.get("gpu", 0), "rateCloud": round(rate, 1) if mode == "cloud" else 0, "rateMac": round(rate, 1) if mode == "local" else 0,
            "hours": round(done_chars / 13 / 3600, 1), "done": done_ids, "macIds": done_ids if mode == "local" else [],
            "titles": {c["id"]: c["title"] for c in book}, "live": live[:4], "jobs": {k: v["status"] for k, v in JOBS.items()}}


def spawn(name, cmd, cwd):
    log = open(pj("work", f"{name}.log"), "ab") if os.path.isdir(pj("work")) else subprocess.DEVNULL
    p = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
    JOBS[name] = {"proc": p, "status": "rodando"}
    def waiter():
        JOBS[name]["status"] = "concluído" if p.wait() == 0 else f"erro (veja work/{name}.log)"
    threading.Thread(target=waiter, daemon=True).start()
    return p


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=UI, **k)

    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/state": return self.send_json(state())
        if p == "/config.json": return self.send_json(config())
        if p == "/voice_peaks.json": return self.send_json(jload(pj("voice", "peaks.json"), [.3] * 180))
        if p == "/api/voice": return self.send_json({"text": open(pj("voice", "ref.txt"), encoding="utf8").read().strip() if os.path.exists(pj("voice", "ref.txt")) else ""})
        if p == "/voice/ref.wav" and os.path.exists(pj("voice", "ref.wav")):
            b = open(pj("voice", "ref.wav"), "rb").read()
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
        if p == "/": self.path = "/setup.html"
        super().do_GET()

    def body(self):
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def do_POST(self):
        p = urlparse(self.path).path
        os.makedirs(pj("work"), exist_ok=True)
        try:
            if p == "/api/book":      # corpo = bytes do .epub
                open(pj("book.epub"), "wb").write(self.body())
                r = subprocess.run([sys.executable, "-m", "studio.prepare_book", pj("book.epub"), pj("book.json")], cwd=os.path.dirname(HERE), capture_output=True, text=True)
                if r.returncode: return self.send_json({"error": r.stderr[-400:]}, 400)
                b = jload(pj("book.json")); return self.send_json({"title": b["title"], "author": b["author"], "chapters": len(b["chapters"]), "summary": r.stdout.strip()})
            if p == "/api/voice":     # corpo = áudio (qualquer formato que o ffmpeg leia)
                os.makedirs(pj("voice"), exist_ok=True)
                open(pj("voice", "_upload"), "wb").write(self.body())
                lang = (jload(pj("book.json"), {}) or {}).get("language", "pt")
                r = subprocess.run([sys.executable, "-m", "studio.prepare_voice", pj("voice", "_upload"), "--project", P, "--lang", lang], cwd=os.path.dirname(HERE), capture_output=True, text=True)
                if r.returncode: return self.send_json({"error": r.stderr[-400:]}, 400)
                return self.send_json({"text": open(pj("voice", "ref.txt"), encoding="utf8").read().strip()})
            if p == "/api/voice-text":  # o usuário corrige a transcrição
                open(pj("voice", "ref.txt"), "w", encoding="utf8").write(json.loads(self.body())["text"].strip() + "\n"); return self.send_json({"ok": True})
            if p == "/api/config":
                c = jload(pj("config.json"), {}) or {}; c.update(json.loads(self.body())); json.dump(c, open(pj("config.json"), "w"), ensure_ascii=False, indent=1); return self.send_json({"ok": True})
            if p == "/api/start":
                o = json.loads(self.body() or b"{}")
                if not (os.path.exists(pj("book.json")) and os.path.exists(pj("voice", "ref.wav"))):
                    return self.send_json({"error": "Falta o livro ou a voz."}, 400)
                if o.get("mode") == "cloud":
                    spawn("cloud", [sys.executable, "-m", "studio.cloud", "run", "--project", P, "--gpu", o.get("gpu", "A100")], os.path.dirname(HERE))
                else:
                    spawn("generate", [sys.executable, "-m", "studio.generate", "--project", P], os.path.dirname(HERE))
                return self.send_json({"ok": True})
            if p == "/api/assemble":
                c = config(); spawn("assemble", [sys.executable, "-m", "studio.assemble", "--project", P], os.path.dirname(HERE)); return self.send_json({"ok": True})
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)
        self.send_json({"error": "rota desconhecida"}, 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True); ap.add_argument("--port", type=int, default=8791)
    a = ap.parse_args(); P = os.path.abspath(a.project)
    for d in ("work/chunks", "chapters", "voice"):
        os.makedirs(pj(d), exist_ok=True)
    print(f"http://localhost:{a.port}/  (projeto: {P})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
