"""Offline contract fixture. It makes no claim of literary judgment."""

from novel_os.quality.policy import paragraphs


def response(request, scenario):
    draft = next(i for i in request.context_package.items if i.selector_id == "target-version")
    evidence = {
        "paragraph_index": 1,
        "excerpt": paragraphs(draft.structured_payload["content"])[0][:100],
        "reason": "离线契约样例引用实际段落；不是人工或模型文学验收。",
    }
    result = dict(
        kind=request.output_kind,
        chapter_id=str(request.target_ref),
        chapter_version_id=str(draft.source_id),
        strengths=[
            {
                "description": "开篇保留了具体场景入口（Mock 证据样例）。",
                "evidence": [evidence],
                "preservation_direction": "修改时保留已经建立的场景入口。",
            }
        ],
        revision_priorities=[],
        source_refs=[],
        confidence=0.8,
    )
    compliance = request.output_kind == "chapter_compliance_review"
    if compliance:
        result.update(compliance_verdict="PASS", hard_gate_issues=[])
    else:
        result.update(narrative_verdict="PASS", audience_fit_verdict="PASS", quality_issues=[])
        if request.prompt.output.version >= 2:
            result["audience_evidence"] = []
        if scenario == "QUALITY_FAIL":
            result.update(
                narrative_verdict="FAIL",
                quality_issues=[
                    dict(
                        code="LOW_IMMERSION",
                        severity="P1",
                        category="NARRATIVE",
                        title="读者难以进入场景",
                        description="离线失败契约样例，不代表对本文的真实判断。",
                        evidence=[evidence],
                        source_refs=[],
                        impact="此样例将问题设为主要阅读阻碍。",
                        revision_direction="聚焦已有场景的感受和行动，不改变主线。",
                        confidence=0.8,
                        requires_revision=True,
                    )
                ],
            )
    return dict(
        task_id=str(request.task_id),
        status="SUCCESS",
        result=result,
        confidence=0.8,
        assumptions=[],
        issues=[],
        proposed_changes=[],
        memory_proposals=[],
        escalation=None,
    )
