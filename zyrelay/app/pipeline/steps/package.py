from zyrelay import __version__
from zyrelay.app.core.config import (
    Settings,
    config_hash,
    configuration_inventory,
    ground_truth_version,
)
from zyrelay.app.models import (
    CandidateStatus,
    CandidateType,
    DocumentStatus,
    SemanticCandidate,
)
from zyrelay.app.models.uom import (
    BOMSection,
    MOMSection,
    ProcessingRecord,
    SemanticObjectSection,
    SOMSection,
    UOMPackage,
)
from zyrelay.app.pipeline.context import ProcessingContext
from zyrelay.app.storage import LocalStorage

from .semantic_steps import business_objects


class BuildUOMPackageStep:
    name = "build_uom_package"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        if context.document is None:
            raise RuntimeError("document is required")
        context.document.status = DocumentStatus.COMPLETED
        context.package = UOMPackage(
            package_id=f"PKG-{context.document.document_id.removeprefix('DOC-')}",
            source=context.document,
            mom=MOMSection(document=context.document, blocks=context.blocks),
            som=SOMSection(
                labels=context.labels,
                mentions=context.mentions,
                semantic_index=context.semantic_index,
                raw_token_index=context.raw_token_index,
                candidates=context.candidates,
                code_conventions=context.code_conventions,
                convention_index=context.convention_index,
            ),
            semantic_objects=SemanticObjectSection(
                objects=context.semantic_objects,
                validation=context.semantic_validation
                or SemanticObjectSection().validation,
            ),
            bom=BOMSection(
                business_objects=[
                    *business_objects(context),
                    *self._team_code_convention_candidates(context),
                ]
            ),
            processing=ProcessingRecord(
                pipeline_version=__version__,
                ground_truth_version=ground_truth_version(self.settings),
                label_config_hash=config_hash(self.settings.label_config),
                business_object_config_hash=config_hash(
                    self.settings.business_object_config
                ),
                code_convention_label_config_hash=config_hash(
                    self.settings.code_convention_label_config
                ),
                code_rule_pattern_config_hash=config_hash(
                    self.settings.code_rule_pattern_config
                ),
                layout=context.model_metadata.get("layout", {}),
                table=context.model_metadata.get("table", {}),
                classifier=context.model_metadata.get("classifier", {}),
                language=context.model_metadata.get("language", {}),
                ner=context.model_metadata.get("ner", {}),
                spell=context.model_metadata.get("spell", {}),
                model_routing=context.model_metadata.get("routing", {}),
                configuration=configuration_inventory(self.settings),
                steps=context.steps,
                warnings=context.warnings,
                errors=context.errors,
            ),
        )
        return context

    @staticmethod
    def _team_code_convention_candidates(
        context: ProcessingContext,
    ) -> list[SemanticCandidate]:
        if context.document is None or not context.code_conventions:
            return []
        convention_ids = [
            convention.convention_id for convention in context.code_conventions
        ]
        mention_ids = list(
            dict.fromkeys(
                mention_id
                for convention in context.code_conventions
                for mention_id in convention.source_mentions
            )
        )
        categories = sorted(
            {convention.category.value for convention in context.code_conventions}
        )
        confidence = sum(
            convention.confidence for convention in context.code_conventions
        ) / len(context.code_conventions)
        return [
            SemanticCandidate(
                candidate_id=(
                    "CAN-TEAM-CONVENTION-"
                    + context.document.document_id.removeprefix("DOC-")
                ),
                candidate_type=CandidateType.BUSINESS_OBJECT,
                name="团队代码规范",
                source_mentions=mention_ids,
                attributes={
                    "type": "TeamCodeConvention",
                    "document_id": context.document.document_id,
                    "convention_ids": convention_ids,
                    "categories": categories,
                    "count": len(convention_ids),
                },
                confidence=confidence,
                ontology_uri="uom://bom/TeamCodeConvention",
                status=CandidateStatus.DETECTED,
            )
        ]


class SaveResultStep:
    name = "save_result"

    def __init__(self, storage: LocalStorage) -> None:
        self.storage = storage

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        if (
            context.document is None
            or context.parsed_document is None
            or context.package is None
        ):
            raise RuntimeError("package construction must run before storage")
        source_path = self.storage.save_source(
            context.document.document_id,
            context.document.file_name,
            context.file_bytes,
        )
        # URI serialization must not depend on the caller supplying an
        # absolute data root (benchmark runners commonly use relative output).
        context.document.source_uri = source_path.resolve().as_uri()
        self.storage.save_prepared(
            context.document.document_id,
            context.parsed_document.pages,
            context.blocks,
        )
        context.package.source = context.document
        context.package.mom.document = context.document
        self.storage.save_package(context.package)
        return context
