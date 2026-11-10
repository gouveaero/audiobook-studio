"""T10: prepare_book.py com EPUBs sintéticos (R1 a R8). Sem modelo de voz."""
import json, os, shutil, subprocess, sys

import pytest

from studio import prepare_book as pb
from tests.epub_sintetico import FRASES_EN, encryption_xml, make_epub, paras

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build(tmp_path, spine, **kw):
    epub = make_epub(str(tmp_path / "livro.epub"), spine, **kw)
    out = tmp_path / "proj"
    out.mkdir(exist_ok=True)
    pb.build(epub, str(out / "book.json"))
    return json.load(open(out / "book.json"))


def cli(tmp_path, epub, *args):
    out = tmp_path / "cli"
    out.mkdir(exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "studio.prepare_book", epub, str(out / "book.json"), *args],
                       cwd=ROOT, capture_output=True, text=True)
    return r, out


def heads(book):
    return [c["chunks"][i] for c in book["chapters"] for i in c["head"]]


def text(ch):
    return " ".join(ch["chunks"])


# R1 ---------------------------------------------------------------------------------------------------------------

def test_r1_capitulos_na_ordem_do_sumario(tmp_path):
    spine = [("c1.xhtml", "<h1>A chegada</h1>" + paras(3)), ("c2.xhtml", "<h1>O rio</h1>" + paras(3, start=2)),
             ("c3.xhtml", "<h1>A partida</h1>" + paras(3, start=4))]
    book = build(tmp_path, spine, toc=[("A chegada", "c1.xhtml"), ("O rio", "c2.xhtml"), ("A partida", "c3.xhtml")])
    assert [c["title"] for c in book["chapters"]] == ["A chegada", "O rio", "A partida"]
    assert [c["id"] for c in book["chapters"]] == ["01", "02", "03"]


def test_r1_ancoras_no_mesmo_arquivo_viram_capitulos(tmp_path):
    body = ('<h2 id="a">A chegada</h2><p>Primeiro capítulo com a carta azul.</p>'
            '<h2 id="b">O rio</h2><p>Segundo capítulo com o barco velho.</p>'
            '<h2 id="c">A partida</h2><p>Terceiro capítulo com a estação vazia.</p>' + paras(6))
    book = build(tmp_path, [("tudo.xhtml", body)], toc_format="nav",
                 toc=[("A chegada", "tudo.xhtml#a"), ("O rio", "tudo.xhtml#b"), ("A partida", "tudo.xhtml#c")])
    chs = book["chapters"]
    assert [c["title"] for c in chs] == ["A chegada", "O rio", "A partida"]
    assert "carta azul" in text(chs[0]) and "barco" not in text(chs[0])
    assert "barco velho" in text(chs[1]) and "estação" not in text(chs[1])
    assert "estação vazia" in text(chs[2])


def test_r1_nav_ignora_landmarks(tmp_path):
    spine = [("c1.xhtml", "<h1>Um</h1>" + paras(3)), ("c2.xhtml", "<h1>Dois</h1>" + paras(3))]
    book = build(tmp_path, spine, toc_format="nav", toc=[("Um", "c1.xhtml"), ("Dois", "c2.xhtml")],
                 landmarks=[("Começo da leitura", "c2.xhtml")])
    assert [c["title"] for c in book["chapters"]] == ["Um", "Dois"]


def test_r1_texto_fora_de_p_e_notas_removidas(tmp_path):
    body = ('<h1>A casa</h1><div>Texto solto dentro de uma div sem parágrafo.</div>'
            '<p>Ela riu<sup><a href="#n1">1</a></sup> e saiu.</p>'
            '<blockquote>Uma citação curta no meio do capítulo.</blockquote>' + paras(3)
            + '<aside epub:type="footnote" id="n1"><p>Nota do tradutor que não deve ser lida.</p></aside>'
            + '<p class="nota-rodape">Outra nota que não deve ser lida.</p>')
    book = build(tmp_path, [("c1.xhtml", body)], toc=[("A casa", "c1.xhtml")])
    t = text(book["chapters"][0])
    assert "Texto solto dentro de uma div" in t
    assert "citação curta" in t
    assert "Ela riu e saiu." in t
    assert "Nota do tradutor" not in t and "Outra nota" not in t


