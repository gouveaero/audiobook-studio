"""EPUB -> book.json: capítulos limpos, prontos para o TTS.

Lê o sumário do próprio EPUB (nav.xhtml ou toc.ncx) e a ordem de leitura (spine). Cada entrada do sumário vira um
capítulo, inclusive as que apontam para uma âncora dentro de um arquivo; arquivos fora do sumário entram no capítulo
anterior. Sem sumário, o livro é dividido pelos títulos do texto. Notas de rodapé e sobrescritos são removidos.
Capítulos como bibliografia, índice e créditos saem por padrão (--skip-title), e capítulos sem texto também.
EPUB com DRM, inválido ou fora do português para com BookError, sem gravar nada. Sem capa, gera uma capa simples.

book.json:
  {"title","author","language","chapters":[{"id","title","include","chunks":[...],"pauses":[...],"head":[...]}]}
  head lista os índices dos trechos de título.
"""
import argparse, html, importlib, json, os, posixpath, re, subprocess, sys, zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container", "o": "http://www.idpf.org/2007/opf",
      "dc": "http://purl.org/dc/elements/1.1/", "n": "http://www.daisy.org/z3986/2005/ncx/",
      "x": "http://www.w3.org/1999/xhtml", "e": "http://www.idpf.org/2007/ops",
      "enc": "http://www.w3.org/2001/04/xmlenc#"}
SKIP_TITLE = (r"^(capa|rosto|folha de rosto|sum[aá]rio|[ií]ndice|notas?(?: finais| e refer[eê]ncias)?$|bibliografia|cr[eé]ditos|copyright|sobre o autor|"
              r"agradecimentos|mapas?|[aá]rvores? geneal|caderno|cover|title page|contents|table of contents|index|notes|"
              r"bibliography|credits|acknowledg|about the author|also by|dedication|dedicat[oó]ria)")
SKIP_CLASS = re.compile(r"rodape|footnote|endnote|nota")
SKIP_TYPE = re.compile(r"footnote|endnote|rearnote|noteref|pagebreak|doc-footnote|doc-endnote|doc-noteref|doc-pagebreak")
MAXC = 900
FONT_OBFUSCATION = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}
LANG_NAMES = {"en": "inglês", "es": "espanhol", "fr": "francês", "it": "italiano", "de": "alemão"}
STOPWORDS = {
    "pt": set("não uma com do da dos das os ao aos em é ele ela eles elas seu sua seus suas também você isso isto pelo pela "
              "mas são está foi muito então quando onde já depois ainda havia nem".split()),
    "en": set("the and of to is was he she it that with his her they not for but you have had this from were "
              "which would there their what when".split()),
    "es": set("el los las del y pero muy es lo su sus le les una con por para está fue también cuando donde ya "
              "después todavía había ni".split()),
    "fr": set("le les des et est il elle ils pas une avec pour mais vous dans qui sur au aux était ont".split()),
    "it": set("il gli della delle e è non una con per ma sono anche quando dove già dopo ancora".split()),
    "de": set("der die das und ist nicht ein eine mit für aber sie er es den dem wir auch wenn".split()),
}
BLOCK = {"p", "div", "li", "blockquote", "dd", "dt", "td", "th", "tr", "figcaption", "pre", "section", "article", "aside",
         "header", "footer", "main", "body", "table", "ul", "ol", "dl", "figure", "nav",
         "h1", "h2", "h3", "h4", "h5", "h6"}
VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "source", "col", "area", "base", "embed", "param", "track"}
SKIP_TAGS = {"head", "script", "style", "sup", "svg", "math", "rt", "rp"}
NUM_WORDS = {w: i for i, w in enumerate(
    "zero um dois três quatro cinco seis sete oito nove dez onze doze treze catorze quinze dezesseis dezessete dezoito "
    "dezenove vinte".split())}
ORDINAL_PART = {w: i for i, w in enumerate(
    "primeira segunda terceira quarta quinta sexta sétima oitava nona décima".split(), 1)}
ROMAN = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
SEP = r"\s*[.:\-–—]\s*"


