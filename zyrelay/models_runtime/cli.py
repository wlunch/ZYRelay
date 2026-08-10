from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .manager import ModelManager


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m zyrelay.models")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("warmup")
    install = commands.add_parser("install")
    names = [
        "paddleocr",
        "minilm_classifier",
        "fasttext_language",
        "doclayout_yolo",
        "table_transformer",
        "gliner",
        "tree_sitter",
        "symspell",
        "all",
    ]
    install.add_argument("name", choices=names)
    verify = commands.add_parser("verify")
    verify.add_argument("name", choices=names)
    args = parser.parse_args(argv)
    manager = ModelManager()
    if args.command == "status":
        result = {
            "models": {
                "paddleocr": manager.paddleocr_status(),
                **{
                    name: manager.model_status(name)
                    for name in names
                    if name not in {"paddleocr", "all"}
                },
            }
        }
    elif args.command == "install":
        result = manager.install(args.name)
    elif args.command == "warmup":
        result = manager.warmup()
    else:
        result = manager.verify(args.name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command in {"status", "warmup"}:
        return 0
    return 0 if result.get("verified", result.get("cache_ready", False)) else 1