def test_formato_do_book_json(tmp_path):
    book = build(tmp_path, [("c1.xhtml", "<h1>Começo</h1>" + paras(4))], toc=[("Começo", "c1.xhtml")])
    assert set(book) >= {"title", "author", "language", "chapters"}
    assert book["language"] == "pt"
    for c in book["chapters"]:
        assert c["include"] is True
        assert c["head"] == [0]
        assert len(c["chunks"]) == len(c["pauses"])
        assert all(len(k) <= pb.MAXC for k in c["chunks"])


# R2 ---------------------------------------------------------------------------------------------------------------

def test_r2_capitulo_so_com_imagem_sai_e_parte_curta_fica(tmp_path):
    spine = [("foto.xhtml", '<p><img src="../Images/f.jpg" alt="foto"/><br/></p><div id="rosto"></div>'),
             ("foto2.xhtml", '<div><img src="../Images/f2.jpg" alt="foto"/></div>'),
             ("parte1.xhtml", "<div><h1><strong>Parte</strong> <small>I</small></h1></div>"),
             ("c1.xhtml", "<h2>1.</h2>" + paras(4))]
    toc = [("Foto", "foto.xhtml"), ("Foto", "foto.xhtml"), ("Parte I", "parte1.xhtml", [("1.", "c1.xhtml")])]
    book = build(tmp_path, spine, toc=toc)
    titles = [c["title"] for c in book["chapters"]]
    assert "Foto" not in titles
    assert titles[0] == "Parte I"
    assert book["chapters"][0]["chunks"] == ["Parte um."]


# R3 ---------------------------------------------------------------------------------------------------------------

def test_r3_fala_do_titulo_limpa(tmp_path):
    spine = [("c1.xhtml", "<h2>1.</h2>" + paras(3)), ("c2.xhtml", "<h2>2</h2>" + paras(3)),
             ("pos.xhtml", "<h1>Posfácios</h1>"),
             ("pos1.xhtml", "<h2>Fulana de Tal (1961)</h2>" + paras(3)),
             ("pos2.xhtml", "<h2>Beltrano Souza (1989)</h2>" + paras(3))]
    toc = [("1.", "c1.xhtml"), ("2", "c2.xhtml"),
           ("Posfácios", "pos.xhtml", [("1 | Fulana de Tal (1961)", "pos1.xhtml"), ("2 | Beltrano Souza (1989)", "pos2.xhtml")])]
    book = build(tmp_path, spine, toc=toc)
    hs = heads(book)
    assert hs[0] == "Capítulo um."
    assert hs[1] == "Capítulo dois."
    for h in hs:
        assert ".." not in h and "|" not in h and " ," not in h, h
        assert not h.lower().startswith(("um ", "um.", "dois ", "dois.")), h
    chs = book["chapters"]
    assert chs[0]["title"] == "Capítulo 1"
    assert chs[3]["title"] == "Fulana de Tal (1961)"
    assert chs[3]["chunks"][0].startswith("Fulana de Tal")
    assert chs[2]["chunks"] == ["Posfácios."]


def test_r3_parte_com_romano_nao_vira_ordinal(tmp_path):
    spine = [("p1.xhtml", "<h1>Parte I</h1>"), ("p2.xhtml", "<h1>Parte II</h1>"), ("p3.xhtml", "<h1>Livro III</h1>"),
             ("c.xhtml", "<h1>Fim</h1>" + paras(3))]
    toc = [("Parte I", "p1.xhtml"), ("Parte II", "p2.xhtml"), ("Livro III", "p3.xhtml"), ("Fim", "c.xhtml")]
    hs = heads(build(tmp_path, spine, toc=toc))
    assert hs[:3] == ["Parte um.", "Parte dois.", "Livro três."]
    assert not any("primeir" in h or "segund" in h for h in hs)


# R4 ---------------------------------------------------------------------------------------------------------------

def _partes_spine():
    return [("p1.xhtml", "<h1>Parte I</h1>"), ("c1.xhtml", "<h2>1.</h2>" + paras(3)),
            ("c2.xhtml", "<h2>2.</h2>" + paras(3)), ("c3.xhtml", "<h2>3.</h2>" + paras(3)),
            ("p2.xhtml", "<h1>Parte II</h1>"), ("d1.xhtml", "<h2>1.</h2>" + paras(3)),
            ("ap.xhtml", "<h1>Apêndice</h1>" + paras(3))]


