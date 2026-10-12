"""Read-only evidence collection before each isolated Writing test schema is removed."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime, ExecutionResult
from novel_os.agents.writing_schemas import WritingMetadata
from novel_os.context.profiles import ContextProfile, ContextProfileRegistry
from novel_os.context.serialization import ContextSerializer
from novel_os.models.agents import AgentRunModel, AgentTaskModel
from novel_os.models.context import ContextPackageModel
from novel_os.models.core import ChapterPlanModel, ChapterVersionModel
from novel_os.models.prompts import PromptLineageModel
from novel_os.models.writing import WritingGenerationModel, WritingTaskBindingModel
from novel_os.repositories.agent_tasks import AgentTaskRepository


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_hash(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def audit(session):
    drafts = list(
        session.scalars(select(ChapterVersionModel).where(ChapterVersionModel.source == "AGENT"))
    )
    generations = list(session.scalars(select(WritingGenerationModel)))
    # Check both directions: an orphan Agent Draft cannot disappear from a JOIN.
    draft_ids = {row.id for row in drafts}
    bound_ids = [row.chapter_version_id for row in generations if row.check_status == "PASS"]
    assert draft_ids == set(bound_ids), "Agent Draft missing WritingResult or vice versa"
    assert len(bound_ids) == len(set(bound_ids)), "Draft has duplicate generation records"
    evidence = []
    for generation in generations:
        task = session.get(AgentTaskModel, generation.agent_task_id)
        run = session.get(AgentRunModel, generation.agent_run_id)
        binding = session.get(WritingTaskBindingModel, generation.agent_task_id)
        plan = session.get(ChapterPlanModel, generation.plan_id)
        context = session.get(ContextPackageModel, generation.context_package_id)
        prompt = session.get(PromptLineageModel, generation.prompt_lineage_id)
        assert all(row is not None for row in (task, run, binding, plan, context, prompt))
        assert task.task_type == "WRITE_CHAPTER" and str(task.agent_id) == "A04_WRITING"
        assert task.task_id == run.task_id == context.task_id == prompt.task_id == binding.task_id
        assert run.run_id == context.agent_run_id == prompt.agent_run_id == task.result_ref
        assert generation.project_id == task.project_id == binding.project_id == plan.project_id
        assert generation.chapter_id == task.target_ref == binding.chapter_id == plan.chapter_id
        assert generation.workflow_id == task.workflow_instance_id == binding.workflow_id
        assert generation.plan_id == binding.plan_id
        assert generation.plan_version == binding.plan_version == plan.version
        # Historical plans may now be SUPERSEDED; approval is checked in the run snapshot.
        assert plan.approved_at is not None
        package = ContextSerializer.restore(context.snapshot)
        assert context.package_hash == ContextSerializer.hash(package) == package.package_hash
        assert context.build_status == "READY" and package.profile_id == "CP-005"
        bound_profile = ContextProfile.model_validate_json(binding.profile_json)
        assert "WRITE_CHAPTER" in bound_profile.allowed_task_types
        assert (
            (context.profile_id, context.profile_version, context.profile_hash)
            == (
                package.profile_id,
                package.profile_version,
                package.profile_hash,
            )
            == (bound_profile.profile_id, bound_profile.version, bound_profile.profile_hash)
        )
        ContextProfileRegistry().resolve(
            bound_profile.profile_id,
            bound_profile.version,
            expected_hash=bound_profile.profile_hash,
        )
        assert package.request.project_id == generation.project_id
        assert package.request.chapter_id == generation.chapter_id
        assert package.request.workflow_id == generation.workflow_id
        selected = [item for item in package.items if item.selector_id == "approved-plan"]
        assert len(selected) == 1
        item = selected[0]
        assert (item.source_id, item.source_version) == (plan.id, plan.version)
        assert str(item.status) in {"APPROVED", "LOCKED"}
        assert generation.model_profile == prompt.model_profile_id == "mock-writing"
        profile = prompt.model_profile
        assert json.loads(binding.profile_json) == json.loads(package.profile_json)
        assert prompt.model_profile_hash == json_hash(profile)
        assert generation.provider == run.provider == profile["provider"] == "mock"
        assert generation.model == run.model == profile["model"]
        assert task.expected_output_schema == (
            prompt.output_schema_id + ".v" + str(prompt.output_schema_version)
        )
        assert prompt.agent_role["module_id"] == "writing-agent"
        assert prompt.task_template["module_id"] == "write-chapter"
        assert len(prompt.compiled_prompt_hash) == 64
        # Recompile persisted inputs locally. prepare() performs no provider call.
        rebuilt = AgentRuntime(MockModelProvider()).prepare(
            AgentTaskRepository(session).get(task.task_id), package
        )
        assert not isinstance(rebuilt, ExecutionResult), "Cannot reconstruct Writing prompt"
        assert rebuilt.prompt.compiled_hash == prompt.compiled_prompt_hash
        assert rebuilt.prompt.output.schema_hash == prompt.output_schema_hash
        assert rebuilt.profile.profile_hash == prompt.model_profile_hash
        stored_pins = [
            prompt.system_policy,
            prompt.agent_role,
            prompt.task_template,
            prompt.quality_profile,
            *prompt.skills,
        ]
        rebuilt_pins = [module.module.pin().model_dump() for module in rebuilt.prompt.modules]
        assert sorted(stored_pins, key=lambda pin: pin["module_id"]) == sorted(
            rebuilt_pins, key=lambda pin: pin["module_id"]
        )
        metadata = WritingMetadata.model_validate(generation.result_metadata)
        assert (metadata.chapter_id, metadata.plan_id, metadata.plan_version) == (
            generation.chapter_id,
            plan.id,
            plan.version,
        )
        assert "content" not in generation.result_metadata
        assert str(run.status) == "SUCCEEDED"
        assert run.output_metadata["kind"] == "writing_result"
        draft = None
        if generation.check_status == "PASS":
            draft = session.get(ChapterVersionModel, generation.chapter_version_id)
            assert (draft.project_id, draft.chapter_id) == (plan.project_id, plan.chapter_id)
            assert draft.created_by == "A04_WRITING"
            assert sha(draft.content) == generation.content_hash
            assert draft.version == binding.expected_draft_version + 1
            assert str(task.status) == "SUCCEEDED" and run.disposition == "APPLIED"
            assert not generation.check_codes
        else:
            assert generation.check_status == "BLOCKED" and generation.chapter_version_id is None
            assert generation.check_codes and str(task.status) == "BLOCKED"
        evidence.append(
            {
                "writing_result_id": str(generation.id),
                "draft_id": str(draft.id) if draft else None,
                "draft_version": draft.version if draft else None,
                "content_sha256": generation.content_hash,
                "project_id": str(generation.project_id),
                "chapter_id": str(generation.chapter_id),
                "workflow_id": str(generation.workflow_id),
                "plan_id": str(plan.id),
                "plan_version": plan.version,
                "plan_status_at_execution": str(item.status),
                "context_package_id": str(context.context_package_id),
                "context_package_hash": context.package_hash,
                "context_profile": f"{package.profile_id}.v{package.profile_version}",
                "context_profile_hash": package.profile_hash,
                "context_sources": [
                    {
                        "type": str(source.source_type),
                        "id": str(source.source_id),
                        "version": source.source_version,
                        "status": str(source.status),
                        "future_knowledge": source.future_knowledge,
                        "knowledge_scope": str(source.knowledge_scope),
                    }
                    for source in package.items
                ],
                "prompt_lineage_id": str(prompt.lineage_id),
                "compiled_prompt_hash": prompt.compiled_prompt_hash,
                "prompt_recompiled_and_verified": True,
                "output_schema_hash": prompt.output_schema_hash,
                "prompt_modules": [
                    prompt.system_policy,
                    prompt.agent_role,
                    prompt.task_template,
                    prompt.quality_profile,
                    *prompt.skills,
                ],
                "agent_task_id": str(task.task_id),
                "agent_run_id": str(run.run_id),
                "attempt_number": run.attempt_number,
                "model_profile": profile,
                "model_profile_hash": prompt.model_profile_hash,
                "writing_metadata": generation.result_metadata,
                "check_status": generation.check_status,
                "check_codes": generation.check_codes,
                "lineage_valid": True,
            }
        )
    return {"agent_drafts": len(drafts), "generations": evidence}


class LineageAudit:
    def __init__(self, output, source_commit, case_hashes):
        self.output = output
        self.document = {
            "suite": "writing/v0.1",
            "source_commit": source_commit,
            "started_at": datetime.now(UTC).isoformat(),
            "provider": "mock",
            "real_provider_calls": 0,
            "case_hashes": case_hashes,
            "trials": [],
        }

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        outcome = yield
        trial = {"test_id": item.nodeid, "test_passed": outcome.excinfo is None}
        self.document["trials"].append(trial)
        try:
            database = item.funcargs["core_database"]
            with database.session() as session:
                trial.update(audit(session))
        except Exception as exc:
            trial["lineage_error_type"] = type(exc).__name__
            raise
        finally:
            self.output.write_text(json.dumps(self.document, ensure_ascii=False, indent=2) + "\n")

    def pytest_sessionfinish(self, session, exitstatus):
        self.document["finished_at"] = datetime.now(UTC).isoformat()
        self.document["pytest_exit_code"] = int(exitstatus)
        self.document["total_agent_drafts"] = sum(
            trial.get("agent_drafts", 0) for trial in self.document["trials"]
        )
        self.output.write_text(json.dumps(self.document, ensure_ascii=False, indent=2) + "\n")
