"""Load immutable, versioned transition tables. YAML never contains executable code."""

import hashlib
import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import TERMINAL_STATES, ChapterState, WorkflowDefinition

GUARDS = frozenset({"writable", "plan_current", "plan_approved", "draft_current", "draft_approved"})
CONTROL_EVENTS = frozenset({"PAUSE", "RESUME", "CANCEL", "BLOCK", "EXECUTOR_FAILED", "FATAL_ERROR"})


class TransitionRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: ChapterState
    event: str = Field(pattern=r"^[A-Z][A-Z_]{1,63}$")
    target: ChapterState
    actor: ActorType
    guards: tuple[str, ...] = ()
    effect: Literal["create_plan", "create_draft"] | None = None


class DefinitionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")
    version: int = Field(strict=True, ge=1)
    initial_state: Literal[ChapterState.C00_CREATED]
    max_technical_retries: int = Field(strict=True, ge=0, le=10)
    simulation: Literal[True]
    transitions: tuple[TransitionRule, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_graph(self):
        seen = set()
        for rule in self.transitions:
            key = (rule.source, rule.event)
            if (
                key in seen
                or rule.source in TERMINAL_STATES
                or rule.source == ChapterState.C90_BLOCKED
            ):
                raise ValueError("Duplicate transition or outgoing terminal/control transition")
            seen.add(key)
            if rule.event in CONTROL_EVENTS or set(rule.guards) - GUARDS:
                raise ValueError("Reserved event or unknown guard")
            if rule.target in {
                ChapterState.C90_BLOCKED,
                ChapterState.C91_FAILED,
                ChapterState.C92_CANCELLED,
            }:
                raise ValueError("Exceptional states belong to runtime control handling")
            required = {
                ChapterState.C07_WRITING: "plan_approved",
                ChapterState.C14_MEMORY_PREPARATION: "draft_approved",
                ChapterState.C15_MEMORY_COMMIT: "draft_approved",
                ChapterState.C16_COMPLETED: "draft_approved",
                ChapterState.C06_PLAN_APPROVAL: "plan_current",
                ChapterState.C12_USER_REVIEW: "draft_current",
            }.get(rule.target)
            if required and required not in rule.guards:
                raise ValueError("Missing mandatory artifact guard")
            human_event = rule.event in {"USER_APPROVED", "USER_REJECTED"}
            gate_source = rule.source in {
                ChapterState.C06_PLAN_APPROVAL,
                ChapterState.C12_USER_REVIEW,
            }
            if human_event != gate_source or (human_event and rule.actor != ActorType.USER):
                raise ValueError("Gate transitions require user decisions")
            if rule.effect and rule.actor != ActorType.AGENT:
                raise ValueError("Artifact effects require executor results")
            if rule.effect == "create_plan" and (rule.source, rule.event) != (
                ChapterState.C04_CHAPTER_PLANNING,
                "PLAN_READY",
            ):
                raise ValueError("Plan effect belongs to planning completion")
            if rule.effect == "create_draft" and rule.source not in {
                ChapterState.C07_WRITING,
                ChapterState.C10_REVISION,
            }:
                raise ValueError("Draft effect belongs to writing or revision")
        reachable = {self.initial_state}
        for _ in ChapterState:
            reachable |= {r.target for r in self.transitions if r.source in reachable}
        required_states = set(ChapterState) - {
            ChapterState.C90_BLOCKED,
            ChapterState.C91_FAILED,
            ChapterState.C92_CANCELLED,
        }
        if not required_states <= reachable:
            raise ValueError("Chapter states must be reachable")
        return self


class UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError("YAML keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeySafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def digest(body: dict) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class WorkflowDefinitionLoader:
    def from_body(self, body: dict) -> WorkflowDefinition:
        try:
            validated = DefinitionBody.model_validate(body)
            canonical = validated.model_dump(mode="json")
        except (ValidationError, ValueError, TypeError, RecursionError):
            raise DomainError("INVALID_DEFINITION", "Invalid workflow definition") from None
        return WorkflowDefinition(
            id=validated.id, version=validated.version, body=canonical, digest=digest(canonical)
        )

    def load(self, path: Path | None = None) -> WorkflowDefinition:
        resource = path or files("novel_os.workflow").joinpath(
            "definitions/chapter-production.v1.yaml"
        )
        try:
            content = resource.read_text(encoding="utf-8")
            if len(content) > 100_000:
                raise ValueError("Definition too large")
            body = yaml.load(content, Loader=UniqueKeySafeLoader)
        except (OSError, yaml.YAMLError, ValueError, RecursionError):
            raise DomainError("INVALID_DEFINITION", "Invalid workflow YAML") from None
        return self.from_body(body)


class WorkflowDefinitionRegistry:
    def __init__(self, definitions: list[WorkflowDefinition] | None = None):
        self._definitions = {}
        for definition in (
            definitions if definitions is not None else [WorkflowDefinitionLoader().load()]
        ):
            self.register(definition)

    def register(self, definition: WorkflowDefinition) -> None:
        checked = WorkflowDefinitionLoader().from_body(definition.body)
        if (definition.id, definition.version, definition.digest) != (
            checked.id,
            checked.version,
            checked.digest,
        ):
            raise DomainError("INVALID_DEFINITION", "Definition identity or digest mismatch")
        key = (definition.id, definition.version)
        previous = self._definitions.get(key)
        if previous is not None and previous.digest != definition.digest:
            raise DomainError("INVALID_DEFINITION", "A definition version cannot be overwritten")
        self._definitions[key] = deepcopy(definition)

    def get(self, definition_id: str, version: int) -> WorkflowDefinition:
        try:
            return deepcopy(self._definitions[(definition_id, version)])
        except KeyError:
            raise DomainError("INVALID_DEFINITION", "Unknown workflow definition version") from None


class EventDispatcher:
    def __init__(self, definition: WorkflowDefinition):
        checked = WorkflowDefinitionLoader().from_body(definition.body)
        if (checked.id, checked.version, checked.digest) != (
            definition.id,
            definition.version,
            definition.digest,
        ):
            raise DomainError("INVALID_DEFINITION", "Stored workflow definition is corrupt")
        self.definition = DefinitionBody.model_validate(checked.body)
        self.rules = {(r.source, r.event): r for r in self.definition.transitions}

    def resolve(self, state: ChapterState, event: str) -> TransitionRule:
        try:
            return self.rules[(state, event)]
        except KeyError:
            raise DomainError(
                "ILLEGAL_TRANSITION", "Event is not allowed in the current state"
            ) from None
