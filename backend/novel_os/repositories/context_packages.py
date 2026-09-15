from sqlalchemy import select, text

from novel_os.context.serialization import ContextSerializer
from novel_os.domain.errors import DomainError
from novel_os.models.agents import AgentRunModel
from novel_os.models.context import ContextPackageModel


class ContextPackageRepository:
    def __init__(self, session):
        self.session = session

    def add(self, run_id, package):
        self.session.add(
            ContextPackageModel(
                context_package_id=package.context_package_id,
                agent_run_id=run_id,
                task_id=package.task_id,
                profile_id=package.profile_id,
                profile_version=package.profile_version,
                profile_hash=package.profile_hash,
                package_hash=package.package_hash,
                build_status=package.build_status.value,
                snapshot=ContextSerializer.snapshot(package),
                created_at=package.created_at,
            )
        )
        self.session.flush()
        return package

    def get(self, identity):
        row = self.session.get(ContextPackageModel, identity)
        if row is None:
            raise DomainError("NOT_FOUND", "Context package not found")
        return ContextSerializer.restore(row.snapshot)

    def for_run(self, run_id):
        row = self.session.scalar(
            select(ContextPackageModel).where(ContextPackageModel.agent_run_id == run_id)
        )
        return ContextSerializer.restore(row.snapshot) if row else None

    def for_task(self, task_id):
        # An explicit execution attempt order, never a content-version selection rule.
        row = self.session.scalar(
            select(ContextPackageModel)
            .join(AgentRunModel, AgentRunModel.run_id == ContextPackageModel.agent_run_id)
            .where(ContextPackageModel.task_id == task_id)
            .order_by(AgentRunModel.attempt_number.desc())
            .limit(1)
        )
        if row is None:
            raise DomainError("NOT_FOUND", "Task has no context package")
        return ContextSerializer.restore(row.snapshot)

    def check_profile(self, profile):
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || :key, 0))"),
            {"key": f"context-profile:{profile.profile_id}:{profile.version}"},
        )
        conflict = self.session.scalar(
            select(ContextPackageModel.context_package_id)
            .where(
                ContextPackageModel.profile_id == profile.profile_id,
                ContextPackageModel.profile_version == profile.version,
                ContextPackageModel.profile_hash != profile.profile_hash,
            )
            .limit(1)
        )
        if conflict:
            raise DomainError(
                "VERSION_CONFLICT", "Context profile conflicts with execution history"
            )
