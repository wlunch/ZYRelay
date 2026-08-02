from __future__ import annotations

import uuid

from zyrelay.app.conventions import CodeConventionCandidate
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
            source_block_ids=list(
                dict.fromkeys(item.block_id for item in candidate.source_evidence)
            ),
            source_mention_ids=candidate.source_mentions,
            rule_ids=[candidate.convention_id],
            model_execution_ids=model_execution_ids,
            validation_records=["evidence_text_matches_block", "numeric_threshold_in_evidence"],
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
                    "text": block.text[item.start_offset:item.end_offset],
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                    "metadata": block.metadata,
                }
            )
        return evidence
