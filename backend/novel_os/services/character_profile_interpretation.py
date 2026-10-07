"""Explicit A02 interpretation uses the shared runtime and durable execution records."""

from datetime import timedelta
from uuid import uuid4

from novel_os.agents.runtime import ExecutionResult
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.agents import (
    AgentId,
    AgentRun,
    AgentTask,
    Capability,
    ResultStatus,
    RunStatus,
    TaskStatus,
)
from novel_os.domain.core import VersionToken
from novel_os.domain.errors import DomainError
from novel_os.prompts.contracts import canonical
from novel_os.providers.base import ModelResponse, TokenUsage
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.services.character_profiles import CharacterProfileService
from novel_os.services.prompt_lineages import PromptLineageService
from novel_os.services.task_history import RELEASE_LEASE, TaskHistory


class CharacterProfileInterpretationService:
    def __init__(self, session, runtime):
        self.session = session
        self.profiles = CharacterProfileService(session)
        self.tasks = AgentTaskRepository(session)
        self.history = TaskHistory(session)
        self.runtime = runtime

    def interpret(self, project_id, character_id, text, expected_version, context):
        # Permission/version preflight and durable configuration precede Provider IO.
        with self.profiles.mutation(project_id, context):
            subject = self.profiles.get_subject(project_id, character_id)
            current = self.profiles.profiles.get(project_id, character_id)
            VersionToken(expected_version).check(current.version if current else 0)
            related = self.profiles.memory.subjects_in_text(project_id, text)
            identities = {
                "character_id": str(subject.id),
                "character_name": subject.name,
                "related_characters": [
                    {"id": str(peer.id), "name": peer.name, "aliases": peer.aliases}
                    for peer in related
                    if peer.kind == "CHARACTER" and peer.id != character_id
                ],
            }
            task_id = uuid4()
            requirements = [canonical(identities)]
            prepared = self.runtime.prepare_report(
                "INTERPRET_CHARACTER_PROFILE",
                text,
                task_id=task_id,
                project_id=project_id,
                target_ref=character_id,
                requirements=requirements,
            )
            if isinstance(prepared, ExecutionResult):
                raise DomainError(prepared.error_code, "人物表现草稿的执行配置未能准备。")
            stamp, token = self.tasks.clock(), uuid4()
            task = self.tasks.add(
                AgentTask(
                    task_id=task_id,
                    project_id=project_id,
                    workflow_instance_id=None,
                    workflow_state=None,
                    workflow_state_version=None,
                    target_ref=None,
                    report_character_id=character_id,
                    agent_id=AgentId.A02_REQUIREMENT,
                    task_type="INTERPRET_CHARACTER_PROFILE",
                    objective=text,
                    requirements=requirements,
                    capabilities=[Capability.REPORT_RESULT],
                    expected_output_schema="character-profile-draft.v1",
                    max_attempts=1,
                    attempt_count=1,
                    status=TaskStatus.RUNNING,
                    created_at=stamp,
                    available_at=stamp,
                    claimed_at=stamp,
                    started_at=stamp,
                    lease_owner="explicit-profile-interpreter",
                    lease_token=token,
                    lease_expires_at=stamp + timedelta(hours=1),
                    heartbeat_at=stamp,
                    result_metadata={"expected_version": expected_version},
                )
            )
            run = self.tasks.add(
                AgentRun(
                    task_id=task.task_id,
                    attempt_number=1,
                    worker_id=task.lease_owner,
                    lease_token=token,
                    status=RunStatus.RUNNING,
                    claimed_at=stamp,
                    started_at=stamp,
                    provider=prepared.profile.provider,
                    model=prepared.profile.model,
                    input_metadata={
                        "expected_version": expected_version,
                        "profile_snapshot": current.binding() if current else None,
                    },
                )
            )
            packages = ContextPackageRepository(self.session)
            packages.check_profile(
                ContextProfileRegistry().resolve(
                    prepared.context_package.profile_id,
                    prepared.context_package.profile_version,
                    expected_hash=prepared.context_package.profile_hash,
                )
            )
            packages.add(run.run_id, prepared.context_package)
            PromptLineageService(self.session).record_in_transaction(task, run, prepared, context)
            self.history.audit(
                task, None, task, context, "Explicit character profile interpretation started"
            )
        # No transaction or project lock is held while the Provider runs.
        execution = self.runtime.execute_report(
            task.task_type,
            text,
            task_id=task.task_id,
            project_id=project_id,
            target_ref=character_id,
            requirements=requirements,
            prepared=prepared,
        )
        result = execution.result
        error = execution.error_code
        if error is None and (
            result is None
            or result.status != ResultStatus.SUCCESS
            or result.result is None
            or result.confidence < 0.6
            or (result.escalation and result.escalation.required)
        ):
            error = "PROFILE_CHANGE_REQUIRED"
        if error is None and (
            execution.context_package_id != prepared.context_package.context_package_id
            or execution.context_package_hash != prepared.context_package.package_hash
        ):
            error = "CONTEXT_STALE"
        if error is None:
            try:
                # Draft and successful execution completion commit as one mutation.
                with self.profiles.mutation(project_id, context):
                    task = self.tasks.get(task.task_id, for_update=True)
                    profile = self.profiles.create_draft(
                        project_id,
                        character_id,
                        result.result.profile.model_dump(mode="json"),
                        expected_version,
                        context,
                        "Explicit A02 interpretation of user character description",
                        source_text=text,
                        in_transaction=True,
                    )
                    self.finish(task, run, execution, context, profile=profile)
                    return profile
            except DomainError as exc:
                error = exc.code
            except Exception:
                # No raw Provider output, validation payload or exception message is retained.
                error = "TRANSIENT_INFRASTRUCTURE_ERROR"
        # Diagnostic completion remains legal after the project is locked/archived.
        with self.session.begin():
            self.profiles.repo.get_project(project_id, for_update=True)
            task = self.tasks.get(task.task_id, for_update=True)
            self.finish(task, run, execution, context, error=error)
        raise DomainError(error, "人物表现草稿未能保存，请查看错误码后重试或澄清描述。")

    def finish(self, task, run, execution, context, *, error=None, profile=None):
        if error in {"VERSION_CONFLICT", "CONTEXT_STALE"}:
            status, disposition = TaskStatus.CANCELLED, "STALE_IGNORED"
        elif error in {
            "LOCKED_OBJECT",
            "INVALID_STATE",
            "PROFILE_CHANGE_REQUIRED",
            "AUTHORITY_DENIED",
        }:
            status, disposition = TaskStatus.BLOCKED, "BLOCKED"
        elif error:
            status, disposition = TaskStatus.FAILED, "REJECTED"
        else:
            status, disposition = TaskStatus.SUCCEEDED, "APPLIED"
        current = self.profiles.profiles.get(task.project_id, task.report_character_id)
        metadata = {
            "expected_version": task.result_metadata["expected_version"],
            "actual_profile_snapshot": current.binding() if current else None,
            "context_package_id": str(execution.context_package_id),
            "context_package_hash": execution.context_package_hash,
            "disposition": disposition,
        }
        if isinstance(execution.model_metadata, dict):
            summary = execution.model_metadata
            usage = summary.get("usage", {})
            usage = usage if isinstance(usage, dict) else {}
            metadata["model"] = ModelResponse(
                "",
                usage=TokenUsage(
                    usage.get("input_tokens"), usage.get("output_tokens"), usage.get("total_tokens")
                ),
                finish_reason=summary.get("finish_reason"),
                latency_ms=summary.get("latency_ms"),
            ).safe_summary()
        if execution.result is not None:
            metadata["result_status"] = execution.result.status.value
            metadata["confidence"] = execution.result.confidence
        if profile is not None:
            metadata["profile_record_id"] = str(profile.id)
        self.history.finish_run(
            task,
            run,
            context,
            RunStatus.FAILED if error else RunStatus.SUCCEEDED,
            output_metadata=metadata,
            error_code=error,
            error_message="Character profile interpretation was not applied" if error else None,
            result_status=execution.result.status if execution.result is not None else None,
            disposition=disposition,
        )
        self.history.task(
            task,
            context,
            "Character profile interpretation " + disposition,
            status=status,
            completed_at=self.tasks.clock(),
            result_ref=run.run_id,
            result_metadata=metadata,
            last_error_code=error,
            last_error_message="Character profile interpretation was not applied"
            if error
            else None,
            **RELEASE_LEASE,
        )
