"""T13 (R27 a R29): montagem do M4B, vídeo sob pedido, metadados de IA; R9 e R50 na montagem."""
import json
import subprocess
from pathlib import Path

import pytest

from tests.conftest import FAKE_ENGINE, make_project


def capa(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x334455:s=128x128",
         "-frames:v", "1", str(path)],
        check=True,
    )
    return path


def faixa(path, segundos):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=f=220:d={segundos}", "-ac", "1", "-b:a", "64k", str(path)],
        check=True,
    )
    return path


def dur(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def tags_formato(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout).get("format", {}).get("tags", {})


def capitulos_m4b(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout).get("chapters", [])


def tem_capa(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:stream_disposition=attached_pic",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return any(
        s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") == 1
        for s in json.loads(r.stdout).get("streams", [])
    )


def projeto_montagem(tmp_path, *, com_include=True, renomear=None):
    """Projeto com três capítulos em áudio; o do meio pode ficar de fora (include false)."""
    P = make_project(tmp_path, [
        ("01", "Capítulo um", ["Um."]),
        ("02", "Capítulo dois", ["Dois."]),
        ("03", "Capítulo três", ["Três."]),
    ], config={"motor": FAKE_ENGINE, "voz": "Voz de teste"})
    book = json.loads((P / "book.json").read_text(encoding="utf8"))
    book["title"] = "Livro Montado"
    book["author"] = "Autora Teste"
    if renomear:
        for c in book["chapters"]:
            if c["id"] in renomear:
                c["title"] = renomear[c["id"]]
    if com_include:
        for c in book["chapters"]:
            c["include"] = True
        book["chapters"][1]["include"] = False
    (P / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf8")
    capa(P / "cover.jpg")
    durs = {"01": 1.2, "02": 2.4, "03": 1.8}
    for cid, sec in durs.items():
        faixa(P / "chapters" / f"{cid}.m4a", sec)
    return P, durs


def test_m4b_metadados_capitulos_capa_e_duracoes(tmp_path):
    """R28: título, autor, narrador, capa e todos os capítulos com durações corretas."""
    from studio.assemble import montar_projeto

    P, durs = projeto_montagem(tmp_path, com_include=False)
    m4b = montar_projeto(str(P))
    assert Path(m4b).exists()
    tags = tags_formato(m4b)
    assert tags.get("title") == "Livro Montado"
    assert tags.get("artist") == "Autora Teste"
    assert tags.get("composer") == "Voz de teste"
    assert tem_capa(m4b)

    caps = capitulos_m4b(m4b)
    assert [c["tags"]["title"] for c in caps] == ["Capítulo um", "Capítulo dois", "Capítulo três"]
    esperado = [durs["01"], durs["02"], durs["03"]]
    obtidos = [float(c["end_time"]) - float(c["start_time"]) for c in caps]
    for e, o in zip(esperado, obtidos):
        assert abs(e - o) <= 0.15, (esperado, obtidos)
    total = float(caps[-1]["end_time"])
    assert abs(total - sum(esperado)) <= 0.2


def test_include_false_fica_de_fora_e_renomeado_aparece(tmp_path):
    """R9: include false não entra; título renomeado aparece no marcador."""
    from studio.assemble import montar_projeto

    P, durs = projeto_montagem(
        tmp_path, com_include=True, renomear={"01": "Prólogo renomeado", "03": "Final novo"},
    )
    m4b = montar_projeto(str(P))
    caps = capitulos_m4b(m4b)
    titulos = [c["tags"]["title"] for c in caps]
    assert titulos == ["Prólogo renomeado", "Final novo"]
    assert "Capítulo dois" not in titulos
    obtidos = [float(c["end_time"]) - float(c["start_time"]) for c in caps]
    assert abs(obtidos[0] - durs["01"]) <= 0.15
    assert abs(obtidos[1] - durs["03"]) <= 0.15


def test_video_so_se_pedido(tmp_path):
    """R29: MP4 só sai com video=True / --video."""
    from studio.assemble import montar_projeto

    P, _ = projeto_montagem(tmp_path, com_include=False)
    montar_projeto(str(P), video=False)
    out = P / "audiobook"
    assert list(out.glob("*.m4b"))
    assert list(out.glob("*.mp4")) == []

    montar_projeto(str(P), video=True)
    assert list(out.glob("*.mp4"))


def test_metadados_dizem_narracao_por_ia_em_portugues(tmp_path):
    """R27: comentário dos metadados em português, sem travessão, diz que é IA."""
    from studio.assemble import COMENTARIO_IA, montar_projeto

    assert "—" not in COMENTARIO_IA
    assert "IA" in COMENTARIO_IA or "inteligência artificial" in COMENTARIO_IA.lower()
    P, _ = projeto_montagem(tmp_path, com_include=False)
    m4b = montar_projeto(str(P))
    comment = tags_formato(m4b).get("comment", "")
    assert "—" not in comment
    assert "IA" in comment or "inteligência artificial" in comment.lower()
    assert "gerad" in comment.lower()  # gerada / gerado


def test_projeto_antigo_sem_head_include_e_motor_monta(tmp_path):
    """R50: projeto antigo sem head, sem include e sem motor continua montando."""
    from studio.assemble import montar_projeto

    P = make_project(tmp_path, [
        ("01", "Um", ["Oi."]),
        ("02", "Dois", ["Olá."]),
    ], config={"voz": "Narradora antiga"})  # sem "motor"
    book = json.loads((P / "book.json").read_text(encoding="utf8"))
    for c in book["chapters"]:
        c.pop("head", None)
        c.pop("include", None)
    (P / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf8")
    capa(P / "cover.jpg")
    faixa(P / "chapters" / "01.m4a", 1.0)
    faixa(P / "chapters" / "02.m4a", 1.5)
    m4b = montar_projeto(str(P))
    assert Path(m4b).exists()
    caps = capitulos_m4b(m4b)
    assert [c["tags"]["title"] for c in caps] == ["Um", "Dois"]
    assert tags_formato(m4b).get("composer") == "Narradora antiga"


def test_entrada_montar_projeto_existe_e_cli_aceita_video(tmp_path):
    """Entrada para generate/servidor: montar_projeto(P); CLI padrão sem vídeo."""
    import sys
    from studio import assemble

    assert callable(assemble.montar_projeto)
    P, _ = projeto_montagem(tmp_path, com_include=False)
    # CLI sem --video: M4B sim, MP4 não
    assemble.main(["--project", str(P)])
    assert list((P / "audiobook").glob("*.m4b"))
    assert list((P / "audiobook").glob("*.mp4")) == []
