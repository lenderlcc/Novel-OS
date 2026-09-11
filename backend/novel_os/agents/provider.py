"""Minimal provider contract and deterministic mock; no real model integration."""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from novel_os.domain.agents import MockScenario


@dataclass(frozen=True)
class ModelRequest:
    task_id: UUID
    task_type: str
    attempt_number: int
    target_ref: UUID
    output_kind: str


class ProviderError(Exception):
    def __init__(self, code="MODEL_UNAVAILABLE"):
        self.code = code


class ModelProvider(ABC):
    @abstractmethod
    def generate(self, request: ModelRequest) -> str:
        """Return untrusted text for the normal parser/validators."""


class MockModelProvider(ModelProvider):
    def __init__(self, scenario=MockScenario.SUCCESS, *, delay_seconds=2.0):
        self.scenario = MockScenario(scenario)
        self.delay_seconds = delay_seconds

    def generate(self, request: ModelRequest) -> str:
        scenario = self.scenario
        if scenario == MockScenario.ALWAYS_FAIL or (
            scenario == MockScenario.MODEL_ERROR_ONCE and request.attempt_number == 1
        ):
            raise ProviderError("MODEL_TIMEOUT")
        if scenario == MockScenario.FORMAT_ERROR_ONCE and request.attempt_number == 1:
            return "{ invalid JSON"
        if scenario == MockScenario.MALFORMED_OUTPUT:
            return json.dumps({"task_id": str(request.task_id), "next_event": "UNTRUSTED"})
        if scenario == MockScenario.SLOW_SUCCESS:
            time.sleep(self.delay_seconds)
        output = {
            "ack": {"kind": "ack", "simulation": True},
            "plan": {
                "kind": "plan",
                "objective": "Mock plan for " + str(request.task_id),
                "required_outcome": "Exercise the asynchronous execution contract",
            },
            "draft": {
                "kind": "draft",
                "content": "Mock chapter body for " + str(request.task_id),
                "change_reason": "NOVEL-004 mock execution",
            },
            "review": {
                "kind": "review",
                "verdict": "FAIL" if scenario == MockScenario.QUALITY_FAIL else "PASS",
            },
        }[request.output_kind]
        status = {MockScenario.BLOCKED: "BLOCKED", MockScenario.NEEDS_HUMAN: "NEEDS_HUMAN"}.get(
            scenario, "SUCCESS"
        )
        return json.dumps(
            {
                "task_id": str(request.task_id),
                "status": status,
                "result": output if status == "SUCCESS" else None,
                "confidence": 0.2 if scenario == MockScenario.LOW_CONFIDENCE else 0.95,
                "assumptions": [],
                "issues": [],
                "proposed_changes": [
                    {"capability": "APPROVE", "target_ref": str(request.target_ref)}
                ]
                if scenario == MockScenario.AUTHORITY_VIOLATION
                else [],
                "memory_proposals": [],
                "escalation": {"required": True, "reason": "Mock requires user decision"}
                if status == "NEEDS_HUMAN"
                else None,
            }
        )
