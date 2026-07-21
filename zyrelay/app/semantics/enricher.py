from __future__ import annotations

import json
from typing import Protocol

import httpx

from zyrelay.app.core.exceptions import LLMError
from zyrelay.app.models import (
    CandidateStatus,
    CandidateType,
    DocumentBlock,
    LabelDefinition,
    LabelMention,
    SemanticCandidate,
    SourceDocument,
)


class SemanticEnricher(Protocol):
    def enrich(
        self,
        document: SourceDocument,
        blocks: list[DocumentBlock],
        labels: list[LabelDefinition],
        mentions: list[LabelMention],
    ) -> list[SemanticCandidate]: ...


class NoOpSemanticEnricher:
    def enrich(
        self,
        document: SourceDocument,
        blocks: list[DocumentBlock],
        labels: list[LabelDefinition],
        mentions: list[LabelMention],
    ) -> list[SemanticCandidate]:
        return []


class OpenAICompatibleSemanticEnricher:
    """Optional single-call enrichment; rule results remain authoritative."""

    def __init__(
        self, *, base_url: str, api_key: str, model: str, timeout: float = 30
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def enrich(
        self,
        document: SourceDocument,
        blocks: list[DocumentBlock],
        labels: list[LabelDefinition],
        mentions: list[LabelMention],
    ) -> list[SemanticCandidate]:
        if not self.base_url or not self.api_key or not self.model:
            raise LLMError("LLM 已启用但配置不完整")

        covered_blocks = {mention.block_id for mention in mentions}
        relevant_blocks = [
            block
            for block in blocks
            if block.block_id not in covered_blocks and block.text.strip()
        ][:10]
        if not relevant_blocks:
            return []

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "仅从给定原文识别明确的 entity/relation/event/business_object "
                        "候选。每个候选必须引用 block_id 和逐字 evidence，不得推断。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "document_id": document.document_id,
                            "labels": [
                                label.model_dump(mode="json") for label in labels
                            ],
                            "blocks": [
                                {"block_id": block.block_id, "text": block.text}
                                for block in relevant_blocks
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "semantic_candidates",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "candidates": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "candidate_type": {
                                            "enum": [
                                                "entity",
                                                "relation",
                                                "event",
                                                "business_object",
                                            ]
                                        },
                                        "name": {"type": "string"},
                                        "block_id": {"type": "string"},
                                        "evidence": {"type": "string"},
                                        "attributes": {"type": "object"},
                                        "ontology_uri": {
                                            "type": ["string", "null"]
                                        },
                                        "confidence": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 0.8,
                                        },
                                    },
                                    "required": [
                                        "candidate_type",
                                        "name",
                                        "block_id",
                                        "evidence",
                                        "attributes",
                                        "ontology_uri",
                                        "confidence",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["candidates"],
                        "additionalProperties": False,
                    },
                },
            },
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            raw_candidates = json.loads(content)["candidates"]
        except Exception as exc:
            raise LLMError(f"LLM enrichment 调用失败：{exc}") from exc

        block_map = {block.block_id: block for block in relevant_blocks}
        validated: list[SemanticCandidate] = []
        for index, item in enumerate(raw_candidates):
            block = block_map.get(item["block_id"])
            evidence = item["evidence"]
            if block is None or not evidence or evidence not in block.text:
                continue
            validated.append(
                SemanticCandidate(
                    candidate_id=f"LLM-{document.document_id}-{index + 1:04d}",
                    candidate_type=CandidateType(item["candidate_type"]),
                    name=item["name"],
                    source_mentions=[],
                    attributes={
                        **item["attributes"],
                        "block_id": item["block_id"],
                        "evidence": evidence,
                    },
                    confidence=min(float(item["confidence"]), 0.8),
                    ontology_uri=item.get("ontology_uri"),
                    status=CandidateStatus.DETECTED,
                )
            )
        return validated