class BookError(Exception):
    """Erro que a pessoa precisa ver. code: drm, idioma, invalido ou vazio."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


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


# EPUB ---------------------------------------------------------------------------------------------------------------

def open_epub(path):
    try:
        z = zipfile.ZipFile(path)
        z.read("META-INF/container.xml")
        return z
    except (zipfile.BadZipFile, KeyError, OSError):
        raise BookError("invalido", "Este arquivo não parece ser um EPUB válido. Confira se escolheu o arquivo certo.")


def check_drm(z):
    if "META-INF/encryption.xml" not in z.namelist():
        return
    try:
        root = ET.fromstring(z.read("META-INF/encryption.xml"))
    except ET.ParseError:
        return
    for ed in root.iter("{%s}EncryptedData" % NS["enc"]):
        m = ed.find("enc:EncryptionMethod", NS)
        if m is None or m.get("Algorithm") not in FONT_OBFUSCATION:
            raise BookError("drm", "Este EPUB tem proteção contra cópia (DRM) e não pode ser lido. "
                                   "Use um arquivo sem DRM, como os comprados em lojas que entregam o EPUB aberto.")


def read_epub(path):
    z = open_epub(path)
    try:
        opf_path = ET.fromstring(z.read("META-INF/container.xml")).find(".//c:rootfile", NS).get("full-path")
        base = posixpath.dirname(opf_path)
        opf = ET.fromstring(z.read(opf_path))
    except (ET.ParseError, AttributeError, KeyError):
        raise BookError("invalido", "Este EPUB está danificado e não pode ser lido.")
    man = {i.get("id"): i for i in opf.findall(".//o:manifest/o:item", NS)}
    names = set(z.namelist())
    spine = [posixpath.normpath(posixpath.join(base, man[r.get("idref")].get("href")))
             for r in opf.findall(".//o:spine/o:itemref", NS) if r.get("idref") in man]
    spine = [f for f in spine if f in names]
    meta = {"title": (opf.findtext(".//dc:title", "", NS) or "").strip(),
            "author": (opf.findtext(".//dc:creator", "", NS) or "").strip(),
            "language": (opf.findtext(".//dc:language", "", NS) or "").split("-")[0].strip().lower()}
    # sumário: ncx (EPUB 2) ou nav (EPUB 3); cada entrada é (título, arquivo, âncora, profundidade)
    toc = []
    nav = next((i for i in man.values() if "nav" in (i.get("properties") or "").split()), None)
    ncx = next((i for i in man.values() if i.get("media-type") == "application/x-dtbncx+xml"), None)
    if ncx is not None:
        npath = posixpath.normpath(posixpath.join(base, ncx.get("href"))); tb = posixpath.dirname(npath)
        try:
            root = ET.fromstring(z.read(npath))
        except (ET.ParseError, KeyError):
            root = None

        def walk(el, depth):
            for p in el.findall("n:navPoint", NS):
                lab = p.find("n:navLabel/n:text", NS); src = p.find("n:content", NS)
                if lab is not None and src is not None and src.get("src"):
                    f, _, frag = src.get("src").partition("#")
                    toc.append((clean(lab.text or ""), posixpath.normpath(posixpath.join(tb, f)), frag, depth))
                walk(p, depth + 1)
        if root is not None and root.find("n:navMap", NS) is not None:
            walk(root.find("n:navMap", NS), 0)
    if not toc and nav is not None:
        npath = posixpath.normpath(posixpath.join(base, nav.get("href"))); tb = posixpath.dirname(npath)
        try:
            p = NavParser(); p.feed(z.read(npath).decode("utf8", "ignore"))
            for title, href, depth in p.entries:
                f, _, frag = href.partition("#")
                toc.append((clean(title), posixpath.normpath(posixpath.join(tb, f)), frag, depth))
        except KeyError:
            pass
    return z, meta, spine, toc


class NavParser(HTMLParser):
    """Links do <nav epub:type="toc"> (ou do primeiro <nav>, se nenhum tiver o tipo), com a profundidade das listas."""

    def __init__(self):
        super().__init__()
        self.entries, self.navs, self.cur, self.depth, self.a = [], [], None, 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav":
            self.cur = []; self.navs.append((a.get("epub:type") or "", self.cur)); self.depth = 0
        elif self.cur is not None and tag == "ol":
            self.depth += 1
        elif self.cur is not None and tag == "a" and a.get("href"):
            self.a = [a["href"], ""]

    def handle_endtag(self, tag):
        if tag == "nav":
            self.cur = None
            toc = [n for t, n in self.navs if "toc" in t.split()]
            self.entries = toc[0] if toc else self.navs[0][1]
        elif self.cur is not None and tag == "ol":
            self.depth -= 1
        elif self.a is not None and tag == "a":
            self.cur.append((self.a[1], self.a[0], max(self.depth - 1, 0))); self.a = None

    def handle_data(self, d):
        if self.a is not None:
            self.a[1] += d


def clean(t):
    t = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", t.replace("\xa0", " "))
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


class Blocks(HTMLParser):
    """Texto de um arquivo do livro em blocos ("p" ou "h1".."h6"), sem notas, e o índice do bloco de cada id."""

    def __init__(self):
        super().__init__()
        self.blocks, self.anchors, self.buf, self.stack, self.skip = [], {}, [], [], 0

    def flush(self):
        t = clean("".join(self.buf)); self.buf = []
        if t:
            kind = next((tag for tag, _ in reversed(self.stack) if re.fullmatch(r"h[1-6]", tag)), "p")
            self.blocks.append((kind, t))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in VOID:
            if tag == "br" and not self.skip:
                self.buf.append(" ")
            return
        skip = (tag in SKIP_TAGS or bool(SKIP_CLASS.search(a.get("class") or ""))
                or bool(SKIP_TYPE.search((a.get("epub:type") or "") + " " + (a.get("role") or ""))))
        if tag in BLOCK:
            self.flush()
        self.stack.append((tag, skip))
        self.skip += skip
        if a.get("id") and not self.skip:
            self.anchors.setdefault(a["id"], len(self.blocks))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID or tag not in (t for t, _ in self.stack):
            return
        if tag in BLOCK:
            self.flush()
        while self.stack:
            t, skip = self.stack.pop()
            self.skip -= skip
            if t == tag:
                break

    def handle_data(self, d):
        if not self.skip:
            self.buf.append(d)

    def close(self):
        super().close(); self.flush()


def file_blocks(z, path):
    p = Blocks()
    p.feed(z.read(path).decode("utf8", "ignore")); p.close()
    return p.blocks, p.anchors


def extract_cover(z, path_out):
    """Procura a capa no OPF (properties=cover-image, <meta name=cover>, ou nome com 'cover'/'capa') e salva em path_out."""
    opf_path = ET.fromstring(z.read("META-INF/container.xml")).find(".//c:rootfile", NS).get("full-path")
    base = posixpath.dirname(opf_path)
    opf = ET.fromstring(z.read(opf_path))
    items = opf.findall(".//o:manifest/o:item", NS)
    cid = next((m.get("content") for m in opf.findall(".//o:metadata/o:meta", NS) if m.get("name") == "cover"), None)
    for test in (lambda i: "cover-image" in (i.get("properties") or ""),
                 lambda i: i.get("id") == cid and i.get("media-type", "").startswith("image/"),
                 lambda i: i.get("media-type", "").startswith("image/") and re.search(r"cover|capa", i.get("href", ""), re.I)):
        pick = next((i for i in items if test(i)), None)
        if pick is not None:
            try:
                data = z.read(posixpath.normpath(posixpath.join(base, pick.get("href"))))
            except KeyError:
                continue
            open(path_out, "wb").write(data)
            return True
    return False


def generate_cover(path_out):
    """Capa simples para livro sem capa: quadrado escuro com moldura clara (o ffmpeg do app não desenha texto)."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x23304a:s=1400x1400",
                    "-vf", "drawbox=x=90:y=90:w=1220:h=1220:color=0xe8dcc4:t=10,"
                           "drawbox=x=130:y=1050:w=1140:h=6:color=0xe8dcc4:t=fill",
                    "-frames:v", "1", "-q:v", "3", path_out], check=True)


