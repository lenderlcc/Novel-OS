"""Phase 2 integration boundaries; recorded outputs are not AI behavior acceptance."""

import json
from pathlib import Path
from uuid import UUID

import pytest

from novel_os.agents.registry import AgentRegistry
from novel_os.domain.agents import FORBIDDEN_CAPABILITIES, AgentId, Capability
from novel_os.domain.enums import Authority
from tests.context.test_character_profile_context import character, profile_version
from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_memory_commit import complete_request, confirm
from tests.core.quality.test_multi_chapter_continuity import boundary_checks, inspect_lineage
from tests.core.quality.test_revision import request_revision
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_creative_exploration import (
    REJECTED_SENTINEL,
    ExplorationDriver,
    ExplorationProvider,
)
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.test_quality_contracts import issue


def test_phase2_has_seven_agents_and_no_agent_commit_authority():
    registry = AgentRegistry()
    assert len(registry.definitions) == len(AgentId) == 7
    assert len(Authority) == 8
    assert Capability.COMMIT_CANON in FORBIDDEN_CAPABILITIES
    assert Capability.DIRECT_DATABASE_WRITE in FORBIDDEN_CAPABILITIES
    assert all(
        not (definition.default_capabilities & FORBIDDEN_CAPABILITIES)
        for definition in registry.definitions.values()
    )


class Phase2Driver(QualityDriver):
    def __init__(self, client, chapter_api, exploration):
        raw = "Mira 和 Jun 在雨夜找到信件，约定继续沿河寻找，不改变重要方向。"
        if exploration:
            ExplorationDriver.__init__(self, client, chapter_api, raw=raw)
        else:
            super().__init__(client, chapter_api, raw_requirement=raw)


def recorded_slice(request, body):
    result = body["result"]
    if request.output_kind == "chapter_plan":
        result["objective"] = "Mira 和 Jun 找到信件，沿河寻找。"
        result["required_outcome"] = "Mira 和 Jun 约定继续沿河寻找。"
        result["ending_state"] = result["required_outcome"]
    elif request.output_kind == "writing_result":
        result["content"] = "Mira 收好信件。\n\nJun 指向河岸。\n\n他们约定继续沿河寻找。"
    elif request.output_kind == "chapter_memory":
        source = next(i for i in request.context_package.items if i.selector_id == "target-version")
        paragraph = source.structured_payload["content"].split("\n\n")[0]
        result["candidates"] = [
            dict(
                id="accepted_summary",
                candidate_type="DERIVED_CHAPTER_SUMMARY",
                subject_ref=None,
                statement="Mira 和 Jun 继续寻找。",
                slot="summary",
                value="Mira 和 Jun 继续寻找。",
                state_before=None,
                state_after=None,
                epistemic_status=None,
                importance="DERIVED_HINT",
                evidence=[
                    dict(paragraph_index=1, short_excerpt=paragraph, reason="Accepted prose")
                ],
                target_layer="DERIVED",
                source_refs=[
                    dict(
                        source_type="CHAPTER_VERSION",
                        logical_id=str(source.logical_id),
                        version=source.source_version,
                    )
                ],
                confidence=0.9,
                existing_entry_id=None,
                authority_checks=boundary_checks(request.context_package, source),
                uncertainty=None,
            )
        ]