def _check_partes(book):
    chs = book["chapters"]
    assert [c["title"] for c in chs] == ["Parte I", "Parte I, capítulo 1", "Parte I, capítulo 2", "Parte I, capítulo 3",
                                         "Parte II", "Parte II, capítulo 1", "Apêndice"]
    assert chs[3]["chunks"][0] == "Capítulo três."
    assert chs[5]["chunks"][0] == "Capítulo um."
    assert chs[6]["chunks"][0] == "Apêndice."


def test_r4_capitulos_dentro_de_partes_sumario_aninhado(tmp_path):
    toc = [("Parte I", "p1.xhtml", [("1.", "c1.xhtml"), ("2.", "c2.xhtml"), ("3.", "c3.xhtml")]),
           ("Parte II", "p2.xhtml", [("1.", "d1.xhtml")]), ("Apêndice", "ap.xhtml")]
    _check_partes(build(tmp_path, _partes_spine(), toc=toc))


def test_r4_capitulos_dentro_de_partes_sumario_plano(tmp_path):
    toc = [("Parte I", "p1.xhtml"), ("1.", "c1.xhtml"), ("2.", "c2.xhtml"), ("3.", "c3.xhtml"),
           ("Parte II", "p2.xhtml"), ("1.", "d1.xhtml"), ("Apêndice", "ap.xhtml")]
    _check_partes(build(tmp_path, _partes_spine(), toc=toc, toc_format="nav"))


def test_r4_capitulo_com_subtitulo_dentro_de_parte(tmp_path):
    spine = [("p1.xhtml", "<h1>Parte I</h1>"), ("c1.xhtml", "<h2>Capítulo 1: A volta</h2>" + paras(3))]
    toc = [("Parte I", "p1.xhtml", [("Capítulo 1: A volta", "c1.xhtml")])]
    ch = build(tmp_path, spine, toc=toc)["chapters"][1]
    assert ch["title"] == "Parte I, capítulo 1: A volta"
    assert ch["chunks"][0] == "Capítulo um. A volta."


# R5 ---------------------------------------------------------------------------------------------------------------

AES = "http://www.w3.org/2001/04/xmlenc#aes128-cbc"
FONTE = "http://www.idpf.org/2008/embedding"


def test_r5_drm_mostra_erro_e_nao_cria_projeto(tmp_path):
    epub = make_epub(str(tmp_path / "drm.epub"), [("c1.xhtml", "<h1>Um</h1>" + paras(4))],
                     encryption=encryption_xml([(AES, "OEBPS/Text/c1.xhtml")]))
    with pytest.raises(pb.BookError) as e:
        pb.build(epub, str(tmp_path / "x" / "book.json"))
    assert e.value.code == "drm"
    assert "DRM" in str(e.value)
    r, out = cli(tmp_path, epub)
    assert r.returncode != 0
    assert "DRM" in r.stderr and "Traceback" not in r.stderr
    assert os.listdir(out) == []


def test_r5_fonte_ofuscada_nao_e_drm(tmp_path):
    epub = make_epub(str(tmp_path / "fonte.epub"), [("c1.xhtml", "<h1>Um</h1>" + paras(4))],
                     encryption=encryption_xml([(FONTE, "OEBPS/Fonts/letra.otf")]),
                     extra={"OEBPS/Fonts/letra.otf": b"fonte"})
    out = tmp_path / "p"
    out.mkdir()
    assert len(pb.build(epub, str(out / "book.json"))) == 1


def test_epub_invalido_mostra_erro_claro(tmp_path):
    f = tmp_path / "nao.epub"
    f.write_bytes(b"isto nao e um zip")
    r, out = cli(tmp_path, str(f))
    assert r.returncode != 0 and "Traceback" not in r.stderr and "EPUB" in r.stderr
    assert os.listdir(out) == []


# R6 ---------------------------------------------------------------------------------------------------------------

def test_r6_sem_sumario_divide_pelos_titulos_dos_arquivos(tmp_path):
    spine = [("c1.xhtml", "<h1>A chegada</h1>" + paras(3)), ("c2.xhtml", "<h1>O rio</h1>" + paras(3)),
             ("c3.xhtml", "<h2>A partida</h2>" + paras(3))]
    book = build(tmp_path, spine, toc_format=None)
    assert [c["title"] for c in book["chapters"]] == ["A chegada", "O rio", "A partida"]
    assert book["chapters"][1]["chunks"][0] == "O rio."


