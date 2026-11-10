"""EPUBs sintéticos para os testes do livro. Todo o texto é inventado aqui, nunca copiado de livro real.

Uso:
    make_epub(caminho, [("c1.xhtml", "<h1>1.</h1>" + paras(3))], toc=[("1.", "c1.xhtml")])

`spine` é a ordem de leitura: lista de (arquivo, corpo HTML). `toc` é o sumário: lista de (rótulo, href) ou
(rótulo, href, filhos), com href podendo ter âncora ("c1.xhtml#s2"). `toc_format` escolhe "ncx" (EPUB 2), "nav"
(EPUB 3) ou None (sem sumário).
"""
import zipfile
from xml.sax.saxutils import escape

FRASES_PT = [
    "O vento frio descia pela rua estreita e ninguém sabia dizer de onde vinha aquele cheiro de pão.",
    "Ela abriu a janela, olhou para o relógio da praça e pensou que ainda havia tempo para tudo.",
    "Os vizinhos não falavam com ele desde o inverno, mas também não pareciam ter raiva de nada.",
    "Na manhã seguinte, a carta estava sobre a mesa, com o selo azul e uma letra que ela conhecia bem.",
    "Ele guardou o caderno na gaveta, porque não queria que o irmão lesse aquelas páginas antes da hora.",
    "Era uma cidade pequena, com uma igreja, duas padarias e um rio que mudava de cor em cada estação.",
]
FRASES_EN = [
    "The cold wind came down the narrow street and nobody could say where that smell of bread was from.",
    "She opened the window, looked at the clock in the square and thought that there was still time.",
    "The neighbors had not spoken to him since the winter, but they did not seem angry about anything.",
    "The next morning, the letter was on the table, with the blue stamp and handwriting she knew well.",
]


def paras(n, frases=FRASES_PT, start=0):
    return "".join(f"<p>{frases[(start + i) % len(frases)]} {frases[(start + i + 1) % len(frases)]}</p>" for i in range(n))


def _xhtml(body):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>x</title></head>'
            f"<body>{body}</body></html>")


def _ncx(toc):
    n = [0]

    def points(items):
        out = ""
        for it in items:
            label, href, kids = (it + ([],))[:3] if len(it) == 2 else it
            n[0] += 1
            out += (f'<navPoint id="np{n[0]}" playOrder="{n[0]}"><navLabel><text>{escape(label)}</text></navLabel>'
                    f'<content src="Text/{href}"/>{points(kids)}</navPoint>')
        return out
    return ('<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            f"<head/><docTitle><text>x</text></docTitle><navMap>{points(toc)}</navMap></ncx>")


def _nav(toc, landmarks):
    def ol(items):
        out = "<ol>"
        for it in items:
            label, href, kids = (it + ([],))[:3] if len(it) == 2 else it
            out += f'<li><a href="{href}">{escape(label)}</a>{ol(kids) if kids else ""}</li>'
        return out + "</ol>"
    lm = "".join(f'<li><a epub:type="x" href="{h}">{escape(t)}</a></li>' for t, h in landmarks)
    return _xhtml(f'<nav epub:type="toc"><h1>Sumário</h1>{ol(toc)}</nav>'
                  + (f'<nav epub:type="landmarks"><ol>{lm}</ol></nav>' if landmarks else ""))


def make_epub(path, spine, toc=None, toc_format="ncx", lang="pt-BR", title="Livro de Teste",
              author="Autora Inventada", cover=True, encryption=None, landmarks=(), extra=None):
    toc = toc if toc is not None else [(f.rsplit(".", 1)[0], f) for f, _ in spine]
    man = [f'<item id="s{i}" href="Text/{f}" media-type="application/xhtml+xml"/>' for i, (f, _) in enumerate(spine)]
    meta = f"<dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator>"
    if lang:
        meta += f"<dc:language>{lang}</dc:language>"
    if cover:
        man.append('<item id="capa" href="Images/capa.jpg" media-type="image/jpeg" properties="cover-image"/>')
        meta += '<meta name="cover" content="capa"/>'
    spine_attr = ""
    if toc_format == "ncx":
        man.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
        spine_attr = ' toc="ncx"'
    elif toc_format == "nav":
        man.append('<item id="nav" href="Text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    opf = ('<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
           'unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="id">urn:uuid:teste</dc:identifier>{meta}</metadata>'
           f'<manifest>{"".join(man)}</manifest><spine{spine_attr}>'
           + "".join(f'<itemref idref="s{i}"/>' for i in range(len(spine))) + "</spine></package>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                   "</rootfiles></container>")
        z.writestr("OEBPS/content.opf", opf)
        for f, body in spine:
            z.writestr(f"OEBPS/Text/{f}", _xhtml(body))
        if toc_format == "ncx":
            z.writestr("OEBPS/toc.ncx", _ncx(toc))
        elif toc_format == "nav":
            z.writestr("OEBPS/Text/nav.xhtml", _nav(toc, landmarks))
        if cover:
            z.writestr("OEBPS/Images/capa.jpg", b"\xff\xd8\xff\xe0capa-falsa\xff\xd9")
        if encryption is not None:
            z.writestr("META-INF/encryption.xml", encryption)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return path


def encryption_xml(entries):
    """entries: lista de (algoritmo, URI cifrada)."""
    body = "".join(
        '<enc:EncryptedData xmlns:enc="http://www.w3.org/2001/04/xmlenc#">'
        f'<enc:EncryptionMethod Algorithm="{alg}"/>'
        f'<enc:CipherData><enc:CipherReference URI="{uri}"/></enc:CipherData></enc:EncryptedData>'
        for alg, uri in entries)
    return ('<?xml version="1.0"?><encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            f'xmlns:enc="http://www.w3.org/2001/04/xmlenc#">{body}</encryption>')
