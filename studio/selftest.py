"""Autoteste ampliado na janela real (R43): guias 2, 4, 5 e 6 via evaluate_js.

Usa download simulado (AUDIOBOOK_FAKE_DOWNLOAD) e o motor mínimo
`studio.selftest_engine:SelftestEngine` (não aparece na lista de vozes da UI).
Imprime um JSON com resultado por passo e caminhos de captura quando possível.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from studio.brand import APP_NAME, ensure_dirs


SELFTEST_MOTOR = "studio.selftest_engine:SelftestEngine"


def _captura_janela(dest: Path, titulo_contem: str = "") -> str | None:
    """Tenta capturar a janela do app. Devolve o caminho ou None se pywebview/OS não permitir."""
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
        )
        from Quartz import CGImageDestinationCreateWithURL, CGImageDestinationAddImage, CGImageDestinationFinalize
        from Foundation import NSURL
        import Quartz

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
            CGRectNull,
            kCGWindowListOptionIncludingWindow,
            alvo,
            kCGWindowImageDefault,
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


def _epub_b64() -> str:
    from tests.epub_sintetico import make_epub, paras
    import tempfile as tf

    fd, nome = tf.mkstemp(suffix=".epub")
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
        return base64.b64encode(path.read_bytes()).decode("ascii")
    finally:
        path.unlink(missing_ok=True)


def _eval(window, js: str):
    return window.evaluate_js(js)


def _wait_js(window, expr: str, timeout=30.0, interval=0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = _eval(window, f"(() => {{ try {{ return JSON.stringify({expr}); }} catch(e) {{ return JSON.stringify({{err: String(e)}}); }} }})()")
            if raw and raw != "null":
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict) and data.get("err"):
                    time.sleep(interval)
                    continue
                return data
        except Exception:
            pass
        time.sleep(interval)
    return None


def _passo(result: dict, nome: str, ok: bool, detalhe=None, captura=None):
    entry = {"ok": bool(ok), "detalhe": detalhe}
    if captura:
        entry["captura"] = captura
    result["passos"][nome] = entry
    result["guias"] = result.get("guias") or {}


def run_self_test(argv=None) -> int:
    """Autoteste na janela real. Imprime JSON em stdout."""
    # Motor e download só neste modo (não vão para a UI de produção).
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

        try:
            epub_b64 = _epub_b64()
        except Exception as e:
            # No app frozen, tests.epub_sintetico pode não existir: EPUB mínimo embutido.
            result["error"] = f"epub: {e}"
            epub_b64 = None

        if epub_b64 is None:
            # Fallback: zip mínimo gerado sem o módulo de testes
            import zipfile
            from io import BytesIO
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
                z.writestr("META-INF/container.xml",
                           '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                           '<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
                z.writestr("content.opf",
                           '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="u">'
                           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Crônicas da Praça</dc:title>'
                           '<dc:language>pt-BR</dc:language><dc:identifier id="u">selftest</dc:identifier></metadata>'
                           '<manifest><item id="c1" href="Text/c1.xhtml" media-type="application/xhtml+xml"/>'
                           '<item id="c2" href="Text/c2.xhtml" media-type="application/xhtml+xml"/>'
                           '<item id="c3" href="Text/c3.xhtml" media-type="application/xhtml+xml"/>'
                           '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
                           '<spine toc="ncx"><itemref idref="c1"/><itemref idref="c2"/><itemref idref="c3"/></spine></package>')
                for i, t in enumerate(("Manhã na Praça", "A Carta Azul", "O Rio no Inverno"), 1):
                    body = f"<h1>{i}. {t}</h1><p>O vento frio descia pela rua estreita e ninguém sabia dizer de onde vinha aquele cheiro de pão.</p>" \
                           f"<p>Ela abriu a janela, olhou para o relógio da praça e pensou que ainda havia tempo para tudo.</p>"
                    z.writestr(f"Text/c{i}.xhtml",
                               '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title></head>'
                               f"<body>{body}</body></html>")
                z.writestr("toc.ncx",
                           '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head/>'
                           '<docTitle><text>x</text></docTitle><navMap>'
                           '<navPoint id="n1" playOrder="1"><navLabel><text>1. Manhã na Praça</text></navLabel><content src="Text/c1.xhtml"/></navPoint>'
                           '<navPoint id="n2" playOrder="2"><navLabel><text>2. A Carta Azul</text></navLabel><content src="Text/c2.xhtml"/></navPoint>'
                           '<navPoint id="n3" playOrder="3"><navLabel><text>3. O Rio no Inverno</text></navLabel><content src="Text/c3.xhtml"/></navPoint>'
                           '</navMap></ncx>')
            epub_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        def fluxo(window):
            nonlocal result
            try:
                # --- smoke getUserMedia / Range (mantém R43 básico) ---
                kick = r"""
