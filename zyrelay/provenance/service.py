from __future__ import annotations

import uuid

from zyrelay.app.conventions import CodeConventionCandidate
from zyrelay.app.models import SemanticObject
from zyrelay.relay.repository import JsonRecordRepository

from .models import ProvenanceRecord


class ProvenanceService:
    def __init__(self, data_root) -> None:
        self.store = JsonRecordRepository(data_root / "provenance", ProvenanceRecord)

    def create_for_convention(
        self,
        candidate: CodeConventionCandidate,
        *,
        execution_id: str,
        document_id: str,
        ground_selection_id: str,
        ground_snapshot_id: str,
        resource_plan_id: str,
        model_execution_ids: list[str],
        blocks: list | None = None,
        model_executions: list | None = None,
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            provenance_id=f"PROV-{uuid.uuid4().hex[:16].upper()}",
            execution_id=execution_id,
            document_id=document_id,
            ground_selection_id=ground_selection_id,
            ground_snapshot_id=ground_snapshot_id,
            resource_plan_id=resource_plan_id,
            source_pages=list(
                dict.fromkeys(
                    item.page_no for item in candidate.source_evidence if item.page_no
                )
            ),
            source_offsets=[
                {"start": item.start_offset, "end": item.end_offset}
                for item in candidate.source_evidence
            ],
            resource_ids=list(
                dict.fromkeys(item.resource_id for item in (model_executions or []))
            ),
            source_block_ids=list(
                dict.fromkeys(item.block_id for item in candidate.source_evidence)
            ),
            source_mention_ids=candidate.source_mentions,
            rule_ids=[candidate.convention_id],
            model_execution_ids=model_execution_ids,
            validation_records=[
                "evidence_text_matches_block",
                "numeric_threshold_in_evidence",
            ],
            evidence=self._evidence(candidate, blocks or []),
            model_details=[
                item.model_dump(mode="json")
                for item in (model_executions or [])
                if item.model_execution_id in model_execution_ids
            ],
        )
        self.store.save(record, record.provenance_id)
        return record

    def get(self, provenance_id: str) -> ProvenanceRecord:
        return self.store.load(provenance_id)

    def create_for_semantic_object(
        self,
        semantic_object: SemanticObject,
        *,
        execution_id: str,
        ground_selection_id: str,
        ground_snapshot_id: str,
        resource_plan_id: str,
        model_execution_ids: list[str],
        model_executions: list | None = None,
    ) -> ProvenanceRecord:
        """Persist object-level provenance without introducing a graph store."""
        record = ProvenanceRecord(
            provenance_id=f"PROV-{uuid.uuid4().hex[:16].upper()}",
            execution_id=execution_id,
            document_id=semantic_object.document_id,
            ground_selection_id=ground_selection_id,
            ground_snapshot_id=ground_snapshot_id,
            resource_plan_id=resource_plan_id,
            object_id=semantic_object.object_id,
            source_pages=[semantic_object.page] if semantic_object.page else [],
            source_offsets=(
                [
                    {
                        "start": semantic_object.offset.start,
                        "end": semantic_object.offset.end,
                    }
                ]
                if semantic_object.offset
                else []
            ),
            resource_ids=list(
                dict.fromkeys(item.resource_id for item in (model_executions or []))
            ),
            source_block_ids=[semantic_object.block_id]
            if semantic_object.block_id
            else [],
            source_mention_ids=list(semantic_object.attributes.get("mention_ids", [])),
            rule_ids=[semantic_object.object_id]
            if semantic_object.object_type.value == "rule"
            else [],
            model_execution_ids=model_execution_ids,
            validation_records=["semantic_object_evidence_present"],
            evidence=[
                {
                    "evidence_id": evidence_id,
                    "page_no": semantic_object.page,
                    "block_id": semantic_object.block_id,
                    "start_offset": semantic_object.offset.start
                    if semantic_object.offset
                    else None,
                    "end_offset": semantic_object.offset.end
                    if semantic_object.offset
                    else None,
                }
                for evidence_id in semantic_object.evidence_ids
            ]
            or (
                [
                    {
                        "evidence_id": semantic_object.object_id,
                        "page_no": semantic_object.page,
                        "block_id": semantic_object.block_id,
                        "start_offset": semantic_object.offset.start
                        if semantic_object.offset
                        else None,
                        "end_offset": semantic_object.offset.end
                        if semantic_object.offset
                        else None,
                        "matched_text": semantic_object.attributes.get("matched_text"),
                    }
                ]
                if semantic_object.object_type.value == "evidence"
                else []
            ),
            model_details=[
                item.model_dump(mode="json")
                for item in (model_executions or [])
                if item.model_execution_id in model_execution_ids
            ],
        )
        self.store.save(record, record.provenance_id)
        return record

    def find_by_convention(self, convention_id: str) -> ProvenanceRecord | None:
        for record in sorted(
            self.store.list(), key=lambda item: item.created_at, reverse=True
        ):
            if convention_id in record.rule_ids:
                return record
        return None

    @staticmethod
    def _evidence(candidate: CodeConventionCandidate, blocks: list) -> list[dict]:
        by_id = {block.block_id: block for block in blocks}
        evidence: list[dict] = []
        for item in candidate.source_evidence:
            block = by_id.get(item.block_id)
            if block is None:
                continue
            evidence.append(
                {
                    "block_id": block.block_id,
                    "page_no": block.page_no,
                    "text": block.text[item.start_offset : item.end_offset],
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                    "metadata": block.metadata,
                }
            )
        return evidence
