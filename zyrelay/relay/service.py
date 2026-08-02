from __future__ import annotations

import uuid
from pathlib import Path

from zyrelay.app.core.config import Settings
from zyrelay.ground import GroundChooseService, GroundRepository
from zyrelay.provenance import ProvenanceService
from zyrelay.resources import ResourcePlanner, create_default_registry

from .models import ModelExecutionRecord, RelayExecution, RelayRequest, RelayResult
from .pipeline import SimpleRelayPipeline
from .repository import JsonRecordRepository


class RelayService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.ground_repository = GroundRepository(self.settings)
        self.ground_chooser = GroundChooseService(self.ground_repository)
        self.resources = create_default_registry()
        self.resource_planner = ResourcePlanner(self.settings, self.resources)
        self.provenance = ProvenanceService(self.settings.data_root)
        self.execution_store = JsonRecordRepository(
            self.settings.data_root / "relay_executions", RelayExecution
        )
        self.model_execution_store = JsonRecordRepository(
            self.settings.data_root / "model_executions", ModelExecutionRecord
        )
        self.pipeline = SimpleRelayPipeline(
            settings=self.settings,
            ground_repository=self.ground_repository,
            ground_chooser=self.ground_chooser,
            resource_registry=self.resources,
            resource_planner=self.resource_planner,
            provenance=self.provenance,
            model_execution_store=self.model_execution_store,
        )

    def process(self, request: RelayRequest) -> RelayResult:
        execution = RelayExecution(
            execution_id=f"EXEC-{uuid.uuid4().hex[:16].upper()}",
            request_id=request.request_id or f"REQ-{uuid.uuid4().hex[:16].upper()}",
            enterprise_id=request.enterprise_id,
            team_id=request.team_id,
            project_id=request.project_id,
            mode=request.mode,
            metadata={key: value for key, value in request.metadata.items() if not key.startswith("_")},
        )
        try:
            package, selection, snapshot, plan = self.pipeline.execute(request, execution)
            result = self._result_payload(request, execution, package, selection, snapshot, plan)
            return result
        finally:
            self.execution_store.save(execution, execution.execution_id)

    def get_execution(self, execution_id: str) -> RelayExecution:
        return self.execution_store.load(execution_id)

    def get_ground(self, execution_id: str) -> dict:
        execution = self.get_execution(execution_id)
        if not execution.ground_selection_id or not execution.ground_snapshot_id:
            raise FileNotFoundError(execution_id)
        return {
            "selection": self.ground_repository.selection_store.load(execution.ground_selection_id),
            "snapshot": self.ground_repository.snapshot_store.load(execution.ground_snapshot_id),
        }

    def get_resources(self, execution_id: str):
        execution = self.get_execution(execution_id)
        if not execution.resource_plan_id:
            raise FileNotFoundError(execution_id)
        return self.resource_planner.store.load(execution.resource_plan_id)

    def get_models(self, execution_id: str) -> list[ModelExecutionRecord]:
        return [
            item for item in self.model_execution_store.list()
            if item.execution_id == execution_id
        ]

    def get_provenance(self, provenance_id: str):
        return self.provenance.get(provenance_id)

    def get_convention_provenance(self, convention_id: str):
        result = self.provenance.find_by_convention(convention_id)
        if result is None:
            raise FileNotFoundError(convention_id)
        return result

    @staticmethod
    def _result_payload(request, execution, package, selection, snapshot, plan) -> RelayResult:
        document = package.source.model_dump(mode="json", exclude={"source_uri"})
        document["source_uri"] = f"relay://executions/{execution.execution_id}/source"
        payload = {
            "document": document,
            "code_conventions": [item.model_dump(mode="json") for item in package.som.code_conventions],
            "convention_index": package.som.convention_index.model_dump(mode="json"),
            "business_objects": [item.model_dump(mode="json") for item in package.bom.business_objects],
            "uom_artifact": execution.artifacts[0] if execution.artifacts else {},
        }
        if request.output_detail == "full":
            payload.update(
                {
                    "blocks": [item.model_dump(mode="json") for item in package.mom.blocks],
                    "mentions": [item.model_dump(mode="json") for item in package.som.mentions],
                    "semantic_index": {
                        key: value.model_dump(mode="json")
                        for key, value in package.som.semantic_index.items()
                    },
                    "step_records": [item.model_dump(mode="json") for item in execution.steps],
                    "model_executions": [item.model_dump(mode="json") for item in execution.model_executions],
                }
            )
        return RelayResult(
            execution_id=execution.execution_id,
            status=execution.status,
            document_id=execution.document_id,
            ground={
                "profile_id": selection.selected_profile_id,
                "profile_version": selection.selected_profile_version,
                "selection_reason": selection.selection_reason,
                "snapshot_id": snapshot.snapshot_id,
                "resolved_hash": snapshot.resolved_hash,
            },
            resources={
                "plan_id": plan.plan_id,
                "bindings": plan.bindings,
                "fallbacks_used": [
                    item.capability for item in plan.selection_records if item.fallback_used
                ],
            },
            result=payload,
            warnings=list(dict.fromkeys(execution.warnings)),
            errors=execution.errors,
            metrics=execution.metrics,
        )
