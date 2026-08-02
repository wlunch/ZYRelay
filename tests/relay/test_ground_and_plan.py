from zyrelay.ground import GroundChooseService


def test_ground_choose_explicit_snapshot_and_plan(relay_service) -> None:
    chooser = GroundChooseService(relay_service.ground_repository)
    selection, profile, inherited = chooser.choose(
        execution_id="EXEC-0000000000000001",
        enterprise_id="default",
        team_id=None,
        project_id=None,
        mode="contract",
        document_type="pdf",
        explicit_ground_profile_id="code-convention-sampling",
    )
    snapshot = relay_service.ground_repository.create_snapshot(
        snapshot_id="GSNAP-000000000000001",
        execution_id=selection.execution_id,
        profile=profile,
        inherited=inherited,
    )
    plan = relay_service.resource_planner.build(
        execution_id=selection.execution_id,
        enterprise_id="default",
        requested_profile_id=None,
        recommended_profile_id=profile.resource_profile_id,
    )
    assert selection.selection_reason == "explicit_request"
    assert selection.rejected_profiles
    assert snapshot.resolved_hash
    assert relay_service.ground_repository.snapshot_store.load(snapshot.snapshot_id) == snapshot
    assert plan.plan_hash
    assert plan.bindings["ocr"] == "noop-ocr"
    assert any(item.fallback_used for item in plan.selection_records if item.capability == "ocr")


def test_ground_choose_uses_mode_default(relay_service) -> None:
    selection, profile, _ = GroundChooseService(relay_service.ground_repository).choose(
        execution_id="EXEC-0000000000000002",
        enterprise_id="default",
        team_id=None,
        project_id=None,
        mode="contract",
        document_type="pdf",
        explicit_ground_profile_id=None,
    )
    assert selection.selection_reason == "mode_default"
    assert profile.profile_id == "contract-default"