@pytest.mark.integration
@pytest.mark.parametrize(
    "exploration,profiles",
    [(False, False), (True, False), (True, True)],
    ids=["legacy", "exploration-only", "exploration-and-profile"],
)
def test_phase2_gate_revision_memory_next_chapter(
    core_client, core_database, project_api, chapter_api, exploration, profiles
):
    core_client._transport.raise_server_exceptions = True
    draft(core_client, project_api, narrative_perspective="THIRD_PERSON")
    approve(core_client, project_api)
    profile = None
    if profiles:
        project_id = UUID(project_api.rsplit("/", 1)[1])
        mira = character(core_database, project_id, "Mira")
        jun = character(core_database, project_id, "Jun")
        atlas = character(core_database, project_id, "Atlas")
        profile = profile_version(
            core_database,
            project_id,
            mira.id,
            avoids_saying_directly=["fear"],
            risk_tolerance="LOW",
            relationship_modifiers=[
                dict(other_character_id=str(jun.id), interaction_tendency="Answers briefly"),
                dict(other_character_id=str(atlas.id), interaction_tendency="UNINVOLVED_PAIR"),
            ],
        )
        profile_version(
            core_database, project_id, atlas.id, communication_style="UNRELATED_PROFILE"
        )
        profile_version(
            core_database,
            project_id,
            mira.id,
            1,
            approved=False,
            communication_style="UNAPPROVED_CURRENT",
        )

    provider = (
        ExplorationProvider(transform=recorded_slice)
        if exploration
        else RecordedProvider(recorded_slice)
    )
    driver = Phase2Driver(core_client, chapter_api, exploration)
    for _ in range(6):
        if driver.workflow["status"] == "WAITING_HUMAN":
            break
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL", driver.workflow
    assert driver.workflow["draft_version"] is None
    assert driver.decide().status_code == 200  # Explicit test human action.
    for _ in range(3):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["status"] == "WAITING_HUMAN"
    original = core_client.get(chapter_api + "/versions/1").json()
    response, _ = submit(driver, "Mira 这一段不像她，请局部修改对白，开头结尾不要动。")
    assert response.status_code == 200, response.text
    driver.refresh()
    for _ in range(6):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["status"] == "WAITING_HUMAN" and driver.workflow["draft_version"] == 2
    revised = core_client.get(chapter_api + "/versions/2").json()
    assert revised["id"] != original["id"]
    assert core_client.get(chapter_api + "/versions/1").json() == original
    assert driver.reviews()[0]["chapter_version_id"] == revised["id"]
    revision = driver.read("/revisions")[0]
    assert revision["result"]["body"]["fidelity"]["verdict"] == "PASS"
    assert driver.read("/feedback")[0]["interpretation"]["body"]["action"] == "REVISION"
    assert core_client.get(project_api + "/memory").json() == []
    accepted = complete_request(driver)
    run_one(core_database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C15_MEMORY_COMMIT", driver.read("/agent-tasks")
    assert core_client.get(project_api + "/memory").json() == []
    assert confirm(driver, ["accepted_summary"]).status_code == 200
    driver.refresh()
    assert driver.workflow["current_state"] == "C16_COMPLETED"
    entries = core_client.get(project_api + "/memory").json()
    assert len(entries) == 1 and entries[0]["chapter_version_id"] == accepted["id"] == revised["id"]
    assert entries[0]["authority_level"] == "A6_DERIVED_MEMORY"
    inspect_lineage(driver, provider)

    if profile:
        current = core_client.get(project_api + f"/characters/{mira.id}/behavior-profile").json()
        assert current["current_profile_version"] == 2 and current["approved_profile_version"] == 1
        assert current["approved"]["id"] == str(profile.id)
    for request in provider.requests:
        package = request.context_package
        assert package.build_status == "READY"
        assert all(item.source_version > 0 and item.selected_reason for item in package.items)
        rendered = json.dumps([i.structured_payload for i in package.items], default=str)
        assert REJECTED_SENTINEL not in rendered
        assert "UNAPPROVED_CURRENT" not in rendered and "UNINVOLVED_PAIR" not in rendered
        assert "UNRELATED_PROFILE" not in rendered
        if profile and request.task_type in {
            "EXPLORE_CHAPTER_CONCEPTS",
            "PLAN_CHAPTER",
            "REVIEW_CHAPTER_PLAN",
            "WRITE_CHAPTER",
            "REVIEW_CHAPTER_COMPLIANCE",
            "REVIEW_CHAPTER_NARRATIVE",
            "INTERPRET_CHAPTER_FEEDBACK",
            "PLAN_CHAPTER_REVISION",
            "REVISE_CHAPTER",
            "VALIDATE_REVISION_FIDELITY",
        }:
            selected = [
                i for i in package.items if i.selector_id == "approved-character-behavior-profiles"
            ]
            assert len(selected) == 1
            assert selected[0].source_id == profile.id and selected[0].source_version == 1
            assert selected[0].authority_level == "A3_CANON"
            assert selected[0].structured_payload["character_profile_hash"] == profile.profile_hash
        if request.task_type in {
            "WRITE_CHAPTER",
            "REVIEW_CHAPTER_NARRATIVE",
            "REVISE_CHAPTER",
            "EXTRACT_CHAPTER_MEMORY",
        }:
            assert all(i.selector_id != "selected-creative-concept" for i in package.items)

    response = core_client.post(project_api + "/chapters", json=dict(sequence=2, title="Next"))
    assert response.status_code == 201
    next_driver = Phase2Driver(
        core_client, project_api + "/chapters/" + response.json()["id"], exploration
    )
    next_provider = (
        ExplorationProvider(transform=recorded_slice)
        if exploration
        else RecordedProvider(recorded_slice)
    )
    for _ in range(3 if exploration else 2):
        run_one(core_database, next_driver, provider=next_provider)
    plan_request = next(r for r in next_provider.requests if r.task_type == "PLAN_CHAPTER")
    committed = [
        i
        for i in plan_request.context_package.items
        if i.provenance and i.provenance[0] == "committed_memory"
    ]
    assert any(str(i.source_id) == entries[0]["id"] for i in committed)
    assert all(str(i.source_id) != original["id"] for i in committed)

    root = Path(".runtime/checkpoint001")
    root.mkdir(parents=True, exist_ok=True)
    samples = [
        dict(
            task=r.task_type,
            context_profile=f"{r.context_package.profile_id}.v{r.context_package.profile_version}",
            items=len(r.context_package.items),
            estimated_tokens=r.context_package.estimated_tokens,
            package_hash=r.context_package.package_hash,
            compiled_prompt_hash=r.prompt.compiled_hash,
        )
        for r in provider.requests
    ]
    (root / f"compatibility-{exploration}-{profiles}.json").write_text(
        json.dumps(dict(result="PASS", mock_only=True, samples=samples), indent=2)
    )


@pytest.mark.integration
def test_recorded_voice_issue_revises_locally_without_changing_profile(
    core_client, core_database, project_api, chapter_api
):
    """A supplied diagnosis tests its wiring, never the model's detection ability."""
    project_id = UUID(project_api.rsplit("/", 1)[1])
    mira = character(core_database, project_id, "Mira")
    approved_profile = profile_version(
        core_database, project_id, mira.id, avoids_saying_directly=["fear"]
    )
    draft(core_client, project_api, narrative_perspective="THIRD_PERSON")
    approve(core_client, project_api)
    original = "Mira 收好信件。\n\nMira 说：我很害怕。\n\n她沿河寻找 Jun。"
    revised = "Mira 收好信件。\n\nMira 把信件握得更紧，停了一下。\n\n她沿河寻找 Jun。"

    def output(request, body):
        recorded_slice(request, body)
        if request.output_kind == "writing_result":
            body["result"]["content"] = original
        elif request.task_type == "REVIEW_CHAPTER_NARRATIVE":
            target = next(
                i for i in request.context_package.items if i.selector_id == "target-version"
            )
            if target.source_version == 1:
                profile = next(
                    i
                    for i in request.context_package.items
                    if i.selector_id == "approved-character-behavior-profiles"
                )
                ref = dict(
                    source_type="EXTENSION",
                    source_id=str(profile.source_id),
                    source_version=1,
                    field="profile.avoids_saying_directly",
                )
                finding = issue("WEAK_CHARACTER_VOICE", "P1")
                finding.update(
                    requires_revision=True,
                    title="直接说出畏惧与人物表达倾向不符",
                    description="Recorded diagnosis: the middle line states fear directly.",
                    source_refs=[ref],
                    revision_direction="只调整第二段的表达，保留信件与沿河寻找的场景。",
                )
                finding["evidence"] = [
                    dict(
                        paragraph_index=2,
                        excerpt="Mira 说：我很害怕。",
                        reason="Exact source prose against supplied tendency",
                    )
                ]
                body["result"].update(
                    narrative_verdict="FAIL",
                    quality_issues=[finding],
                    source_refs=[ref],
                    revision_priorities=[],
                )
        elif request.output_kind == "revision_result":
            body["result"]["content"] = revised
            body["result"]["declared_changes"] = ["Only changed the middle expression of fear"]

    provider = ExplorationProvider(transform=output)
    driver = Phase2Driver(core_client, chapter_api, True)
    for _ in range(4):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert driver.decide().status_code == 200
    for _ in range(3):
        run_one(core_database, driver, provider=provider)
    review = driver.reviews()[0]
    assert review["body"]["quality_issues"][0]["code"] == "WEAK_CHARACTER_VOICE"
    assert review["body"]["overall_verdict"] == "FAIL"
    request_revision(driver, review)
    for _ in range(5):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["draft_version"] == 2 and driver.workflow["status"] == "WAITING_HUMAN"
    v1 = core_client.get(chapter_api + "/versions/1").json()
    v2 = core_client.get(chapter_api + "/versions/2").json()
    assert v1["content"] == original and v2["content"] == revised
    assert v2["content"].split("\n\n")[::2] == v1["content"].split("\n\n")[::2]
    history = driver.read("/revisions")[0]
    assert history["plan"]["body"]["preserve_scene_elements"]
    assert history["plan"]["body"]["preserve_relationship_elements"]
    assert history["result"]["body"]["fidelity"]["verdict"] == "PASS"
    assert driver.reviews()[0]["chapter_version_id"] == v2["id"]
    state = core_client.get(project_api + f"/characters/{mira.id}/behavior-profile").json()
    assert state["approved"]["id"] == str(approved_profile.id)
    assert state["approved_profile_version"] == state["current_profile_version"] == 1
    assert core_client.get(project_api + "/memory").json() == []
