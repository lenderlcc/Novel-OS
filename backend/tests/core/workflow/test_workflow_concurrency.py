from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from novel_os.domain.core import CommandContext
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import EventCommand, GateDecision
from novel_os.models.workflow import WorkflowEventModel, WorkflowTransitionModel
from novel_os.workflow.runtime import WorkflowRuntime

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("same_event", [False, True])
def test_simultaneous_events_one_transition(driver, core_database, same_event):
    barrier = Barrier(2)
    event_id = uuid4()
    workflow_id = UUID(driver.workflow["id"])

    def dispatch(index):
        command = EventCommand(
            event_id=event_id if same_event else uuid4(),
            event_type="USER_SUBMITTED",
            expected_state_version=1,
        )
        with core_database.session() as session:
            barrier.wait(timeout=5)
            try:
                return WorkflowRuntime(session).dispatch_event(
                    workflow_id, command, CommandContext(f"parallel-{index}", "user")
                )
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(dispatch, range(2)))
    if same_event:
        assert sorted(r.duplicate for r in results) == [False, True]
    else:
        assert sum(r == "VERSION_CONFLICT" for r in results) == 1
        assert sum(not isinstance(r, str) for r in results) == 1
    assert driver.refresh()["state_version"] == 2
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowTransitionModel)) == 2
        assert session.scalar(select(func.count()).select_from(WorkflowEventModel)) == 2


def test_simultaneous_gate_decisions_only_one_approval(driver, core_database):
    driver.advance_to("C06_PLAN_APPROVAL")
    gate_id = UUID(driver.gate()["id"])
    version = driver.workflow["state_version"]
    barrier = Barrier(2)

    def approve(index):
        with core_database.session() as session:
            barrier.wait(timeout=5)
            try:
                return WorkflowRuntime(session).decide_gate(
                    gate_id,
                    uuid4(),
                    version,
                    1,
                    GateDecision.APPROVE,
                    "approve",
                    CommandContext(f"gate-{index}", "user"),
                )
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, range(2)))
    assert sum(r == "VERSION_CONFLICT" for r in results) == 1
    assert driver.refresh()["state_version"] == version + 1
    assert driver.workflow["current_state"] == "C07_WRITING"
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] == 1