def test_r6_sem_sumario_divide_arquivo_unico(tmp_path):
    body = ("<h1>Parte I</h1><h2>1</h2>" + paras(3) + "<h2>2</h2>" + paras(3) + "<h3>Uma seção</h3>" + paras(2)
            + "<h1>Parte II</h1><h2>1</h2>" + paras(3))
    book = build(tmp_path, [("tudo.xhtml", body)], toc_format=None)
    assert [c["title"] for c in book["chapters"]] == ["Parte I", "Parte I, capítulo 1", "Parte I, capítulo 2",
                                                       "Parte II", "Parte II, capítulo 1"]
    assert "Uma seção." in book["chapters"][2]["chunks"]


# R7 ---------------------------------------------------------------------------------------------------------------

def test_r7_capa_do_epub_e_extraida(tmp_path):
    build(tmp_path, [("c1.xhtml", "<h1>Um</h1>" + paras(3))], toc=[("Um", "c1.xhtml")])
    assert (tmp_path / "proj" / "cover.jpg").read_bytes() == b"\xff\xd8\xff\xe0capa-falsa\xff\xd9"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="precisa de ffmpeg no PATH")
def test_r7_sem_capa_gera_capa_e_montagem_funciona(tmp_path):
    book = build(tmp_path, [("c1.xhtml", "<h1>Um</h1>" + paras(3)), ("c2.xhtml", "<h1>Dois</h1>" + paras(3))],
                 toc=[("Um", "c1.xhtml"), ("Dois", "c2.xhtml")], cover=False)
    proj = tmp_path / "proj"
    cover = proj / "cover.jpg"
    assert cover.exists()
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height", "-of", "json",
                            str(cover)], capture_output=True, text=True)
    st = json.loads(probe.stdout)["streams"][0]
    assert st["codec_name"] == "mjpeg" and st["width"] == st["height"] >= 600
    (proj / "chapters").mkdir()
    for c in book["chapters"]:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=1", "-ac", "1",
                        "-b:a", "64k", str(proj / "chapters" / f"{c['id']}.m4a")], check=True)
    r = subprocess.run([sys.executable, "-m", "studio.assemble", "--project", str(proj)], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    m4b = proj / "audiobook" / "Livro de Teste.m4b"
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:stream_disposition=attached_pic",
                            "-of", "json", str(m4b)], capture_output=True, text=True)
    assert any(s["codec_type"] == "video" and s["disposition"]["attached_pic"] == 1
               for s in json.loads(probe.stdout)["streams"])
    # R29: vídeo só se pedido; a montagem padrão gera só o M4B com a capa embutida
    assert not (proj / "audiobook" / "Livro de Teste.mp4").exists()


# R8 ---------------------------------------------------------------------------------------------------------------

def _ingles(tmp_path, lang):
    return make_epub(str(tmp_path / "en.epub"), [("c1.xhtml", "<h1>One</h1>" + paras(30, FRASES_EN))],
                     toc=[("One", "c1.xhtml")], lang=lang)


@pytest.mark.parametrize("lang", ["en", "pt-BR", None])
def test_r8_livro_fora_do_portugues_avisa_e_nao_segue(tmp_path, lang):
    epub = _ingles(tmp_path, lang)
    with pytest.raises(pb.BookError) as e:
        pb.build(epub, str(tmp_path / "x" / "book.json"))
    assert e.value.code == "idioma"
    assert "português" in str(e.value)
    r, out = cli(tmp_path, epub)
    assert r.returncode != 0 and "português" in r.stderr and "Traceback" not in r.stderr
    assert os.listdir(out) == []


def test_r8_metadado_errado_com_texto_em_portugues_segue(tmp_path):
    book = build(tmp_path, [("c1.xhtml", "<h1>Um</h1>" + paras(30))], toc=[("Um", "c1.xhtml")], lang="en")
    assert book["language"] == "pt"


def test_r8_lang_explicito_na_linha_de_comando_continua_valendo(tmp_path):
    r, out = cli(tmp_path, _ingles(tmp_path, "en"), "--lang", "en")
    assert r.returncode == 0, r.stderr
    assert json.load(open(out / "book.json"))["language"] == "en"


# T11: defeitos achados nos livros reais, reproduzidos com texto inventado ----------------------------------------------

