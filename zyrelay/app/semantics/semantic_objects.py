"""Rule-first conversion from Relay outputs into portable semantic objects."""

from __future__ import annotations

import hashlib
import json

from zyrelay.app.models import (
    CandidateStatus,
    CandidateType,
    LabelCategory,
    SemanticObject,
    SemanticObjectStatus,
    SemanticObjectType,
    SemanticOffset,
    SemanticValidationResult,
)
from zyrelay.app.pipeline.context import ProcessingContext


class BuildSemanticObjectsStep:
    """Build only explicit, evidence-supported objects; never infer facts."""

    name = "build_semantic_objects"

    def __init__(
        self,
        *,
        ground_snapshot_id: str | None = None,
        resource_plan_id: str | None = None,
    ) -> None:
        self.ground_snapshot_id = ground_snapshot_id
        self.resource_plan_id = resource_plan_id

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        if context.document is None:
            raise RuntimeError("semantic objects require a document")
        document = context.document
        labels = {label.code: label for label in context.labels}
        blocks = {block.block_id: block for block in context.blocks}
        objects: list[SemanticObject] = []
        evidence_by_key: dict[str, SemanticObject] = {}

        def stable_id(
            object_type: SemanticObjectType,
            name: str,
            page: int | None,
            block_id: str | None,
            offset: tuple[int, int] | None,
        ) -> str:
            canonical = json.dumps(
                {
                    "document_hash": document.sha256,
                    "object_type": object_type.value,
                    "name": name.strip().casefold(),
                    "page": page,
                    "block": block_id,
                    "offset": offset,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return (
                "SOBJ-"
                + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24].upper()
            )

        def evidence(
            *,
            block_id: str,
            start: int,
            end: int,
            matched_text: str,
            confidence: float,
            mention_id: str | None = None,
        ) -> SemanticObject | None:
            block = blocks.get(block_id)
            if block is None or end <= start:
                return None
            key = f"{block_id}:{start}:{end}:{matched_text}"
            if key in evidence_by_key:
                existing = evidence_by_key[key]
                if mention_id and mention_id not in existing.attributes["mention_ids"]:
                    existing.attributes["mention_ids"].append(mention_id)
                return existing
            page = block.page_no
            object_id = stable_id(
                SemanticObjectType.EVIDENCE, matched_text, page, block_id, (start, end)
            )
            metadata = block.metadata
            item = SemanticObject(
                object_id=object_id,
                object_type=SemanticObjectType.EVIDENCE,
                name="Evidence",
                attributes={
                    "matched_text": matched_text,
                    "bbox": metadata.get("bbox"),
                    "polygon": metadata.get("polygon"),
                    "ocr_confidence": metadata.get("ocr_confidence"),
                    "parser": document.parser,
                    "plugin": metadata.get("resource_id"),
                    "model_execution": metadata.get("model_execution_id"),
                    "ground_snapshot_id": self.ground_snapshot_id,
                    "mention_ids": [mention_id] if mention_id else [],
                },
                confidence=confidence,
                status=SemanticObjectStatus.DETECTED,
                document_id=document.document_id,
                page=page,
                block_id=block_id,
                offset=SemanticOffset(start=start, end=end),
                provenance_id="PROV-" + object_id.removeprefix("SOBJ-"),
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
            )
            evidence_by_key[key] = item
            objects.append(item)
            return item

        # Every non-empty document gets a document object anchored to its first
        # text block, rather than a generated, unverifiable document summary.
        anchor = next((block for block in context.blocks if block.text.strip()), None)
        anchor_evidence = (
            evidence(
                block_id=anchor.block_id,
                start=0,
                end=min(len(anchor.text), max(1, len(anchor.text))),
                matched_text=anchor.text,
                confidence=1.0,
            )
            if anchor
            else None
        )
        document_object_id = stable_id(
            SemanticObjectType.DOCUMENT_OBJECT,
            document.file_name,
            anchor.page_no if anchor else None,
            anchor.block_id if anchor else None,
            (0, len(anchor.text)) if anchor else None,
        )
        objects.append(
            SemanticObject(
                object_id=document_object_id,
                object_type=SemanticObjectType.DOCUMENT_OBJECT,
                name=document.file_name,
                attributes={
                    "file_type": document.file_type,
                    "sha256": document.sha256,
                    "page_count": document.page_count,
                },
                confidence=1.0,
                document_id=document.document_id,
                page=anchor.page_no if anchor else None,
                block_id=anchor.block_id if anchor else None,
                offset=SemanticOffset(start=0, end=len(anchor.text))
                if anchor
                else None,
                provenance_id="PROV-" + document_object_id.removeprefix("SOBJ-"),
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
                evidence_ids=[anchor_evidence.object_id] if anchor_evidence else [],
                category="document",
            )
        )

        entity_objects: list[SemanticObject] = []
        mention_evidence_ids: dict[str, str] = {}
        for mention in context.mentions:
            definition = labels.get(mention.label_code)
            item_evidence = evidence(
                block_id=mention.block_id,
                start=mention.start_offset,
                end=mention.end_offset,
                matched_text=mention.matched_text,
                confidence=mention.confidence,
                mention_id=mention.mention_id,
            )
            if item_evidence is None:
                continue
            mention_evidence_ids[mention.mention_id] = item_evidence.object_id
            is_entity = (
                definition is not None and definition.category == LabelCategory.ENTITY
            )
            object_type = (
                SemanticObjectType.ENTITY
                if is_entity
                else SemanticObjectType.OBSERVATION
            )
            object_name = mention.normalized_value or mention.matched_text
            item = SemanticObject(
                object_id=stable_id(
                    object_type,
                    object_name,
                    mention.page_no,
                    mention.block_id,
                    (mention.start_offset, mention.end_offset),
                ),
                object_type=object_type,
                name=object_name,
                attributes={
                    "type": definition.value_type if definition else "unknown",
                    "aliases": [mention.matched_text],
                    "label_code": mention.label_code,
                    "match_method": mention.match_method.value,
                    "evidence": [item_evidence.object_id],
                },
                confidence=mention.confidence,
                document_id=document.document_id,
                page=mention.page_no,
                block_id=mention.block_id,
                offset=SemanticOffset(
                    start=mention.start_offset, end=mention.end_offset
                ),
                provenance_id="PROV-"
                + stable_id(
                    object_type,
                    object_name,
                    mention.page_no,
                    mention.block_id,
                    (mention.start_offset, mention.end_offset),
                ).removeprefix("SOBJ-"),
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
                evidence_ids=[item_evidence.object_id],
                category=definition.category.value if definition else None,
            )
            objects.append(item)
            if is_entity:
                entity_objects.append(item)

        # NER remains an observation unless a grounded label already confirms it.
        for block in context.blocks:
            for detected in block.entities:
                start, end = int(detected.get("start", 0)), int(detected.get("end", 0))
                text = str(detected.get("text", ""))
                item_evidence = evidence(
                    block_id=block.block_id,
                    start=start,
                    end=end,
                    matched_text=text,
                    confidence=float(detected.get("score", 0.0)),
                )
                if item_evidence is None:
                    continue
                item = SemanticObject(
                    object_id=stable_id(
                        SemanticObjectType.OBSERVATION,
                        text,
                        block.page_no,
                        block.block_id,
                        (start, end),
                    ),
                    object_type=SemanticObjectType.OBSERVATION,
                    name=text,
                    attributes={
                        "type": detected.get("label", "unknown"),
                        "source": "ner",
                        "evidence": [item_evidence.object_id],
                    },
                    confidence=float(detected.get("score", 0.0)),
                    document_id=document.document_id,
                    page=block.page_no,
                    block_id=block.block_id,
                    offset=SemanticOffset(start=start, end=end),
                    provenance_id="PROV-"
                    + stable_id(
                        SemanticObjectType.OBSERVATION,
                        text,
                        block.page_no,
                        block.block_id,
                        (start, end),
                    ).removeprefix("SOBJ-"),
                    ground_snapshot_id=self.ground_snapshot_id,
                    resource_plan_id=self.resource_plan_id,
                    evidence_ids=[item_evidence.object_id],
                    category="ner",
                )
                if item.object_id not in {existing.object_id for existing in objects}:
                    objects.append(item)

        rule_objects: list[SemanticObject] = []
        for convention in context.code_conventions:
            refs = [
                evidence(
                    block_id=item.block_id,
                    start=item.start_offset,
                    end=item.end_offset,
                    matched_text=item.evidence_text,
                    confidence=convention.confidence,
                )
                for item in convention.source_evidence
            ]
            evidence_ids = [item.object_id for item in refs if item]
            if not evidence_ids:
                continue
            first = next(item for item in refs if item)
            expression = convention.rule_expression
            attributes = {
                "target": expression.target if expression else None,
                "operator": expression.operator.value if expression else None,
                "value": expression.expected if expression else None,
                "severity": convention.metadata.get("severity"),
                "category": convention.category.value,
                "language": convention.language,
                "tool": convention.suggested_tools,
                "requirement_level": convention.requirement_level.value,
                "candidate_id": convention.convention_id,
                "evidence": evidence_ids,
            }
            item = SemanticObject(
                object_id=stable_id(
                    SemanticObjectType.RULE,
                    convention.title,
                    first.page,
                    first.block_id,
                    (first.offset.start, first.offset.end) if first.offset else None,
                ),
                object_type=SemanticObjectType.RULE,
                name=convention.title,
                attributes=attributes,
                confidence=convention.confidence,
                status=_status(convention.status.value),
                document_id=document.document_id,
                page=first.page,
                block_id=first.block_id,
                offset=first.offset,
                provenance_id=convention.provenance_id
                or "PROV-" + convention.convention_id,
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
                evidence_ids=evidence_ids,
                category=convention.category.value,
                language=convention.language[0] if convention.language else None,
            )
            objects.append(item)
            rule_objects.append(item)

        business_objects: list[SemanticObject] = []
        for candidate in context.candidates:
            candidate_evidence_ids = [
                mention_evidence_ids[mention_id]
                for mention_id in candidate.source_mentions
                if mention_id in mention_evidence_ids
            ]
            if candidate.candidate_type == CandidateType.ENTITY:
                if not candidate_evidence_ids:
                    continue
                source = next(
                    item
                    for item in objects
                    if item.object_id == candidate_evidence_ids[0]
                )
                item = SemanticObject(
                    object_id=stable_id(
                        SemanticObjectType.ENTITY,
                        candidate.name,
                        source.page,
                        source.block_id,
                        (source.offset.start, source.offset.end)
                        if source.offset
                        else None,
                    ),
                    object_type=SemanticObjectType.ENTITY,
                    name=candidate.name,
                    attributes={
                        **candidate.attributes,
                        "candidate_id": candidate.candidate_id,
                        "aliases": candidate.attributes.get("aliases", []),
                        "evidence": candidate_evidence_ids,
                    },
                    confidence=candidate.confidence,
                    status=_status(candidate.status.value),
                    document_id=document.document_id,
                    page=source.page,
                    block_id=source.block_id,
                    offset=source.offset,
                    provenance_id="PROV-" + candidate.candidate_id,
                    ground_snapshot_id=self.ground_snapshot_id,
                    resource_plan_id=self.resource_plan_id,
                    evidence_ids=candidate_evidence_ids,
                    category="candidate_entity",
                )
                if item.object_id not in {existing.object_id for existing in objects}:
                    objects.append(item)
                    entity_objects.append(item)
                continue
            if candidate.candidate_type == CandidateType.EVENT:
                if not candidate_evidence_ids:
                    continue
                source = next(
                    item
                    for item in objects
                    if item.object_id == candidate_evidence_ids[0]
                )
                objects.append(
                    SemanticObject(
                        object_id=stable_id(
                            SemanticObjectType.EVENT,
                            candidate.name,
                            source.page,
                            source.block_id,
                            (source.offset.start, source.offset.end)
                            if source.offset
                            else None,
                        ),
                        object_type=SemanticObjectType.EVENT,
                        name=candidate.name,
                        attributes={
                            **candidate.attributes,
                            "candidate_id": candidate.candidate_id,
                            "timestamp": candidate.attributes.get("timestamp"),
                            "participants": candidate.attributes.get(
                                "participants", []
                            ),
                            "evidence": candidate_evidence_ids,
                        },
                        confidence=candidate.confidence,
                        status=_status(candidate.status.value),
                        document_id=document.document_id,
                        page=source.page,
                        block_id=source.block_id,
                        offset=source.offset,
                        provenance_id="PROV-" + candidate.candidate_id,
                        ground_snapshot_id=self.ground_snapshot_id,
                        resource_plan_id=self.resource_plan_id,
                        evidence_ids=candidate_evidence_ids,
                        category="event",
                    )
                )
                continue
            if candidate.candidate_type == CandidateType.RELATION:
                source_id = candidate.attributes.get("source_object_id")
                target_id = candidate.attributes.get("target_object_id")
                known_ids = {item.object_id for item in objects}
                if (
                    not candidate_evidence_ids
                    or source_id not in known_ids
                    or target_id not in known_ids
                ):
                    context.warnings.append(
                        f"relation candidate {candidate.candidate_id} omitted: explicit endpoints or evidence missing"
                    )
                    continue
                source = next(item for item in objects if item.object_id == source_id)
                objects.append(
                    SemanticObject(
                        object_id=stable_id(
                            SemanticObjectType.RELATION,
                            candidate.name,
                            source.page,
                            source.block_id,
                            (source.offset.start, source.offset.end)
                            if source.offset
                            else None,
                        ),
                        object_type=SemanticObjectType.RELATION,
                        name=candidate.name,
                        attributes={
                            **candidate.attributes,
                            "candidate_id": candidate.candidate_id,
                            "evidence": candidate_evidence_ids,
                        },
                        confidence=candidate.confidence,
                        status=_status(candidate.status.value),
                        document_id=document.document_id,
                        page=source.page,
                        block_id=source.block_id,
                        offset=source.offset,
                        provenance_id="PROV-" + candidate.candidate_id,
                        ground_snapshot_id=self.ground_snapshot_id,
                        resource_plan_id=self.resource_plan_id,
                        evidence_ids=candidate_evidence_ids,
                        source_object_id=source_id,
                        target_object_id=target_id,
                        category="relation",
                    )
                )
                continue
            if candidate.candidate_type != CandidateType.BUSINESS_OBJECT:
                continue
            evidence_ids = candidate_evidence_ids
            if not evidence_ids and anchor_evidence:
                evidence_ids = [anchor_evidence.object_id]
            item = SemanticObject(
                object_id=stable_id(
                    SemanticObjectType.BUSINESS_OBJECT,
                    candidate.name,
                    anchor.page_no if anchor else None,
                    anchor.block_id if anchor else None,
                    (0, len(anchor.text)) if anchor else None,
                ),
                object_type=SemanticObjectType.BUSINESS_OBJECT,
                name=candidate.name,
                attributes={
                    **candidate.attributes,
                    "candidate_id": candidate.candidate_id,
                    "semantic_object_ids": evidence_ids,
                    "evidence": evidence_ids,
                },
                confidence=candidate.confidence,
                status=_status(candidate.status.value),
                document_id=document.document_id,
                page=anchor.page_no if anchor else None,
                block_id=anchor.block_id if anchor else None,
                offset=SemanticOffset(start=0, end=len(anchor.text))
                if anchor
                else None,
                provenance_id="PROV-" + candidate.candidate_id,
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
                evidence_ids=evidence_ids,
                category="business_object",
            )
            objects.append(item)
            business_objects.append(item)

        # Only deterministic, source-backed relations are emitted.
        relations: list[SemanticObject] = []
        for item in [*entity_objects, *rule_objects, *business_objects]:
            if not item.evidence_ids:
                continue
            relation_name = (
                "defined_by"
                if item.object_type != SemanticObjectType.BUSINESS_OBJECT
                else "supported_by"
            )
            relation = _relation(
                stable_id=stable_id,
                source=item,
                target_id=document_object_id,
                name=relation_name,
                document_id=document.document_id,
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
            )
            relations.append(relation)
        # ``target`` is emitted by the deterministic convention rule parser.
        # It is therefore safe to represent it as an observation and connect a
        # Rule via ``applies_to`` without inventing a class/API/etc.
        for rule in rule_objects:
            target_name = rule.attributes.get("target")
            if not target_name or not rule.evidence_ids:
                continue
            target = SemanticObject(
                object_id=stable_id(
                    SemanticObjectType.OBSERVATION,
                    str(target_name),
                    rule.page,
                    rule.block_id,
                    (rule.offset.start, rule.offset.end) if rule.offset else None,
                ),
                object_type=SemanticObjectType.OBSERVATION,
                name=str(target_name),
                attributes={
                    "type": "rule_target",
                    "source_rule_id": rule.object_id,
                    "evidence": rule.evidence_ids,
                },
                confidence=rule.confidence,
                document_id=document.document_id,
                page=rule.page,
                block_id=rule.block_id,
                offset=rule.offset,
                provenance_id=rule.provenance_id,
                ground_snapshot_id=self.ground_snapshot_id,
                resource_plan_id=self.resource_plan_id,
                evidence_ids=rule.evidence_ids,
                category="rule_target",
                language=rule.language,
            )
            if target.object_id not in {existing.object_id for existing in objects}:
                objects.append(target)
            relations.append(
                _relation(
                    stable_id=stable_id,
                    source=rule,
                    target_id=target.object_id,
                    name="applies_to",
                    document_id=document.document_id,
                    ground_snapshot_id=self.ground_snapshot_id,
                    resource_plan_id=self.resource_plan_id,
                )
            )
        objects.extend(relations)
        context.semantic_objects = sorted(
            objects, key=lambda item: (item.object_type.value, item.object_id)
        )
        context.semantic_validation = validate_semantic_objects(
            context.semantic_objects
        )
        if not context.semantic_validation.valid:
            context.warnings.extend(context.semantic_validation.errors)
        return context


def _relation(
    *,
    stable_id,
    source: SemanticObject,
    target_id: str,
    name: str,
    document_id: str,
    ground_snapshot_id: str | None,
    resource_plan_id: str | None,
) -> SemanticObject:
    offset = (source.offset.start, source.offset.end) if source.offset else None
    object_id = stable_id(
        SemanticObjectType.RELATION,
        f"{source.object_id}:{name}:{target_id}",
        source.page,
        source.block_id,
        offset,
    )
    return SemanticObject(
        object_id=object_id,
        object_type=SemanticObjectType.RELATION,
        name=name,
        attributes={"relation_type": name, "evidence": source.evidence_ids},
        confidence=source.confidence,
        document_id=document_id,
        page=source.page,
        block_id=source.block_id,
        offset=source.offset,
        provenance_id=source.provenance_id,
        ground_snapshot_id=ground_snapshot_id,
        resource_plan_id=resource_plan_id,
        evidence_ids=source.evidence_ids,
        source_object_id=source.object_id,
        target_object_id=target_id,
        category=name,
        language=source.language,
    )


def _status(value: str) -> SemanticObjectStatus:
    return (
        SemanticObjectStatus.CONFIRMED
        if value == CandidateStatus.CONFIRMED.value or value == "confirmed"
        else SemanticObjectStatus.REJECTED
        if value == "rejected"
        else SemanticObjectStatus.DETECTED
    )


def validate_semantic_objects(
    objects: list[SemanticObject],
) -> SemanticValidationResult:
    ids = {item.object_id for item in objects}
    errors: list[str] = []
    for item in objects:
        if item.object_type != SemanticObjectType.EVIDENCE and not item.evidence_ids:
            errors.append(f"{item.object_id}: missing evidence")
        if not item.provenance_id:
            errors.append(f"{item.object_id}: missing provenance")
        if item.object_type == SemanticObjectType.RELATION and (
            not item.source_object_id
            or not item.target_object_id
            or item.source_object_id not in ids
            or item.target_object_id not in ids
        ):
            errors.append(f"{item.object_id}: invalid relation endpoints")
        if item.object_type == SemanticObjectType.BUSINESS_OBJECT:
            refs = item.attributes.get("semantic_object_ids", [])
            if any(reference not in ids for reference in refs):
                errors.append(f"{item.object_id}: invalid business object references")
    return SemanticValidationResult(
        valid=not errors,
        object_count=len(objects),
        relation_count=sum(
            item.object_type == SemanticObjectType.RELATION for item in objects
        ),
        evidence_count=sum(
            item.object_type == SemanticObjectType.EVIDENCE for item in objects
        ),
        errors=errors,
    )
