from zyrelay.app.conventions.candidate_builder import (
    CodeConventionCandidateBuilder,
)
from zyrelay.app.conventions.candidate_validator import (
    ConventionCandidateValidator,
)
from zyrelay.app.conventions.config_repository import ConventionConfigRepository
from zyrelay.app.conventions.index_builder import ConventionIndexBuilder
from zyrelay.app.conventions.section_detector import ConventionSectionDetector
from zyrelay.app.core.config import Settings
from zyrelay.app.pipeline.context import ProcessingContext


class BuildConventionSectionsStep:
    name = "build_convention_sections"

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.convention_sections = ConventionSectionDetector().detect(context.blocks)
        return context


class ExtractConventionCandidatesStep:
    name = "extract_convention_candidates"

    def __init__(self, settings: Settings) -> None:
        self.config = ConventionConfigRepository(
            settings.code_rule_pattern_config
        ).load()

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.code_conventions = CodeConventionCandidateBuilder(self.config).build(
            context.convention_sections,
            context.blocks,
            context.mentions,
        )
        return context


class ValidateConventionCandidatesStep:
    name = "validate_convention_candidates"

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.code_conventions, warnings = ConventionCandidateValidator().validate(
            context.code_conventions,
            context.blocks,
        )
        context.warnings.extend(warnings)
        return context


class BuildConventionIndexStep:
    name = "build_convention_index"

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.convention_index = ConventionIndexBuilder().build(
            context.code_conventions
        )
        return context
