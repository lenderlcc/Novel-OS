"""Execution metadata must never masquerade as evidence of user requirements."""

from types import SimpleNamespace

import pytest

from novel_os.agents.planning_schemas import RequirementAgentResult
from novel_os.domain.errors import DomainError
from novel_os.services.planning_policy import ref_key, validate_brief_sources
from tests.planning_support import fixture_outputs

EXECUTION_RULE = "Planning only; no chapter prose"


def brief_and_source(raw, category):
    body = fixture_outputs()[0]
    source = next(
        ref for ref in body["result"]["source_refs"] if ref["source_type"] == "TASK_INPUT"
    )
    for field in (
        "must",
        "should",
        "preferences",
        "forbidden",
        "preserve",
        "quality_expectations",
        "change_requests",
        "persistent_preference_candidates",
    ):
        body["result"][field] = []
    body["result"][category] = [
        {
            "id": "execution-claim",
            "text": EXECUTION_RULE,
            "quote": EXECUTION_RULE,
            "source_ref": source,
        }
    ]
    result = RequirementAgentResult.model_validate(body)
    key = next(ref_key(ref) for ref in result.result.source_refs if ref.source_type == "TASK_INPUT")
    selected = {
        key: SimpleNamespace(structured_payload={"objective": raw, "constraints": [EXECUTION_RULE]})
    }
    return result.result, selected, {ref_key(ref) for ref in result.result.source_refs}


@pytest.mark.parametrize("category", ["must", "forbidden", "preserve"])
def test_execution_control_is_not_user_quote_evidence(category):
    output, selected, source_keys = brief_and_source("两人在码头相遇，保持合作。", category)
    with pytest.raises(DomainError, match="quotation is not present") as error:
        validate_brief_sources(output, selected, source_keys)
    assert error.value.code == "AUTHORITY_DENIED"


def test_same_words_in_actual_user_objective_remain_valid_evidence():
    output, selected, source_keys = brief_and_source("请做章节规划。" + EXECUTION_RULE, "forbidden")
    validate_brief_sources(output, selected, source_keys)
