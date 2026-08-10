"""Offline benchmark checks for v0.6 local-AI resource plugins.

These are deliberately small, deterministic acceptance benchmarks: no network
or hosted model is contacted and every unavailable heavyweight model is tested
through its registered local fallback.
"""

from __future__ import annotations

from pathlib import Path

from zyrelay.app.core.config import Settings
from zyrelay.app.models import BlockType, DocumentBlock
from zyrelay.resources.auxiliary import (
    FastTextLanguageResource,
    HeuristicNERResource,
    HeuristicTableResource,
    SymSpellResource,
    TreeSitterCodeResource,
)
from zyrelay.resources.heuristic_layout import HeuristicLayoutResource
from zyrelay.resources.models import ResourceRequest


def _block(text: str, block_type: BlockType = BlockType.PARAGRAPH) -> DocumentBlock:
    return DocumentBlock(
        block_id="BLK-BENCH-001",
        document_id="DOC-BENCH-001",
        page_no=1,
        block_type=block_type,
        sequence=0,
        text=text,
        normalized_text=text,
        start_offset=0,
        end_offset=len(text),
    )


def test_layout_benchmark_uses_parser_layout_without_model() -> None:
    response = HeuristicLayoutResource().execute(
        ResourceRequest(capability="layout"), object()
    )
    assert response.status == "completed"


def test_table_benchmark_marks_native_table_block(tmp_path: Path) -> None:
    resource = HeuristicTableResource(Settings(data_root=tmp_path))
    response = resource.execute(
        ResourceRequest(
            capability="table_recognition",
            options={"blocks": [_block("A | B", BlockType.TABLE)]},
        ),
        object(),
    )
    assert response.payload["tables"]["BLK-BENCH-001"].startswith("TBL-")


def test_language_benchmark_fasttext_is_offline() -> None:
    resource = FastTextLanguageResource(Settings())
    response = resource.execute(
        ResourceRequest(
            capability="language_detection",
            options={"blocks": [_block("这是一个合同文档")]},
        ),
        object(),
    )
    assert response.status == "completed"
    assert response.payload["blocks"]["BLK-BENCH-001"]["language"] == "zh-CN"


def test_ner_benchmark_fallback_keeps_text_evidence(tmp_path: Path) -> None:
    resource = HeuristicNERResource(Settings(data_root=tmp_path))
    response = resource.execute(
        ResourceRequest(
            capability="ner", options={"blocks": [_block("甲方：星辰科技有限公司")]}
        ),
        object(),
    )
    entity = response.payload["entities"]["BLK-BENCH-001"][0]
    assert entity["text"] == "星辰科技有限公司"
    assert entity["start"] >= 0


def test_code_detection_benchmark_tree_sitter() -> None:
    resource = TreeSitterCodeResource(Settings())
    response = resource.execute(
        ResourceRequest(
            capability="code_detection",
            options={"blocks": [_block("def hello(name):\n    return name")]},
        ),
        object(),
    )
    assert response.payload["blocks"]["BLK-BENCH-001"] == {
        "is_code": True,
        "code_language": "python",
    }


def test_spell_benchmark_returns_explainable_suggestion() -> None:
    resource = SymSpellResource(Settings())
    response = resource.execute(
        ResourceRequest(
            capability="spell_correction",
            options={"blocks": [_block("This contrcat is valid.")]},
        ),
        object(),
    )
    assert any(
        item["suggestion"] == "contract" for item in response.payload["suggestions"]
    )