# Títulos ------------------------------------------------------------------------------------------------------------

def _number(s):
    if re.fullmatch(r"\d{1,3}", s):
        return int(s)
    if ROMAN.match(s) and s:
        v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        return sum(-v[c] if i + 1 < len(s) and v[c] < v[s[i + 1]] else v[c] for i, c in enumerate(s))
    return NUM_WORDS.get(s.lower())


def part_match(title):
    """"Parte I", "Livro 2: Subtítulo", "Primeira parte" -> (rótulo, número, subtítulo)."""
    m = re.match(rf"^(parte|livro)\s+([IVXLCDM]+|\d{{1,3}}|[a-zà-ú]+)\b(?:(?:{SEP}|\s+)(.*))?$", title, re.I)
    num = m and (m.group(2).upper() if ROMAN.match(m.group(2).upper()) else m.group(2))
    if m and _number(num):
        return f"{m.group(1).capitalize()} {num}", _number(num), (m.group(3) or "").strip()
    m = re.match(rf"^({'|'.join(ORDINAL_PART)})\s+parte\b(?:(?:{SEP}|\s+)(.*))?$", title, re.I)
    if m:
        return f"{m.group(1).capitalize()} parte", ORDINAL_PART[m.group(1).lower()], (m.group(2) or "").strip()
    return None


