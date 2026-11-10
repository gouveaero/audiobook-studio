"""R49: nada pessoal nos arquivos nem nos commits de main..HEAD.

Os termos proibidos e o autor esperado vêm do arquivo apontado por LOCAL_MD,
que fica fora do git, para que o próprio teste não publique o que proíbe.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Voz, pesos, livros e áudio nunca entram no repositório.
EXTENSOES_PROIBIDAS = {
    ".safetensors", ".epub", ".mobi", ".pdf",
    ".wav", ".mp3", ".m4a", ".m4b", ".mp4", ".flac", ".ogg",
}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, check=True, capture_output=True
    ).stdout.decode("utf-8", errors="replace")


def ler_local_md() -> str:
    caminho = os.environ.get("LOCAL_MD")
    if not caminho:
        pytest.skip("LOCAL_MD não definido; o scripts/verify_beta.sh exige essa variável")
    return Path(caminho).expanduser().read_text(encoding="utf-8")


def linha_com(texto: str, marca: str) -> str:
    for linha in texto.splitlines():
        if marca in linha:
            return linha.split(marca, 1)[1]
    raise AssertionError(f"LOCAL_MD sem a linha {marca!r}")


def padroes_proibidos() -> list[re.Pattern]:
    termos = re.findall(r"`([^`]+)`", linha_com(ler_local_md(), "Termos proibidos no teste de R49:"))
    assert termos, "LOCAL_MD sem termos proibidos"
    padroes = []
    for termo in termos:
        if termo == "hf_":
            # token do Hugging Face; nomes como hf_hub_download continuam permitidos
            padroes.append(re.compile(r"hf_[A-Za-z0-9]{20,}"))
        else:
            padroes.append(re.compile(re.escape(termo), re.IGNORECASE))
    return padroes


def autor_esperado() -> str:
    autores = re.findall(r"`([^`]+<[^`]+>)`", linha_com(ler_local_md(), "Autor dos commits novos:"))
    assert autores, "LOCAL_MD sem o autor dos commits"
    return autores[0]


def base() -> str:
    for ref in ("main", "origin/main"):
        r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=RAIZ, capture_output=True)
        if r.returncode == 0:
            return ref
    raise AssertionError("sem a branch main para comparar")


def achados(texto: str, padroes: list[re.Pattern]) -> list[int]:
    """Índices dos padrões encontrados. Nunca devolve o termo, para não ir parar no log."""
    return [i for i, p in enumerate(padroes) if p.search(texto)]


def test_arquivos_versionados_sem_dados_pessoais():
    padroes = padroes_proibidos()
    problemas = []
    for nome in git("ls-files", "-z").split("\0"):
        if not nome:
            continue
        caminho = RAIZ / nome
        if not caminho.is_file():
            continue
        texto = caminho.read_bytes().decode("utf-8", errors="replace")
        for i in achados(texto, padroes) + achados(nome, padroes):
            problemas.append(f"{nome}: termo proibido nº {i + 1} do LOCAL_MD")
    assert not problemas, "\n".join(problemas)


def test_arquivos_versionados_sem_voz_nem_livro():
    ruins = [n for n in git("ls-files", "-z").split("\0") if Path(n).suffix.lower() in EXTENSOES_PROIBIDAS]
    assert not ruins, f"arquivos que não podem ser versionados: {ruins}"


def test_commits_novos_sem_voz_nem_livro():
    nomes = git("log", "--format=", "--name-only", "-z", f"{base()}..HEAD").split("\0")
    ruins = sorted({n.strip() for n in nomes if Path(n.strip()).suffix.lower() in EXTENSOES_PROIBIDAS})
    assert not ruins, f"commits novos tocam em arquivos que não podem ser versionados: {ruins}"


def test_commits_novos_sem_dados_pessoais():
    padroes = padroes_proibidos()
    problemas = []
    for sha in git("rev-list", f"{base()}..HEAD").split():
        conteudo = git("show", "--format=%an <%ae>%n%cn <%ce>%n%B", "-p", sha)
        for i in achados(conteudo, padroes):
            problemas.append(f"{sha[:8]}: termo proibido nº {i + 1} do LOCAL_MD")
    assert not problemas, "\n".join(problemas)


def test_autor_dos_commits_novos():
    esperado = autor_esperado()
    problemas = []
    for linha in git("log", "--format=%h|%an <%ae>|%cn <%ce>", f"{base()}..HEAD").splitlines():
        sha, autor, committer = linha.split("|")
        if autor != esperado or committer != esperado:
            problemas.append(f"{sha}: autor ou committer diferente do LOCAL_MD")
    assert not problemas, "\n".join(problemas)


def _rotulo_voz_permitido() -> str | None:
    """Rótulo do pacote de voz (permitido dentro do .app)."""
    try:
        texto = ler_local_md()
    except Exception:
        return None
    m = re.search(r'rótulo\s+no\s+app:\s*"([^"]+)"', texto, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"rótulo\s+no\s+app:\s*'([^']+)'", texto, re.I)
    return m.group(1).strip() if m else None


def _app_path() -> Path:
    env = os.environ.get("APP_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return RAIZ / "dist" / "Audiobook Studio.app"


@pytest.mark.package
def test_pacote_app_sem_dados_pessoais():
    """R49 no conteúdo do .app: nenhum termo proibido, exceto o rótulo do pacote de voz."""
    app = _app_path()
    assert app.is_dir(), (
        f"Camada package: app ausente em {app}. "
        "Rode scripts/build_mac.sh e defina APP_PATH se necessário."
    )
    padroes = padroes_proibidos()
    rotulo = _rotulo_voz_permitido()
    problemas = []
    # Só textos/recursos do app (não varre Mach-O/.so: o freeze pode embutir caminhos de build).
    exts = {".plist", ".json", ".txt", ".md", ".js", ".html", ".css", ".xml", ".strings", ".csv"}
    for path in app.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(app)).replace("\\", "/")
        if path.suffix.lower() not in exts and path.name != "Info.plist":
            continue
        try:
            texto = path.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue
        if rotulo and ("voice-pack" in rel or path.name == "manifest.json"):
            texto = texto.replace(rotulo, "")
        for i in achados(texto, padroes) + achados(rel, padroes):
            problemas.append(f"{rel}: termo proibido nº {i + 1} do LOCAL_MD")
    assert not problemas, "\n".join(problemas[:40])
