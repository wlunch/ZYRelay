from zyrelay.app.core.config import Settings, load_yaml
from zyrelay.app.labeling import LabelRepository, MatcherService
from zyrelay.app.models import CandidateType
from zyrelay.app.pipeline.context import ProcessingContext
from zyrelay.app.semantics import (
    CandidateBuilder,
    NoOpSemanticEnricher,
    OpenAICompatibleSemanticEnricher,
    SemanticIndexBuilder,
)


class MatchLabelsStep:
    name = "match_labels"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = LabelRepository(
            settings.label_config, settings.ground_truth_dir
        )

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.labels = self.repository.load()
        matcher = MatcherService(
            self.repository,
            fuzzy_enabled=self.settings.fuzzy_enabled,
            fuzzy_threshold=self.settings.fuzzy_threshold,
        )
        context.mentions, warnings = matcher.match(context.blocks, context.labels)
        convention_repository = LabelRepository(
            self.settings.code_convention_label_config,
            self.settings.ground_truth_dir,
        )
        convention_labels = convention_repository.load()
        convention_matcher = MatcherService(
            convention_repository,
            fuzzy_enabled=False,
            fuzzy_threshold=self.settings.fuzzy_threshold,
            preserve_cross_label_overlaps=True,
        )
        convention_mentions, convention_warnings = convention_matcher.match(
            context.blocks, convention_labels
        )
        context.labels.extend(convention_labels)
        context.mentions.extend(convention_mentions)
        context.mentions.sort(
            key=lambda item: (item.block_id, item.start_offset, item.label_code)
        )
        warnings.extend(convention_warnings)
        context.warnings.extend(warnings)
        return context


class BuildSemanticIndexStep:
    name = "build_semantic_index"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        builder = SemanticIndexBuilder()
        context.semantic_index = builder.build(context.mentions)
        stopwords = set(
            load_yaml(self.settings.ground_truth_dir / "stopwords.yaml").get(
                "stopwords", []
            )
        )
        context.raw_token_index = builder.build_raw_token_index(
            context.blocks, stopwords
        )
        return context


class BuildSemanticCandidatesStep:
    name = "build_semantic_candidates"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.candidates = CandidateBuilder(
            self.settings.business_object_config
        ).build(context.labels, context.mentions)
        return context


class LLMEnrichmentStep:
    name = "llm_enrichment"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        if not self.settings.llm_enabled:
            enricher = NoOpSemanticEnricher()
        else:
            enricher = OpenAICompatibleSemanticEnricher(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                model=self.settings.llm_model,
            )
        try:
            enriched = enricher.enrich(
                context.document,  # type: ignore[arg-type]
                context.blocks,
                context.labels,
                context.mentions,
            )
            context.candidates.extend(enriched)
        except Exception as exc:
            context.warnings.append(
                f"LLM enrichment 失败但规则结果已保留：{exc}"
            )
        return context


def business_objects(context: ProcessingContext):
    return [
        candidate
        for candidate in context.candidates
        if candidate.candidate_type == CandidateType.BUSINESS_OBJECT
    ]
