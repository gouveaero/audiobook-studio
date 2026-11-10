"""Lógica das rotas do app (projetos, voz, modelos, estado). Usada por studio.server."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

from studio.audio import eq_por_graves
from studio.brand import (
    ANDROID_WAITLIST_URL,
    APP_NAME,
    DONATION_URL,
    GITHUB_REPO,
    VOICE_FALLBACK,
    app_home,
    ensure_dirs,
)
from studio.prepare_book import BookError, build as build_book

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Catálogo de vozes prontas do Pocket (nomes públicos; sem baixar nada).
VOZES_PRONTAS = [
    "cosette", "marius", "javert", "alba", "jean", "anna", "vera", "fantine",
    "charles", "paul", "eponine", "azelma", "george", "mary", "jane", "michael",
    "eve", "bill_boerst", "peter_yearsley", "stuart_bell", "caro_davy",
    "giovanni", "lola", "juergen", "rafael", "daan", "estelle",
]

MODEL_ID = "portuguese_24l"
# Pesos sem clonagem (os mesmos que pocket.py / TTSModel.load_model usa sem login).
# Ver pocket_tts/config/portuguese_24l.yaml → weights_path_without_voice_cloning + tokenizer.
MODEL_REPO = "kyutai/pocket-tts-without-voice-cloning"
MODEL_REVISION = "4e1e0a3e611c51c0b4ed8174fc10f32a54644303"
# get_predefined_voice(language, name) em pocket_tts/utils/utils.py
EMBEDDING_REVISION = "a7056f505a4a8ca72d8b5fb1440071d6f1a35739"
# (repo, filename, revision) — primeiro uso: modelo + tokenizer + voz de reserva (R22, R35).
def arquivos_primeiro_uso():
    return (
        (MODEL_REPO, f"languages/{MODEL_ID}/model.safetensors", MODEL_REVISION),
        (MODEL_REPO, f"languages/{MODEL_ID}/tokenizer.json", MODEL_REVISION),
        (MODEL_REPO, f"languages/{MODEL_ID}/embeddings/{VOICE_FALLBACK}.safetensors", EMBEDDING_REVISION),
    )


MODEL_FILES = tuple(fn for _, fn, _ in arquivos_primeiro_uso())
# Tamanho medido (~672 MB do modelo + embedding da voz de reserva); o download real atualiza.
MODEL_TOTAL_BYTES = 672 * 1024 * 1024
APP_VERSION = "0.1.0-beta"


def caminho_embedding_voz(nome: str) -> str:
    """Caminho no Hub do embedding de uma voz pronta (pocket_tts.get_predefined_voice)."""
    return f"languages/{MODEL_ID}/embeddings/{nome}.safetensors"


def slugify(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return (s[:60] or "livro")


def projects_root() -> Path:
    ensure_dirs()
    return app_home() / "projects"


def project_path(pid: str) -> Path | None:
    if not pid or ".." in pid or "/" in pid or "\\" in pid:
        return None
    d = projects_root() / pid
    return d if d.is_dir() else None


def list_projects() -> list[dict]:
    items = []
    root = projects_root()
    if not root.is_dir():
        return items
    for d in sorted(root.iterdir()):
        book_path = d / "book.json"
        if d.is_dir() and book_path.is_file():
            try:
                book = json.loads(book_path.read_text(encoding="utf8"))
            except (OSError, ValueError):
                book = {}
            items.append({"id": d.name, "title": book.get("title", d.name), "author": book.get("author", "")})
    return items


def create_project_from_epub(epub_bytes: bytes) -> dict:
    ensure_dirs()
    if not modelo_pronto():
        raise BookError(
            "modelo",
            "Baixe o modelo de voz antes de criar um audiolivro.",
        )
    tmp = app_home() / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    epub_path = tmp / f"upload-{int(time.time() * 1000)}.epub"
    epub_path.write_bytes(epub_bytes)
    try:
        # pasta provisória; o slug final vem do título
        staging = tmp / f"staging-{os.getpid()}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        book_out = staging / "book.json"
        try:
            build_book(str(epub_path), str(book_out))
        except BookError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        book = json.loads(book_out.read_text(encoding="utf8"))
        base = slugify(book.get("title") or "livro")
        pid = base
        n = 2
        while (projects_root() / pid).exists():
            pid = f"{base}-{n}"
            n += 1
        dest = projects_root() / pid
        staging.rename(dest)
        # copia o epub para o projeto
        shutil.copy2(epub_path, dest / "book.epub")
        for sub in ("work/chunks", "chapters", "voice", "audiobook"):
            (dest / sub).mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text(
            json.dumps({"motor": "pocket", "model": MODEL_ID}, ensure_ascii=False, indent=1),
            encoding="utf8",
        )
        return {
            "id": pid,
            "title": book.get("title", pid),
            "author": book.get("author", ""),
            "chapters": len(book.get("chapters", [])),
        }
    finally:
        try:
            epub_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_book(pid: str) -> dict:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    return json.loads((p / "book.json").read_text(encoding="utf8"))


def save_book(pid: str, book: dict) -> dict:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    # R9: respeita include e title por capítulo
    if "chapters" not in book or not isinstance(book["chapters"], list):
        raise ValueError("book.json sem capítulos")
    for ch in book["chapters"]:
        if "include" not in ch:
            ch["include"] = True
        if "title" not in ch:
            raise ValueError("capítulo sem título")
    (p / "book.json").write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf8")
    return book


def read_job(pid: str) -> dict | None:
    p = project_path(pid)
    if not p:
        return None
    path = p / "work" / "job.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None


def write_job(pid: str, job: dict) -> None:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    work = p / "work"
    work.mkdir(parents=True, exist_ok=True)
    path = work / "job.json"
    tmp = work / "job.json.tmp"
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf8")
    os.replace(tmp, path)


# Status finais que o generate grava em work/job.json (Motor T8); a interface não sobrescreve.
JOB_FINAIS = frozenset({"pronto", "concluido", "erro", "cancelado"})
JOB_ATIVOS = frozenset({"gerando", "rodando", "refazendo", "montando"})


def project_state(pid: str) -> dict:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    job = read_job(pid) or {}
    status = job.get("status") or "parado"
    # Preferir o que o generate já gravou; pause/cancel só coloram enquanto ativo.
    if status not in JOB_FINAIS:
        if (p / "work" / "cancel").exists() and status in JOB_ATIVOS | {"pausado"}:
            status = "cancelando"
        elif (p / "work" / "pause").exists() and status in JOB_ATIVOS:
            status = "pausado"
    # Progresso: chars_done do job quando existir; senão estima pelos WAV.
    book = {}
    try:
        book = json.loads((p / "book.json").read_text(encoding="utf8"))
    except (OSError, ValueError):
        pass
    chapters = [c for c in book.get("chapters", []) if c.get("include", True)]
    chars = {(c["id"], k): len(t) for c in chapters for k, t in enumerate(c.get("chunks", []))}
    tot = int(job.get("chars_total") or 0) or (sum(chars.values()) or 1)
    done_chars = job.get("chars_done")
    if done_chars is None:
        done_chars = 0
        chunks_dir = p / "work" / "chunks"
        if chunks_dir.is_dir():
            for f in os.listdir(chunks_dir):
                m = re.fullmatch(r"(\w+)_(\d+)\.wav", f)
                if m and (m.group(1), int(m.group(2))) in chars:
                    done_chars += chars[(m.group(1), int(m.group(2)))]
    done_ids = []
    if (p / "chapters").is_dir():
        done_ids = sorted(f[:-4] for f in os.listdir(p / "chapters") if re.fullmatch(r"\w+\.m4a", f))
    flagged = _flagged_from_progress(p)
    eta = job.get("eta_seconds")
    cps = job.get("chars_per_second")
    return {
        "status": status,
        "job": job,
        "total": min(1.0, float(done_chars) / float(tot or 1)),
        "hours": round(float(done_chars) / 13 / 3600, 2),
        "done": done_ids,
        "titles": {c["id"]: c["title"] for c in book.get("chapters", [])},
        "eta_seconds": eta,
        "chars_done": done_chars,
        "chars_total": tot,
        "chars_per_second": cps,
        "m4b": job.get("m4b"),
        "error": job.get("error"),
        "flagged": flagged,
    }


def _flagged_from_progress(p: Path) -> list[dict]:
    """Trechos marcados em work/progress.jsonl (para a tela final / refazer).

    Vale o último evento `done` de cada capítulo (mesmo com flagged vazio).
    Eventos `flagged` isolados só contam até o próximo `done` daquele capítulo.
    """
    path = p / "work" / "progress.jsonl"
    if not path.is_file():
        return []
    by_ch: dict[str, set[int]] = {}
    try:
        for line in path.read_text(encoding="utf8").splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            ch = ev.get("ch") or ev.get("chapter")
            if ch is None:
                continue
            ch = str(ch)
            kind = ev.get("kind")
            if kind == "done" and "flagged" in ev:
                by_ch[ch] = {int(k) for k in (ev.get("flagged") or []) if k is not None}
            elif kind == "flagged":
                k = ev.get("chunk")
                if k is not None:
                    by_ch.setdefault(ch, set()).add(int(k))
            elif kind == "done" and ev.get("flagged"):
                by_ch[ch] = {int(k) for k in ev["flagged"] if k is not None}
    except OSError:
        pass
    out = []
    for ch, ks in by_ch.items():
        for k in sorted(ks):
            out.append({"chapter": ch, "chunk": int(k)})
    return out


def set_pause(pid: str, paused: bool) -> None:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    work = p / "work"
    work.mkdir(parents=True, exist_ok=True)
    flag = work / "pause"
    if paused:
        flag.write_text("1", encoding="utf8")
        # o generate passa a status "pausado" ao ler o arquivo; não forçar se já finalizou
    else:
        flag.unlink(missing_ok=True)


def set_cancel(pid: str) -> None:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    work = p / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "cancel").write_text("1", encoding="utf8")
    # o generate grava "cancelado"; não sobrescrever job aqui


def start_generate(pid: str, *, only: str = "", extra: dict | None = None) -> dict:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    cfg = {}
    try:
        cfg = json.loads((p / "config.json").read_text(encoding="utf8"))
    except (OSError, ValueError):
        pass
    motor = cfg.get("motor") or "pocket"
    (p / "work").mkdir(parents=True, exist_ok=True)
    for f in ("pause", "cancel"):
        (p / "work" / f).unlink(missing_ok=True)
    cmd = [sys.executable, "-m", "studio.generate", "--project", str(p), "--motor", motor]
    if only:
        cmd.extend(["--only", only])
    log = open(p / "work" / "generate.log", "ab")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    job = {
        "pid": proc.pid,
        "status": "gerando",
        "motor": motor,
        "model": cfg.get("model") or MODEL_ID,
        "started": time.time(),
        "eta_seconds": None,
        "chars_total": None,
        "chars_done": 0,
        "chars_per_second": None,
    }
    if only:
        job["only"] = only
    if extra:
        job.update(extra)
    write_job(pid, job)

    def waiter():
        code = proc.wait()
        cur = read_job(pid) or {}
        # generate já grava pronto/concluido/cancelado/erro; não apagar
        if cur.get("status") in JOB_FINAIS:
            return
        if (p / "work" / "cancel").exists():
            cur["status"] = "cancelado"
        else:
            cur["status"] = "concluido" if code == 0 else "erro"
        write_job(pid, cur)

    threading.Thread(target=waiter, daemon=True).start()
    return job


def redo_chunk(pid: str, chapter: str, chunk: int) -> dict:
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    chunks = p / "work" / "chunks"
    chunks.mkdir(parents=True, exist_ok=True)
    stem = f"{chapter}_{int(chunk):04d}"
    for f in list(chunks.glob(stem + "*")):
        f.unlink(missing_ok=True)
    (p / "chapters" / f"{chapter}.m4a").unlink(missing_ok=True)
    # generate.py só reclama o capítulo se a trava não existir
    locks = p / "work" / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    (locks / chapter).unlink(missing_ok=True)
    return start_generate(pid, only=chapter, extra={
        "status": "refazendo",
        "redo": {"chapter": chapter, "chunk": int(chunk)},
    })


def save_hf_token(token: str) -> None:
    ensure_dirs()
    token = (token or "").strip()
    if not token:
        raise ValueError("Informe o token do Hugging Face.")
    path = app_home() / "hf" / "token"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Cria já com 0600 (R26); se existir, corrige a permissão antes de escrever.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (token + "\n").encode("utf8"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    os.environ["HF_HOME"] = str(app_home() / "hf")


def models_status_path() -> Path:
    ensure_dirs()
    return app_home() / "models" / f"{MODEL_ID}.json"


def get_models_status() -> dict:
    path = models_status_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf8"))
            data.setdefault("total_bytes", MODEL_TOTAL_BYTES)
            data.setdefault("model", MODEL_ID)
            return data
        except (OSError, ValueError):
            pass
    return {
        "model": MODEL_ID,
        "status": "ausente",
        "bytes": 0,
        "total_bytes": MODEL_TOTAL_BYTES,
        "error": None,
    }


def set_models_status(**kw) -> dict:
    cur = get_models_status()
    cur.update(kw)
    path = models_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf8")
    return cur


def _hf_home_do_app() -> Path:
    """HF_HOME do app. Isola do cache global e de HF_HOME/HF_TOKEN herdados (R35, R36)."""
    ensure_dirs()
    hf = app_home() / "hf"
    hub = hf / "hub"
    hub.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(hf)
    os.environ["HF_HUB_CACHE"] = str(hub)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hub)
    for k in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        os.environ.pop(k, None)
    return hf


def hub_cache_do_app() -> Path:
    return _hf_home_do_app() / "hub"


def bytes_no_hub(hub: Path | None = None) -> int:
    """Soma o tamanho dos arquivos (completos ou .incomplete) no cache do app."""
    root = hub or hub_cache_do_app()
    if not root.is_dir():
        return 0
    total = 0
    for p in root.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def caminhos_modelo_no_app() -> list[Path]:
    """Arquivos finais do primeiro uso dentro de AUDIOBOOK_STUDIO_HOME/hf/ (não no cache global)."""
    hub = hub_cache_do_app()
    achados = []
    for _, fn, _ in arquivos_primeiro_uso():
        nome = Path(fn).name
        cands = [p for p in hub.rglob(nome)
                 if p.is_file() and "incomplete" not in p.name and MODEL_ID in str(p)]
        # embedding fica em .../embeddings/rafael.safetensors
        if "embeddings/" in fn:
            cands = [p for p in cands if "embeddings" in p.parts]
        snaps = [p for p in cands if "snapshots" in p.parts]
        escolhido = (snaps or cands)
        if escolhido:
            achados.append(escolhido[0])
    return achados


def tamanho_modelo_remoto() -> int:
    """Soma o tamanho real dos arquivos do primeiro uso (modelo + tokenizer + voz de reserva)."""
    from huggingface_hub import hf_hub_url, get_hf_file_metadata
    _hf_home_do_app()
    total = 0
    for repo, fn, rev in arquivos_primeiro_uso():
        url = hf_hub_url(repo, fn, revision=rev)
        meta = get_hf_file_metadata(url, token=False)
        total += int(meta.size or 0)
    return total or MODEL_TOTAL_BYTES


def baixar_arquivo_hub(filename: str, revision: str, *, repo: str = MODEL_REPO) -> Path:
    """Baixa um arquivo do Hub para o hf/ do app (usado no primeiro uso e na T17)."""
    from huggingface_hub import hf_hub_download
    hub = hub_cache_do_app()
    return Path(hf_hub_download(
        repo_id=repo,
        filename=filename,
        revision=revision,
        cache_dir=str(hub),
        token=False,
        force_download=False,
    ))


def baixar_embedding_voz(nome: str, on_progress=None) -> Path:
    """Baixa o embedding de uma voz pronta (demais vozes sob demanda na T17)."""
    fn = caminho_embedding_voz(nome)
    if on_progress:
        on_progress(0, 1)
    path = baixar_arquivo_hub(fn, EMBEDDING_REVISION)
    if on_progress:
        on_progress(1, 1)
    return path


def baixar_modelo_fake(on_progress) -> None:
    """Download simulado para o Testador (AUDIOBOOK_FAKE_DOWNLOAD=1).

    1ª tentativa: progresso parcial e falha de conexão.
    2ª tentativa em diante: completa até o total.
    """
    ensure_dirs()
    total = MODEL_TOTAL_BYTES
    marker = app_home() / "models" / ".fake_download_attempt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        n = int(marker.read_text(encoding="utf8").strip() or "0")
    except (OSError, ValueError):
        n = 0
    n += 1
    marker.write_text(str(n), encoding="utf8")
    on_progress(0, total)
    time.sleep(0.05)
    on_progress(max(1, total // 5), total)
    time.sleep(0.05)
    if n <= 1:
        raise ConnectionError("queda simulada")
    on_progress(total // 2, total)
    time.sleep(0.05)
    on_progress(total, total)


def baixar_modelo(on_progress) -> None:
    """Baixa pesos sem clonagem + embedding da voz de reserva só para hf/ do app.

    Ignora ~/.cache/huggingface e qualquer HF_HOME herdado. token=False: sem login.
    Depois disso o motor carrega offline com a voz de reserva (R22, R35).
    Com AUDIOBOOK_FAKE_DOWNLOAD=1 usa baixar_modelo_fake (só testes / Testador).
    """
    if os.environ.get("AUDIOBOOK_FAKE_DOWNLOAD", "").strip() in ("1", "true", "yes", "sim"):
        return baixar_modelo_fake(on_progress)
    hf = _hf_home_do_app()
    hub = hf / "hub"
    try:
        total = tamanho_modelo_remoto()
    except Exception:
        total = MODEL_TOTAL_BYTES
    on_progress(0, total)

    stop = threading.Event()
    ultimo = [0]

    def watch():
        while not stop.wait(0.3):
            done = bytes_no_hub(hub)
            if done > ultimo[0]:
                ultimo[0] = done
                on_progress(min(done, total), total)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        for repo, fn, rev in arquivos_primeiro_uso():
            baixar_arquivo_hub(fn, rev, repo=repo)
            done = bytes_no_hub(hub)
            ultimo[0] = max(ultimo[0], done)
            on_progress(min(ultimo[0], total), total)
    finally:
        stop.set()
        watcher.join(timeout=2)
    # tamanho final pelos arquivos no app (não pelo cache global)
    finais = caminhos_modelo_no_app()
    if finais:
        real = sum(p.stat().st_size for p in finais)
        on_progress(real, real if real >= total * 0.9 else total)
    else:
        on_progress(total, total)


_download_lock = threading.Lock()


def modelo_pronto() -> bool:
    return get_models_status().get("status") == "pronto"


def start_model_download(baixar=None) -> dict:
    if baixar is None:
        baixar = baixar_modelo
    cur = get_models_status()
    if cur.get("status") == "baixando":
        return cur
    set_models_status(status="baixando", bytes=0, total_bytes=MODEL_TOTAL_BYTES, error=None)

    def run():
        with _download_lock:
            try:
                def on_progress(done, total):
                    set_models_status(
                        status="baixando",
                        bytes=int(done),
                        total_bytes=int(total or MODEL_TOTAL_BYTES),
                        error=None,
                    )

                baixar(on_progress)
                st = get_models_status()
                set_models_status(
                    status="pronto",
                    bytes=int(st.get("total_bytes") or MODEL_TOTAL_BYTES),
                    error=None,
                )
            except Exception:
                set_models_status(
                    status="erro",
                    error="O download falhou. Verifique a conexão e tente de novo.",
                )

    threading.Thread(target=run, daemon=True).start()
    return get_models_status()


FRASE_PREVIEW = "Olá. Esta é uma frase curta para ouvir a voz."
AVISO_GRAVACAO_CURTA = (
    "A gravação ficou muito curta. Grave de novo, falando por cerca de 10 segundos."
)
AVISO_GRAVACAO_BAIXA = (
    "A gravação ficou muito baixa. Aproxime o microfone e grave de novo."
)
AVISO_GRAVACAO_RUIDO = (
    "Há muito ruído de fundo. Grave de novo num lugar mais silencioso."
)
MSG_SEM_CONEXAO_VOZ = (
    "Sem conexão com a internet. Conecte-se para baixar esta voz, "
    "ou use a voz de reserva já baixada."
)
# Limiares da checagem de gravação (R25). Excesso de graves não avisa: só liga o EQ.
GRAVACAO_MIN_SECS = 5.0
GRAVACAO_RMS_MIN = 0.015
GRAVACAO_PICO_MIN = 0.05
GRAVACAO_RUIDO_FRACAO = 0.55  # energia fora da faixa de fala (300 Hz a 4 kHz)


def voice_pack_dir() -> Path | None:
    env = os.environ.get("VOICE_PACK_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    bundled = ROOT / "build" / "voice-pack"
    return bundled if bundled.is_dir() else None


def settings_path() -> Path:
    ensure_dirs()
    return app_home() / "settings.json"


def load_settings() -> dict:
    path = settings_path()
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    path = settings_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf8")


def hf_logged_in() -> bool:
    path = app_home() / "hf" / "token"
    try:
        return path.is_file() and bool(path.read_text(encoding="utf8").strip())
    except OSError:
        return False


def embedding_local(nome: str) -> Path | None:
    """Caminho local do embedding se já estiver no hf/ do app."""
    hub = hub_cache_do_app()
    if not hub.is_dir():
        return None
    alvo = f"{nome}.safetensors"
    cands = [
        p for p in hub.rglob(alvo)
        if p.is_file() and "incomplete" not in p.name
        and "embeddings" in p.parts and MODEL_ID in str(p)
    ]
    snaps = [p for p in cands if "snapshots" in p.parts]
    escolhido = snaps or cands
    return escolhido[0] if escolhido else None


def garantir_embedding_voz(nome: str, on_progress=None) -> Path:
    """Garante o embedding no hf/ do app; mensagem em português se estiver sem conexão."""
    local = embedding_local(nome)
    if local is not None:
        if on_progress:
            on_progress(1, 1)
        return local
    try:
        return baixar_embedding_voz(nome, on_progress=on_progress)
    except Exception as e:
        msg = str(e).lower()
        offline = (
            "offlinemodeisenabled" in msg.replace("_", "").replace(" ", "")
            or "offline" in msg
            or "connection" in msg
            or "network" in msg
            or "failed to resolve" in msg
            or "nodename nor servname" in msg
            or "name or service not known" in msg
            or "temporary failure" in msg
        )
        if offline or isinstance(e, (ConnectionError, TimeoutError, OSError)):
            raise ConnectionError(MSG_SEM_CONEXAO_VOZ) from e
        raise ConnectionError(MSG_SEM_CONEXAO_VOZ) from e


def checar_gravacao(ref_wav: str | Path) -> list[str]:
    """Avisos para regravar (R25). Excesso de graves NÃO entra aqui: só liga o EQ."""
    import numpy as np
    from studio.wavio import read_wav

    samples, sr = read_wav(ref_wav)
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    avisos: list[str] = []
    if len(samples) < 2 or sr <= 0:
        return [AVISO_GRAVACAO_CURTA, AVISO_GRAVACAO_BAIXA]
    dur = len(samples) / float(sr)
    if dur < GRAVACAO_MIN_SECS:
        avisos.append(AVISO_GRAVACAO_CURTA)
    rms = float(np.sqrt(np.mean(samples * samples))) if len(samples) else 0.0
    pico = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if rms < GRAVACAO_RMS_MIN or pico < GRAVACAO_PICO_MIN:
        avisos.append(AVISO_GRAVACAO_BAIXA)
    # ruído: muita energia aguda fora da fala. Graves NÃO contam (R25: só ligam o EQ).
    espec = np.fft.rfft(samples)
    pot = (espec.real ** 2 + espec.imag ** 2)
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sr)
    total = float(pot.sum())
    if total > 0:
        agudos = float(pot[freqs > 4000.0].sum())
        if (agudos / total) > GRAVACAO_RUIDO_FRACAO and rms >= GRAVACAO_RMS_MIN:
            avisos.append(AVISO_GRAVACAO_RUIDO)
    return avisos


def _ids_voz_conhecidos() -> set[str]:
    ids = set(VOZES_PRONTAS)
    pack = voice_pack_dir()
    if pack and (pack / "manifest.json").is_file():
        try:
            man = json.loads((pack / "manifest.json").read_text(encoding="utf8"))
            ids.add(man.get("id", "padrao"))
        except (OSError, ValueError):
            pass
    vroot = app_home() / "voices"
    if vroot.is_dir():
        for d in vroot.iterdir():
            if (d / "manifest.json").is_file():
                ids.add(d.name)
    return ids


def list_voices() -> dict:
    voices = []
    pack = voice_pack_dir()
    pack_id = None
    if pack and (pack / "manifest.json").is_file():
        man = json.loads((pack / "manifest.json").read_text(encoding="utf8"))
        pack_id = man.get("id", "padrao")
        voices.append({**man, "kind": "padrao", "local": True})
    for name in VOZES_PRONTAS:
        voices.append({
            "id": name,
            "name": name,
            "label": name.replace("_", " ").title(),
            "engine": "pocket",
            "model": MODEL_ID,
            "kind": "pronta",
            "local": embedding_local(name) is not None,
        })
    # vozes clonadas do usuário
    vroot = app_home() / "voices"
    if vroot.is_dir():
        for d in sorted(vroot.iterdir()):
            man_path = d / "manifest.json"
            if man_path.is_file():
                man = json.loads(man_path.read_text(encoding="utf8"))
                voices.append({**man, "kind": "clonada", "local": True})
    prefer = (load_settings().get("voice_id") or "").strip()
    ids = {v["id"] for v in voices}
    if prefer and prefer in ids:
        selected = prefer
    elif pack_id:
        selected = pack_id
    else:
        selected = VOICE_FALLBACK
    return {
        "voices": voices,
        "selected": selected,
        "hf_logged_in": hf_logged_in(),
        "preview_phrase": FRASE_PREVIEW,
        "ai_notice": "A narração é gerada por inteligência artificial.",
        "clone_blocked": (
            "Para usar a sua voz, entre na sua conta do Hugging Face e aceite os termos "
            "do Pocket TTS. Sem isso, só a voz padrão e as vozes prontas funcionam."
        ),
        "terms_guide": [
            "Abra o Hugging Face no navegador e entre na sua conta (ou crie uma).",
            "Aceite os termos do modelo Pocket TTS (kyutai/pocket-tts).",
            "Crie um token de acesso e cole abaixo. O token fica só neste computador.",
        ],
    }


def select_voice(voice_id: str, *, baixar: bool = True) -> dict:
    """Marca a voz escolhida; baixa embedding de voz pronta se ainda não estiver local (T17)."""
    voice_id = (voice_id or "").strip()
    if not voice_id or voice_id not in _ids_voz_conhecidos():
        raise FileNotFoundError("Voz não encontrada.")
    if baixar and voice_id in VOZES_PRONTAS:
        garantir_embedding_voz(voice_id)
    cfg = load_settings()
    cfg["voice_id"] = voice_id
    save_settings(cfg)
    return list_voices()


def motor_preview():
    """Motor para ouvir a amostra. Testes: AUDIOBOOK_PREVIEW_MOTOR=tests.fake_engine:FakeEngine."""
    from studio.engines import load_engine
    nome = (os.environ.get("AUDIOBOOK_PREVIEW_MOTOR") or "pocket").strip()
    return load_engine(nome, device=os.environ.get("AUDIOBOOK_PREVIEW_DEVICE") or "cpu")


def _manifest_voz(voice_id: str) -> dict:
    pack = voice_pack_dir()
    if pack and (pack / "manifest.json").is_file():
        man = json.loads((pack / "manifest.json").read_text(encoding="utf8"))
        if man.get("id") == voice_id:
            out = dict(man)
            # caminho absoluto do arquivo exportado, se existir
            if out.get("file"):
                f = pack / out["file"]
                if f.is_file():
                    out["file"] = str(f)
            return out
    cand = app_home() / "voices" / voice_id / "manifest.json"
    if cand.is_file():
        man = json.loads(cand.read_text(encoding="utf8"))
        out = dict(man)
        if out.get("file"):
            f = cand.parent / out["file"]
            if f.is_file():
                out["file"] = str(f)
        if out.get("ref_wav") is None and (cand.parent / "ref.wav").is_file():
            out["ref_wav"] = str(cand.parent / "ref.wav")
        return out
    if voice_id in VOZES_PRONTAS:
        return {"model": MODEL_ID, "name": voice_id, "id": voice_id, "engine": "pocket"}
    raise FileNotFoundError("Voz não encontrada.")


def preview_voice(voice_id: str, *, engine=None) -> Path:
    """Gera WAV curto com o motor (falso nos testes; Pocket no @pytest.mark.model)."""
    from studio.wavio import write_wav

    voice_id = (voice_id or "").strip()
    man = _manifest_voz(voice_id)
    eng = engine or motor_preview()
    # voz pronta: baixa embedding sob demanda (exceto motor falso, que não precisa)
    if man.get("name") and getattr(eng, "id", "") != "fake":
        local = garantir_embedding_voz(man["name"])
        _hf_home_do_app()
        # passa caminho local para não depender de rede no get_state
        man = {**man, "file": str(local)}
        man.pop("name", None)
    eng.load(man)
    audio = eng.synth(FRASE_PREVIEW, 0)
    tmp = app_home() / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    out = tmp / f"preview-{slugify(voice_id)}.wav"
    write_wav(str(out), audio, eng.sample_rate)
    return out


def save_cloned_voice(audio_bytes: bytes, *, label: str, text: str, consent: bool) -> dict:
    if not consent:
        raise PermissionError("Marque a declaração de que a voz é sua ou que você tem autorização.")
    ensure_dirs()
    base = slugify(label or "minha-voz")
    vid = base
    n = 2
    while (app_home() / "voices" / vid).exists():
        vid = f"{base}-{n}"
        n += 1
    vdir = app_home() / "voices" / vid
    vdir.mkdir(parents=True)
    ref = vdir / "ref.wav"
    # se já for WAV, grava direto; senão tenta ffmpeg
    if audio_bytes[:4] == b"RIFF":
        ref.write_bytes(audio_bytes)
    else:
        raw = vdir / "_upload"
        raw.write_bytes(audio_bytes)
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw), "-ac", "1", "-ar", "16000", str(ref)],
            capture_output=True, text=True,
        )
        raw.unlink(missing_ok=True)
        if r.returncode or not ref.is_file():
            shutil.rmtree(vdir, ignore_errors=True)
            raise ValueError("Não foi possível ler o áudio. Envie um arquivo WAV ou M4A.")
    (vdir / "ref.txt").write_text((text or "").strip() + "\n", encoding="utf8")
    avisos = checar_gravacao(ref)
    usar_eq = bool(eq_por_graves(str(ref)))
    man = {
        "id": vid,
        "label": label or "Minha voz",
        "engine": "pocket",
        "model": MODEL_ID,
        "file": f"voz_{MODEL_ID}.safetensors",
        "eq": usar_eq,
        "kind": "clonada",
    }
    (vdir / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf8")
    cfg = load_settings()
    cfg["voice_id"] = vid
    save_settings(cfg)
    return {"id": vid, "label": man["label"], "eq": usar_eq, "warnings": avisos}


def attach_voice_to_project(pid: str, voice_id: str) -> None:
    """Copia o manifest da voz para voice/manifest.json do projeto (onde a geração lê)."""
    p = project_path(pid)
    if not p:
        raise FileNotFoundError(pid)
    src = None
    pack = voice_pack_dir()
    if pack and (pack / "manifest.json").is_file():
        man = json.loads((pack / "manifest.json").read_text(encoding="utf8"))
        if man.get("id") == voice_id:
            src = pack / "manifest.json"
    if src is None:
        cand = app_home() / "voices" / voice_id / "manifest.json"
        if cand.is_file():
            src = cand
    if src is None:
        # voz pronta: só grava o manifesto sem arquivo
        man = {
            "id": voice_id, "label": voice_id, "engine": "pocket",
            "model": MODEL_ID, "name": voice_id, "eq": False,
        }
        (p / "voice").mkdir(parents=True, exist_ok=True)
        (p / "voice" / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf8")
        return
    (p / "voice").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, p / "voice" / "manifest.json")
    # copia ref se existir (voz clonada / pacote)
    for name in ("ref.wav", "ref.txt"):
        f = src.parent / name
        if f.is_file():
            shutil.copy2(f, p / "voice" / name)


def version_info() -> dict:
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "github_repo": GITHUB_REPO,
        "donation_url": DONATION_URL or "",
        "android_waitlist_url": ANDROID_WAITLIST_URL or "",
    }


def releases_api_url() -> str:
    """URL da API de releases a partir de brand.GITHUB_REPO (sem barra no fim)."""
    repo = (GITHUB_REPO or "").rstrip("/")
    prefix = "https://github.com/"
    if not repo.startswith(prefix):
        raise ValueError("GITHUB_REPO inválido")
    slug = repo[len(prefix):]
    return f"https://api.github.com/repos/{slug}/releases/latest"


def _normalizar_versao(texto: str) -> tuple[int, ...]:
    """Converte 'v0.2.0-beta' em tupla comparável (0, 2, 0). Sufixos são ignorados no número."""
    s = (texto or "").strip().lstrip("vV")
    # pega só o núcleo numérico inicial
    m = re.match(r"^(\d+(?:\.\d+)*)", s)
    if not m:
        return (0,)
    return tuple(int(p) for p in m.group(1).split("."))


def versao_mais_nova(atual: str, remota: str) -> bool:
    """True se remota > atual (comparação numérica simples; R44)."""
    a, b = _normalizar_versao(atual), _normalizar_versao(remota)
    # equaliza comprimento
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return b > a


def _http_get_json(url: str) -> dict:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": APP_NAME})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf8"))


def verificar_versao_nova(*, buscar=None) -> dict:
    """Consulta a release mais nova no GitHub. Sem internet ou resposta inválida: sem erro (R44).

    `buscar(url) -> dict` é injetável nos testes (nenhum teste acessa a rede).
    """
    atual = APP_VERSION
    base = {
        "current": atual,
        "latest": None,
        "update_available": False,
        "release_url": None,
        "github_repo": GITHUB_REPO,
    }
    try:
        url = releases_api_url()
    except ValueError:
        return base
    fetch = buscar or _http_get_json
    try:
        data = fetch(url)
    except Exception:
        # offline / timeout / DNS: silencioso
        return {**base, "offline": True}
    if not isinstance(data, dict):
        return base
    tag = data.get("tag_name") or data.get("name") or ""
    if not isinstance(tag, str) or not tag.strip():
        return base
    latest = tag.strip()
    href = data.get("html_url") or f"{GITHUB_REPO.rstrip('/')}/releases/tag/{latest.lstrip('v')}"
    return {
        **base,
        "latest": latest,
        "update_available": versao_mais_nova(atual, latest),
        "release_url": href,
        "offline": False,
    }
