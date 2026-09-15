"""Append-only Writing persistence; the application owns every transaction."""

from dataclasses import asdict, fields

from sqlalchemy import select

from novel_os.domain.errors import DomainError
from novel_os.domain.writing import WritingGeneration, WritingTaskBinding
from novel_os.models.writing import WritingGenerationModel, WritingTaskBindingModel


class WritingRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def entity(row, kind):
        if row is None:
            return None
        return kind(
            **{
                f.name: getattr(row, "result_metadata" if f.name == "metadata" else f.name)
                for f in fields(kind)
            }
        )

    def add(self, entity):
        values = asdict(entity)
        model = WritingTaskBindingModel
        if isinstance(entity, WritingGeneration):
            model = WritingGenerationModel
            values["result_metadata"] = values.pop("metadata")
        self.session.add(model(**values))
        self.session.flush()
        return entity

    def binding(self, task_id):
        result = self.entity(self.session.get(WritingTaskBindingModel, task_id), WritingTaskBinding)
        if result is None:
            raise DomainError("CONTEXT_MISSING", "Writing task has no exact Plan binding")
        return result

    def latest_binding(self, workflow_id):
        from novel_os.models.agents import AgentTaskModel

        return self.entity(
            self.session.scalar(
                select(WritingTaskBindingModel)
                .join(AgentTaskModel, AgentTaskModel.task_id == WritingTaskBindingModel.task_id)
                .where(WritingTaskBindingModel.workflow_id == workflow_id)
                .order_by(AgentTaskModel.workflow_state_version.desc())
                .limit(1)
            ),
            WritingTaskBinding,
        )

    def generation(self, generation_id):
        result = self.entity(
            self.session.get(WritingGenerationModel, generation_id), WritingGeneration
        )
        if result is None:
            raise DomainError("NOT_FOUND", "Writing generation is not available")
        return result

    def for_version(self, project_id, chapter_id, version_id):
        return self.entity(
            self.session.scalar(
                select(WritingGenerationModel).where(
                    WritingGenerationModel.project_id == project_id,
                    WritingGenerationModel.chapter_id == chapter_id,
                    WritingGenerationModel.chapter_version_id == version_id,
                )
            ),
            WritingGeneration,
        )

    def history(self, workflow_id, limit=100, offset=0):
        return [
            self.entity(row, WritingGeneration)
            for row in self.session.scalars(
                select(WritingGenerationModel)
                .where(WritingGenerationModel.workflow_id == workflow_id)
                .order_by(WritingGenerationModel.created_at, WritingGenerationModel.id)
                .limit(limit)
                .offset(offset)
            )
        ]
