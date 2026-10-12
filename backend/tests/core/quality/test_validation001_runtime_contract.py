"""Local VALIDATION-001 evidence only; no real provider and no worker process."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from novel_os.agents.authority import AuthorityValidator
from novel_os.agents.planning_schemas import result_model
from novel_os.agents.provider import MockModelProvider
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.runtime import AgentRuntime, execution_failure
from novel_os.db.base import Base
from novel_os.domain.agents import AgentId, AgentTask
from novel_os.domain.enums import Authority
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from tests.context.test_character_profile_context import character, profile_version
from tests.core import test_character_profile_interpretation_lineage as interpretation
from tests.core.quality import test_checkpoint_phase2 as checkpoint
from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_memory_commit import complete_request, confirm
from tests.core.quality.test_revision import request_revision
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_creative_exploration import REJECTED_SENTINEL, ExplorationProvider
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import fixture_outputs
from tests.test_quality_contracts import issue, output
from tests.test_writing_contracts import sample

TASKS = (
    "PARSE_CHAPTER_REQUIREMENT",
    "EXPLORE_CHAPTER_CONCEPTS",
    "PLAN_CHAPTER",
    "REVIEW_CHAPTER_PLAN",
    "WRITE_CHAPTER",
    "REVIEW_CHAPTER_COMPLIANCE",
    "REVIEW_CHAPTER_NARRATIVE",
    "PLAN_CHAPTER_REVISION",
    "REVISE_CHAPTER",
    "VALIDATE_REVISION_FIDELITY",
    "INTERPRET_CHAPTER_FEEDBACK",
    "EXTRACT_CHAPTER_MEMORY",
    "INTERPRET_CHARACTER_PROFILE",
)
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / ".runtime/validation001"
CHANGED_TASKS = TASKS[:1] + TASKS[2:7]


def save(name, value):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_agent_and_authority_roster():
    assert [agent.value for agent in AgentId] == [
        "A01_ORCHESTRATOR",
        "A02_REQUIREMENT",
        "A03_PLANNING",
        "A04_WRITING",
        "A05_REVIEW",
        "A06_REVISION",
        "A07_MEMORY",
    ]
    assert [authority.value for authority in Authority] == [
        "A0_SYSTEM_RULE",
        "A1_USER_LOCKED",
        "A2_USER_APPROVED",
        "A3_CANON",
        "A4_APPROVED_PLAN",
        "A5_USER_PREFERENCE",
        "A6_DERIVED_MEMORY",
        "A7_AI_INFERENCE",
    ]
    assert AgentRegistry().task("EXPLORE_CHAPTER_CONCEPTS").agent_id == AgentId.A03_PLANNING
    assert TaskDefinitionRegistry().get("INTERPRET_CHARACTER_PROFILE").agent_id == (
        AgentId.A02_REQUIREMENT
    )


@pytest.mark.parametrize("task_type", TASKS)
def test_latest_prompt_schema_service_operations_contract(task_type):
    definition = TaskDefinitionRegistry().get(task_type)
    schema = json.loads(definition.output_schema.schema_json)
    if task_type != "INTERPRET_CHARACTER_PROFILE":
        assert definition.output_schema.model is result_model(task_type)
        mapping = AgentRegistry().task(task_type)
        assert mapping.result_schema == (
            f"{definition.output_schema.schema_id}.v{definition.output_schema.version}"
        )
    # Runtime universally forbids memory operations. Typed memory candidates use result.
    assert schema["properties"]["memory_proposals"]["maxItems"] == 0
    if task_type not in {"PARSE_CHAPTER_REQUIREMENT", "PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"}:
        assert schema["properties"]["proposed_changes"]["maxItems"] == 0
    modules = definition.resolve(PromptRegistry())
    text = "\n".join(module.content for module in modules)
    assert "memory_proposals" in text and ("=[]" in text or "both be []" in text)


@pytest.mark.parametrize("task_type", TASKS)
def test_latest_compiled_template_matches_registry_contract(task_type):
    provider = MockModelProvider()
    runtime = AgentRuntime(provider)
    definition = runtime.prompts.tasks.get(task_type)
    if task_type == "INTERPRET_CHARACTER_PROFILE":
        prepared = runtime.prepare_report(task_type, "Only supplied tendencies")
    else:
        mapping = AgentRegistry().task(task_type)
        task = AgentTask(
            project_id=uuid4(),
            workflow_instance_id=uuid4(),
            workflow_state=mapping.state,
            workflow_state_version=1,
            agent_id=mapping.agent_id,
            task_type=task_type,
            objective="Compile only",
            target_ref=uuid4(),
            capabilities=[mapping.capability],
            expected_output_schema=mapping.result_schema,
            attempt_count=1,
        )
        prepared = runtime.prepare(task)
    assert prepared.prompt.output.model is definition.output_schema.model
    current = runtime.prompts.prompts.resolve(definition.task_template).module.pin()
    selected = next(
        m.module.pin() for m in prepared.prompt.modules if m.module.module_type == ("TASK_TEMPLATE")
    )
    assert selected == current


def recorded_envelope(task_type):
    if task_type in TASKS[:4]:
        return fixture_outputs()[
            {
                "PARSE_CHAPTER_REQUIREMENT": 0,
                "PLAN_CHAPTER": 1,
                "REVIEW_CHAPTER_PLAN": 2,
            }[task_type]
        ]
    if task_type == "WRITE_CHAPTER":
        return sample()
    envelope = fixture_outputs()[0]
    envelope["result"] = output(compliance=task_type == "REVIEW_CHAPTER_COMPLIANCE").model_dump(
        mode="json"
    )
    if task_type == "REVIEW_CHAPTER_NARRATIVE":
        envelope["result"]["audience_evidence"] = []
    return envelope


@pytest.mark.parametrize("task_type", CHANGED_TASKS)
def test_new_operations_schema_rejects_only_currently_forbidden_envelope_fields(task_type):
    contract = TaskDefinitionRegistry().get(task_type).output_schema
    body = recorded_envelope(task_type)
    contract.parse(json.dumps(body))
    fields = ["memory_proposals"]
    if task_type in {"WRITE_CHAPTER", "REVIEW_CHAPTER_COMPLIANCE", "REVIEW_CHAPTER_NARRATIVE"}:
        fields.append("proposed_changes")
    for field in fields:
        changed = {**body, field: [{"capability": "REPORT_RESULT", "target_ref": str(uuid4())}]}
        with pytest.raises(ValidationError) as error:
            contract.parse(json.dumps(changed))
        assert [entry["loc"] for entry in error.value.errors()] == [(field,)]
        assert execution_failure(error.value).error_code == "SCHEMA_PARSE_ERROR"


@pytest.mark.parametrize("task_type", CHANGED_TASKS)
def test_prior_output_model_hash_and_task_prompt_are_unchanged(task_type):
    old = next(
        row
        for row in json.loads((EVIDENCE / "runtime-task-contract-audit.json").read_text())["tasks"]
        if row["task_type"] == task_type
    )
    tasks, prompts = TaskDefinitionRegistry(), PromptRegistry()
    historical = tasks.get(task_type, old["output_schema"])
    assert historical.output_schema.schema_hash == old["schema_hash"]
    assert historical.output_schema.model is result_model(task_type, old["output_schema"])
    previous = prompts.resolve(historical.task_template)
    pin = next(
        module
        for module in old["prompt_modules"]
        if module["module_id"] == (historical.task_template.module_id)
    )
    assert previous.module.pin().model_dump(mode="json") == pin
    current = prompts.resolve(tasks.get(task_type).task_template)
    assert current.module.version == previous.module.version + 1
    assert current.content.startswith(previous.content)
    historical.output_schema.parse(json.dumps(recorded_envelope(task_type)))


def test_planning_retains_legal_scoped_proposals_and_major_change_contract():
    mapping = AgentRegistry().task("PLAN_CHAPTER")
    task = AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=mapping.state,
        workflow_state_version=1,
        agent_id=mapping.agent_id,
        task_type=mapping.task_type,
        objective="Recorded contract",
        target_ref=uuid4(),
        capabilities=[mapping.capability],
        expected_output_schema=mapping.result_schema,
    )
    body = recorded_envelope(task.task_type)
    body["task_id"] = str(task.task_id)
    body["proposed_changes"] = [{"capability": "PROPOSE_PLAN", "target_ref": str(task.target_ref)}]
    parsed = TaskDefinitionRegistry().get(task.task_type).output_schema.parse(json.dumps(body))
    AuthorityValidator(AgentRegistry()).validate(task, parsed)
    assert "proposed_major_changes" in type(parsed.result).model_fields
    assert parsed.result.proposed_major_changes == body["result"]["proposed_major_changes"]


def database_snapshot(database):
    # Compare every persisted row as well as counts. This includes all current pointers,
    # immutable history, workflow state/version and audit records, not just the export APIs.
    snapshot = {}
    with database.session() as session:
        for table in Base.metadata.sorted_tables:
            rows = session.execute(select(table)).mappings().all()
            encoded = sorted(
                json.dumps(dict(row), sort_keys=True, ensure_ascii=False, default=str)
                for row in rows
            )
            snapshot[table.name] = {
                "row_count": len(rows),
                "rows_sha256": hashlib.sha256("\n".join(encoded).encode()).hexdigest(),
            }
    return snapshot


@pytest.mark.integration
def test_full_recorded_slice_all_lineage_and_readonly_database_export(
    core_client, core_database, project_api, chapter_api, monkeypatch, tmp_path
):
    spec = importlib.util.spec_from_file_location(
        "validation001_export", ROOT.parent / "evals/e2e/multi-chapter/run.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    # Reuse the existing exact A02 report integration, including its before-IO lineage check.
    interpretation.test_success_persists_exact_report_configuration_before_io_and_links_only_draft(
        core_client, project_api, core_database, monkeypatch
    )
    observed = {}

    def inspect_and_export(driver, provider):
        records = checkpoint.inspect_lineage(driver, provider)
        observed["tasks"] = sorted({record["task"]["task_type"] for record in records})
        assert set(observed["tasks"]) == set(TASKS) - {"INTERPRET_CHARACTER_PROFILE"}
        for record in records:
            prompt = record["prompt_lineage"]
            for name in ("system_policy", "agent_role", "task_template", "quality_profile"):
                assert prompt[name]["version"] > 0
                assert len(prompt[name]["content_hash"]) == 64
                assert len(prompt[name]["execution_hash"]) == 64
            assert prompt["skills"] and all(pin["version"] > 0 for pin in prompt["skills"])
            assert len(prompt["compiled_prompt_hash"]) == 64
            assert prompt["model_profile"] and len(prompt["model_profile_hash"]) == 64
            assert record["context"]["context_package_id"]

        state = {
            "test_id": "014R",
            "run_id": str(uuid4()),
            "project_id": driver.creation["project_id"],
            "scenario_id": "VALIDATION-001",
            "fixture_hash": runner.fixture_hash("014R"),
            "chapters": {
                "1": {
                    "chapter_id": driver.creation["chapter_id"],
                    "workflow_id": driver.workflow["id"],
                }
            },
        }
        calls = []

        def transport(request):
            assert request.method == "GET"
            calls.append(str(request.url.raw_path, "utf-8"))
            response = core_client.request("GET", "/api/v1" + calls[-1])
            return httpx.Response(response.status_code, content=response.content)

        before = database_snapshot(core_database)
        state_before = json.dumps(state, sort_keys=True)
        exported_path = tmp_path / "exported.json"
        with httpx.Client(
            base_url="http://local-validation001", transport=httpx.MockTransport(transport)
        ) as client:
            runner.export(client, state, exported_path)
        after = database_snapshot(core_database)
        assert before == after
        assert json.dumps(state, sort_keys=True) == state_before
        bundle = json.loads(exported_path.read_text())
        assert bundle["execution_kind"] == "MOCK_OR_RECORDED"
        assert bundle["providers_observed"] == ["mock"]
        assert not bundle["lineage_errors"]
        exported_tasks = {
            row["task"]["task_type"]
            for source in bundle["chapters"] + bundle["character_profiles"]
            for row in source["runs"]
        }
        assert exported_tasks == set(TASKS)
        chapter = bundle["chapters"][0]
        assert chapter["planning"]["explorations"] and chapter["plan_versions"]
        assert len(chapter["versions"]) == 3 and chapter["reviews"]
        assert chapter["revisions"] and chapter["human_feedback"]
        assert chapter["memory"][0]["proposal"] and chapter["memory"][0]["entries"]
        assert bundle["current_memory"] and bundle["historical_memory"]
        assert bundle["character_profiles"]
        # Acceptance export describes pending human behavior evaluation; recorded evidence
        # keeps a separate explicit engineering marker and never upgrades AI behavior.
        observed.update(
            exported_tasks=sorted(exported_tasks),
            tables=before,
            export_get_requests=len(calls),
            database_unchanged=before == after,
            exporter_state_unchanged=True,
            real_provider_calls=0,
            real_ai_behavior="NOT RUN",
            export_sha256=save("runtime-export.json", bundle),
        )
        save("runtime-export-immutability.json", observed)
        return records

    from uuid import UUID

    project_id = UUID(project_api.rsplit("/", 1)[1])
    mira = SimpleNamespace(
        id=UUID(
            next(
                row
                for row in core_client.get(project_api + "/characters").json()
                if row["name"] == "Mira"
            )["id"]
        )
    )
    jun = character(core_database, project_id, "Jun")
    profile = profile_version(
        core_database,
        project_id,
        mira.id,
        1,
        avoids_saying_directly=["fear"],
        relationship_modifiers=[dict(other_character_id=str(jun.id), interaction_tendency="Brief")],
    )
    profile_version(
        core_database,
        project_id,
        mira.id,
        2,
        approved=False,
        communication_style="UNAPPROVED_CURRENT",
    )
    draft(core_client, project_api, narrative_perspective="THIRD_PERSON")
    approve(core_client, project_api)
    versions = [
        "Mira 收好信件。\n\nMira 说：我很害怕。\n\n她沿河寻找 Jun。",
        "Mira 收好信件。\n\nMira 把信件握得更紧，停了一下。\n\n她沿河寻找 Jun。",
        "Mira 收好信件。\n\nMira 把信件握得更紧，淡淡地说：走吧。\n\n她沿河寻找 Jun。",
    ]

    def output_slice(request, body):
        checkpoint.recorded_slice(request, body)
        if request.output_kind == "writing_result":
            body["result"]["content"] = versions[0]
        elif request.task_type == "REVIEW_CHAPTER_NARRATIVE":
            source = next(
                i for i in request.context_package.items if i.selector_id == "target-version"
            )
            if source.source_version == 1:
                selected = next(
                    i
                    for i in request.context_package.items
                    if i.selector_id == ("approved-character-behavior-profiles")
                )
                ref = dict(
                    source_type="EXTENSION",
                    source_id=str(selected.source_id),
                    source_version=selected.source_version,
                    field="profile.avoids_saying_directly",
                )
                finding = issue("WEAK_CHARACTER_VOICE", "P1")
                finding.update(
                    requires_revision=True,
                    source_refs=[ref],
                    revision_direction="只调整第二段表达，保留信件与沿河寻找。",
                )
                finding["evidence"] = [
                    dict(
                        paragraph_index=2,
                        excerpt="Mira 说：我很害怕。",
                        reason="Recorded profile expression diagnosis",
                    )
                ]
                body["result"].update(
                    narrative_verdict="FAIL",
                    quality_issues=[finding],
                    source_refs=[ref],
                    revision_priorities=[],
                )
        elif request.output_kind == "revision_result":
            base = next(
                i for i in request.context_package.items if i.selector_id == "target-version"
            )
            body["result"]["content"] = versions[base.source_version]
            body["result"]["declared_changes"] = ["Only changed the middle expression"]

    provider = ExplorationProvider(transform=output_slice)
    driver = checkpoint.Phase2Driver(core_client, chapter_api, True)
    for _ in range(4):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert driver.decide().status_code == 200
    for _ in range(3):
        run_one(core_database, driver, provider=provider)
    assert driver.reviews()[0]["body"]["quality_issues"][0]["code"] == "WEAK_CHARACTER_VOICE"
    request_revision(driver, driver.reviews()[0])
    for _ in range(5):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["draft_version"] == 2 and driver.workflow["status"] == "WAITING_HUMAN"
    response, _ = submit(driver, "Mira 这里应该更冷一点，只改第二段，其他地方不要动。")
    assert response.status_code == 200, response.text
    driver.refresh()
    for _ in range(6):
        run_one(core_database, driver, provider=provider)
    assert driver.workflow["draft_version"] == 3 and driver.workflow["status"] == "WAITING_HUMAN"
    for number, content in enumerate(versions, 1):
        assert core_client.get(chapter_api + f"/versions/{number}").json()["content"] == content
    assert len(driver.read("/revisions")) == 2
    assert all(
        row["result"]["body"]["fidelity"]["verdict"] == "PASS" for row in driver.read("/revisions")
    )
    assert core_client.get(project_api + "/memory").json() == []
    accepted = complete_request(driver)
    run_one(core_database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C15_MEMORY_COMMIT"
    assert confirm(driver, ["accepted_summary"]).status_code == 200
    driver.refresh()
    assert driver.workflow["current_state"] == "C16_COMPLETED"
    entries = core_client.get(project_api + "/memory").json()
    assert len(entries) == 1 and entries[0]["chapter_version_id"] == accepted["id"]
    state = core_client.get(project_api + f"/characters/{mira.id}/behavior-profile").json()
    assert state["current_profile_version"] == 3 and state["approved_profile_version"] == 2
    for request in provider.requests:
        rendered = json.dumps(
            [i.structured_payload for i in request.context_package.items], default=str
        )
        assert REJECTED_SENTINEL not in rendered and "UNAPPROVED_CURRENT" not in rendered
        selected = [
            i
            for i in request.context_package.items
            if i.selector_id == ("approved-character-behavior-profiles")
        ]
        if request.task_type not in {"PARSE_CHAPTER_REQUIREMENT", "EXTRACT_CHAPTER_MEMORY"}:
            assert len(selected) == 1 and selected[0].source_id == profile.id
            assert selected[0].source_version == 2 and selected[0].authority_level == "A3_CANON"
            assert selected[0].logical_id == profile.logical_id and selected[0].selected_reason
    inspect_and_export(driver, provider)
    response = core_client.post(project_api + "/chapters", json=dict(sequence=2, title="Next"))
    assert response.status_code == 201
    next_driver = checkpoint.Phase2Driver(
        core_client, project_api + "/chapters/" + response.json()["id"], True
    )
    next_provider = ExplorationProvider(transform=checkpoint.recorded_slice)
    for _ in range(3):
        run_one(core_database, next_driver, provider=next_provider)
    planning = next(r for r in next_provider.requests if r.task_type == "PLAN_CHAPTER")
    assert any(str(i.source_id) == entries[0]["id"] for i in planning.context_package.items)
    observed.update(
        revisions=2,
        accepted_version=3,
        next_chapter_memory_context=True,
        real_provider_calls=0,
        real_ai_behavior="NOT RUN",
    )
    save("runtime-full-slice.json", observed)
    assert observed["database_unchanged"]
