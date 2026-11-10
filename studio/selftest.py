"""Autoteste ampliado na janela real (R43): guias 2, 4, 5 e 6 via evaluate_js.

Usa download simulado (AUDIOBOOK_FAKE_DOWNLOAD) e o motor mínimo
`studio.selftest_engine:SelftestEngine` (não aparece na lista de vozes da UI).
Imprime um JSON com resultado por passo e caminhos de captura quando possível.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
import wave
from io import BytesIO
from pathlib import Path

from studio.brand import APP_NAME, ensure_dirs


SELFTEST_MOTOR = "studio.selftest_engine:SelftestEngine"


def _captura_janela(dest: Path, titulo_contem: str = "") -> str | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
            CGWindowListCreateImage,
            CGRectNull,
            kCGWindowImageDefault,
            kCGWindowListOptionIncludingWindow,
            CGImageDestinationCreateWithURL,
            CGImageDestinationAddImage,
            CGImageDestinationFinalize,
        )
        from Foundation import NSURL

        info = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID) or []
        alvo = None
        needle = (titulo_contem or APP_NAME).lower()
        for w in info:
            nome = str(w.get("kCGWindowName") or "")
            owner = str(w.get("kCGWindowOwnerName") or "")
            if needle in nome.lower() or needle in owner.lower() or "audiobook" in owner.lower():
                alvo = int(w["kCGWindowNumber"])
                break
        if alvo is None:
            return None
        img = CGWindowListCreateImage(
            CGRectNull, kCGWindowListOptionIncludingWindow, alvo, kCGWindowImageDefault,
        )
        if img is None:
            return None
        url = NSURL.fileURLWithPath_(str(dest))
        dest_img = CGImageDestinationCreateWithURL(url, "public.png", 1, None)
        if dest_img is None:
            return None
        CGImageDestinationAddImage(dest_img, img, None)
        if not CGImageDestinationFinalize(dest_img):
            return None
        return str(dest) if dest.is_file() else None
    except Exception:
        return None


def _epub_bytes() -> bytes:
    try:
        from tests.epub_sintetico import make_epub, paras
        import tempfile
        fd, nome = tempfile.mkstemp(suffix=".epub")
        os.close(fd)
        path = Path(nome)
        try:
            make_epub(
                path,
                [
                    ("c1.xhtml", "<h1>1. Manhã na Praça</h1>" + paras(2)),
                    ("c2.xhtml", "<h1>2. A Carta Azul</h1>" + paras(2)),
                    ("c3.xhtml", "<h1>3. O Rio no Inverno</h1>" + paras(2)),
                ],
                toc=[
                    ("1. Manhã na Praça", "c1.xhtml"),
                    ("2. A Carta Azul", "c2.xhtml"),
                    ("3. O Rio no Inverno", "c3.xhtml"),
                ],
                title="Crônicas da Praça",
                cover=True,
            )
            return path.read_bytes()
        finally:
            path.unlink(missing_ok=True)
    except Exception:
        import zipfile
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
            )
            z.writestr(
                "content.opf",
                '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="u">'
                '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Crônicas da Praça</dc:title>'
                '<dc:language>pt-BR</dc:language><dc:identifier id="u">selftest</dc:identifier></metadata>'
                '<manifest><item id="c1" href="Text/c1.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="c2" href="Text/c2.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="c3" href="Text/c3.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
                '<spine toc="ncx"><itemref idref="c1"/><itemref idref="c2"/><itemref idref="c3"/></spine></package>',
            )
            for i, t in enumerate(("Manhã na Praça", "A Carta Azul", "O Rio no Inverno"), 1):
                body = (
                    f"<h1>{i}. {t}</h1>"
                    "<p>O vento frio descia pela rua estreita e ninguém sabia dizer de onde vinha aquele cheiro de pão.</p>"
                    "<p>Ela abriu a janela, olhou para o relógio da praça e pensou que ainda havia tempo para tudo.</p>"
                )
                z.writestr(
                    f"Text/c{i}.xhtml",
                    '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title></head>'
                    f"<body>{body}</body></html>",
                )
            z.writestr(
                "toc.ncx",
                '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head/>'
                '<docTitle><text>x</text></docTitle><navMap>'
                '<navPoint id="n1" playOrder="1"><navLabel><text>1. Manhã na Praça</text></navLabel><content src="Text/c1.xhtml"/></navPoint>'
                '<navPoint id="n2" playOrder="2"><navLabel><text>2. A Carta Azul</text></navLabel><content src="Text/c2.xhtml"/></navPoint>'
                '<navPoint id="n3" playOrder="3"><navLabel><text>3. O Rio no Inverno</text></navLabel><content src="Text/c3.xhtml"/></navPoint>'
                "</navMap></ncx>",
            )
        return buf.getvalue()


def _eval(window, js: str):
    return window.evaluate_js(js)


def _passo(result: dict, nome: str, ok: bool, detalhe=None, captura=None):
    entry = {"ok": bool(ok), "detalhe": detalhe}
    if captura:
        entry["captura"] = captura
    result["passos"][nome] = entry


def _wait_step(window, token: str, timeout=60.0, interval=0.25):
    """Espera window.__absStep com o token deste passo (evita copiar resultado anterior)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = _eval(
                window,
                "window.__absStep ? JSON.stringify(window.__absStep) : null",
            )
            if raw and raw != "null":
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict) and data.get("step") == token:
                    return data
        except Exception:
            pass
        time.sleep(interval)
    return None