def number_match(title):
    """"1.", "IV", "Capítulo 3", "Capítulo três: A volta", "2. O rio" -> (número, subtítulo, tinha "capítulo")."""
    m = re.match(rf"^(cap[ií]tulo\s+|cap\.\s*)?(\d{{1,3}}|[IVXLCDM]+|[a-zà-ú]+)(?:{SEP}(.*))?$", title, re.I)
    if not m:
        return None
    word, num, sub = m.group(1), m.group(2), (m.group(3) or "").strip()
    if not word and not re.fullmatch(r"\d{1,3}|[IVXLCDM]+", num):
        return None
    n = _number(num if re.fullmatch(r"\d+|[IVXLCDM]+", num) else num.lower())
    return (n, sub, bool(word)) if n else None


def tame(s):
    """Título todo em maiúsculas vira só com a inicial maiúscula ("PARTE II: A ORIGEM" -> "Parte II: a origem")."""
    if sum(c.isalpha() for c in s) < 4 or s != s.upper():
        return s
    words = [w if w.strip(".,:;") and ROMAN.match(w.strip(".,:;")) else w.lower() for w in s.split(" ")]
    return " ".join(words)[:1].upper() + " ".join(words)[1:]


def roman_parts(entries):
    """Livro que numera capítulos em arábico usa os números romanos para as partes ("I. Origem" > "1. A casa")."""
    nums = [(e, number_match(e["title"])) for e in entries]
    roman = [e for e, m in nums if m and not m[2] and re.match(r"^[IVXLCDM]+\b", e["title"])]
    arabic = [e for e, m in nums if m and re.match(r"^\d", e["title"])]
    return bool(roman) and len(arabic) >= len(roman) and max(e["depth"] for e in roman) <= min(e["depth"] for e in arabic)


def chapter_titles(entries):
    """Título mostrado e título falado (antes de normalizar) de cada entrada, com o contexto de parte."""
    out, part = [], None   # part: (rótulo, profundidade)
    romans_are_parts = roman_parts(entries)
    for e in entries:
        t = e["title"]
        pipe = re.match(r"^(\d{1,3}|[IVXLCDM]+)\s*\|\s*(.+)$", t)
        if pipe:
            t = pipe.group(2).strip()
        pm, nm = part_match(t), (None if pipe else number_match(t))
        if nm and romans_are_parts and re.match(r"^[IVXLCDM]+\b", t) and not nm[2]:
            pm, nm = (f"Parte {re.match(r'^[IVXLCDM]+', t).group(0)}", nm[0], nm[1]), None
            t = pm[0] + (f": {tame(pm[2])}" if pm[2] else "")
        if pm:
            pm = (pm[0], pm[1], tame(pm[2]))
            part = (pm[0], e["depth"])
            lead = pm[0] if pm[0].endswith(" parte") else f"{pm[0].split()[0]} {pm[1]}"
            out.append((tame(t), lead, pm[2]))
            continue
        if part and (e["depth"] < part[1] or (e["depth"] == part[1] and not nm)):
            part = None
        if nm:
            n, sub = nm[0], tame(nm[1])
            if part:
                title = f"{part[0]}, capítulo {n}" + (f": {sub}" if sub else "")
            else:
                title = tame(t) if sub else f"Capítulo {n}"
            out.append((title, f"Capítulo {n}", sub))
        else:
            out.append((tame(t), tame(t).replace("|", ","), ""))
    return out


