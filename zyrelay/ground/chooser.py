from __future__ import annotations

import hashlib
import json
import uuid

from .models import CandidateProfile, GroundSelection
from .repository import GroundRepository


class GroundChooseService:
    def __init__(self, repository: GroundRepository) -> None:
        self.repository = repository

    def choose(
        self,
        *,
        execution_id: str,
        enterprise_id: str,
        team_id: str | None,
        project_id: str | None,
        mode: str,
        document_type: str,
        explicit_ground_profile_id: str | None,
    ) -> tuple[GroundSelection, object, list[object]]:
        profiles = self.repository.profiles()
        bindings = self.repository.bindings()
        selected_id, reason = self._select_id(
            bindings,
            enterprise_id=enterprise_id,
            team_id=team_id,
            project_id=project_id,
            mode=mode,
            explicit=explicit_ground_profile_id,
        )
        profile, inherited = self.repository.resolve_profile(selected_id)
        candidates: list[CandidateProfile] = []
        for priority, item in enumerate(
            sorted(profiles.values(), key=lambda p: p.profile_id), 1
        ):
            matched = item.profile_id == profile.profile_id
            candidates.append(
                CandidateProfile(
                    profile_id=item.profile_id,
                    version=item.version,
                    matched=matched,
                    rejection_reason=None if matched else "lower_priority_or_not_bound",
                    priority=priority,
                )
            )
        source_files, source_hashes = self.repository.profile_sources(inherited)
        resolved_hash = hashlib.sha256(
            json.dumps(
                profile.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        selection = GroundSelection(
            selection_id=f"GSEL-{uuid.uuid4().hex[:16].upper()}",
            execution_id=execution_id,
            requested_profile_id=explicit_ground_profile_id,
            selected_profile_id=profile.profile_id,
            selected_profile_version=profile.version,
            selection_reason=reason,
            candidate_profiles=candidates,
            rejected_profiles=[item for item in candidates if not item.matched],
            inherited_profiles=[item.profile_id for item in inherited[:-1]],
            source_files=source_files,
            source_hashes=source_hashes,
            resolved_profile_hash=resolved_hash,
        )
        self.repository.selection_store.save(selection, selection.selection_id)
        return selection, profile, inherited

    @staticmethod
    def _select_id(
        bindings: dict,
        *,
        enterprise_id: str,
        team_id: str | None,
        project_id: str | None,
        mode: str,
        explicit: str | None,
    ) -> tuple[str, str]:
        if explicit:
            return explicit, "explicit_request"
        for key, value, reason in (
            ("projects", project_id, "project_binding"),
            ("teams", team_id, "team_binding"),
            ("enterprises", enterprise_id, "enterprise_binding"),
            ("modes", mode, "mode_default"),
        ):
            binding = (bindings.get("bindings", {}).get(key, {}) or {}).get(value)
            if binding:
                return str(binding), reason
        default = bindings.get("global_default")
        if not default:
            raise ValueError("未配置 global_default Ground Profile")
        return str(default), "global_default"
