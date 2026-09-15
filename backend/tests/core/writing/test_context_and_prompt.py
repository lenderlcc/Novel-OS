import json
from dataclasses import replace
from uuid import UUID

import pytest

from novel_os.context.serialization import ContextSerializer, item_data
from novel_os.domain.context import KnowledgeScope
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import chapter, plan, post


def test_writer_uses_cp005_p0_requirements_and_approved_decisions(writing_driver, core_database):
    d = writing_driver
    project = d.chapter_api.split("/chapters/")[0]
    for category in ("MUST", "FORBIDDEN", "PRESERVE"):
        record = post(
            d.client,
            project + "/requirements",
            dict(content=category + "有效约束", requirement_type=category),
        )
        post(
            d.client,
            project + "/requirements/" + record["logical_id"] + "/approve",
            dict(expected_version=1),
        )
    for locked in (False, True):
        record = post(
            d.client, project + "/decisions", dict(question="方向", decision="批准的人物方向")
        )
        post(
            d.client,
            project + "/decisions/" + record["logical_id"] + "/approve",
            dict(expected_version=1),
        )
        if locked:
            post(
                d.client,
                project + "/locks",
                dict(target_type="DECISION", target_id=record["logical_id"], expected_version=1),
            )
    d.approve_plan(core_database)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    package = provider.requests[0].context_package
    assert (package.profile_id, package.profile_version, package.future_knowledge_policy) == (
        "CP-005",
        3,
        "REQUIRED_ONLY",
    )
    assert {
        i.structured_payload["requirement_type"]
        for i in package.items
        if i.source_type == "REQUIREMENT"
    } == {"MUST", "FORBIDDEN", "PRESERVE"}
    assert all(
        i.priority == "P0"
        for i in package.items
        if i.source_type in {"REQUIREMENT", "DECISION", "CHAPTER_PLAN", "CHAPTER"}
    )
    assert len([i for i in package.items if i.source_type == "DECISION"]) == 2


def test_previous_approved_body_not_latest_and_no_future_or_foreign_leak(
    writing_driver, core_database
):
    old = writing_driver
    assert old.event("CANCEL").status_code == 200
    previous = old.chapter_api
    for v in (1, 2, 3):
        post(
            old.client,
            previous + "/versions",
            dict(
                expected_version=v - 1,
                content="PREVIOUS_APPROVED" if v == 2 else "BODY_SECRET_" + str(v),
                change_reason="history fixture",
            ),
        )
        if v == 2:
            post(old.client, previous + "/versions/approve", dict(expected_version=2))
    project = previous.split("/chapters/")[0]
    d = type(old)(old.client, chapter(old.client, project, 2))
    future = chapter(old.client, project, 3)
    plan(d.client, future, objective="FUTURE_APPROVED_SECRET")
    post(d.client, future + "/plans/approve", dict(expected_version=1))
    plan(d.client, future, 2, objective="FUTURE_DRAFT_SECRET")
    post(
        d.client,
        future + "/versions",
        dict(expected_version=0, content="FUTURE_BODY_SECRET", change_reason="fixture"),
    )
    foreign = post(d.client, "/api/v1/projects", dict(name="Foreign project"))
    foreign_url = "/api/v1/projects/" + foreign["id"] + "/requirements"
    record = post(d.client, foreign_url, dict(content="FOREIGN_SECRET"))
    post(d.client, foreign_url + "/" + record["logical_id"] + "/approve", dict(expected_version=1))
    record = post(d.client, project + "/requirements", dict(content="PROPOSED_REQUIREMENT_SECRET"))
    d.approve_plan(core_database)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    package = provider.requests[0].context_package
    serialized = json.dumps(ContextSerializer.serialize(package))
    assert "SECRET" not in serialized
    bodies = [i for i in package.items if i.source_type == "CHAPTER_VERSION"]
    assert len(bodies) == 1 and bodies[0].source_version == 2
    assert bodies[0].structured_payload["content"] == "PREVIOUS_APPROVED"
    assert not any(i.future_knowledge for i in package.items)


