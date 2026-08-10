"""Deterministic gates for optional local model resources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelGateDecision:
    capability: str
    should_run: bool
    reason: str
    input_signals: dict[str, Any]
    resource_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "decision": "run" if self.should_run else "skip",
            "reason": self.reason,
            "input_signals": self.input_signals,
            "resource_id": self.resource_id,
        }


class ModelRouter:
    """Rule-only model routing; it never changes parser or extraction results."""

    def decide(
        self, capability: str, *, context, request, resource_id: str, blocks=None
    ) -> ModelGateDecision:
        document = context.document
        blocks = list(blocks or context.blocks)
        signals = {
            "file_type": document.file_type if document else None,
            "requires_ocr": bool(document and document.requires_ocr),
            "mode": request.mode.value,
            "resource_id": resource_id,
            "block_count": len(blocks),
            "ocr_block_count": sum(
                item.metadata.get("source_method") == "ocr" for item in blocks
            ),
            "table_block_count": sum(
                item.block_type.value == "table" for item in blocks
            ),
            "entity_mention_count": sum(
                label.category.value == "entity"
                for label in context.labels
                for mention in context.mentions
                if mention.label_code == label.code
            ),
        }
        if resource_id == "disabled":
            return self._skip(
                capability, "enterprise_profile_disabled", signals, resource_id
            )
        if capability == "ocr":
            return self.should_run_ocr(request, signals, resource_id)
        if capability == "layout":
            return self.should_run_layout_model(request, signals, resource_id)
        if capability == "table_recognition":
            return self.should_run_table_model(request, signals, resource_id)
        if capability == "document_classifier":
            return self.should_run_classifier(request, signals, resource_id)
        if capability == "language_detection":
            return self.should_run_language_detection(request, signals, resource_id)
        if capability == "ner":
            return self.should_run_ner(request, signals, resource_id)
        if capability == "code_detection":
            return self.should_run_code_detection(request, signals, resource_id, blocks)
        if capability == "spell_correction":
            return self.should_run_spell_correction(request, signals, resource_id)
        return ModelGateDecision(
            capability, True, "required_resource", signals, resource_id
        )

    @staticmethod
    def should_run_ocr(request, signals, resource_id):
        if not request.enable_ocr:
            return ModelRouter._skip("ocr", "request_disabled", signals, resource_id)
        if signals["file_type"] != "pdf":
            return ModelRouter._skip("ocr", "not_pdf", signals, resource_id)
        if not signals["requires_ocr"]:
            return ModelRouter._skip(
                "ocr", "native_text_available", signals, resource_id
            )
        return ModelGateDecision(
            "ocr", True, "scanned_pdf_requires_ocr", signals, resource_id
        )

    @staticmethod
    def should_run_layout_model(request, signals, resource_id):
        if signals["file_type"] == "docx":
            return ModelRouter._skip(
                "layout", "docx_logical_blocks_are_sufficient", signals, resource_id
            )
        if resource_id == "heuristic-layout":
            return ModelGateDecision(
                "layout", True, "pdf_heuristic_layout", signals, resource_id
            )
        if signals["requires_ocr"] or request.enable_layout_model:
            return ModelGateDecision(
                "layout",
                True,
                "visual_layout_requested_or_scanned",
                signals,
                resource_id,
            )
        return ModelRouter._skip(
            "layout", "native_text_pdf_uses_heuristic_first", signals, resource_id
        )

    @staticmethod
    def should_run_table_model(request, signals, resource_id):
        if signals["table_block_count"]:
            return ModelGateDecision(
                "table_recognition",
                True,
                "native_table_block_present",
                signals,
                resource_id,
            )
        if signals["file_type"] == "pdf" and request.enable_layout_model:
            return ModelGateDecision(
                "table_recognition",
                True,
                "visual_table_detection_requested",
                signals,
                resource_id,
            )
        return ModelRouter._skip(
            "table_recognition", "no_table_signal", signals, resource_id
        )

    @staticmethod
    def should_run_classifier(request, signals, resource_id):
        if request.mode.value == "auto":
            return ModelGateDecision(
                "document_classifier", True, "document_mode_auto", signals, resource_id
            )
        return ModelRouter._skip(
            "document_classifier", "document_mode_already_known", signals, resource_id
        )

    @staticmethod
    def should_run_language_detection(request, signals, resource_id):
        if request.metadata.get("language_hint"):
            return ModelRouter._skip(
                "language_detection", "request_language_hint", signals, resource_id
            )
        return ModelGateDecision(
            "language_detection",
            True,
            "no_reliable_language_hint",
            signals,
            resource_id,
        )

    @staticmethod
    def should_run_ner(request, signals, resource_id):
        if signals["entity_mention_count"]:
            return ModelRouter._skip(
                "ner", "rule_entities_already_extracted", signals, resource_id
            )
        return ModelGateDecision(
            "ner", True, "rule_entities_missing", signals, resource_id
        )

    @staticmethod
    def should_run_code_detection(request, signals, resource_id, blocks):
        if request.mode.value == "code_convention":
            return ModelGateDecision(
                "code_detection", True, "code_convention_mode", signals, resource_id
            )
        if any(
            "```" in block.text or "def " in block.text or "class " in block.text
            for block in blocks
        ):
            return ModelGateDecision(
                "code_detection", True, "code_signal_present", signals, resource_id
            )
        return ModelRouter._skip(
            "code_detection", "no_code_signal", signals, resource_id
        )

    @staticmethod
    def should_run_spell_correction(request, signals, resource_id):
        if signals["ocr_block_count"]:
            return ModelGateDecision(
                "spell_correction", True, "ocr_generated_text", signals, resource_id
            )
        return ModelRouter._skip(
            "spell_correction", "not_ocr_text", signals, resource_id
        )

    @staticmethod
    def _skip(capability, reason, signals, resource_id):
        return ModelGateDecision(capability, False, reason, signals, resource_id)
