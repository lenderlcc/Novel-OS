from novel_os.domain.agents import RunStatus, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.domain.prompts import PromptLineage
from novel_os.prompts.contracts import ModuleType
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.agent_results import AgentResultHandler, valid_lease
from novel_os.services.task_history import TaskHistory, worker_context


class PromptLineageService:
    def __init__(self, session):
        self.session = session
        self.repo = PromptLineageRepository(session)
        self.tasks = AgentTaskRepository(session)

    def get(self, run_id):
        self.tasks.run(run_id)
        lineage = self.repo.for_run(run_id)
        if lineage is None:
            raise DomainError("NOT_FOUND", "This run has no prompt lineage")
        return lineage

    def bind(self, lease, request):
        """A short fenced transaction; no provider call while this transaction is open."""
        with self.session.begin():
            task, _ = AgentResultHandler(self.session).lock_task(lease.task_id)
            run = self.tasks.run(lease.run_id)
            if (
                task.status != TaskStatus.RUNNING
                or run.status != RunStatus.RUNNING
                or run.task_id != task.task_id
                or run.lease_token != lease.token
                or run.worker_id != lease.worker_id
                or not valid_lease(task, lease, self.tasks.clock())
            ):
                return False
            if (request.task_id, request.attempt_number, request.task_type, request.target_ref) != (
                task.task_id,
                task.attempt_count,
                task.task_type,
                task.target_ref,
            ):
                raise DomainError("VALIDATION_ERROR", "Prompt execution binding mismatch")
            if (run.provider, run.model) != (request.profile.provider, request.profile.model):
                raise DomainError(
                    "VERSION_CONFLICT", "Claimed model does not match prepared request"
                )
            existing = self.repo.for_run(run.run_id)
            if existing:
                if (
                    existing.compiled_prompt_hash != request.prompt.compiled_hash
                    or existing.model_profile_hash != request.profile.profile_hash
                ):
                    raise DomainError(
                        "VERSION_CONFLICT", "Run already has a different prompt binding"
                    )
                return True
            pins = [item.module.pin().model_dump() for item in request.prompt.modules]
            if not self.repo.matches_historical_pins(pins):
                raise DomainError(
                    "VERSION_CONFLICT", "Prompt version conflicts with recorded history"
                )
            layers = {
                kind: [
                    item.module.pin().model_dump()
                    for item in request.prompt.modules
                    if item.module.module_type == kind
                ]
                for kind in ModuleType
            }
            lineage = self.repo.add(
                PromptLineage(
                    agent_run_id=run.run_id,
                    task_id=task.task_id,
                    system_policy=layers[ModuleType.SYSTEM_POLICY][0],
                    agent_role=layers[ModuleType.AGENT_ROLE][0],
                    task_template=layers[ModuleType.TASK_TEMPLATE][0],
                    skills=layers[ModuleType.SKILL],
                    quality_profile=layers[ModuleType.QUALITY_PROFILE][0],
                    output_schema_id=request.prompt.output.schema_id,
                    output_schema_version=request.prompt.output.version,
                    output_schema_hash=request.prompt.output.schema_hash,
                    model_profile_id=request.profile.profile_id,
                    model_profile_hash=request.profile.profile_hash,
                    model_profile=request.profile.model_dump(mode="json"),
                    compiled_prompt_hash=request.prompt.compiled_hash,
                    compiler_version=request.prompt.compiler_version,
                    created_at=self.tasks.clock(),
                )
            )
            TaskHistory(self.session).audit(
                task,
                None,
                lineage,
                worker_context(lease.worker_id, run.run_id),
                "Exact prompt configuration bound to run",
            )
            return True