def test_prompt_modules_contract_and_lineage_keep_knowledge_boundary(ready_writer, core_database):
    d = ready_writer
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    request = provider.requests[0]
    record = d.read("/writing/history")[0]
    with core_database.session() as session:
        lineage = PromptLineageRepository(session).for_run(UUID(record["agent_run_id"]))
        package = ContextPackageRepository(session).for_run(UUID(record["agent_run_id"]))
    assert lineage.lineage_id == UUID(record["prompt_lineage_id"])
    assert package.context_package_id == UUID(record["context_package_id"])
    assert {s["module_id"] for s in lineage.skills} == {
        "scene-execution",
        "dialogue",
        "character-voice",
        "narrative-rhythm",
        "natural-prose",
    }
    assert lineage.output_schema_id == "chapter-writing-result"
    assert lineage.agent_role["module_id"] == "writing-agent"
    assert lineage.task_template["module_id"] == "write-chapter"
    assert record["model_profile"] == "mock-writing"
    prompt = "\n".join(m.content for m in request.prompt.messages if m.layer != "CONTEXT_DATA")
    for rule in ("AS-01", "AS-02", "AS-03", "AS-04", "AS-05", "AS-06", "AS-07", "AS-12"):
        assert rule in prompt
    for boundary in (
        "GLOBAL_ONLY",
        "CHARACTER KNOWLEDGE",
        "CHARACTER BELIEF",
        "CHARACTER SUSPICION",
        "CHARACTER MISUNDERSTANDING",
    ):
        assert boundary in prompt
    serialized = ContextSerializer.serialize(package)
    assert all(
        item["knowledge_scope"] == "GLOBAL_ONLY" and item["character_id"] is None
        for item in serialized["items"]
    )
    original = package.items[0]
    attributed = replace(
        original,
        knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE,
        character_id=UUID(d.workflow["chapter_id"]),
    )
    assert item_data(original)["knowledge_scope"] == "GLOBAL_ONLY"
    assert item_data(attributed)["knowledge_scope"] == "CHARACTER_KNOWLEDGE"
    assert item_data(attributed)["character_id"] is not None


@pytest.mark.parametrize("before_model", [False, True])
def test_released_relevant_lock_invalidates_writer(writing_driver, core_database, before_model):
    d = writing_driver
    project = d.chapter_api.split("/chapters/")[0]
    record = post(
        d.client, project + "/decisions", dict(question="核心边界", decision="不能背叛同伴")
    )
    lock = post(
        d.client,
        project + "/locks",
        dict(target_type="DECISION", target_id=record["logical_id"], expected_version=1),
    )
    d.approve_plan(core_database)

    def release(*_):
        post(d.client, project + "/locks/" + lock["id"] + "/release", dict(expected_version=1))

    if before_model:
        release()
    provider = RecordedProvider(None if before_model else release)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == (0 if before_model else 1)
    assert d.read("/writing/history") == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"


@pytest.mark.parametrize("approved", [False, True])
def test_even_explicit_locked_future_plan_requires_approval(ready_writer, core_database, approved):
    from novel_os.context.engine import ContextEngine
    from novel_os.context.profiles import ContextProfileRegistry
    from novel_os.domain.context import SourceRef, SourceType
    from novel_os.repositories.agent_tasks import AgentTaskRepository
    from novel_os.services.memory_query import MemoryQueryService

    d = ready_writer
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    package = provider.requests[0].context_package
    project = d.chapter_api.split("/chapters/")[0]
    future = chapter(d.client, project, 2)
    plan(d.client, future, objective="EXPLICIT_FUTURE_FACT")
    if approved:
        post(d.client, future + "/plans/approve", dict(expected_version=1))
    post(
        d.client,
        project + "/locks",
        dict(target_type="CHAPTER_PLAN", target_id=future.rsplit("/", 1)[1], expected_version=1),
    )
    ref = SourceRef(
        source_type=SourceType.CHAPTER_PLAN, logical_id=UUID(future.rsplit("/", 1)[1]), version=1
    )
    request = replace(
        package.request, explicit_refs=(ref,), required_refs=(ref,), required_future_refs=(ref,)
    )
    profile = ContextProfileRegistry().for_task("WRITE_CHAPTER")
    with core_database.session() as session:
        tasks = AgentTaskRepository(session)
        task = tasks.get(package.task_id)
        batch = MemoryQueryService(session).query(request, profile, tasks.clock(), task.created_at)
    built = ContextEngine().build(request, profile, batch)
    future_items = [i for i in built.package.items if i.future_knowledge]
    assert len(future_items) == int(approved)
    if not approved:
        assert built.error_code == "CONTEXT_MISSING"
        assert "EXPLICIT_FUTURE_FACT" not in str(built.package.items)
    else:
        assert built.status == "READY"
        assert future_items[0].ref == ref and future_items[0].locked
