from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from zyrelay.app.core.config import load_yaml
from zyrelay.app.models import (
    CandidateStatus,
    CandidateType,
    LabelDefinition,
    LabelMention,
    SemanticCandidate,
)


class BusinessObjectRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    name: str
    ontology_uri: str | None = None
    required_labels: list[str] = Field(default_factory=list)
    optional_labels: list[str] = Field(default_factory=list)
    min_required_matches: int = Field(ge=1)
    candidate_builder: str | None = None


class CandidateBuilder:
    def __init__(self, rules_path: Path) -> None:
        self.rules_path = rules_path

    def load_rules(self) -> list[BusinessObjectRule]:
        return [
            BusinessObjectRule.model_validate(item)
            for item in load_yaml(self.rules_path).get("business_objects", [])
        ]

    def build(
        self,
        labels: list[LabelDefinition],
        mentions: list[LabelMention],
    ) -> list[SemanticCandidate]:
        candidates = self._entity_candidates(labels, mentions)
        candidates.extend(self._business_object_candidates(mentions))
        return candidates

    @staticmethod
    def _entity_candidates(
        labels: list[LabelDefinition], mentions: list[LabelMention]
    ) -> list[SemanticCandidate]:
        entity_codes = {
            label.code: label for label in labels if label.category == "entity"
        }
        result: list[SemanticCandidate] = []
        for mention in mentions:
            label = entity_codes.get(mention.label_code)
            if label is None:
                continue
            result.append(
                SemanticCandidate(
                    candidate_id=f"CAN-{mention.mention_id.removeprefix('MEN-')}",
                    candidate_type=CandidateType.ENTITY,
                    name=mention.normalized_value,
                    source_mentions=[mention.mention_id],
                    attributes={"label_code": mention.label_code},
                    confidence=mention.confidence,
                    ontology_uri=label.ontology_uri,
                    status=CandidateStatus.DETECTED,
                )
            )
        return result

    def _business_object_candidates(
        self, mentions: list[LabelMention]
    ) -> list[SemanticCandidate]:
        by_label: dict[str, list[LabelMention]] = defaultdict(list)
        for mention in mentions:
            by_label[mention.label_code].append(mention)

        result: list[SemanticCandidate] = []
        for rule in self.load_rules():
            if rule.candidate_builder:
                continue
            matched_required = [
                code for code in rule.required_labels if by_label.get(code)
            ]
            if len(matched_required) < rule.min_required_matches:
                continue

            used_codes = matched_required + [
                code for code in rule.optional_labels if by_label.get(code)
            ]
            source = [
                mention
                for code in used_codes
                for mention in by_label[code]
            ]
            attributes = {
                code: self._collapse_values(
                    [mention.normalized_value for mention in by_label[code]]
                )
                for code in used_codes
            }
            confidence = sum(item.confidence for item in source) / len(source)
            identity = "|".join(sorted(item.mention_id for item in source))
            candidate_id = (
                "CAN-" + hashlib.sha256(f"{rule.type}|{identity}".encode()).hexdigest()[:16]
            )
            result.append(
                SemanticCandidate(
                    candidate_id=candidate_id,
                    candidate_type=CandidateType.BUSINESS_OBJECT,
                    name=rule.name,
                    source_mentions=[item.mention_id for item in source],
                    attributes={"type": rule.type, **attributes},
                    confidence=confidence,
                    ontology_uri=rule.ontology_uri,
                    status=CandidateStatus.DETECTED,
                )
            )
        return result

    @staticmethod
    def _collapse_values(values: list[str]) -> str | list[str]:
        unique = list(dict.fromkeys(values))
        return unique[0] if len(unique) == 1 else unique
