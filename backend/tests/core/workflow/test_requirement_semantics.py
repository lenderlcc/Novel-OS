"""Pipeline regression examples are human annotations, never an NLP implementation.

The single live trial runs only on an explicit --live-model invocation. It executes
one Requirement attempt, saves each boundary, and does not run Planning or Writing.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from novel_os.agents.planning_mock import response as mock_response
from novel_os.agents.planning_schemas import REQUIREMENT_FIELDS, RequirementAgentResult
from novel_os.agents.runtime import AgentRuntime
from novel_os.core.config import Settings
from novel_os.domain.agents import MockScenario
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.base import ModelProvider
from novel_os.providers.openai import LingzhiModelProvider
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.runtime_factory import build_model_provider
from novel_os.worker import AgentWorker
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.planning_support import RecordedProvider

EVAL_ROOT = Path(__file__).resolve().parents[4] / "evals/requirements/v0.1"


def case01():
    return json.loads((EVAL_ROOT / "cases/R001.json").read_text())


def test_new_requirement_modules_keep_old_pins_resolvable():
    registry = PromptRegistry()
    definition = TaskDefinitionRegistry().get("PARSE_CHAPTER_REQUIREMENT")
    selected = {m.module.module_id: m for m in definition.resolve(registry)}
    expected_versions = {
        "requirement-agent": 2,
        "requirement-normalization": 2,
        "parse-chapter-requirement": 4,
    }
    for name, version in expected_versions.items():
        assert selected[name].module.version == version
        for old_version in range(1, version):
            assert (
                registry.resolve(ModuleRef(module_id=name, version=old_version)).module.version
                == old_version
            )
    assert case01()["raw_requirement"] not in "\n".join(m.content for m in selected.values())


def test_case01_annotated_decomposition_survives_provider_parser_and_persistence(
    core_client, chapter_api, core_database
):
    case = case01()
    d = PlanningDriver(core_client, chapter_api, case["raw_requirement"])
    emitted = []

    def annotation(request, body):
        brief = body["result"]
        source = brief["must"][0]["source_ref"]
        for field in REQUIREMENT_FIELDS.values():
            brief[field] = [
                {"id": f"{field[0]}{i}", "text": text, "quote": text, "source_ref": source}
                for i, text in enumerate(case["human_expectations"].get(field, []), 1)
            ]
        brief["intent_summary"] = case["human_expectations"]["intent"]
        brief["chapter_objective"] = case["human_expectations"]["objective"]
        brief["required_outcome"] = "读者感到关系出现变化，但没有直接和解或彻底说开"
        brief["desired_reader_effect"] = "察觉微妙变化和未解决的张力"
        brief["creative_freedom"] = {
            "level": "HIGH",
            "allowed_operations": ["LOCAL_DETAIL", "LOCAL_CONFLICT", "INFORMATION_DELIVERY"],
            "scope_description": "自行设计场景、对话和合作小事，保持结构功能与关系边界",
            "major_changes": "PROPOSAL_ONLY",
        }
        brief["confidence"] = body["confidence"] = 0.88
        body["issues"] = []
        emitted.append(json.loads(json.dumps(body)))

    provider = RecordedProvider(annotation)
    run_one(core_database, d, provider=provider)
    stored = d.read("/creative-brief")
    parsed = RequirementAgentResult.model_validate(emitted[0]).result.model_dump(mode="json")
    assert stored["raw_requirement"] == case["raw_requirement"]
    assert stored["body"] == parsed == emitted[0]["result"]
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert len(provider.requests) == 1
    assert len(d.read("/agent-tasks")) == 2  # Planning queued, never executed.
    assert d.read("/planning/history")["plans"] == []
    assert d.read("/writing/history") == []
    for field in REQUIREMENT_FIELDS.values():
        assert [c["quote"] for c in stored["body"][field]] == case["human_expectations"].get(
            field, []
        )


@pytest.mark.parametrize(
    "raw,field,quote",
    [
        (
            "这一段必须发现钥匙；若方便，可以采用黄昏背景。",
            "preferences",
            "若方便，可以采用黄昏背景",
        ),
        (
            "例如‘他必须离开’只是一个可选设想。",
            "preferences",
            "例如‘他必须离开’只是一个可选设想",
        ),
        ("不能放弃调查，但不必现在公布答案。", "forbidden", "不能放弃调查"),
        ("尽量保持叙述简洁。", "should", "尽量保持叙述简洁"),
    ],
)
def test_parser_preserves_annotated_modal_force_without_keyword_mapping(
    core_client, chapter_api, core_database, raw, field, quote
):
    d = PlanningDriver(core_client, chapter_api, raw)

    def annotation(request, body):
        brief = body["result"]
        constraint = brief["must"].pop()
        constraint.update(text=quote, quote=quote)
        brief[field].append(constraint)

    run_one(core_database, d, provider=RecordedProvider(annotation))
    saved = d.read("/creative-brief")["body"]
    assert saved[field][0]["quote"] == quote
    assert saved["must"] == []  # No hidden fallback reclassifies "必须" inside an example.


def test_mock_does_not_claim_semantic_confidence_or_force_clarification(
    planning_driver, core_database
):
    d = planning_driver
    run_one(core_database, d)
    brief = d.read("/creative-brief")["body"]
    task = d.read("/agent-tasks")[0]
    assert brief["confidence"] == task["result_metadata"]["confidence"] == 0
    assert "not evaluated" in brief["desired_reader_effect"]
    assert task["result_metadata"]["escalation_required"] is False
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"


@pytest.mark.parametrize("outer,inner", [(0.01, 0.99), (0.99, 0.01)])
def test_inconsistent_requirement_confidence_never_reaches_persistence(
    planning_driver, core_database, outer, inner
):
    def inconsistent(request, body):
        body["confidence"] = outer
        body["result"]["confidence"] = inner

    d = planning_driver
    run_one(core_database, d, provider=RecordedProvider(inconsistent))
    assert d.read("/agent-tasks")[0]["last_error_code"] == "SCHEMA_PARSE_ERROR"
    assert d.read("/planning/history")["briefs"] == []
    assert d.read("/planning/history")["plans"] == []
    assert d.read("/writing/history") == []


class CaptureOneRequirement(ModelProvider):
    def __init__(self, provider, directory):
        self.provider = provider
        self.provider_id = provider.provider_id
        self.directory = directory
        self.calls = 0

    def get_capabilities(self):
        return self.provider.get_capabilities()

    def generate(self, request):
        raise AssertionError("Requirement smoke requires structured output")

    def generate_structured(self, request):
        assert request.task_type == "PARSE_CHAPTER_REQUIREMENT" and self.calls == 0
        self.calls += 1
        self.save(
            "request.json",
            {
                "task_type": request.task_type,
                "provider_base_url": self.provider.base_url,
                "model_profile": request.profile.model_dump(mode="json"),
                "modules": [m.module.pin().model_dump(mode="json") for m in request.prompt.modules],
                "compiled_prompt_hash": request.prompt.compiled_hash,
                "messages": [
                    {"role": m.role, "layer": m.layer, "content": m.content}
                    for m in request.prompt.messages
                ],
            },
        )
        # Existing transport has no retry/redirect and never logs credentials.
        response = self.provider.generate_structured(request)
        (self.directory / "provider-output.txt").write_text(response.content)
        self.save("usage.json", response.safe_summary())
        return response

    def save(self, name, value):
        (self.directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def test_lingzhi_single_attempt_capture_and_lineage_are_offline(
    core_client, chapter_api, core_database, tmp_path
):
    from pydantic import SecretStr

    from tests.prompts.test_providers import response_body

    requests = []
    captured = []

    class OfflineLingzhi(LingzhiModelProvider):
        def generate_structured(self, request):
            requests.append(request)
            return super().generate_structured(request)

    def handler(request):
        captured.append(str(request.url))
        body = mock_response(requests[-1], MockScenario.SUCCESS)
        return httpx.Response(200, json=response_body(json.dumps(body)))

    inner = OfflineLingzhi(SecretStr("fixture-key"), transport=httpx.MockTransport(handler))
    provider = CaptureOneRequirement(inner, tmp_path)
    d = PlanningDriver(core_client, chapter_api, case01()["raw_requirement"])
    runtime = AgentRuntime(
        provider, tasks=TaskDefinitionRegistry(model_profile="lingzhi-requirement")
    )
    assert AgentWorker(core_database, runtime).run_once()
    d.refresh()
    brief = d.read("/creative-brief")
    lineage = core_client.get(f"/api/v1/agent-runs/{brief['agent_run_id']}/prompt-lineage").json()
    assert lineage["model_profile"]["provider"] == "lingzhi"
    assert lineage["model_profile"]["model"] == "gpt-5.6-sol"
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert d.read("/planning/history")["plans"] == d.read("/writing/history") == []
    saved = json.loads((tmp_path / "request.json").read_text())
    assert saved["provider_base_url"] == "https://lingzhi.agibot.com/v1"
    assert "fixture-key" not in "".join(p.read_text() for p in tmp_path.iterdir())
    with pytest.raises(AssertionError):
        provider.generate_structured(requests[0])
    assert provider.calls == 1 and captured == ["https://lingzhi.agibot.com/v1/responses"]


@pytest.mark.live_model
def test_case01_one_live_requirement_attempt(request, core_client, chapter_api, core_database):
    if not request.config.getoption("--live-model"):
        pytest.skip("Exactly one paid Requirement attempt requires explicit --live-model")
    settings = Settings.from_file()
    profile = ModelProfileRegistry().get(settings.requirement_smoke_profile)
    directory = (
        EVAL_ROOT
        / "results"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    )
    directory.mkdir(parents=True, mode=0o700)
    provider = CaptureOneRequirement(build_model_provider(settings, profile), directory)
    d = PlanningDriver(core_client, chapter_api, case01()["raw_requirement"])
    runtime = AgentRuntime(provider, tasks=TaskDefinitionRegistry(model_profile=profile.profile_id))
    worker = AgentWorker(core_database, runtime, retry_seconds=0)
    assert worker.run_once()
    d.refresh()
    tasks = d.read("/agent-tasks")
    task = next(t for t in tasks if t["task_type"] == "PARSE_CHAPTER_REQUIREMENT")
    runs = core_client.get(f"/api/v1/agent-tasks/{task['task_id']}/runs").json()
    brief_response = core_client.get(d.url + "/creative-brief")
    brief = brief_response.json() if brief_response.status_code == 200 else None
    run = runs[0]
    evidence = {
        "input": case01()["raw_requirement"],
        "input_sha256": case01()["sha256"],
        "calls": provider.calls,
        "workflow": d.workflow,
        "task": task,
        "run": run,
        "brief": brief,
        "context": core_client.get(f"/api/v1/agent-runs/{run['run_id']}/context").json(),
        "lineage": core_client.get(f"/api/v1/agent-runs/{run['run_id']}/prompt-lineage").json(),
        "plans": d.read("/planning/history")["plans"],
        "writing": d.read("/writing/history"),
    }
    provider.save("trace.json", evidence)
    print("Requirement attempt evidence:", directory)
    assert provider.calls == 1
    assert evidence["plans"] == evidence["writing"] == []
    assert brief is not None, f"Requirement failed: {run['error_code']}; see saved evidence"
    raw = (directory / "provider-output.txt").read_text()
    parsed = RequirementAgentResult.model_validate_json(raw).result.model_dump(mode="json")
    provider.save("parsed-output.json", parsed)
    assert parsed == brief["body"]
    # Semantic acceptance is assessed from this saved sample, not an automatic exact-match oracle.
