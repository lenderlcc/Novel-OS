"""Transactional persistence of A06 proposals; only application code creates Drafts."""

from dataclasses import asdict

from novel_os.domain.agents import ResultStatus, TaskStatus
from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType, ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.revision import RevisionCandidate, RevisionPlan, RevisionResult
from novel_os.prompts.contracts import digest
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.repositories.revision import RevisionRepository
from novel_os.revision.fidelity import RevisionFidelityValidator
from novel_os.revision.policy import validate_plan, validate_result
from novel_os.services.core_base import CoreService
from novel_os.services.quality_results import QualityResultService
from novel_os.services.revision_binding import RevisionBindingService
from novel_os.services.versioning import ChapterVersionService


class RevisionResultService:
    def __init__(self, session):
        self.session = session
        self.repo = RevisionRepository(session)
        self.core = CoreService(session)

    def validate(self, task, run, result, package, workflow):
        request = RevisionBindingService(self.session).check(task, workflow)
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if result.proposed_changes or result.memory_proposals:
            # Current schemas reject this before Service/Authority validation.
            # Retain the guard for legacy envelopes without mislabeling format as permission.
            raise ValueError("Revision output requires empty proposal arrays")
        if (
            package is None
            or lineage is None
            or package.task_id != task.task_id
            or lineage.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
        ):
            raise DomainError(
                "AUTHORITY_DENIED", "Revision requires exact Context and Prompt lineage"
            )
        if task.task_type == "PLAN_CHAPTER_REVISION":
            validate_plan(result.result, request, package)
            source = next(i for i in package.items if i.selector_id == "target-version")
            RevisionFidelityValidator.plan(
                result.result, request, source.structured_payload["content"]
            )
        else:
            plan = self.repo.evidence(request.id)
            if plan is None or not plan.body["revision_targets"]:
                raise DomainError("INVALID_STATE", "Execution requires a safe Revision Plan")
            if task.task_type == "VALIDATE_REVISION_FIDELITY":
                candidate = self.repo.evidence(request.id, RevisionCandidate)
                if candidate is None or not candidate.body["content"]:
                    raise DomainError("INVALID_STATE", "Fidelity needs an immutable candidate")
                RevisionFidelityValidator.semantic(result.result, request, plan, candidate, package)
            else:
                validate_result(result.result, request, plan, package)
                RevisionFidelityValidator.candidate(result.result, request, plan, package)
        return request, lineage

    def persist(self, task, run, result, package, workflow):
        request, lineage = self.validate(task, run, result, package, workflow)
        output = result.result
        fields = dict(
            request_id=request.id,
            task_id=task.task_id,
            run_id=run.run_id,
            prompt_lineage_id=lineage.lineage_id,
            context_package_id=package.context_package_id,
            body=output.model_dump(mode="json"),
        )
        blocked = (
            result.status != ResultStatus.SUCCESS
            or min(result.confidence, output.confidence) < 0.6
            or bool(result.escalation and result.escalation.required)
        )
        if task.task_type == "PLAN_CHAPTER_REVISION":
            record = self.repo.add(RevisionPlan(**fields))
            blocked = blocked or not output.revision_targets
            event = "REVISION_PLAN_READY"
        elif task.task_type == "REVISE_CHAPTER":
            plan = self.repo.evidence(request.id)
            source = next(i for i in package.items if i.selector_id == "target-version")
            blocked = (
                blocked
                or output.content is None
                or output.content == source.structured_payload["content"]
            )
            fields["body"]["content_hash"] = digest(output.content) if output.content else None
            record = self.repo.add(RevisionCandidate(**fields, revision_plan_id=plan.id))
            event = "REVISION_CANDIDATE_READY"
        else:
            plan = self.repo.evidence(request.id)
            candidate = self.repo.evidence(request.id, RevisionCandidate)
            blocked = blocked or output.verdict != "PASS"
            version = None
            if not blocked:
                version = ChapterVersionService(self.session).create_version_in_transaction(
                    request.project_id,
                    request.chapter_id,
                    {
                        "content": candidate.body["content"],
                        "change_reason": (
                            "Directed revision from feedback " + str(request.source_feedback_id)
                            if request.source_feedback_id
                            else "Targeted revision from Review " + str(request.source_review_id)
                        ),
                    },
                    workflow.draft_version,
                    CommandContext(str(run.run_id), task.agent_id.value, ActorType.AGENT),
                    "Fidelity accepted an immutable successor Draft",
                )
            fields["body"] = {
                **{k: v for k, v in candidate.body.items() if k != "content"},
                "candidate_id": str(candidate.id),
                "fidelity": output.model_dump(mode="json"),
                "accepted": not blocked,
            }
            record = self.repo.add(
                RevisionResult(
                    **fields,
                    revision_plan_id=plan.id,
                    chapter_version_id=version.id if version else None,
                )
            )
            event = "REVISION_READY"
        QualityResultService(self.session).audit(
            task,
            run,
            "Revision evidence recorded",
            {
                "revision_request_id": str(request.id),
                "artifact_id": str(record.id),
                "blocked": blocked,
            },
        )
        if blocked:
            return (
                "BLOCK",
                {
                    "reason": "这次修改范围过大，未替换当前正文。"
                    if task.task_type == "VALIDATE_REVISION_FIDELITY" and output.verdict == "FAIL"
                    else "Revision cannot safely proceed; inspect preserved evidence"
                },
                TaskStatus.BLOCKED,
            )
        return event, {"revision_artifact_id": str(record.id)}, TaskStatus.SUCCEEDED

    def check_persisted(self, workflow, artifact_id, run_id, event):
        record = self.repo.evidence(
            workflow.revision_request_id,
            {
                "REVISION_PLAN_READY": RevisionPlan,
                "REVISION_CANDIDATE_READY": RevisionCandidate,
                "REVISION_READY": RevisionResult,
            }[event],
        )
        if record is None or str(record.id) != artifact_id or record.run_id != run_id:
            raise DomainError("AUTHORITY_DENIED", "Revision event requires its exact recorded run")
        if event == "REVISION_PLAN_READY":
            if not record.body["revision_targets"]:
                raise DomainError("INVALID_STATE", "Blocked plan cannot execute")
            return None
        if event == "REVISION_CANDIDATE_READY":
            if not record.body["content"]:
                raise DomainError("INVALID_STATE", "Empty candidate cannot be validated")
            return None
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        version = self.core.repo.get_version(
            ObjectType.CHAPTER_VERSION, workflow.project_id, chapter.id, chapter.current_version
        )
        request = self.repo.get(workflow.revision_request_id)
        if (
            version.id != record.chapter_version_id
            or version.supersedes_id != request.source_chapter_version_id
            or digest(version.content) != record.body["content_hash"]
        ):
            raise DomainError("VERSION_CONFLICT", "Revision successor binding mismatch")
        return version

    def history(self, workflow_id, limit=100, offset=0):
        from novel_os.repositories.workflows import WorkflowRepository

        WorkflowRepository(self.session).get(workflow_id)
        values = []
        for request, plan, result, binding, candidate in self.repo.history_bundles(
            workflow_id, limit, offset
        ):
            values.append(
                dict(
                    request=asdict(request),
                    source_binding=asdict(binding) if binding else None,
                    plan=asdict(plan) if plan else None,
                    result=asdict(result) if result else None,
                    candidate=asdict(candidate) if candidate else None,
                )
            )
        return values
