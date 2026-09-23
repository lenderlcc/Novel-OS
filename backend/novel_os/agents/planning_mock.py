"""Deterministic contract fixtures, NOT a natural-language interpretation algorithm.

Real interpretation uses the versioned prompts and configured ModelProvider. Tests can
inject recorded structured responses to exercise language/ambiguity cases offline.
"""

from copy import deepcopy

from novel_os.agents.planning_schemas import REQUIREMENT_FIELDS
from novel_os.domain.agents import MockScenario


def source_ref(item):
    return {
        "source_type": item.source_type.value,
        "logical_id": str(item.logical_id),
        "version": item.source_version,
    }


def response(request, scenario):
    items = request.context_package.items
    kind = request.output_kind
    if kind == "creative_brief":
        raw = next(item for item in items if item.source_type == "TASK_INPUT")
        text = raw.structured_payload["objective"][:1200]
        needs_human = scenario == MockScenario.NEEDS_HUMAN
        output = {
            "kind": kind,
            "intent_summary": text,
            "chapter_objective": text,
            "must": [{"id": "M1", "text": text, "source_ref": source_ref(raw), "quote": text}],
            "should": [],
            "preferences": [],
            "forbidden": [],
            "preserve": [],
            "quality_expectations": [],
            "change_requests": [],
            "required_outcome": text,
            "desired_reader_effect": (
                "Mock contract fixture; semantic interpretation is not evaluated"
            ),
            "character_focus": [],
            "plot_focus": [],
            "creative_freedom": {
                "level": "MEDIUM",
                "allowed_operations": ["LOCAL_DETAIL", "SCENE_ORDER"],
                "scope_description": "Local structure only; major direction remains user-owned",
                "major_changes": "PROPOSAL_ONLY",
            },
            "unresolved_ambiguities": [
                {
                    "issue": "Mock consequential ambiguity",
                    "impact": "HIGH",
                    "confidence": 0.2,
                    "can_safely_infer": False,
                    "impact_explanation": "Would change major character direction",
                    "user_decision_needed": "Choose the intended major direction",
                }
            ]
            if needs_human
            else [],
            "assumptions": [],
            "conflicts": [],
            "persistent_preference_candidates": [],
            "source_refs": [source_ref(raw)],
            # No language understanding took place. Zero means unmeasured here,
            # not an empirically calibrated probability of an incorrect reading.
            "confidence": 0.0,
        }
        for index, item in enumerate(items):
            if item.source_type == "REQUIREMENT":
                payload = item.structured_payload
                value = payload["content"]
                output[REQUIREMENT_FIELDS[payload["requirement_type"]]].append(
                    {
                        "id": f"R{index}",
                        "text": value,
                        "quote": value,
                        "source_ref": source_ref(item),
                    }
                )
                output["source_refs"].append(source_ref(item))
    elif kind == "chapter_plan":
        brief_item = next(item for item in items if item.source_type == "CREATIVE_BRIEF")
        brief = brief_item.structured_payload
        locks = [
            item
            for item in items
            if item.locked
            and item.source_type in {"DECISION", "REQUIREMENT", "CHAPTER_PLAN", "CHAPTER_VERSION"}
        ]
        constraints = [item for field in REQUIREMENT_FIELDS.values() for item in brief[field]]
        output = {
            "kind": kind,
            "objective": brief["chapter_objective"],
            "required_outcome": brief["required_outcome"],
            "opening_function": "Establish the chapter conflict",
            "scenes": [
                {
                    "id": "S1",
                    "purpose": "Resolve the requested chapter objective",
                    "conflict": "Characters must choose how to act",
                    "key_change": "The intended outcome becomes possible",
                    "information_release": [],
                    "character_state_change": "A consequential local choice is made",
                    "exit_condition": "Required chapter outcome is reached",
                }
            ],
            "character_progression": [],
            "plot_progression": ["Advance the requested local conflict"],
            "information_release": [],
            "foreshadow_actions": [],
            "ending_function": "Complete the requested change",
            "ending_state": brief["required_outcome"],
            "creative_freedom": deepcopy(brief["creative_freedom"]),
            "constraints": [
                c["text"] for c in brief["must"] + brief["forbidden"] + brief["change_requests"]
            ],
            "preserved_elements": [c["text"] for c in brief["preserve"]],
            "locked_dependencies": [source_ref(item) for item in locks],
            "assumptions": [],
            "risks": [],
            "proposed_new_elements": [],
            "proposed_major_changes": [],
            "requirement_coverage": [
                {
                    "constraint_id": c["id"],
                    "covered": True,
                    "scope": "SCENE",
                    "scene_ids": ["S1"],
                    "explanation": "Applied in the scene intent",
                }
                for c in constraints
            ],
            "source_refs": [source_ref(brief_item)] + [source_ref(item) for item in locks],
        }
    else:
        brief_item = next(item for item in items if item.source_type == "CREATIVE_BRIEF")
        plan_item = next(
            item
            for item in items
            if item.source_type == "CHAPTER_PLAN" and "planning" in item.structured_payload
        )
        failed = scenario == MockScenario.QUALITY_FAIL
        output = {
            "kind": kind,
            "verdict": "FAIL" if failed else "PASS",
            "hard_gate_issues": [
                {"code": "OUTCOME_UNACHIEVABLE", "description": "Mock outcome repair required"}
            ]
            if failed
            else [],
            "quality_issues": [],
            "requirement_coverage": deepcopy(
                plan_item.structured_payload["planning"]["requirement_coverage"]
            ),
            "missing_requirements": [],
            "forbidden_violations": [],
            "locked_conflicts": [],
            "direction_conflicts": [],
            "logic_risks": [],
            "over_specification_issues": [],
            "recommendations": [],
            "source_refs": [source_ref(brief_item), source_ref(plan_item)],
            "confidence": 0.95,
        }
    needs_human = kind == "creative_brief" and scenario == MockScenario.NEEDS_HUMAN
    return {
        "task_id": str(request.task_id),
        "status": "NEEDS_HUMAN" if needs_human else "SUCCESS",
        "result": output,
        "confidence": output["confidence"]
        if kind == "creative_brief"
        else 0.2
        if scenario == MockScenario.LOW_CONFIDENCE
        else 0.95,
        "assumptions": [],
        "issues": [
            {
                "code": "MOCK_SEMANTICS_NOT_EVALUATED",
                "severity": "WARNING",
                "description": "Contract fixture only; not natural-language decomposition.",
            }
        ]
        if kind == "creative_brief"
        else [],
        "proposed_changes": [{"capability": "APPROVE", "target_ref": str(request.target_ref)}]
        if scenario == MockScenario.AUTHORITY_VIOLATION
        else [],
        "memory_proposals": [],
        "escalation": {"required": True, "reason": "Mock requires a user direction decision"}
        if needs_human
        else None,
    }
