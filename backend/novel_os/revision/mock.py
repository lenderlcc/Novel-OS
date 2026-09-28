"""Offline execution fixture only; never a literary quality verdict."""


def response(request, scenario):
    items = {i.selector_id: i for i in request.context_package.items}
    item = items["revision-contract"]
    contract = item.structured_payload
    ref = dict(source_type="EXTENSION", source_id=str(item.source_id), source_version=1, field=None)
    blocked = scenario in {"BLOCKED", "NEEDS_HUMAN"}
    common = dict(
        kind=request.output_kind,
        source_chapter_version_id=contract["source_chapter_version_id"],
        source_review_id=contract["source_review_id"],
        source_refs=[ref],
        confidence=0.8,
    )
    if request.output_kind == "revision_plan":
        output = dict(
            **common,
            chapter_id=str(request.target_ref),
            target_issue_ids=list(contract["target_issues"]),
            preserve_items=list(contract["preserve_items"]),
            do_not_change=list(contract["do_not_change"]),
            revision_strategy="以已有正文为基础，仅修改审阅指出的局部问题。",
            scope="TARGETED",
            revision_targets=[]
            if blocked
            else [
                dict(
                    issue_id=id,
                    issue_code=i["code"],
                    priority=i["severity"],
                    problem=i["description"],
                    revision_direction=i["revision_direction"],
                    evidence_refs=i["evidence"],
                )
                for id, i in contract["target_issues"].items()
            ],
            blocked_reasons=[
                dict(issue_id=id, reason="当前证据不足，不能安全增加故事事实。")
                for id in contract["target_issues"]
            ]
            if blocked
            else [],
        )
    else:
        plan = items["revision-plan"].structured_payload
        safe = [i["issue_id"] for i in plan["revision_targets"]]
        output = dict(
            **common,
            revision_plan_id=plan["revision_plan_id"],
            content=None
            if blocked
            else items["target-version"].structured_payload["content"]
            + "\n\n（离线修订链路验证，不代表真实改进。）",
            addressed_issue_ids=[] if blocked else safe,
            preserved_items=list(contract["preserve_items"]),
            declared_changes=["离线验证局部修订版本链。"],
            unresolved_issue_ids=list(contract["target_issues"])
            if blocked
            else [id for id in contract["target_issues"] if id not in safe],
            blocked_reasons=[dict(issue_id=id, reason="不能安全执行修改。") for id in safe]
            if blocked
            else [],
        )
    return dict(
        task_id=str(request.task_id),
        status="SUCCESS",
        result=output,
        confidence=0.8,
        assumptions=[],
        issues=[],
        proposed_changes=[],
        memory_proposals=[],
        escalation=None,
    )
