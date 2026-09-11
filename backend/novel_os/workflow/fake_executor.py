"""Synchronous test/dev simulator. Produces events; never writes state or chooses targets."""

from uuid import UUID, uuid4

from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState, EventCommand, WorkflowInstance

EVENTS = {
    ChapterState.C01_REQUIREMENT_INTAKE: "AGENT_SUCCEEDED",
    ChapterState.C02_CONTEXT_ASSEMBLY: "CONTEXT_READY",
    ChapterState.C03_REQUIREMENT_READY: "AGENT_SUCCEEDED",
    ChapterState.C04_CHAPTER_PLANNING: "PLAN_READY",
    ChapterState.C05_PLAN_REVIEW: "PLAN_REVIEW_PASSED",
    ChapterState.C07_WRITING: "DRAFT_READY",
    ChapterState.C08_DETERMINISTIC_CHECK: "DETERMINISTIC_CHECK_PASSED",
    ChapterState.C09_INTERNAL_REVIEW: "REVIEW_PASSED",
    ChapterState.C10_REVISION: "REVISION_READY",
    ChapterState.C11_INTERNAL_PASS: "READY_FOR_USER",
    ChapterState.C13_USER_FEEDBACK_DIAGNOSIS: "LOCAL_CHANGE",
    ChapterState.C14_MEMORY_PREPARATION: "MEMORY_CHANGESET_READY",
    ChapterState.C15_MEMORY_COMMIT: "MEMORY_COMMITTED",
}
FAIL_EVENTS = {
    ChapterState.C05_PLAN_REVIEW: "REVIEW_FAILED",
    ChapterState.C08_DETERMINISTIC_CHECK: "DETERMINISTIC_CHECK_FAILED",
    ChapterState.C09_INTERNAL_REVIEW: "REVIEW_FAILED",
}


class FakeExecutor:
    def execute(
        self, instance: WorkflowInstance, *, event_id: UUID | None = None, outcome: str = "success"
    ) -> EventCommand:
        if instance.current_state not in EVENTS:
            raise DomainError("ILLEGAL_TRANSITION", "This state does not execute a fake task")
        event = EVENTS[instance.current_state]
        if outcome == "technical_failure":
            event = "EXECUTOR_FAILED"
        elif outcome == "fatal_failure":
            event = "FATAL_ERROR"
        elif outcome == "review_failure" and instance.current_state in FAIL_EVENTS:
            event = FAIL_EVENTS[instance.current_state]
        elif (
            outcome == "replan"
            and instance.current_state == ChapterState.C13_USER_FEEDBACK_DIAGNOSIS
        ):
            event = "CHAPTER_REPLAN_REQUIRED"
        elif outcome != "success":
            raise DomainError("VALIDATION_ERROR", "Unsupported fake outcome for this state")
        payload = {}
        if event == "PLAN_READY":
            payload = {
                "objective": f"Simulated plan {instance.planning_iteration_count}",
                "required_outcome": "Demonstrate workflow transitions",
            }
        elif event in {"DRAFT_READY", "REVISION_READY"}:
            payload = {
                "content": (
                    f"Simulated chapter {instance.chapter_id}; revision {instance.revision_count}."
                ),
                "change_reason": "NOVEL-003 fake execution",
            }
        elif event in {"EXECUTOR_FAILED", "FATAL_ERROR"}:
            payload = {"reason": "Simulated executor failure"}
        return EventCommand(
            event_id=event_id or uuid4(),
            event_type=event,
            expected_state_version=instance.state_version,
            origin_state=instance.current_state,
            payload=payload,
        )
