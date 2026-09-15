"""Offline contract fixtures, not an algorithm for interpreting arbitrary chapter intent."""

from uuid import uuid4

BODY = """门上的铜环还带着雨水。林舟握住它，听见院里有人把碗轻轻搁下。

“再晚一点，门就关了。”阿岚没有回头，仍在擦桌上的水。

他把湿透的信放在桌角。纸黏着袖口，抽了两次才松开。她看着信，没有伸手。

“路断了。”他说。

“哪一段？”

林舟抬眼看她。来时准备的解释忽然显得多余。他挪开挡着灯光的椅子，让她看清封口的泥。阿岚放下布，从柜底取出另一张旧地图，压在碗下。

雨顺着屋檐落成一条线。他们各握地图一角，纸在中间拱起。她指向靠河的那条小路，他用指背抹掉那里的一滴水。

“走这边，要多半天。”

“我等得起。”

他松开地图，终于坐了下来。阿岚将那封信移到灯下，却没有拆。两人把要带的东西一件件排在桌上；最后剩下那只空碗，没有人把它收走。

天亮前，院门开了一道缝。林舟将地图折好，放进已经干了半边的袖子。阿岚站在门内，把灯举高了一点，等他看清台阶。
"""


def response(request, scenario):
    plan = next(i for i in request.context_package.items if i.selector_id == "approved-plan")
    output = {
        "kind": "writing_result",
        "chapter_id": str(request.target_ref),
        "plan_id": str(plan.source_id),
        "plan_version": plan.source_version,
        "content": BODY,
        "scene_execution": [
            {
                "scene_id": scene["id"],
                "planned_function": scene["purpose"],
                "execution_summary": "人物通过相互询问作出下一步选择。",
                "source_location": "院门至准备行装",
                "function_completed": True,
                "deviation": None,
            }
            for scene in plan.structured_payload["planning"]["scenes"]
        ],
        "introduced_elements": [],
        "proposed_new_facts": [],
        "plan_deviations": [],
        "unresolved_questions": [],
        "assumptions": [],
        "knowledge_risk_flags": [],
        "style_notes": ["以动作和简短对白呈现互动；这是离线契约样例。"],
        "confidence": 0.95,
    }
    if scenario in {
        "WRITING_LOCAL_DEVIATION",
        "WRITING_MODERATE_DEVIATION",
        "WRITING_MAJOR_DEVIATION",
    }:
        severity = scenario.removeprefix("WRITING_").removesuffix("_DEVIATION")
        output["plan_deviations"] = [
            {
                "type": "MAJOR_DIRECTION" if severity == "MAJOR" else "LOCAL_EXECUTION",
                "location": "结尾",
                "planned_behavior": "完成已批准场景功能",
                "actual_behavior": "调整执行方式",
                "reason": "样例偏离",
                "impact": "供后续独立审查",
                "severity": severity,
                "requires_replan": severity == "MAJOR",
                "confidence": 0.9,
            }
        ]
    if scenario == "WRITING_PROPOSED_FACT":
        output["proposed_new_facts"] = [
            {
                "fact": "屋内留有旧地图",
                "scope": "当前场景",
                "importance": "MINOR",
                "reason": "支撑局部互动",
                "source_location": "地图展开处",
                "confidence": 0.8,
            }
        ]
    if scenario == "WRITING_KNOWLEDGE_RISK":
        output["knowledge_risk_flags"] = [
            {
                "character_ref": "阿岚",
                "fact": "河边道路是否畅通",
                "knowledge_type": "SUSPICION",
                "source_location": "讨论路线",
                "risk": "仅为推测，未提升成已知事实",
                "confirmed_leak": False,
            }
        ]
    if scenario == "WRITING_EMPTY_CONTENT":
        output["content"] = "  \n"
    if scenario == "WRITING_STALE_RESULT":
        output["plan_id"] = str(uuid4())
    return {
        "task_id": str(request.task_id),
        "status": "SUCCESS",
        "result": output,
        "confidence": 0.95,
        "assumptions": [],
        "issues": [],
        "proposed_changes": [],
        "memory_proposals": [],
        "escalation": None,
    }
