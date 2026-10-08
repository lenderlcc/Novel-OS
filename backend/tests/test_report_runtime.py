"""Pure preparation preserves exact report identity and the existing smoke contract."""

from dataclasses import replace
from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime, ExecutionResult


class CountingMock(MockModelProvider):
    def __init__(self):
        super().__init__()
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return super().generate(request)


def test_report_preparation_and_execution_share_exact_id_package_and_prompt():
    provider = CountingMock()
    runtime = AgentRuntime(provider)
    values = dict(task_id=uuid4(), project_id=uuid4(), target_ref=uuid4(), requirements=("bound",))
    prepared = runtime.prepare_report("INTERPRET_CHARACTER_PROFILE", "Direct", **values)
    assert not isinstance(prepared, ExecutionResult) and provider.requests == []
    execution = runtime.execute_report(
        "INTERPRET_CHARACTER_PROFILE", "Direct", prepared=prepared, **values
    )
    assert execution.error_code is None and execution.result.task_id == values["task_id"]
    assert provider.requests == [prepared]
    assert execution.context_package_id == prepared.context_package.context_package_id
    assert execution.context_package_hash == prepared.context_package.package_hash


@pytest.mark.parametrize(
    "field", ["task_id", "project_id", "target_ref", "requirements", "text", "hash"]
)
def test_prepared_report_cannot_be_reused_for_another_identity_or_input(field):
    provider = CountingMock()
    runtime = AgentRuntime(provider)
    values = dict(task_id=uuid4(), project_id=uuid4(), target_ref=uuid4(), requirements=("bound",))
    prepared = runtime.prepare_report("INTERPRET_CHARACTER_PROFILE", "Direct", **values)
    text = "Direct"
    if field in {"task_id", "project_id", "target_ref"}:
        values[field] = uuid4()
    elif field == "requirements":
        values[field] = ("different",)
    elif field == "text":
        text = "Different"
    else:
        prepared = replace(
            prepared, context_package=replace(prepared.context_package, package_hash="0" * 64)
        )
    execution = runtime.execute_report(
        "INTERPRET_CHARACTER_PROFILE", text, prepared=prepared, **values
    )
    assert execution.error_code == "CONTEXT_STALE" and provider.requests == []


def test_smoke_remains_pure_successful_and_report_whitelist_stays_closed():
    provider = CountingMock()
    runtime = AgentRuntime(provider)
    execution = runtime.execute_smoke("A bounded demo")
    assert execution.error_code is None and execution.result.result.kind == "requirement_demo"
    assert len(provider.requests) == 1 and execution.context_package_id is not None
    failure = runtime.prepare_report("WRITE_CHAPTER", "Forbidden")
    assert failure.error_code == "AUTHORITY_DENIED" and len(provider.requests) == 1
