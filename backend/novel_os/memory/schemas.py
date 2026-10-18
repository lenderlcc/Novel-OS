"""The sole A07 structured output contract; authority is always service-owned."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.planning_schemas import Confidence, EvidenceRef, ShortText, Text
from novel_os.agents.schemas import AgentResult, Proposal, StrictOutput
from novel_os.domain.memory import DERIVED_TYPES, EpistemicStatus, MemoryType


class SubjectRef(StrictOutput):
    name: ShortText = Field(
        description=(
            "For EXISTING, reuse the supplied canonical subject name. For NEW, copy a "
            "contiguous name from the accepted prose exactly; do not append a type or label."
        )
    )
    kind: Literal["CHARACTER", "OBJECT", "LOCATION", "EVENT", "GROUP"]
    logical_id: UUID | None
    aliases: list[ShortText] = Field(
        max_length=10,
        description=(
            "For NEW subjects, every alias must also appear verbatim in the accepted prose. "
            "Do not synthesize names or translations; use [] when no explicit alias is evidenced."
        ),
    )
    resolution: Literal["EXISTING", "NEW", "AMBIGUOUS"]

    @model_validator(mode="after")
    def consistent_identity(self):
        if (self.resolution == "EXISTING") != (self.logical_id is not None):
            raise ValueError("Only an existing subject has a logical_id")
        return self


class MemoryEvidence(StrictOutput):
    paragraph_index: int = Field(strict=True, ge=1)
    short_excerpt: str = Field(min_length=1, max_length=300)
    reason: ShortText


class BoundaryCheck(StrictOutput):
    source_ref: EvidenceRef
    outcome: Literal["COMPATIBLE", "CONFLICT", "UNCERTAIN"]
    reason: ShortText


class MemoryCandidate(StrictOutput):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    candidate_type: MemoryType
    subject_ref: SubjectRef | None
    statement: Text
    # A stable attribute/topic and concise canonical value permit deterministic comparison.
    slot: ShortText
    value: ShortText
    state_before: ShortText | None
    state_after: ShortText | None
    epistemic_status: EpistemicStatus | None
    importance: Literal["CONTINUITY", "DERIVED_HINT"]
    evidence: list[MemoryEvidence] = Field(min_length=1, max_length=5)
    target_layer: Literal["CANON", "DERIVED"]
    source_refs: list[EvidenceRef] = Field(min_length=1, max_length=1)
    confidence: Confidence
    existing_entry_id: UUID | None = Field(
        description=(
            "The current committed memory record ID: copy the matching context item's "
            "source_id for the same subject, memory_type and slot. Do not use its "
            "logical_id, subject_id or source_chapter_version_id. Use null if no entry matches."
        )
    )
    known_fact_id: UUID | None = None
    authority_checks: list[BoundaryCheck] = Field(max_length=400)
    uncertainty: ShortText | None = Field(
        description=(
            "Unresolved truth of an OPEN_THREAD or an owner's BELIEVES/SUSPECTS/DOUBTS "
            "claim is allowed, without asserting Canon truth. Uncertain owner identity "
            "must use subject_ref.resolution=AMBIGUOUS; confidence measures evidence "
            "that the owner holds this belief. Uncertainty still blocks confirmed facts/KNOWS."
        )
    )

    @model_validator(mode="after")
    def type_boundaries(self):
        derived = self.candidate_type in DERIVED_TYPES
        if self.target_layer != ("DERIVED" if derived else "CANON"):
            raise ValueError("Memory type and layer disagree")
        if self.importance != ("DERIVED_HINT" if derived else "CONTINUITY"):
            raise ValueError("Only future-relevant information belongs in memory")
        knowledge = self.candidate_type == MemoryType.CHARACTER_KNOWLEDGE
        if knowledge != (self.epistemic_status is not None):
            raise ValueError("Only character knowledge carries an epistemic status")
        if self.known_fact_id is not None and self.epistemic_status != EpistemicStatus.KNOWS:
            raise ValueError("Only KNOWS may explicitly bind a confirmed Canon fact")
        if (
            self.candidate_type
            in {
                MemoryType.CHARACTER_STATE,
                MemoryType.CHARACTER_KNOWLEDGE,
                MemoryType.RELATIONSHIP_STATE,
            }
            and self.state_after != self.value
        ):
            raise ValueError("State candidates require state_after equal to value")
        if self.candidate_type != MemoryType.DERIVED_CHAPTER_SUMMARY and not self.subject_ref:
            raise ValueError("Memory requires an identified subject")
        if (
            self.candidate_type in {MemoryType.CHARACTER_STATE, MemoryType.CHARACTER_KNOWLEDGE}
            and self.subject_ref.kind != "CHARACTER"
        ):
            raise ValueError("Character state/knowledge requires its character owner")
        # Missing state fields retain a static fact or a historical initial thread.
        if (
            (
                self.candidate_type == MemoryType.OPEN_THREAD
                or (
                    self.candidate_type == MemoryType.CANON_FACT
                    and self.subject_ref.kind == "OBJECT"
                )
            )
            and (self.state_before is not None or self.state_after is not None)
            and self.state_after != self.value
        ):
            raise ValueError("Object/thread states require state_after equal to value")
        return self


class MemoryExtractionOutput(StrictOutput):
    kind: Literal["chapter_memory"]
    candidates: list[MemoryCandidate] = Field(max_length=40)

    @model_validator(mode="after")
    def bounded_unique_candidates(self):
        if len({c.id for c in self.candidates}) != len(self.candidates):
            raise ValueError("Candidate identifiers must be unique")
        if sum(c.candidate_type == MemoryType.DERIVED_CHAPTER_SUMMARY for c in self.candidates) > 1:
            raise ValueError("At most one derived summary per accepted chapter")
        return self


class MemoryAgentResult(AgentResult):
    result: MemoryExtractionOutput
    proposed_changes: list[Proposal] = Field(default_factory=list, max_length=0)
    memory_proposals: list[Proposal] = Field(default_factory=list, max_length=0)
