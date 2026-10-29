"""EPUB -> book.json: capítulos limpos, prontos para o TTS.

Lê o sumário do próprio EPUB (nav.xhtml ou toc.ncx) e a ordem de leitura (spine). Cada entrada do sumário vira um
capítulo; arquivos fora do sumário entram no capítulo anterior. Notas de rodapé e sobrescritos são removidos.
Capítulos como bibliografia, índice e créditos saem por padrão (--skip-title).

book.json:
  {"title","author","language","chapters":[{"id","title","spoken_title","chunks":[...],"pauses":[...]}]}
"""
import argparse, html, importlib, json, posixpath, re, sys, zipfile
import xml.etree.ElementTree as ET

NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container", "o": "http://www.idpf.org/2007/opf",
      "dc": "http://purl.org/dc/elements/1.1/", "n": "http://www.daisy.org/z3986/2005/ncx/",
      "x": "http://www.w3.org/1999/xhtml", "e": "http://www.idpf.org/2007/ops"}
SKIP_TITLE = (r"^(capa|rosto|folha de rosto|sum[aá]rio|[ií]ndice|notas?|bibliografia|cr[eé]ditos|copyright|sobre o autor|"
              r"agradecimentos|mapas?|[aá]rvores? geneal|caderno|cover|title page|contents|table of contents|index|notes|"
              r"bibliography|credits|acknowledg|about the author|also by|dedication|dedicat[oó]ria)")
SKIP_CLASS = re.compile(r"rodape|footnote|endnote|nota")
MAXC = 900


def load_normalizer(lang):
    try:
        return importlib.import_module(f"studio.normalize_{lang}").normalize
    except ModuleNotFoundError:
        try:
            return importlib.import_module(f"normalize_{lang}").normalize
        except ModuleNotFoundError:
            return lambda t: re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def chunks(par, maxc=MAXC):
    sents = re.split(r"(?<=[.!?…])\s+(?=[“\"A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", par)
    merged = []
    for s in sents:  # não corta depois de inicial isolada ("S. Y. Agnon")
        if merged and re.search(r"(?:^|\s)[A-Z]\.$", merged[-1]):
            merged[-1] += " " + s
        else:
            merged.append(s)
    out, cur = [], ""
    for s in merged:
        if cur and len(cur) + len(s) + 1 > maxc:
            out.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    return out + ([cur] if cur else [])


def read_epub(path):
    z = zipfile.ZipFile(path)
    opf_path = ET.fromstring(z.read("META-INF/container.xml")).find(".//c:rootfile", NS).get("full-path")
    base = posixpath.dirname(opf_path)
    opf = ET.fromstring(z.read(opf_path))
    man = {i.get("id"): i for i in opf.findall(".//o:manifest/o:item", NS)}
    spine = [posixpath.normpath(posixpath.join(base, man[r.get("idref")].get("href")))
             for r in opf.findall(".//o:spine/o:itemref", NS) if r.get("idref") in man]
    meta = {"title": (opf.findtext(".//dc:title", "", NS) or "").strip(),
            "author": (opf.findtext(".//dc:creator", "", NS) or "").strip(),
            "language": (opf.findtext(".//dc:language", "pt", NS) or "pt").split("-")[0].lower()}
    # sumário: nav (EPUB 3) ou ncx (EPUB 2)
    toc = []
    nav = next((i for i in man.values() if "nav" in (i.get("properties") or "")), None)
    ncx = next((i for i in man.values() if i.get("media-type") == "application/x-dtbncx+xml"), None)
    if ncx is not None:
        tb = posixpath.dirname(posixpath.normpath(posixpath.join(base, ncx.get("href"))))
        root = ET.fromstring(z.read(posixpath.normpath(posixpath.join(base, ncx.get("href")))))
        for p in root.iter("{%s}navPoint" % NS["n"]):
            lab = p.find("n:navLabel/n:text", NS); src = p.find("n:content", NS)
            if lab is not None and src is not None:
                toc.append((html.unescape(lab.text or "").strip(), posixpath.normpath(posixpath.join(tb, src.get("src").split("#")[0]))))
    elif nav is not None:
        npath = posixpath.normpath(posixpath.join(base, nav.get("href"))); tb = posixpath.dirname(npath)
        for a in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', z.read(npath).decode("utf8", "ignore"), re.S):
            toc.append((html.unescape(re.sub(r"<[^>]+>", "", a[1])).strip(), posixpath.normpath(posixpath.join(tb, a[0].split("#")[0]))))
    return z, meta, spine, toc