def spoken(lead, sub, norm, nw):
    lead = re.sub(r"^(Parte|Livro|Capítulo) (\d+)$", lambda m: f"{m.group(1)} {nw(int(m.group(2)))}", lead)
    s = lead + (f". {sub}" if sub else "")
    s = re.sub(r"\s*\(([^)]*)\)", r", \1", s)
    s = norm(s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"[\s,;:.\-–—]+$", "", s)
    return s if s.endswith(("?", "!", "…")) else s + "."


def _alnum(s):
    return re.sub(r"[\W_]+", "", s.lower())


def same_title(heading, title):
    a, b = _alnum(heading), _alnum(title)
    if not a or not b:
        return False
    if min(len(a), len(b)) <= 2:
        return a == b or re.sub(r"^(capitulo|capítulo|parte|livro)", "", a) == b
    return a in b or b in a


# Idioma -------------------------------------------------------------------------------------------------------------

def detect_language(text):
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    if len(words) < 150:
        return None
    score = {k: sum(w in sw for w in words) / len(words) for k, sw in STOPWORDS.items()}
    best = max(score, key=score.get)
    return best if score[best] >= 0.08 else None


def check_language(meta_lang, text):
    found = detect_language(text)
    if found == "pt" or (found is None and meta_lang in ("pt", "")):
        return "pt"
    lang = found or meta_lang
    name = LANG_NAMES.get(lang)
    raise BookError("idioma", (f"Este livro parece estar em {name}. " if name else "Este livro não parece estar em português. ")
                    + "Por enquanto, só livros em português podem virar audiolivro.")


# Montagem do livro --------------------------------------------------------------------------------------------------

def heading_entries(docs):
    """Sem sumário: um capítulo por título que abre arquivo, e pelos títulos do nível principal."""
    hs = [(si, bi, int(k[1])) for si, (blocks, _) in enumerate(docs) for bi, (k, _) in enumerate(blocks) if k in ("h1", "h2", "h3")]
    levels = sorted({lv for *_, lv in hs})
    top = next((lv for lv in levels if sum(1 for *_, x in hs if x == lv) >= 2), levels[0] if levels else None)
    split = {top}
    if top and any(part_match(docs[si][0][bi][1]) for si, bi, lv in hs if lv == top):
        split.add(top + 1)
    out = [{"title": docs[si][0][bi][1], "pos": (si, bi), "depth": lv - 1} for si, bi, lv in hs if lv in split or bi == 0]
    first = out[0]["pos"] if out else (len(docs), 0)
    if first[1] > 0 or any(docs[si][0] for si in range(first[0])):
        out.insert(0, {"title": "Início", "pos": (0, 0), "depth": 0})   # texto antes do primeiro título
    return out


