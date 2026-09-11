from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from novel_os.domain import workflow as domain
from novel_os.domain.errors import DomainError
from novel_os.models import workflow as orm
from novel_os.repositories.core import to_domain

MAPPINGS = {
    domain.WorkflowDefinition: orm.WorkflowDefinitionModel,
    domain.WorkflowInstance: orm.WorkflowInstanceModel,
    domain.WorkflowEvent: orm.WorkflowEventModel,
    domain.WorkflowTransition: orm.WorkflowTransitionModel,
    domain.HumanGate: orm.HumanGateModel,
}


class WorkflowRepository:
    """Flush-only persistence; application use cases own the transaction."""

    def __init__(self, session: Session):
        self.session = session

    def add(self, entity):
        self.session.add(MAPPINGS[type(entity)](**asdict(entity)))
        self.session.flush()
        return entity

    def save(self, entity):
        if not isinstance(entity, domain.WorkflowInstance | domain.HumanGate):
            raise DomainError("IMMUTABLE_RECORD", "Workflow history and definitions are immutable")
        model = self.session.get(MAPPINGS[type(entity)], entity.id)
        if model is None:
            raise DomainError("NOT_FOUND", "Workflow object not found")
        for name, value in asdict(entity).items():
            setattr(model, name, value)
        self.session.flush()
        return entity

    def ensure_definition(self, definition: domain.WorkflowDefinition):
        self.session.execute(
            insert(orm.WorkflowDefinitionModel)
            .values(**asdict(definition))
            .on_conflict_do_nothing()
        )
        stored = self.definition(definition.id, definition.version)
        if stored.digest != definition.digest or stored.body != definition.body:
            raise DomainError("INVALID_DEFINITION", "A persisted definition version cannot change")

    def definition(self, definition_id: str, version: int):
        model = self.session.get(orm.WorkflowDefinitionModel, (definition_id, version))
        if model is None:
            raise DomainError("INVALID_DEFINITION", "Bound workflow definition is missing")
        return to_domain(model, domain.WorkflowDefinition)

    def get(self, workflow_id: UUID, *, for_update: bool = False):
        statement = select(orm.WorkflowInstanceModel).where(
            orm.WorkflowInstanceModel.id == workflow_id
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        model = self.session.scalar(statement)
        if model is None:
            raise DomainError("NOT_FOUND", "Workflow not found")
        return to_domain(model, domain.WorkflowInstance)

    def event(self, event_id: UUID):
        model = self.session.get(orm.WorkflowEventModel, event_id)
        return to_domain(model, domain.WorkflowEvent) if model else None

    def gate(self, gate_id: UUID):
        model = self.session.get(orm.HumanGateModel, gate_id)
        if model is None:
            raise DomainError("NOT_FOUND", "Human gate not found")
        return to_domain(model, domain.HumanGate)

    def waiting_gate(self, workflow_id: UUID):
        model = self.session.scalar(
            select(orm.HumanGateModel)
            .where(
                orm.HumanGateModel.workflow_id == workflow_id,
                orm.HumanGateModel.status == domain.GateStatus.WAITING,
            )
            .execution_options(populate_existing=True)
        )
        return to_domain(model, domain.HumanGate) if model else None

    def list_history(self, workflow_id: UUID, limit: int, offset: int):
        return self._list(
            domain.WorkflowTransition,
            workflow_id,
            limit,
            offset,
            orm.WorkflowTransitionModel.to_version,
        )

    def list_gates(self, workflow_id: UUID, limit: int, offset: int):
        return self._list(
            domain.HumanGate, workflow_id, limit, offset, orm.HumanGateModel.opened_state_version
        )

    def _list(self, entity_type, workflow_id, limit, offset, order):
        model = MAPPINGS[entity_type]
        rows = self.session.scalars(
            select(model)
            .where(model.workflow_id == workflow_id)
            .order_by(order)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, entity_type) for row in rows]
