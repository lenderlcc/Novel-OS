"""Durable explicit A02 report attempts; isolated test DB and deterministic Mock only."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from novel_os import runtime_factory
from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.providers.base import ProviderError
from novel_os.services.character_profiles import CharacterProfileService
from novel_os.services.task_history import TaskHistory
from novel_os.worker import AgentWorker

pytestmark = pytest.mark.integration


class ReportMock(MockModelProvider):
    def __init__(self, *, transform=None, before=None, error=None):
        super().__init__()
        self.transform, self.before, self.error = transform, before, error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.before:
            self.before(request)
        if self.error:
            raise ProviderError(self.error)
        response = super().generate(request)
        if self.transform:
            body = json.loads(response.content)
            self.transform(body)
            response = replace(response, content=json.dumps(body))
        return replace(response, metadata={"secret": "transport-secret"})


def setup_report(client, project, monkeypatch, provider):
    char = client.post(project + "/characters", json={"name": "Mira"}).json()
    url = project + "/characters/" + char["id"] + "/behavior-profile"
    monkeypatch.setattr(runtime_factory, "build_agent_runtime", lambda _: AgentRuntime(provider))
    return url, char


def inspect_trace(client, url, provider, *, task_status, error=None, freshness="READY"):
    tasks = client.get(url + "/interpretations")
    assert tasks.status_code == 200, tasks.text
    assert len(tasks.json()) == 1
    task = tasks.json()[0]
    assert task["status"] == task_status and task["max_attempts"] == 1
    assert task["capabilities"] == ["REPORT_RESULT"]
    assert task["workflow_instance_id"] is None and task["target_ref"] is None
    assert task["last_error_code"] == error
    response = client.get(f"/api/v1/agent-tasks/{task['task_id']}/runs")
    assert response.status_code == 200 and len(response.json()) == 1
    run = response.json()[0]
    assert task["result_ref"] == run["run_id"]
    assert run["error_code"] == error
    prompt = client.get(f"/api/v1/agent-runs/{run['run_id']}/prompt-lineage")
    assert prompt.status_code == 200, prompt.text
    prompt = prompt.json()
    request = provider.requests[0]
    assert prompt["task_id"] == task["task_id"] == str(request.task_id)
    assert prompt["compiled_prompt_hash"] == request.prompt.compiled_hash
    assert prompt["model_profile_hash"] == request.profile.profile_hash
    assert prompt["task_template"]["module_id"] == "interpret-character-profile"
    assert prompt["task_template"]["version"] == 1
    assert len(prompt["task_template"]["execution_hash"]) == 64
    package = request.context_package
    for endpoint in (
        f"/api/v1/agent-runs/{run['run_id']}/context",
        f"/api/v1/agent-tasks/{task['task_id']}/context",
        f"/api/v1/context-packages/{package.context_package_id}",
    ):
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["freshness"] == freshness
        assert data["package"]["context_package_id"] == str(package.context_package_id)
        assert data["package"]["package_hash"] == package.package_hash
        assert data["package"]["profile_id"] == "CP-010"
        assert [item["source_type"] for item in data["package"]["items"]] == ["TASK_INPUT"]
    assert run["output_metadata"]["context_package_hash"] == package.package_hash
    assert "transport-secret" not in json.dumps(run) + json.dumps(task) + json.dumps(prompt)
    return task, run


def test_success_persists_exact_report_configuration_before_io_and_links_only_draft(
    core_client, project_api, core_database, monkeypatch
):
    provider = ReportMock()
    url, char = setup_report(core_client, project_api, monkeypatch, provider)

    def before(request):
        tasks = core_client.get(url + "/interpretations").json()
        assert len(tasks) == 1 and tasks[0]["status"] == "RUNNING"
        run = core_client.get(f"/api/v1/agent-tasks/{tasks[0]['task_id']}/runs").json()[0]
        assert run["status"] == "RUNNING"
        prompt = core_client.get(f"/api/v1/agent-runs/{run['run_id']}/prompt-lineage")
        assert prompt.status_code == 200
        assert prompt.json()["compiled_prompt_hash"] == request.prompt.compiled_hash
        assert core_client.get(f"/api/v1/agent-runs/{run['run_id']}/context").status_code == 200
        assert not AgentWorker(core_database, AgentRuntime(MockModelProvider())).run_once()

    provider.before = before
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": "Direct"})
    assert response.status_code == 201, response.text
    profile = response.json()
    task, run = inspect_trace(core_client, url, provider, task_status="SUCCEEDED")
    assert len(provider.requests) == 1 and run["status"] == "SUCCEEDED"
    assert task["report_character_id"] == char["id"]
    assert run["disposition"] == "APPLIED"
    assert task["result_metadata"]["profile_record_id"] == profile["id"]
    assert run["output_metadata"]["profile_record_id"] == profile["id"]
    assert profile["status"] == "DRAFT" and profile["authority_level"] == "A7_AI_INFERENCE"
    assert core_client.get(url + "/approved").json() is None
    assert core_client.get(project_api + "/memory").json() == []
    audits = core_client.get(project_api + "/audit").json()
    report_audits = [a for a in audits if a["after"].get("agent_task_id") == task["task_id"]]
    assert len(report_audits) == 4
    assert all(
        a["target_type"] == "PROJECT" and a["after"]["workflow_id"] is None for a in report_audits
    )


@pytest.mark.parametrize(
    ("transform", "provider_error", "code", "status"),
    [
        (None, "MODEL_TIMEOUT", "MODEL_TIMEOUT", "FAILED"),
        (
            lambda b: b["result"]["profile"].update(status="APPROVED"),
            None,
            "SCHEMA_PARSE_ERROR",
            "FAILED",
        ),
        (lambda b: b.update(confidence=0.2), None, "PROFILE_CHANGE_REQUIRED", "BLOCKED"),
        (lambda b: b.update(task_id=str(uuid4())), None, "AUTHORITY_DENIED", "BLOCKED"),
        (
            lambda b: b["result"]["profile"].update(
                relationship_modifiers=[{"other_character_id": str(uuid4())}]
            ),
            None,
            "NOT_FOUND",
            "FAILED",
        ),
    ],
)
def test_failed_attempt_retains_exact_trace_without_a_profile_or_retry(
    core_client, project_api, monkeypatch, transform, provider_error, code, status
):
    provider = ReportMock(transform=transform, error=provider_error)
    url, _ = setup_report(core_client, project_api, monkeypatch, provider)
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": "Direct"})
    assert response.status_code != 201, response.text
    assert response.json()["error"]["code"] == code
    task, run = inspect_trace(core_client, url, provider, task_status=status, error=code)
    assert run["status"] == "FAILED" and run["finished_at"] is not None
    assert task["completed_at"] is not None and task["attempt_count"] == 1
    assert "profile_record_id" not in task["result_metadata"]
    assert core_client.get(url + "/versions").json() == []
    assert len(provider.requests) == 1


@pytest.mark.parametrize("mutation", ["version", "lock"])
def test_post_io_version_or_lock_change_is_traced_and_cannot_apply(
    core_client, project_api, monkeypatch, mutation
):
    provider = ReportMock()
    url, _ = setup_report(core_client, project_api, monkeypatch, provider)

    def before(_):
        if mutation == "version":
            response = core_client.post(
                url + "/drafts",
                json={"expected_version": 0, "profile": {"decision_tendency": "Manual"}},
            )
        else:
            response = core_client.post(
                project_api + "/locks",
                json={
                    "target_type": "PROJECT",
                    "target_id": project_api.split("/")[-1],
                    "expected_version": 1,
                },
            )
        assert response.status_code == 201, response.text

    provider.before = before
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": "Direct"})
    code, status = (
        ("VERSION_CONFLICT", "CANCELLED") if mutation == "version" else ("LOCKED_OBJECT", "BLOCKED")
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == code
    task, run = inspect_trace(
        core_client,
        url,
        provider,
        task_status=status,
        error=code,
        freshness="STALE" if mutation == "version" else "READY",
    )
    versions = core_client.get(url + "/versions").json()
    if mutation == "version":
        assert len(versions) == 1 and versions[0]["decision_tendency"] == "Manual"
        assert task["result_metadata"]["actual_profile_snapshot"]["character_profile_version"] == 1
        assert run["disposition"] == "STALE_IGNORED"
    else:
        assert versions == []
    assert len(provider.requests) == 1


@pytest.mark.parametrize("mutation", ["version", "lock", "foreign"])
def test_preflight_failure_does_not_create_attempt_or_call_model(
    core_client, project_api, monkeypatch, mutation
):
    provider = ReportMock()
    url, char = setup_report(core_client, project_api, monkeypatch, provider)
    if mutation == "version":
        assert (
            core_client.post(
                url + "/drafts", json={"expected_version": 0, "profile": {}}
            ).status_code
            == 201
        )
    elif mutation == "lock":
        assert (
            core_client.post(
                project_api + "/locks",
                json={
                    "target_type": "PROJECT",
                    "target_id": project_api.split("/")[-1],
                    "expected_version": 1,
                },
            ).status_code
            == 201
        )
    else:
        other = core_client.post("/api/v1/projects", json={"name": "Other"}).json()
        target = f"/api/v1/projects/{other['id']}/characters/{char['id']}/behavior-profile"
    response = core_client.post(
        (target if mutation == "foreign" else url) + "/interpret",
        json={"expected_version": 0, "text": "Direct"},
    )
    assert response.status_code in {404, 409}
    assert provider.requests == [] and core_client.get(url + "/interpretations").json() == []


def test_completion_audit_failure_rolls_back_draft_then_marks_actual_attempt_failed(
    core_client, project_api, monkeypatch
):
    provider = ReportMock()
    url, _ = setup_report(core_client, project_api, monkeypatch, provider)
    original = TaskHistory.audit
    fired = False

    def fail_once(self, task, before, after, context, reason):
        nonlocal fired
        if reason == "Character profile interpretation APPLIED" and not fired:
            fired = True
            raise RuntimeError("private database exception details")
        return original(self, task, before, after, context, reason)

    monkeypatch.setattr(TaskHistory, "audit", fail_once)
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": "Direct"})
    assert response.status_code != 201
    assert response.json()["error"]["code"] == "TRANSIENT_INFRASTRUCTURE_ERROR"
    task, run = inspect_trace(
        core_client, url, provider, task_status="FAILED", error="TRANSIENT_INFRASTRUCTURE_ERROR"
    )
    assert fired and run["status"] == "FAILED" and core_client.get(url + "/versions").json() == []
    assert "private database" not in json.dumps(task) + json.dumps(run) + response.text


def test_application_owned_draft_mutation_keeps_user_lock_and_transaction_boundary(
    core_client, project_api, core_database
):
    char = core_client.post(project_api + "/characters", json={"name": "Mira"}).json()
    pid, cid = UUID(project_api.split("/")[-1]), UUID(char["id"])
    user = CommandContext("test", "local-user", ActorType.USER)
    with (
        core_database.session() as session,
        pytest.raises(RuntimeError, match="application transaction"),
    ):
        CharacterProfileService(session).create_draft(
            pid, cid, {}, 0, user, "test", in_transaction=True
        )
    with (
        core_database.session() as session,
        session.begin(),
        pytest.raises(DomainError, match="requires a user"),
    ):
        CharacterProfileService(session).create_draft(
            pid,
            cid,
            {},
            0,
            CommandContext("test", "agent", ActorType.AGENT),
            "test",
            in_transaction=True,
        )
    assert (
        core_client.post(
            project_api + "/locks",
            json={"target_type": "PROJECT", "target_id": str(pid), "expected_version": 1},
        ).status_code
        == 201
    )
    with core_database.session() as session, session.begin(), pytest.raises(DomainError) as error:
        CharacterProfileService(session).create_draft(
            pid, cid, {}, 0, user, "test", in_transaction=True
        )
    assert error.value.code == "LOCKED_OBJECT"
