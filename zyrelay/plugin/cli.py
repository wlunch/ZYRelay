from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .contracts import (
    OutputDetail,
    PluginInput,
    PluginMode,
    PluginOperation,
    PluginOptions,
    PluginRequest,
    PluginStatus,
    SourceType,
)
from .facade import DocIntelligencePlugin

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zyrelay-plugin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("manifest", help="输出插件清单")
    subparsers.add_parser("capabilities", help="输出能力声明")
    for command in ("validate", "execute"):
        item = subparsers.add_parser(command)
        item.add_argument("--file", required=True)
        item.add_argument(
            "--mode",
            choices=[value.value for value in PluginMode],
            default=PluginMode.AUTO.value,
        )
        if command == "execute":
            item.add_argument(
                "--output-detail",
                choices=[value.value for value in OutputDetail],
                default=OutputDetail.STANDARD.value,
            )
            item.add_argument("--output")
            item.add_argument("--enable-llm", action="store_true")
            item.add_argument("--enable-fuzzy-matching", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plugin = DocIntelligencePlugin()
    if args.command == "manifest":
        return _emit(plugin.get_manifest().model_dump(mode="json"))
    if args.command == "capabilities":
        return _emit(plugin.get_capabilities().model_dump(mode="json"))

    path = Path(args.file).expanduser()
    request = PluginRequest(
        operation=(
            PluginOperation.VALIDATE_DOCUMENT
            if args.command == "validate"
            else PluginOperation.PROCESS_DOCUMENT
        ),
        input=PluginInput(
            source_type=SourceType.FILE,
            file_path=str(path),
            file_name=path.name,
            content_type=_content_type(path),
        ),
        options=PluginOptions(
            mode=PluginMode(args.mode),
            output_detail=OutputDetail(
                getattr(args, "output_detail", OutputDetail.STANDARD.value)
            ),
            enable_llm=getattr(args, "enable_llm", False),
            enable_fuzzy_matching=getattr(args, "enable_fuzzy_matching", False),
        ),
        metadata={"client": "cli"},
    )
    if args.command == "validate":
        validation = plugin.validate(request)
        _emit(validation.model_dump(mode="json"))
        return 0 if validation.valid else 3

    response = plugin.execute(request)
    payload = response.model_dump(mode="json", exclude_none=True)
    output = getattr(args, "output", None)
    if output:
        Path(output).expanduser().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        _emit(payload)
    return (
        0
        if response.status
        in {
            PluginStatus.COMPLETED,
            PluginStatus.PARTIAL,
        }
        else 4
    )


def _content_type(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    if path.suffix.lower() == ".docx":
        return DOCX_MIME
    return "application/octet-stream"


def _emit(value: object) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0