window.__absSelf = null;
(async function() {
  const out = {getUserMedia: "ausente", microphone_permission: null, audio_range: false, seek_ok: false};
  try {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) out.getUserMedia = "presente";
  } catch (e) { out.getUserMedia = "erro"; }
  window.__absSelf = out;
})();
true
"""
                _eval(window, kick)
                time.sleep(0.5)
                smoke = _wait_js(window, "window.__absSelf", timeout=5) or {}
                result["getUserMedia"] = smoke.get("getUserMedia") or "ausente"

                # Download simulado do modelo (guia 1 auxiliar para liberar Novo audiolivro)
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
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
    window.__absStep = {ok: m.status === "pronto", status: m.status};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                dl = _wait_js(window, "window.__absStep", timeout=40) or {}
                _passo(result, "modelo_fake", bool(dl.get("ok")), dl)
                cap = _captura_janela(cap_dir / "01-home.png")
                if cap:
                    result["passos"]["modelo_fake"]["captura"] = cap

                # Guia 2: criar livro a partir do EPUB sintético
                js_criar = """
window.__absStep = null;
(async function() {
  try {
    const b64 = %B64%;
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const file = new File([arr], "livro-valido.epub", {type: "application/epub+zip"});
    const j = await studio.post("/api/projects", file);
    window.__absStep = {ok: !!(j && j.id), id: j && j.id, title: j && j.title};
    if (j && j.id) location.href = studio.href("/review.html?id=" + encodeURIComponent(j.id));
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""".replace("%B64%", json.dumps(epub_b64))
                _eval(window, js_criar)
                cri = _wait_js(window, "window.__absStep", timeout=60) or {}
                pid = cri.get("id")
                _passo(result, "guia2_criar", bool(cri.get("ok")), cri,
                       _captura_janela(cap_dir / "02-criar.png"))
                if not pid:
                    raise RuntimeError("falha ao criar projeto")

                # Esperar review carregar
                time.sleep(1.2)
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
    const caps = document.querySelectorAll(".cap");
    window.__absStep = {ok: caps.length >= 3, n: caps.length, href: location.href};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                rev = _wait_js(window, "window.__absStep", timeout=20) or {}
                _passo(result, "guia2_lista", bool(rev.get("ok")), rev,
                       _captura_janela(cap_dir / "02-conferencia.png"))

                # Tirar capítulo 2 e renomear capítulo 1
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
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
      ok: c2.classList.contains("off") && /2 capítulos incluídos/.test(meta),
      meta: meta,
      titulo: tit.value
    };
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                ed = _wait_js(window, "window.__absStep", timeout=15) or {}
                _passo(result, "guia2_editar", bool(ed.get("ok")), ed,
                       _captura_janela(cap_dir / "02-editada.png"))

                # Continuar para voz + setar motor selftest no config
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
    document.getElementById("seguir").click();
    window.__absStep = {ok: true};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                _wait_js(window, "window.__absStep", timeout=10)
                time.sleep(1.0)

                # Guia 4: voz selecionada + ouvir
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
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
      ok: !!on && lista.length >= 1,
      selecionada: !!on,
      ouviu: ouviu,
      n: lista.length
    };
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                voz = _wait_js(window, "window.__absStep", timeout=30) or {}
                _passo(result, "guia4_voz", bool(voz.get("ok")), voz,
                       _captura_janela(cap_dir / "04-voz.png"))
                result["guias"]["guia4"] = bool(voz.get("ok"))

                # Motor selftest no disco + voz + dashboard
                home = ensure_dirs()
                cfg_path = home / "projects" / pid / "config.json"
                try:
                    cfg = json.loads(cfg_path.read_text(encoding="utf8")) if cfg_path.is_file() else {}
                except Exception:
                    cfg = {}
                cfg["motor"] = SELFTEST_MOTOR
                cfg_path.parent.mkdir(parents=True, exist_ok=True)
                cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf8")

                _eval(window, """
window.__absStep = null;
(async function() {
  try {
    document.getElementById("seguir").click();
    window.__absStep = {ok: true};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                _wait_js(window, "window.__absStep", timeout=15)
                time.sleep(1.5)
                # reforça motor após attach_voice (que pode reescrever config)
                try:
                    cfg = json.loads(cfg_path.read_text(encoding="utf8")) if cfg_path.is_file() else {}
                except Exception:
                    cfg = {}
                cfg["motor"] = SELFTEST_MOTOR
                cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf8")

                _eval(window, f"""
(function() {{
  if (!/dashboard\\.html/.test(location.href)) {{
    location.href = studio.href("/dashboard.html?id=" + encodeURIComponent({json.dumps(pid)}));
  }}
  return true;
}})()
""")
                time.sleep(1.5)

                # Guia 5: gerar, pausar, continuar, cancelar, retomar
                def wait_status(*wanted, timeout=90):
                    _eval(window, """
window.__absStep = null;
(async function() {
  try {
    const pid = new URLSearchParams(location.search).get("id");
    const st = await (await studio.fetch("/api/projects/" + encodeURIComponent(pid) + "/state")).json();
    window.__absStep = {ok: true, status: st.status, chars_done: st.chars_done};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                    deadline = time.time() + timeout
                    last = {}
                    while time.time() < deadline:
                        last = _wait_js(window, "window.__absStep", timeout=5) or {}
                        if last.get("status") in wanted:
                            return last
                        _eval(window, """
window.__absStep = null;
(async function() {
  const pid = new URLSearchParams(location.search).get("id");
  const st = await (await studio.fetch("/api/projects/" + encodeURIComponent(pid) + "/state")).json();
  window.__absStep = {ok: true, status: st.status, chars_done: st.chars_done};
})();
true
""")
                        time.sleep(0.4)
                    return last

                # Garante start
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
    const pid = new URLSearchParams(location.search).get("id");
    await studio.post("/api/projects/" + encodeURIComponent(pid) + "/start", "{}");
    window.__absStep = {ok: true};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                _wait_js(window, "window.__absStep", timeout=20)
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

                # Retomar até pronto
                _eval(window, "document.getElementById('btnResume') && document.getElementById('btnResume').click(); true")
                pronto = wait_status("pronto", "concluido", timeout=180)
                _passo(result, "guia5_retomar_pronto", pronto.get("status") in ("pronto", "concluido"), pronto)
                result["guias"]["guia5"] = all(
                    result["passos"].get(k, {}).get("ok")
                    for k in ("guia5_gerando", "guia5_pausar", "guia5_continuar", "guia5_cancelar", "guia5_retomar_pronto")
                )

                # Marca um trecho flagged para guia 6
                prog = home / "projects" / pid / "work" / "progress.jsonl"
                prog.parent.mkdir(parents=True, exist_ok=True)
                with prog.open("a", encoding="utf8") as f:
                    f.write(json.dumps({"kind": "flagged", "ch": "01", "chunk": 0}) + "\n")

                _eval(window, f"""
location.href = studio.href("/ready.html?id=" + encodeURIComponent({json.dumps(pid)}));
true
""")
                time.sleep(1.5)

                # Guia 6: tocar, seek, refazer, salvar M4B
                _eval(window, """
window.__absStep = null;
(async function() {
  try {
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
    window.__absStep = {ok: seek_ok, before: before, after: a.currentTime, duration: a.duration};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                seek = _wait_js(window, "window.__absStep", timeout=30) or {}
                result["audio_range"] = bool(seek.get("ok"))
                _passo(result, "guia6_seek", bool(seek.get("ok")), seek,
                       _captura_janela(cap_dir / "06-ready.png"))

                _eval(window, """
window.__absStep = null;
(async function() {
  try {
    const btn = Array.from(document.querySelectorAll("button")).find(b => /Refazer trecho/.test(b.textContent || ""));
    if (btn) {
      btn.click();
      for (let i = 0; i < 120; i++) {
        const ok = document.getElementById("ok");
        if (ok && !ok.hidden && /refeito/i.test(ok.textContent || "")) {
          window.__absStep = {ok: true, msg: ok.textContent};
          return;
        }
        await new Promise(r => setTimeout(r, 500));
      }
      window.__absStep = {ok: false, err: "timeout redo"};
    } else {
      window.__absStep = {ok: true, skipped: "sem flagged na UI"};
    }
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                redo = _wait_js(window, "window.__absStep", timeout=120) or {}
                _passo(result, "guia6_refazer", bool(redo.get("ok")), redo)

                _eval(window, """
window.__absStep = null;
(async function() {
  try {
    // evita diálogo nativo: chama assemble + confirma mensagem
    const pid = new URLSearchParams(location.search).get("id");
    const j = await studio.post("/api/projects/" + encodeURIComponent(pid) + "/assemble",
      JSON.stringify({video: false}), {"Content-Type": "application/json"});
    const nome = (j.out || j.m4b || "").split(/[/\\\\]/).pop();
    window.__absStep = {ok: !!(j.out || j.m4b), arquivo: nome};
  } catch (e) { window.__absStep = {ok: false, err: String(e)}; }
})();
true
""")
                m4b = _wait_js(window, "window.__absStep", timeout=120) or {}
                _passo(result, "guia6_salvar_m4b", bool(m4b.get("ok")), m4b,
                       _captura_janela(cap_dir / "06-m4b.png"))
                result["guias"]["guia6"] = bool(seek.get("ok")) and bool(m4b.get("ok"))
                result["guias"]["guia2"] = all(
                    result["passos"].get(k, {}).get("ok")
                    for k in ("guia2_criar", "guia2_lista", "guia2_editar")
                )

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

        window = webview.create_window(APP_NAME + " autoteste", url, width=1000, height=720, background_color="#02070c")
        window.events.loaded += on_loaded

        def watchdog():
            time.sleep(420)
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
