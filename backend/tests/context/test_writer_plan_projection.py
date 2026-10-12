"""Lossless Writer projection keeps immutable snapshots and historical prompts intact."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from novel_os.context.engine import ContextEngine
from novel_os.context.policies import ContextFilter, TokenBudgetService
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.context import (
    CandidateBatch,
    ContextRequest,
    ExclusionReason,
    KnowledgeScope,
    SourceType,
)
from novel_os.domain.enums import Status
from novel_os.prompts.contracts import canonical
from tests.context.test_context import item


@pytest.fixture
def writer_request():
    return ContextRequest(
        project_id=uuid4(),
        task_id=uuid4(),
        chapter_id=uuid4(),
        task_type="WRITE_CHAPTER",
        workflow_state_version=1,
    )


def plan_item(request, body):
    return item(
        request,
        selector_id="approved-plan",
        source_type=SourceType.CHAPTER_PLAN,
        payload_json=canonical(body),
    )


def package(request, selected):
    profile = ContextProfileRegistry().for_task(request.task_type)
    # Only the Plan selector is relevant to the projection, not required input retrieval.
    profile = profile.model_copy(
        update={
            "selectors": tuple(s for s in profile.selectors if s.selector_id == "approved-plan")
        }
    )
    built = ContextEngine().build(request, profile, CandidateBatch((selected,)))
    assert built.status == "READY"
    return built.package


def test_exact_plan_duplicates_are_removed_only_from_model_projection(writer_request):
    planning = {
        "objective": "核查记录的出处，不把制定计划写成发现。",
        "constraints": ["保持限知视角"],
        "character_progression": ["由抗拒到有条件地合作"],
        "plot_progression": ["开始翻查原始条目"],
        "ending_state": "两人实际开始核查",
        "scenes": [{"id": "S1", "purpose": "在分歧下选择共同核查"}],
        "source_refs": [{"source_type": "CHAPTER_VERSION", "logical_id": "source", "version": 4}],
        "assumptions": [{"text": "没有得到新的事实"}],
    }
    body = {
        "planning": planning,
        "objective": planning["objective"],
        "constraints": planning["constraints"],
        "character_progression": {"items": planning["character_progression"]},
        "plot_progression": {"items": planning["plot_progression"]},
        "ending_state": {"description": planning["ending_state"]},
        "scene_plans": planning["scenes"],
        "source_refs": planning["source_refs"],
        "unmapped_metadata": {"purpose": "retain provenance"},
    }
    selected = plan_item(writer_request, body)
    snapshot = package(writer_request, selected)
    original = ContextSerializer.snapshot(snapshot)
    serialized = ContextSerializer.serialize(snapshot)
    actual = serialized["items"][0]["structured_payload"]
    assert actual == {
        "planning": planning,
        "unmapped_metadata": {"purpose": "retain provenance"},
    }
    assert selected.structured_payload == body
    assert ContextSerializer.snapshot(snapshot) == original
    assert ContextSerializer.hash(snapshot) == snapshot.package_hash
    assert serialized["items"][0]["source_id"] == str(selected.source_id)
    assert serialized["items"][0]["source_version"] == selected.source_version
    assert serialized["items"][0]["authority_level"] == selected.authority_level
    assert serialized["items"][0]["provenance"] == list(selected.provenance)


@pytest.mark.parametrize(
    "name,top,nested",
    [
        ("objective", "current objective", "different objective"),
        ("constraints", ["one constraint"], ["another constraint"]),
        ("scene_plans", [{"id": "S1"}], [{"id": "S2"}]),
        ("source_refs", [{"id": "current"}], [{"id": "another"}]),
        ("character_progression", {"items": ["one"], "note": "keep"}, ["one"]),
        ("plot_progression", {"items": ["one"]}, ["another"]),
        ("ending_state", {"description": "one", "note": "keep"}, "one"),
        ("confidence", 1, True),
    ],
)
def test_different_values_and_extra_wrapper_metadata_are_preserved(
    writer_request, name, top, nested
):
    target = "scenes" if name == "scene_plans" else name
    body = {name: top, "planning": {target: nested}}
    snapshot = package(writer_request, plan_item(writer_request, body))
    assert ContextSerializer.serialize(snapshot)["items"][0]["structured_payload"] == body


@pytest.mark.parametrize(
    "name,value",
    [
        ("scene_plans", [{"id": "S1"}]),
        ("character_progression", {"items": ["one"], "note": "same metadata"}),
        ("ending_state", {"description": "one", "note": "same metadata"}),
    ],
)
def test_identical_nested_wrappers_and_scene_name_preserve_the_complete_value(
    writer_request, name, value
):
    body = {name: value, "planning": {name: value}}
    snapshot = package(writer_request, plan_item(writer_request, body))
    assert ContextSerializer.serialize(snapshot)["items"][0]["structured_payload"] == {
        "planning": {name: value}
    }


def test_v7_and_nonwriter_projection_remain_unchanged(writer_request):
    registry = ContextProfileRegistry()
    previous = registry.resolve("CP-005", 7)
    current = registry.for_task("WRITE_CHAPTER")
    assert current.version == 8
    assert previous.profile_hash == (
        "481c9afef0996768c563e4c04dca50eea58b80f89bcc43649d01d908ef0e6858"
    )
    assert previous.selectors == current.selectors
    body = {"objective": "unchanged", "planning": {"objective": "unchanged"}}
    selected = plan_item(writer_request, body)
    for request, profile in (
        (writer_request, previous),
        (replace(writer_request, task_type="REVIEW_CHAPTER_NARRATIVE"), current),
        (writer_request, current.model_copy(update={"profile_id": "CP-OTHER"})),
    ):
        actual = ContextSerializer.payload(request, profile, (selected,))
        assert actual["items"][0]["structured_payload"] == body


def test_budget_and_final_prompt_share_the_smaller_projection(writer_request):
    text = "核查来源是行动，而不是新发现。" * 100
    body = {"objective": text, "planning": {"objective": text, "source_refs": []}}
    snapshot = package(writer_request, plan_item(writer_request, body))
    current = ContextProfileRegistry().resolve("CP-005", 8)
    previous = ContextProfileRegistry().resolve("CP-005", 7)
    estimator = TokenBudgetService()
    compact_cost = estimator.cost(writer_request, current, snapshot.items)
    assert compact_cost < estimator.cost(writer_request, previous, snapshot.items)
    final = ContextSerializer.serialize(snapshot)
    # The placeholder hash used by budgeting and final package hash have equal length.
    assert compact_cost == estimator.estimator.estimate(
        canonical({"trust": "UNTRUSTED_DATA_ONLY", "data": final})
    )


def test_projection_keeps_character_knowledge_firewall(writer_request):
    profile = ContextProfileRegistry().resolve("CP-005", 8)
    selector = next(s for s in profile.selectors if s.selector_id == "committed-memory")
    owner, other = uuid4(), uuid4()
    request = replace(writer_request, character_id=owner)
    private = item(
        request,
        selector_id=selector.selector_id,
        source_type=SourceType.EXTENSION,
        status=Status.ACTIVE,
        knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE,
        character_id=other,
        provenance=("committed_memory",),
        payload_json=canonical({"memory_type": "CHARACTER_KNOWLEDGE", "statement": "private"}),
    )
    assert (
        ContextFilter().reason(private, selector, request, profile)
        == ExclusionReason.CHARACTER_KNOWLEDGE
    )
    own = replace(private, character_id=owner)
    assert ContextFilter().reason(own, selector, request, profile) is None
    before = deepcopy(own.structured_payload)
    assert (
        ContextSerializer.payload(request, profile, (own,))["items"][0]["structured_payload"]
        == before
    )
    assert ContextFilter().reason(own, selector, replace(request, character_id=None), profile) == (
        ExclusionReason.CHARACTER_KNOWLEDGE
    )
