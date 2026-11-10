"""Entrada do app empacotado e do modo desenvolvimento unificado.

No PyInstaller, subprocessos usam:
  <exe> _worker generate --project ...
em vez de python -m studio.generate.
"""
from __future__ import annotations

import runpy
import sys


def dispatch_worker(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit("uso: _worker <modulo> [args...]")
    mod = argv[1]
    sys.argv = [f"studio.{mod}"] + argv[2:]
    runpy.run_module(f"studio.{mod}", run_name="__main__")


def worker_cmd(module: str, args: list[str] | None = None) -> list[str]:
    """Comando para subprocesso (frozen ou .venv)."""
    args = list(args or [])
    if getattr(sys, "frozen", False):
        return [sys.executable, "_worker", module, *args]
    return [sys.executable, "-m", f"studio.{module}", *args]


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker":
        dispatch_worker(argv)
        return
    if argv and argv[0] == "--self-test":
        from studio.app import run_self_test
        raise SystemExit(run_self_test(argv[1:]))
    from studio.app import main as app_main
    app_main(argv)


if __name__ == "__main__":
    main()