def extract_cover(z, path_out):
    """Procura a capa no OPF (properties=cover-image, <meta name=cover>, ou nome com 'cover'/'capa') e salva em path_out."""
    base = posixpath.dirname(ET.fromstring(z.read("META-INF/container.xml")).find(".//c:rootfile", NS).get("full-path"))
    opf = ET.fromstring(z.read(ET.fromstring(z.read("META-INF/container.xml")).find(".//c:rootfile", NS).get("full-path")))
    items = opf.findall(".//o:manifest/o:item", NS)
    cid = next((m.get("content") for m in opf.findall(".//o:metadata/o:meta", NS) if m.get("name") == "cover"), None)
    pick = next((i for i in items if "cover-image" in (i.get("properties") or "")), None) \
        or next((i for i in items if i.get("id") == cid), None) \
        or next((i for i in items if i.get("media-type", "").startswith("image/") and re.search(r"cover|capa", i.get("href", ""), re.I)), None)
    if pick is None:
        return False
    open(path_out, "wb").write(z.read(posixpath.normpath(posixpath.join(base, pick.get("href")))))
    return True


def file_text(z, path):
    t = z.read(path).decode("utf8", "ignore")
    body = t[t.find("<body"):]
    head = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", body, re.S)
    head = html.unescape(re.sub(r"<[^>]+>", "", head.group(1))).strip() if head else None
    paras = []
    for cls, inner in re.findall(r'<p(?:\s+class="([^"]*)")?[^>]*>(.*?)</p>', body, re.S):
        if cls and SKIP_CLASS.search(cls):
            continue
        inner = re.sub(r"<sup.*?</sup>", "", inner, flags=re.S)
        x = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", inner)).replace("\xa0", " ")).strip()
        if x:
            paras.append(x)
    return head, paras


def spoken_title(title, number_words):
    m = re.match(r"^(\d+)\.\s+(.*)$", title)
    t = f"Capítulo {number_words(int(m.group(1)))}. {m.group(2)}" if m else title
    return re.sub(r"\((\d[^)]*)\)", r", \1", t)


def build(epub, out, lang=None, skip_title=SKIP_TITLE, skip_files=(), min_body=500):
    z, meta, spine, toc = read_epub(epub)
    lang = lang or meta["language"]
    norm = load_normalizer(lang)
    nw = getattr(sys.modules.get(f"studio.normalize_{lang}") or sys.modules.get(f"normalize_{lang}"), "number_to_words", str)
    toc_by_file = {}
    for title, f in toc:
        toc_by_file.setdefault(f, title)
    chapters, cur = [], None
    for f in spine:
        if f in toc_by_file:
            cur = {"title": toc_by_file[f], "paras": [], "skip": bool(re.search(skip_title, toc_by_file[f], re.I))}
            chapters.append(cur)
        if cur is None or cur["skip"] or any(s in f for s in skip_files):
            continue
        _, paras = file_text(z, f)
        cur["paras"] += paras
    book = []
    for c in chapters:
        if c["skip"]:
            continue
        items = [(norm(spoken_title(c["title"], nw)).rstrip(",") + ".", True)] + [(norm(p), False) for p in c["paras"]]
        cks, pauses = [], []
        for text, is_head in items:
            cs = [text] if is_head else chunks(text)
            cks += cs
            pauses += [0.25] * (len(cs) - 1) + [1.0 if is_head else 0.7]
        book.append({"id": f"{len(book) + 1:02d}", "title": c["title"], "chunks": cks, "pauses": pauses})
    json.dump({**meta, "language": lang, "chapters": book}, open(out, "w"), ensure_ascii=False, indent=1)
    extract_cover(z, posixpath.join(posixpath.dirname(out) or ".", "cover.jpg"))
    chars = sum(len(t) for b in book for t in b["chunks"])
    print(f"{len(book)} capítulos, {sum(len(b['chunks']) for b in book)} trechos, {chars} caracteres, ~{chars / 13 / 3600:.1f} h de áudio")
    return book


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("epub"); ap.add_argument("out")
    ap.add_argument("--lang"); ap.add_argument("--skip-title", default=SKIP_TITLE)
    a = ap.parse_args()
    build(a.epub, a.out, a.lang, a.skip_title)