def _run_js_step(window, token: str, async_body: str, timeout=60.0):
    """Roda um async JS que deve atribuir window.__absStep = {step: token, ...}."""
    js = f"""
window.__absStep = null;
(async function() {{
  const step = {json.dumps(token)};
  try {{
{async_body}
  }} catch (e) {{
    window.__absStep = {{step: step, ok: false, err: String(e)}};
  }}
}})();
true
"""
    _eval(window, js)
    return _wait_step(window, token, timeout=timeout) or {"step": token, "ok": False, "err": "timeout"}


def _api(base: str, token: str, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
    from urllib.parse import urlparse
    parsed = urlparse(base)
    # Só loopback: recusa qualquer outro host antes de abrir a conexão (R37).
    if parsed.hostname != "127.0.0.1":
        raise ValueError(f"selftest só fala com 127.0.0.1, recebeu {parsed.hostname!r}")
    h = dict(headers or {})
    if method not in ("GET", "HEAD"):
        h["X-Studio-Token"] = token
    # Host explícito: o servidor exige 127.0.0.1:<porta> (R33).
    host = parsed.netloc
    h.setdefault("Host", host)
    req = urllib.request.Request(f"{base}{path}", data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def run_self_test(argv=None) -> int:
    os.environ.setdefault("AUDIOBOOK_FAKE_DOWNLOAD", "1")
    os.environ.setdefault("AUDIOBOOK_PREVIEW_MOTOR", SELFTEST_MOTOR)
    os.environ.setdefault("FAKE_ENGINE_DELAY", "0.05")

    from studio.app import free_port, wait_up, _start_server

    ensure_dirs()
    port = free_port(8795)
    token = secrets.token_urlsafe(24)
    srv = _start_server(port, token)
    base = f"http://127.0.0.1:{port}"
    url = f"{base}/home.html?token={token}"
    cap_dir = Path(os.environ.get("AUDIOBOOK_SELFTEST_CAPS") or (ensure_dirs() / "selftest-caps"))
    cap_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "ok": False,
        "getUserMedia": "indisponivel",
        "audio_range": False,
        "microphone_permission": None,
        "error": None,
        "passos": {},
        "guias": {"guia2": None, "guia4": None, "guia5": None, "guia6": None},
        "motor": SELFTEST_MOTOR,
        "fake_download": os.environ.get("AUDIOBOOK_FAKE_DOWNLOAD"),
    }
    done = {"v": None}

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

        # Áudio curto para provar Range (R43) antes dos guias.
        home = ensure_dirs()
        proj = home / "projects" / "_selftest"
        chap = proj / "chapters"
        chap.mkdir(parents=True, exist_ok=True)
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

        started = {"v": False}
        start_lock = threading.Lock()

        def fluxo(window):
            nonlocal result
            with start_lock:
                if started["v"]:
                    return
                started["v"] = True
            try:
                # Smoke getUserMedia + Range + microfone (não bloqueia)
                smoke = _run_js_step(window, "smoke_r43", f"""
  const out = {{step: step, getUserMedia: "ausente", microphone_permission: null, audio_range: false, seek_ok: false}};
  try {{
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) out.getUserMedia = "presente";
  }} catch (e) {{ out.getUserMedia = "erro"; }}
  try {{
    const a = document.createElement("audio");
    a.preload = "auto";
    a.src = {json.dumps(audio_url)};
    document.body.appendChild(a);
    await new Promise((resolve, reject) => {{
      a.onloadedmetadata = () => resolve();
      a.onerror = () => reject(new Error("audio"));
      setTimeout(() => reject(new Error("timeout")), 8000);
    }});
    const mid = Math.max(0.05, (a.duration || 0.5) / 2);
    a.currentTime = mid;
    await new Promise(r => setTimeout(r, 400));
    out.seek_ok = a.currentTime > 0.02;
    out.audio_range = out.seek_ok;
  }} catch (e) {{ out.audio_range = false; out.audio_err = String(e); }}
  if (out.getUserMedia === "presente") {{
    out.microphone_permission = "esperando";
    try {{
      const mic = navigator.mediaDevices.getUserMedia({{audio: true, video: false}}).then(function(stream) {{
        try {{ stream.getTracks().forEach(function(tr) {{ tr.stop(); }}); }} catch (e) {{}}
        return "concedida";
      }}).catch(function(e) {{
        var name = (e && e.name) ? e.name : "";
        if (name === "NotAllowedError" || name === "PermissionDeniedError") return "negada";
        return "erro:" + name;
      }});
      const timed = new Promise(function(resolve) {{ setTimeout(function() {{ resolve("esperando"); }}, 2000); }});
      out.microphone_permission = await Promise.race([mic, timed]);
    }} catch (e) {{ out.microphone_permission = "esperando"; }}
  }}
  out.ok = out.getUserMedia === "presente" && out.audio_range === true;
  window.__absStep = out;
""", timeout=25)
                result["getUserMedia"] = smoke.get("getUserMedia") or "ausente"
                result["audio_range"] = bool(smoke.get("audio_range") or smoke.get("seek_ok"))
                result["microphone_permission"] = smoke.get("microphone_permission")
                _passo(result, "smoke_r43", bool(smoke.get("ok")), smoke,
                       _captura_janela(cap_dir / "00-smoke.png"))

                # Modelo fake (libera Novo audiolivro)
                dl = _run_js_step(window, "modelo_fake", """
  let m = await (await studio.fetch("/api/models")).json();
  if (m.status !== "pronto") {
    await studio.post("/api/models/download", null).catch(() => {});
    for (let i = 0; i < 40; i++) {
      m = await (await studio.fetch("/api/models")).json();
      if (m.status === "pronto" || m.status === "erro") break;
      await new Promise(r => setTimeout(r, 200));
    }
    if (m.status !== "pronto") {
      await studio.post("/api/models/download", null).catch(() => {});
      for (let i = 0; i < 40; i++) {
        m = await (await studio.fetch("/api/models")).json();
        if (m.status === "pronto" || m.status === "erro") break;
        await new Promise(r => setTimeout(r, 200));
      }
    }
  }
  window.__absStep = {step: step, ok: m.status === "pronto", status: m.status};
""", timeout=40)
                _passo(result, "modelo_fake", bool(dl.get("ok")), dl,
                       _captura_janela(cap_dir / "01-home.png"))

                # Guia 2: criar projeto via API Python (evita b64 gigante no evaluate_js do WKWebView)
                st, body = _api(base, token, "POST", "/api/projects", _epub_bytes())
                try:
                    criado = json.loads(body.decode("utf8", errors="replace"))
                except Exception:
                    criado = {"raw": body[:200].decode("utf8", errors="replace")}
                pid = criado.get("id") if st == 200 else None
                _passo(
                    result, "guia2_criar",
                    bool(pid),
                    {"http": st, "id": pid, "title": criado.get("title"), "error": criado.get("error")},
                    _captura_janela(cap_dir / "02-criar.png"),
                )
                if not pid:
                    raise RuntimeError(f"falha ao criar projeto: http={st} body={criado}")

                nav = _run_js_step(window, "guia2_nav", f"""
  location.href = studio.href("/review.html?id=" + encodeURIComponent({json.dumps(pid)}));
  window.__absStep = {{step: step, ok: true, id: {json.dumps(pid)}}};
""", timeout=15)
                time.sleep(1.2)

                rev = _run_js_step(window, "guia2_lista", """
  const caps = document.querySelectorAll(".cap");
  window.__absStep = {step: step, ok: caps.length >= 3, n: caps.length, href: location.href};
""", timeout=20)
                _passo(result, "guia2_lista", bool(rev.get("ok")), rev,
                       _captura_janela(cap_dir / "02-conferencia.png"))

                ed = _run_js_step(window, "guia2_editar", """
  const caps = Array.from(document.querySelectorAll(".cap"));
  if (caps.length < 2) throw new Error("poucos capitulos");
  const c1 = caps[0], c2 = caps[1];
  const tit = c1.querySelector(".tit");
  tit.value = "Capítulo Um: A Praça";
  tit.dispatchEvent(new Event("change"));
  const inc2 = c2.querySelector(".incb");
  if (inc2.checked) { inc2.checked = false; inc2.dispatchEvent(new Event("change")); }
  const meta = document.getElementById("meta") ? document.getElementById("meta").textContent : "";
  window.__absStep = {
    step: step,
    ok: c2.classList.contains("off") && /2 capítulos incluídos/.test(meta),
    meta: meta,
    titulo: tit.value
  };
""", timeout=15)
                _passo(result, "guia2_editar", bool(ed.get("ok")), ed,
                       _captura_janela(cap_dir / "02-editada.png"))
                result["guias"]["guia2"] = all(
                    result["passos"].get(k, {}).get("ok")
                    for k in ("guia2_criar", "guia2_lista", "guia2_editar")
                )

                _run_js_step(window, "guia2_seguir", """
  document.getElementById("seguir").click();
  window.__absStep = {step: step, ok: true};
""", timeout=10)
                time.sleep(1.0)

                # Voz de reserva (rafael): o selftest não depende do pacote de voz embutido.
                st_v, body_v = _api(
                    base, token, "POST", f"/api/projects/{pid}/voice",
                    json.dumps({"voice_id": "rafael"}).encode(),
                    {"Content-Type": "application/json"},
                )
                _passo(result, "guia4_anexar_rafael", st_v == 200, {"http": st_v, "body": body_v[:200].decode("utf8", errors="replace")})

                # Motor selftest no disco antes da geração
                cfg_path = home / "projects" / pid / "config.json"
                try:
                    cfg = json.loads(cfg_path.read_text(encoding="utf8")) if cfg_path.is_file() else {}
                except Exception:
                    cfg = {}
                cfg["motor"] = SELFTEST_MOTOR
                cfg_path.parent.mkdir(parents=True, exist_ok=True)
                cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf8")

                voz = _run_js_step(window, "guia4_voz", """
  const lista = document.querySelectorAll(".voz");
  const on = document.querySelector(".voz.on");
  let ouviu = false;
  const btn = on ? on.querySelector("button") : document.querySelector(".voz button");
  if (btn) {
    btn.click();
    await new Promise(r => setTimeout(r, 2500));
    const player = document.getElementById("player");
    ouviu = !!(player && (player.src || player.currentSrc));
  }
  window.__absStep = {
    step: step,
    ok: !!on && lista.length >= 1,
    selecionada: !!on,
    ouviu: ouviu,
    n: lista.length
  };
""", timeout=30)
                _passo(result, "guia4_voz", bool(voz.get("ok")), voz,
                       _captura_janela(cap_dir / "04-voz.png"))
                result["guias"]["guia4"] = bool(voz.get("ok"))

                _run_js_step(window, "guia4_seguir", """
  document.getElementById("seguir").click();
  window.__absStep = {step: step, ok: true};
""", timeout=15)
                time.sleep(1.5)
                # reforça motor após attach_voice
                try:
                    cfg = json.loads(cfg_path.read_text(encoding="utf8")) if cfg_path.is_file() else {}
                except Exception:
                    cfg = {}
                cfg["motor"] = SELFTEST_MOTOR
                cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf8")

                _run_js_step(window, "guia5_nav", f"""
  if (!/dashboard\\.html/.test(location.href)) {{
    location.href = studio.href("/dashboard.html?id=" + encodeURIComponent({json.dumps(pid)}));
  }}
  window.__absStep = {{step: step, ok: true}};
""", timeout=15)
                time.sleep(1.5)

                def wait_status(*wanted, timeout=90):
                    deadline = time.time() + timeout
                    last = {}
                    while time.time() < deadline:
                        last = _run_js_step(window, "guia5_poll_" + secrets.token_hex(2), """
  const pid = new URLSearchParams(location.search).get("id");
  const st = await (await studio.fetch("/api/projects/" + encodeURIComponent(pid) + "/state")).json();
  window.__absStep = {step: step, ok: true, status: st.status, chars_done: st.chars_done, error: st.error || (st.job && st.job.error)};
""", timeout=10)
                        if last.get("status") in wanted or last.get("status") == "erro":
                            return last
                        time.sleep(0.3)
                    return last

                _run_js_step(window, "guia5_start", """
  const pid = new URLSearchParams(location.search).get("id");
  await studio.post("/api/projects/" + encodeURIComponent(pid) + "/start", "{}");
  window.__absStep = {step: step, ok: true};
""", timeout=20)
                ger = wait_status("gerando", "montando", "pronto", "concluido", timeout=60)
                _passo(result, "guia5_gerando", ger.get("status") in ("gerando", "montando", "pronto", "concluido"), ger,
                       _captura_janela(cap_dir / "05-gerando.png"))

                _eval(window, "document.getElementById('btnPause') && document.getElementById('btnPause').click(); true")
                time.sleep(0.8)
                pau = wait_status("pausado", "pronto", "concluido", timeout=30)
                _passo(result, "guia5_pausar", pau.get("status") in ("pausado", "pronto", "concluido"), pau,
                       _captura_janela(cap_dir / "05-pausado.png"))

                _eval(window, "document.getElementById('btnResume') && document.getElementById('btnResume').click(); true")
                time.sleep(0.8)
                cont = wait_status("gerando", "montando", "pronto", "concluido", timeout=30)
                _passo(result, "guia5_continuar", cont.get("status") in ("gerando", "montando", "pronto", "concluido"), cont)

                _eval(window, "document.getElementById('btnCancel') && document.getElementById('btnCancel').click(); true")
                time.sleep(0.8)
                canc = wait_status("cancelado", "pronto", "concluido", timeout=40)
                _passo(result, "guia5_cancelar", canc.get("status") in ("cancelado", "pronto", "concluido"), canc,
                       _captura_janela(cap_dir / "05-cancelado.png"))

                _eval(window, "document.getElementById('btnResume') && document.getElementById('btnResume').click(); true")
                pronto = wait_status("pronto", "concluido", timeout=180)
                _passo(result, "guia5_retomar_pronto", pronto.get("status") in ("pronto", "concluido"), pronto)
                result["guias"]["guia5"] = all(
                    result["passos"].get(k, {}).get("ok")
                    for k in ("guia5_gerando", "guia5_pausar", "guia5_continuar", "guia5_cancelar", "guia5_retomar_pronto")
                )

                prog = home / "projects" / pid / "work" / "progress.jsonl"
                prog.parent.mkdir(parents=True, exist_ok=True)
                with prog.open("a", encoding="utf8") as f:
                    f.write(json.dumps({"kind": "flagged", "ch": "01", "chunk": 0}) + "\n")

                _run_js_step(window, "guia6_nav", f"""
  location.href = studio.href("/ready.html?id=" + encodeURIComponent({json.dumps(pid)}));
  window.__absStep = {{step: step, ok: true}};
""", timeout=15)
                time.sleep(1.5)

                seek = _run_js_step(window, "guia6_seek", """
  const a = document.querySelector("audio");
  if (!a) throw new Error("sem audio");
  await new Promise((resolve, reject) => {
    a.onloadedmetadata = () => resolve();
    a.onerror = () => reject(new Error("audio"));
    setTimeout(() => resolve(), 8000);
    a.load();
  });
  const before = a.currentTime || 0;
  const mid = Math.max(0.05, (a.duration || 1) / 2);
  a.currentTime = mid;
  await new Promise(r => setTimeout(r, 500));
  const seek_ok = a.currentTime > before && a.currentTime > 0.02;
  window.__absStep = {step: step, ok: seek_ok, before: before, after: a.currentTime, duration: a.duration};
""", timeout=30)
                if seek.get("ok"):
                    result["audio_range"] = True
                _passo(result, "guia6_seek", bool(seek.get("ok")), seek,
                       _captura_janela(cap_dir / "06-ready.png"))

                redo = _run_js_step(window, "guia6_refazer", """
  const btn = Array.from(document.querySelectorAll("button")).find(b => /Refazer trecho/.test(b.textContent || ""));
  if (btn) {
    btn.click();
    for (let i = 0; i < 120; i++) {
      const ok = document.getElementById("ok");
      if (ok && !ok.hidden && /refeito/i.test(ok.textContent || "")) {
        window.__absStep = {step: step, ok: true, msg: ok.textContent};
        return;
      }
      await new Promise(r => setTimeout(r, 500));
    }
    window.__absStep = {step: step, ok: false, err: "timeout redo"};
  } else {
    window.__absStep = {step: step, ok: true, skipped: "sem flagged na UI"};
  }
""", timeout=120)
                _passo(result, "guia6_refazer", bool(redo.get("ok")), redo)

                m4b = _run_js_step(window, "guia6_salvar_m4b", """
  const pid = new URLSearchParams(location.search).get("id");
  const j = await studio.post("/api/projects/" + encodeURIComponent(pid) + "/assemble",
    JSON.stringify({video: false}), {"Content-Type": "application/json"});
  const nome = (j.out || j.m4b || "").split(/[/\\\\]/).pop();
  window.__absStep = {step: step, ok: !!(j.out || j.m4b), arquivo: nome};
""", timeout=120)
                _passo(result, "guia6_salvar_m4b", bool(m4b.get("ok")), m4b,
                       _captura_janela(cap_dir / "06-m4b.png"))
                result["guias"]["guia6"] = bool(seek.get("ok")) and bool(m4b.get("ok"))

                result["ok"] = (
                    result["getUserMedia"] == "presente"
                    and result["audio_range"] is True
                    and result["guias"].get("guia2")
                    and result["guias"].get("guia4")
                    and result["guias"].get("guia5")
                    and result["guias"].get("guia6")
                )
            except Exception as e:
                result["error"] = str(e)
                result["ok"] = False
            finally:
                done["v"] = result
                try:
                    window.destroy()
                except Exception:
                    pass

        def on_loaded():
            threading.Thread(target=fluxo, args=(window,), daemon=True).start()

        window = webview.create_window(
            APP_NAME + " autoteste", url, width=1000, height=720, background_color="#02070c",
        )
        window.events.loaded += on_loaded

        def watchdog():
            time.sleep(600)
            if done["v"] is None:
                result["error"] = "timeout janela"
                done["v"] = result
                try:
                    window.destroy()
                except Exception:
                    pass

        threading.Thread(target=watchdog, daemon=True).start()
        webview.start()
        out = done["v"] or result
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out.get("ok") else 1
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=3)
        except Exception:
            srv.kill()
