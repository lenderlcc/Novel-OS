"""Offline plumbing fixture, not a natural-language interpretation algorithm."""


def response(request, scenario):
    item = next(i for i in request.context_package.items if i.selector_id == "human-feedback")
    feedback = item.structured_payload
    return dict(
        task_id=str(request.task_id),
        status="SUCCESS",
        confidence=0.8,
        assumptions=[],
        issues=[],
        proposed_changes=[],
        memory_proposals=[],
        escalation=None,
        result=dict(
            kind="human_feedback_interpretation",
            feedback_id=feedback["feedback_id"],
            source_chapter_version_id=feedback["source_chapter_version_id"],
            intent_summary="离线反馈链路测试，不代表真实语义理解。",
            requested_changes=[
                dict(description="离线验证局部表达修改", target_regions=["局部表达"])
            ],
            preserve_requests=["保留已有场景"],
            do_not_change=["不修改其他情节"],
            target_regions=["局部表达"],
            quality_concerns=["表达自然度"],
            scope="LOCAL",
            safe_inferences=["离线固定结果"],
            ambiguities=[],
            conflicts=[],
            change_impact="PROSE_ONLY",
            action="REVISION",
            user_message="将按反馈修改局部表达。",
            decision_question=None,
            feedback_evidence=[feedback["raw_feedback"][:30]],
            supporting_review_issue_ids=[],
            source_refs=[
                dict(
                    source_type="EXTENSION",
                    source_id=str(item.source_id),
                    source_version=1,
                    field=None,
                )
            ],
            confidence=0.8,
        ),
    )
