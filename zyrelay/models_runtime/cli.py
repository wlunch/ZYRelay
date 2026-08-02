from __future__ import annotations

import argparse
import json
from typing import Sequence

from .manager import ModelManager


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m zyrelay.models")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    install = commands.add_parser("install")
    install.add_argument("name", choices=["paddleocr"])
    verify = commands.add_parser("verify")
    verify.add_argument("name", choices=["paddleocr"])
    args = parser.parse_args(argv)
    manager = ModelManager()
    if args.command == "status":
        result = manager.paddleocr_status()
    elif args.command == "install":
        result = manager.install(args.name)
    else:
        result = manager.verify(args.name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("verified", result.get("cache_ready", False)) else 1