def build(epub, out, lang=None, skip_title=SKIP_TITLE, skip_files=(), min_body=500):
    z, meta, spine, toc = read_epub(epub)
    check_drm(z)
    docs = [file_blocks(z, f) for f in spine]
    index = {}
    for i, f in enumerate(spine):
        index.setdefault(f, i)

    entries, seen = [], set()
    for title, f, frag, depth in toc:
        if f not in index:
            continue
        si = index[f]
        pos = (si, docs[si][1].get(frag, 0) if frag else 0)
        if (pos, title) in seen:
            continue
        seen.add((pos, title))
        entries.append({"title": title, "pos": pos, "depth": depth})
    if not entries:
        entries = heading_entries(docs)

    # conteúdo de cada entrada: do seu ponto até o próximo ponto do livro
    points = sorted({e["pos"] for e in entries})
    for e in entries:
        nxt = next((p for p in points if p > e["pos"]), (len(docs), 0))
        blocks = []
        for si in range(e["pos"][0], min(nxt[0], len(docs) - 1) + 1):
            if any(s in spine[si] for s in skip_files):
                continue
            b = docs[si][0]
            lo = e["pos"][1] if si == e["pos"][0] else 0
            hi = nxt[1] if si == nxt[0] else len(b)
            blocks += b[lo:hi]
        e["blocks"] = blocks
    # entradas no mesmo ponto (uma parte e o primeiro capítulo no mesmo arquivo): cada uma leva o seu título
    by_pos = {}
    for e in entries:
        by_pos.setdefault(e["pos"], []).append(e)
    for group in by_pos.values():
        owner = group[-1]
        for e in group[:-1]:
            e["blocks"] = []
            k = next((i for i, (kind, t) in enumerate(owner["blocks"][:4]) if kind[0] == "h" and same_title(t, e["title"])), None)
            if k is not None:
                e["blocks"] = [owner["blocks"].pop(k)]

    titles = chapter_titles(entries)
    lang_forced = lang
    lang = lang or meta["language"] or "pt"
    chapters, n = [], 0
    for e, (title, lead, sub) in zip(entries, titles):
        if re.search(skip_title, e["title"], re.I):
            continue
        n += 1
        if not any(ch.isalnum() for _, t in e["blocks"] for ch in t):
            continue   # capítulo sem texto (só imagem): sai do livro
        blocks = list(e["blocks"])
        while blocks and blocks[0][0][0] == "h" and (same_title(blocks[0][1], e["title"]) or same_title(blocks[0][1], title)):
            blocks.pop(0)
        paras = [t if k == "p" or re.search(r"[.!?…:;]$", t) else t + "." for k, t in blocks
                 if any(ch.isalnum() for ch in t)]   # separadores como "* * *" não são lidos
        chapters.append({"id": f"{n:02d}", "title": title, "lead": lead, "sub": sub, "paras": paras})

    if not chapters:
        raise BookError("vazio", "Não foi encontrado texto neste EPUB.")
    if not lang_forced:
        lang = check_language(meta["language"], " ".join(p for c in chapters for p in c["paras"])[:200000])
    norm = load_normalizer(lang)
    nw = getattr(sys.modules.get(f"studio.normalize_{lang}") or sys.modules.get(f"normalize_{lang}"), "number_to_words", str)
    book = []
    for c in chapters:
        items = [(spoken(c["lead"], c["sub"], norm, nw), True)] + [(norm(p), False) for p in c["paras"]]
        cks, pauses = [], []
        for text, is_head in items:
            cs = [text] if is_head else chunks(text)
            cks += cs
            pauses += [0.25] * (len(cs) - 1) + [1.0 if is_head else 0.7]
        book.append({"id": c["id"], "title": c["title"], "include": True, "chunks": cks, "pauses": pauses, "head": [0]})

    meta = {**meta, "language": lang}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cover = os.path.join(os.path.dirname(out) or ".", "cover.jpg")
    if not extract_cover(z, cover):
        generate_cover(cover)
    json.dump({**meta, "chapters": book}, open(out, "w"), ensure_ascii=False, indent=1)
    chars = sum(len(t) for b in book for t in b["chunks"])
    print(f"{len(book)} capítulos, {sum(len(b['chunks']) for b in book)} trechos, {chars} caracteres, ~{chars / 13 / 3600:.1f} h de áudio")
    return book


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("epub"); ap.add_argument("out")
    ap.add_argument("--lang"); ap.add_argument("--skip-title", default=SKIP_TITLE)
    a = ap.parse_args()
    try:
        build(a.epub, a.out, a.lang, a.skip_title)
    except BookError as e:
        sys.exit(str(e))
