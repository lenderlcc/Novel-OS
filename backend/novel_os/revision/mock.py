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
    if contract.get("source_feedback_id"):
        common.update(
            source_feedback_id=contract["source_feedback_id"],
            revision_source=contract["revision_source"],
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
                    revision_direction=i.get("revision_direction", i["description"]),
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
        if contract.get("fidelity_version") == 1:
            output.update(
                locality_fields(
                    output, contract, items["target-version"].structured_payload["content"]
                )
            )
        prompt = getattr(request, "prompt", None)
        if prompt is not None and prompt.output.version >= 3:
            output["unresolved_issue_ids"] = [b["issue_id"] for b in output["blocked_reasons"]]
    elif request.output_kind == "revision_fidelity":
        output = fidelity_output(common, items, scenario)
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


def excerpt(content):
    from novel_os.quality.policy import paragraphs

    return dict(
        paragraph_index=1,
        excerpt=paragraphs(content)[0][: min(100, max(1, len(content) // 2))],
        reason="离线证据，不代表语义判断。",
    )


def locality_fields(output, contract, source):
    evidence = [excerpt(source)]
    return dict(
        preserve_scene_elements=[
            dict(element_id="scene:0", description="保留原稿场景", evidence=evidence)
        ],
        preserve_relationship_elements=[
            dict(element_id="relationship:0", description="保留原稿人物关系功能", evidence=evidence)
        ],
        preserve_effective_details=[
            dict(element_id="detail:0", description="保留原稿有效细节", evidence=evidence)
        ],
        strength_preservation=[
            dict(strength_id=k, mode="FUNCTIONAL", preservation_direction="保留原有阅读效果")
            for k in contract["preserve_items"]
            if k.startswith("strength:")
        ],
        strength_regression_risks=[],
        revision_zones=[
            dict(
                issue_ids=[t["issue_id"]],
                semantic_range=contract["target_issues"][t["issue_id"]].get(
                    "target_regions", ["审阅证据所指向的段落"]
                )[0],
                paragraph_start=None,
                paragraph_end=None,
            )
            for t in output["revision_targets"]
        ],
        allowed_structural_change="LOCAL",
        structural_authorization=None,
        change_budget="MINIMAL",
    )


def fidelity_output(common, items, scenario):
    from novel_os.revision.contracts import read_plan
    from novel_os.revision.fidelity import preservation_ids

    plan = items["revision-plan"].structured_payload
    candidate = items["revision-candidate"].structured_payload
    source = items["target-version"].structured_payload["content"]
    model = read_plan({k: v for k, v in plan.items() if k != "revision_plan_id"})
    from novel_os.feedback.policy import human_fidelity_checks

    required = preservation_ids(model) | human_fidelity_checks(
        items["revision-contract"].structured_payload
    )
    failed = scenario == "QUALITY_FAIL"
    return dict(
        **common,
        revision_plan_id=plan["revision_plan_id"],
        candidate_id=candidate["candidate_id"],
        candidate_content_hash=candidate["content_hash"],
        verdict="FAIL" if failed else "PASS",
        checks=[
            dict(
                check_id=k,
                preserved=not (failed and k == "SCENE_PREMISE"),
                reason="离线验证判定分支，不代表文学评估。",
                source_evidence=[excerpt(source)],
                revised_evidence=[excerpt(candidate["content"])],
            )
            for k in sorted(required)
        ],
        violations=[
            dict(
                code="UNAUTHORIZED_SCENE_REPLACEMENT",
                check_ids=["SCENE_PREMISE"],
                description="离线模拟场景替换拒绝。",
            )
        ]
        if failed
        else [],
    )
