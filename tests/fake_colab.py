"""`colab` simulado para os testes de studio/cloud.py (R51). Registra cada chamada e imita o CLI oficial.

Ambiente:
  FAKE_COLAB_LOG   arquivo JSONL com uma linha por chamada: {"args": [...], "code": "<conteúdo do -f, se houver>"}
  FAKE_COLAB_VM    pasta que espelha a VM: uploads caem nela (o prefixo /content vira esta pasta)
  FAKE_COLAB_M4A   arquivo m4a válido devolvido em todo download de capítulo
"""
import json
import os
import shutil
import sys


def main(argv):
    log, vm, m4a = os.environ["FAKE_COLAB_LOG"], os.environ["FAKE_COLAB_VM"], os.environ.get("FAKE_COLAB_M4A", "")
    args = argv[1:]
    code = ""
    if "-f" in args:
        code = open(args[args.index("-f") + 1], encoding="utf8").read()
    with open(log, "a", encoding="utf8") as f:
        f.write(json.dumps({"args": args, "code": code}, ensure_ascii=False) + "\n")
    cmd = [a for a in args if not a.startswith("-") and a not in ("adc",)]
    if cmd[0] == "upload":
        src, dst = args[-2], args[-1]
        alvo = dst.replace("/content", vm, 1)
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        shutil.copy2(src, alvo)
    elif cmd[0] == "download":
        src, dst = args[-2], args[-1]
        if src.endswith(".m4a") and m4a:
            shutil.copy2(m4a, dst)
        elif src.endswith("progress.jsonl"):
            open(dst, "w").write("")
    elif cmd[0] == "exec":
        if "listdir('/content/project/chapters')" in code:
            prontos = sorted(f for f in os.listdir(os.path.join(vm, "project", "chapters")) if f.endswith(".m4a")) \
                if os.path.isdir(os.path.join(vm, "project", "chapters")) else []
            print("@@" + json.dumps({"ch": prontos, "chunks": [], "gpu": 42, "err": 0}))
        elif ".done" in code:
            print("@@0")
        elif "locks" in code:  # lançamento: a "VM" produz todos os capítulos não travados de uma vez
            os.makedirs(os.path.join(vm, "project", "chapters"), exist_ok=True)
            book = json.load(open(os.path.join(vm, "project", "book.json")))
            locks = os.path.join(vm, "project", "work", "locks"); os.makedirs(locks, exist_ok=True)
            import re
            m = re.search(r"for i in (\[.*?\]):", code)
            travados = set(json.loads(m.group(1).replace("'", '"'))) if m else set()
            for lid in travados:
                open(os.path.join(locks, lid), "w").close()
            for c in book["chapters"]:
                if c["id"] not in travados:
                    shutil.copy2(m4a, os.path.join(vm, "project", "chapters", c["id"] + ".m4a"))
            print("lançado")
        else:
            print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
