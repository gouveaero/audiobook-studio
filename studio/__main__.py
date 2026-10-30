"""python -m studio <comando> ...   (book | voice | generate | cloud | assemble | publish | ui | server)"""
import importlib, sys

CMDS = {"book": "prepare_book", "voice": "prepare_voice", "generate": "generate", "cloud": "cloud", "assemble": "assemble", "publish": "publish_drive", "ui": "app", "server": "server"}
if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
    sys.exit(__doc__)
mod = CMDS[sys.argv[1]]
sys.argv = [f"studio {sys.argv[1]}"] + sys.argv[2:]
if mod in ("assemble", "server", "app", "cloud", "prepare_book", "publish_drive"):
    runpy = __import__("runpy"); runpy.run_module(f"studio.{mod}", run_name="__main__")
else:
    getattr(importlib.import_module(f"studio.{mod}"), "main")()