def test_t11_separador_sem_letras_nao_e_lido(tmp_path):
    body = ("<h1>A casa</h1>" + paras(2) + '<p class="sep">*</p><p>* * *</p><p>⁂</p><p>***</p>'
            "<p>Ela contou até 3.</p>" + paras(2))
    ch = build(tmp_path, [("c1.xhtml", body)], toc=[("A casa", "c1.xhtml")])["chapters"][0]
    assert not any(not any(x.isalnum() for x in k) for k in ch["chunks"]), ch["chunks"]
    assert "*" not in text(ch) and "⁂" not in text(ch)
    assert "Ela contou até três." in ch["chunks"]


def test_t11_romanos_com_capitulos_arabicos_sao_partes(tmp_path):
    spine = [("p1.xhtml", "<h1>I. ORIGEM</h1><p>Uma epígrafe curta, inventada para o teste.</p>"),
             ("c1.xhtml", "<h2>1. A casa</h2>" + paras(3)), ("c2.xhtml", "<h2>2. O rio (812-604 a.C.)</h2>" + paras(3)),
             ("p2.xhtml", "<h1>II. VIAGEM</h1>"), ("c3.xhtml", "<h2>3. O mar (30 a.C.-20 d.C.)</h2>" + paras(3)),
             ("ep.xhtml", "<h1>Epílogo</h1>" + paras(3))]
    toc = [("I. ORIGEM", "p1.xhtml", [("1. A casa", "c1.xhtml"), ("2. O rio (812-604 a.C.)", "c2.xhtml")]),
           ("II. VIAGEM", "p2.xhtml", [("3. O mar (30 a.C.-20 d.C.)", "c3.xhtml")]), ("Epílogo", "ep.xhtml")]
    chs = build(tmp_path, spine, toc=toc)["chapters"]
    assert [c["title"] for c in chs] == ["Parte I: Origem", "Parte I, capítulo 1: A casa",
                                         "Parte I, capítulo 2: O rio (812-604 a.C.)", "Parte II: Viagem",
                                         "Parte II, capítulo 3: O mar (30 a.C.-20 d.C.)", "Epílogo"]
    assert chs[0]["chunks"][0] == "Parte um. Origem."
    assert chs[3]["chunks"] == ["Parte dois. Viagem."]
    assert chs[2]["chunks"][0] == "Capítulo dois. O rio, oitocentos e doze a seiscentos e quatro antes de Cristo."
    assert chs[4]["chunks"][0] == "Capítulo três. O mar, trinta antes de Cristo a vinte depois de Cristo."


def test_t11_capitulos_so_em_romano_continuam_capitulos(tmp_path):
    spine = [("c1.xhtml", "<h2>I</h2>" + paras(3)), ("c2.xhtml", "<h2>II</h2>" + paras(3))]
    chs = build(tmp_path, spine, toc=[("I", "c1.xhtml"), ("II", "c2.xhtml")])["chapters"]
    assert [c["title"] for c in chs] == ["Capítulo 1", "Capítulo 2"]
    assert chs[1]["chunks"][0] == "Capítulo dois."


def test_t11_nota_do_autor_fica_e_notas_finais_saem(tmp_path):
    spine = [("n1.xhtml", "<h1>Notas sobre os nomes</h1>" + paras(2)), ("c1.xhtml", "<h1>A casa</h1>" + paras(3)),
             ("n2.xhtml", "<h1>Notas</h1><p>1. Fonte inventada, página dez.</p>"),
             ("n3.xhtml", "<h1>Notas finais</h1><p>2. Outra fonte inventada.</p>")]
    toc = [("Notas sobre os nomes", "n1.xhtml"), ("A casa", "c1.xhtml"), ("Notas", "n2.xhtml"), ("Notas finais", "n3.xhtml")]
    assert [c["title"] for c in build(tmp_path, spine, toc=toc)["chapters"]] == ["Notas sobre os nomes", "A casa"]


def test_linha_de_comando_atual(tmp_path):
    epub = make_epub(str(tmp_path / "l.epub"), [("c1.xhtml", "<h1>Um</h1>" + paras(4))], toc=[("Um", "c1.xhtml")])
    r, out = cli(tmp_path, epub)
    assert r.returncode == 0, r.stderr
    assert "capítulos" in r.stdout
    assert (out / "book.json").exists() and (out / "cover.jpg").exists()
