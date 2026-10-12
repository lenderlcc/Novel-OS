"""Five formal chapter slices with recorded outputs, never paid-model acceptance.

The fixtures supply provider responses, not database rows. Every persisted Draft,
revision, proposal and committed memory is created by the normal workflow/runtime.
"""

import json
from collections import Counter
from pathlib import Path

from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_memory_commit import complete_request, confirm
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "evals/e2e/multi-chapter"


def read_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def boundary_checks(package, source):
    return [
        dict(
            source_ref=dict(
                source_type=item.source_type,
                logical_id=str(item.logical_id),
                version=item.source_version,
            ),
            outcome="COMPATIBLE",
            reason="Recorded event respects this supplied authority boundary.",
        )
        for item in package.items
        if (
            item.source_type in {"REQUIREMENT", "DECISION", "CHAPTER_PLAN", "CHAPTER_VERSION"}
            and item.source_id != source.source_id
            and (item.locked or item.authority_level.value <= "A4_APPROVED_PLAN")
        )
        or (
            item.source_type == "EXTENSION"
            and item.provenance[0] == "committed_memory"
            and item.authority_level.value == "A3_CANON"
        )
    ]


def memory_rows(request, chapter, entities, subjects):
    source = next(i for i in request.context_package.items if i.selector_id == "target-version")
    content = source.structured_payload["content"]
    paragraphs = content.split("\n\n")
    checks = boundary_checks(request.context_package, source)

    def row(
        candidate_id, kind, subject, slot, value, statement, marker, *, before=None, epistemic=None
    ):
        matches = [
            (index, paragraph)
            for index, paragraph in enumerate(paragraphs, 1)
            if marker.casefold() in paragraph.casefold()
        ]
        assert len(matches) >= 1, (candidate_id, marker, content)
        index, paragraph = matches[0]
        derived = kind in {"OPEN_THREAD", "DERIVED_CHAPTER_SUMMARY"}
        entity = entities[subject] if subject else None
        subject_ref = None
        if entity:
            subject_ref = dict(
                name=entity["name"],
                kind=entity["kind"],
                logical_id=subjects.get(subject),
                aliases=[],
                resolution="EXISTING" if subject in subjects else "NEW",
            )
        state = kind in {
            "CHARACTER_STATE",
            "CHARACTER_KNOWLEDGE",
            "RELATIONSHIP_STATE",
            "OPEN_THREAD",
        } or (kind == "CANON_FACT" and subject == "K")
        return dict(
            id=candidate_id,
            candidate_type=kind,
            subject_ref=subject_ref,
            statement=statement,
            slot=slot,
            value=value,
            state_before=before,
            state_after=value if state else None,
            epistemic_status=epistemic,
            importance="DERIVED_HINT" if derived else "CONTINUITY",
            evidence=[
                dict(
                    paragraph_index=index,
                    short_excerpt=paragraph[:300],
                    reason="Explicit accepted-version continuity event.",
                )
            ],
            target_layer="DERIVED" if derived else "CANON",
            source_refs=[
                dict(
                    source_type="CHAPTER_VERSION",
                    logical_id=str(source.logical_id),
                    version=source.source_version,
                )
            ],
            confidence=0.95,
            existing_entry_id=None,
            authority_checks=checks,
            uncertainty=None,
        )

    sequence = chapter["sequence"]
    if sequence == 1:
        rows = [
            row(
                "A_location",
                "CHARACTER_STATE",
                "A",
                "location",
                entities["L1"]["name"],
                "A is at L1.",
                "waited at River Station",
            ),
            row(
                "B_location",
                "CHARACTER_STATE",
                "B",
                "location",
                entities["L2"]["name"],
                "B is at L2 and was absent when A acquired X.",
                "Gu Che was at Clock Tower",
            ),
            row(
                "X",
                "CANON_FACT",
                "X",
                "secret",
                entities["X"]["value"],
                "The Midnight Code exists.",
                "the box opens at midnight",
            ),
            row(
                "A_X",
                "CHARACTER_KNOWLEDGE",
                "A",
                "knowledge:X",
                entities["X"]["value"],
                "A knows X from reading it herself.",
                "the box opens at midnight",
                epistemic="KNOWS",
            ),
            row(
                "K_condition",
                "CANON_FACT",
                "K",
                "condition",
                "INTACT",
                "K is INTACT.",
                "seal was intact",
            ),
            row(
                "T",
                "OPEN_THREAD",
                "T",
                "search",
                "OPEN",
                "The Missing Courier has not returned; the search is OPEN.",
                "Missing Courier had not returned",
            ),
            row(
                "A_relationship_B",
                "RELATIONSHIP_STATE",
                "A",
                "relationship:B",
                "COOPERATING",
                "A and B cooperate in finding T.",
                "agreed to cooperate",
            ),
            row(
                "A_task",
                "CHARACTER_STATE",
                "A",
                "task",
                "PENDING",
                "A's courier search remains pending.",
                "search remained pending",
            ),
        ]
    elif sequence == 2:
        rows = [
            row(
                "A_location",
                "CHARACTER_STATE",
                "A",
                "location",
                entities["L2"]["name"],
                "A moved from L1 to L2.",
                "arrived at Clock Tower",
                before=entities["L1"]["name"],
            ),
            row(
                "A_knowledge_Y",
                "CHARACTER_KNOWLEDGE",
                "A",
                "knowledge:Y",
                "B_RESPONSIBLE",
                "A suspects B is responsible for Y; there is no proof.",
                "Lin Lan suspected",
                epistemic="SUSPECTS",
            ),
            row(
                "K_condition",
                "CANON_FACT",
                "K",
                "condition",
                "INTACT",
                "K is INTACT.",
                "seal remained intact",
            ),
        ]
    elif sequence == 3:
        rows = [
            row(
                "B_truth_Y",
                "CANON_FACT",
                "B",
                "responsibility:Y",
                "NOT_RESPONSIBLE",
                "B is not responsible for Y.",
                "not responsible for the Station Alarm",
            ),
            row(
                "A_knowledge_Y",
                "CHARACTER_KNOWLEDGE",
                "A",
                "knowledge:Y",
                "NOT_RESPONSIBLE",
                "A knows from the signed log that B is not responsible for Y.",
                "Lin Lan read the entry twice",
                before="B_RESPONSIBLE",
                epistemic="KNOWS",
            ),
            row(
                "K_condition",
                "CANON_FACT",
                "K",
                "condition",
                "DESTROYED",
                "K is permanently DESTROYED.",
                "permanently destroyed",
                before="INTACT",
            ),
        ]
    elif sequence == 4:
        rows = [
            row(
                "T",
                "OPEN_THREAD",
                "T",
                "search",
                "OPEN",
                "The delivery slip supplies new evidence; Missing Courier remains OPEN.",
                "new delivery slip",
                before="OPEN",
            )
        ]
    else:
        rows = []
    rows.append(
        row(
            "summary",
            "DERIVED_CHAPTER_SUMMARY",
            None,
            "summary",
            f"chapter-{sequence}",
            {
                1: "A learns a private code; A and B continue their unresolved search.",
                2: "A reaches L2 and suspects B without proof.",
                3: "The log clears B; K is destroyed.",
                4: "A and B obtain a delivery slip while the courier search remains open.",
                5: "The cooperative courier search continues from L2.",
            }[sequence],
            paragraphs[0][:50],
        )
    )
    return rows


def recorded_provider(chapter, scenario, subjects, current):
    def transform(request, body):
        result = body["result"]
        if request.output_kind == "chapter_plan":
            result["pov_character_id"] = subjects.get(chapter["pov"])
            if chapter["sequence"] >= 2:
                # Recorded Planning explicitly hands relevant current public state to
                # the approved scene; these are not private Writer memory grants.
                selected = committed_items(request)
                handoff = [
                    f"{key}: {selected[entry['id']].structured_payload['value']}"
                    for key, entry in current.items()
                    if key in {"A_location", "K_condition", "T", "B_truth_Y"}
                    and entry["id"] in selected
                ]
                result["scenes"][0]["information_release"] = handoff
        elif request.output_kind == "writing_result":
            result["content"] = chapter["recorded_draft"]
        elif request.output_kind == "human_feedback_interpretation":
            result.update(
                intent_summary="Remove the false universal-key sentence, preserving local action.",
                requested_changes=[
                    dict(
                        description="Delete the unsupported universal-key sentence.",
                        target_regions=["paragraph 3 false claim"],
                    )
                ],
                target_regions=["paragraph 3 false claim"],
                quality_concerns=["Unsupported draft-only major fact"],
                safe_inferences=[],
            )
        elif request.output_kind == "revision_result":
            result["content"] = chapter["revised_draft"]
            result["declared_changes"] = ["Removed the unsupported universal-key sentence."]
        elif request.output_kind == "chapter_memory":
            result["candidates"] = memory_rows(request, chapter, scenario["entities"], subjects)

    return RecordedProvider(transform)


def committed_items(request):
    return {
        str(item.source_id): item
        for item in request.context_package.items
        if item.provenance and item.provenance[0] == "committed_memory"
    }


def inspect_lineage(driver, provider):
    records = []
    requests = {str(request.task_id): request for request in provider.requests}
    for task in driver.read("/agent-tasks"):
        assert task["status"] == "SUCCEEDED", task
        runs = driver.client.get(f"/api/v1/agent-tasks/{task['task_id']}/runs").json()
        assert len(runs) == 1 and runs[0]["status"] == "SUCCEEDED", runs
        run = runs[0]
        request = requests[task["task_id"]]
        context = driver.client.get(f"/api/v1/agent-runs/{run['run_id']}/context")
        lineage = driver.client.get(f"/api/v1/agent-runs/{run['run_id']}/prompt-lineage")
        assert context.status_code == lineage.status_code == 200
        package = context.json()["package"]
        prompt = lineage.json()
        assert package["task_id"] == task["task_id"] == prompt["task_id"]
        assert package["context_package_id"] == str(request.context_package.context_package_id)
        assert prompt["model_profile_id"] == request.profile.profile_id
        assert prompt["compiled_prompt_hash"] == request.prompt.compiled_hash
        assert not package["missing_required_items"] and not package["authority_conflicts"]
        records.append(dict(task=task, run=run, prompt_lineage=prompt, context=package))
    return records


def test_five_chapter_formal_continuity_and_finalized_revision_isolation(
    core_client, core_database
):
    scenario = read_fixture("scenario.json")
    response = core_client.post("/api/v1/projects", json=scenario["project"])
    assert response.status_code == 201, response.text
    project = "/api/v1/projects/" + response.json()["id"]
    core_client._transport.raise_server_exceptions = True
    profile = draft(core_client, project, **scenario["writing_profile"])
    approved_profile = approve(core_client, project)
    assert approved_profile["id"] == profile["id"]
    subjects, current, snapshots, trace = {}, {}, [], []

    for sequence in range(1, 6):
        chapter = read_fixture(f"chapter-{sequence:02d}.json")
        response = core_client.post(
            project + "/chapters", json=dict(sequence=sequence, title=chapter["title"])
        )
        assert response.status_code == 201, response.text
        chapter_api = project + "/chapters/" + response.json()["id"]
        prior_memory_ids = {entry["id"] for entry in core_client.get(project + "/memory").json()}
        driver = QualityDriver(core_client, chapter_api, chapter["raw_requirement"])
        provider = recorded_provider(chapter, scenario, subjects, current)
        for _ in range(3):
            run_one(core_database, driver, provider=provider)
        assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL", (
            sequence,
            driver.workflow,
            [
                (t["task_type"], t["status"], t["last_error_code"], t["last_error_message"])
                for t in driver.read("/agent-tasks")
            ],
        )
        assert driver.decide().status_code == 200  # Human Plan Approval.
        for _ in range(3):
            run_one(core_database, driver, provider=provider)
        assert driver.workflow["status"] == "WAITING_HUMAN", driver.workflow
        original = core_client.get(chapter_api + "/versions/1").json()
        assert original["content"] == chapter["recorded_draft"]
        if sequence == 4:
            response, _ = submit(driver, chapter["human_feedback"])
            assert response.status_code == 200, response.text
            driver.refresh()
            for _ in range(6):
                run_one(core_database, driver, provider=provider)
            assert driver.workflow["draft_version"] == 2, driver.workflow
            newer = core_client.get(chapter_api + "/versions/2").json()
            assert newer["id"] != original["id"] and newer["supersedes_id"] == original["id"]
            assert newer["content"] == chapter["revised_draft"]
            assert scenario["entities"]["Z"]["value"] not in newer["content"]
            assert core_client.get(chapter_api + "/versions/1").json() == original
            revision = driver.read("/revisions")[0]
            assert revision["result"]["body"]["fidelity"]["verdict"] == "PASS"
            assert driver.reviews()[0]["chapter_version_id"] == newer["id"]
        accepted = complete_request(driver)  # Explicit human Draft Acceptance/finalization.
        run_one(core_database, driver, provider=provider)
        history = driver.read("/memory")[0]
        assert (
            history["status"] == "PROPOSED"
            and history["request"]["chapter_version_id"] == accepted["id"]
        )
        assert core_client.get(chapter_api).json()["status"] != "COMPLETED"
        candidate_ids = [c["id"] for c in history["proposal"]["candidates"]]
        response = confirm(driver, candidate_ids)  # Explicit human Memory Confirmation.
        assert response.status_code == 200, response.text
        driver.refresh()
        assert driver.workflow["current_state"] == "C16_COMPLETED", driver.workflow
        completed_chapter = core_client.get(chapter_api).json()
        assert completed_chapter["status"] == "COMPLETED"
        assert (
            completed_chapter["current_version"]
            == completed_chapter["approved_version"]
            == accepted["version"]
        )
        history = driver.read("/memory")[0]
        assert history["status"] == "COMMITTED"
        entries = {entry["candidate_id"]: entry for entry in history["entries"]}
        assert {entry["chapter_version_id"] for entry in entries.values()} == {accepted["id"]}
        for key, entry in entries.items():
            if key != "summary":
                current[key] = entry
        if sequence == 1:
            for logical_id, candidate_id in {
                "A": "A_location",
                "B": "B_location",
                "X": "X",
                "K": "K_condition",
                "T": "T",
            }.items():
                subjects[logical_id] = entries[candidate_id]["subject_id"]
        snapshots.append(dict(current))
        plan_request = next(r for r in provider.requests if r.output_kind == "chapter_plan")
        writer_request = next(r for r in provider.requests if r.output_kind == "writing_result")
        writer_items = committed_items(writer_request)
        writing_profile = next(
            item
            for item in writer_request.context_package.items
            if item.source_type == "PROJECT_WRITING_PROFILE"
        )
        assert str(writing_profile.source_id) == approved_profile["id"]
        assert writing_profile.authority_level == "A5_USER_PREFERENCE"
        if sequence in {3, 4}:
            assert current["A_X"]["id"] in writer_items
            assert (
                writer_items[current["A_X"]["id"]].structured_payload["subject_id"] == subjects["A"]
            )
        if sequence in {2, 5}:
            assert str(writer_request.context_package.request.character_id) == subjects["B"]
            assert current["B_location"]["id"] in writer_items
            assert current["A_X"]["id"] not in writer_items
            assert current["X"]["id"] not in writer_items
            assert not any(
                scenario["entities"]["X"]["value"] in item.payload_json
                for item in writer_request.context_package.items
            )
        if sequence >= 2:
            assert not any(
                item.source_type == "CHAPTER_VERSION"
                for item in writer_request.context_package.items
            )
            assert writer_request.context_package.future_knowledge_policy == "REQUIRED_ONLY"
        plan_memory = committed_items(plan_request)
        assert set(plan_memory) <= prior_memory_ids
        assert set(writer_items) <= prior_memory_ids
        extraction = next(r for r in provider.requests if r.output_kind == "chapter_memory")
        source = next(
            i for i in extraction.context_package.items if i.selector_id == "target-version"
        )
        assert str(source.source_id) == accepted["id"]
        assert source.structured_payload["content"] == accepted["content"]
        if sequence == 4:
            assert original["id"] not in {
                str(i.source_id) for i in extraction.context_package.items
            }
        if sequence == 5:
            for key in {
                "A_location",
                "K_condition",
                "T",
                "A_knowledge_Y",
                "B_truth_Y",
                "A_relationship_B",
                "A_task",
            }:
                assert snapshots[3][key]["id"] in plan_memory, (key, list(plan_memory))
            assert snapshots[0]["A_location"]["id"] not in plan_memory
            assert snapshots[0]["K_condition"]["id"] not in plan_memory
            assert snapshots[0]["T"]["id"] not in plan_memory
            assert snapshots[1]["A_knowledge_Y"]["id"] not in plan_memory
            knowledge = plan_memory[snapshots[3]["A_knowledge_Y"]["id"]].structured_payload
            assert knowledge["epistemic_status"] == "KNOWS"
            assert knowledge["value"] == "NOT_RESPONSIBLE"
            assert snapshots[0]["X"]["id"] not in plan_memory
            assert len(plan_memory) < len(prior_memory_ids)
            approved_plan = next(
                i for i in writer_request.context_package.items if i.selector_id == "approved-plan"
            )
            handoff = approved_plan.structured_payload["planning"]["scenes"][0][
                "information_release"
            ]
            assert "K_condition: DESTROYED" in handoff
            assert "T: OPEN" in handoff
            assert f"A_location: {scenario['entities']['L2']['name']}" in handoff
            assert not any(
                "INTACT" in fact or scenario["entities"]["X"]["value"] in fact for fact in handoff
            )
        counts = Counter(c["conflict_status"] for c in history["proposal"]["candidates"])
        generations = driver.read("/writing/history")
        assert len(generations) == 1 and generations[0]["chapter_version_id"] == original["id"]
        assert generations[0]["plan_id"] == driver.read("/planning/plan")["plan"]["id"]
        assert generations[0]["plan_version"] == 1
        assert generations[0]["context_package_id"] == str(
            writer_request.context_package.context_package_id
        )
        assert generations[0]["model_profile"] == writer_request.profile.profile_id
        trace.append(
            dict(
                sequence=sequence,
                chapter_id=driver.creation["chapter_id"],
                workflow=driver.workflow,
                input=chapter["raw_requirement"],
                approved_plan=driver.read("/planning/plan"),
                accepted_draft=accepted,
                writing_history=generations,
                reviews=driver.reviews(),
                feedback=driver.read("/feedback"),
                revisions=driver.read("/revisions"),
                memory=history,
                counts=dict(
                    candidate=len(candidate_ids),
                    committed=len(entries),
                    excluded=len(candidate_ids) - len(history["batch"]["selected_candidate_ids"]),
                    skipped=len(history["batch"]["skipped_candidate_ids"]),
                    duplicate=counts["DUPLICATE"],
                    conflict=sum(
                        counts[k] for k in {"CONTRADICTION", "AUTHORITY_CONFLICT", "AMBIGUOUS"}
                    ),
                ),
                agent_lineage=inspect_lineage(driver, provider),
            )
        )

    old, final = snapshots[0], snapshots[-1]
    assert final["A_X"]["epistemic_status"] == "KNOWS"
    assert final["A_X"]["subject_id"] == subjects["A"]
    earlier_belief = snapshots[1]["A_knowledge_Y"]
    assert earlier_belief["epistemic_status"] == "SUSPECTS"
    assert final["A_knowledge_Y"]["epistemic_status"] == "KNOWS"
    assert final["A_knowledge_Y"]["subject_id"] == subjects["A"]
    assert final["A_knowledge_Y"]["value"] == "NOT_RESPONSIBLE"
    assert final["A_knowledge_Y"]["logical_id"] == earlier_belief["logical_id"]
    assert final["A_knowledge_Y"]["supersedes_id"] == earlier_belief["id"]
    assert final["B_truth_Y"]["memory_type"] == "CANON_FACT"
    assert final["B_truth_Y"]["subject_id"] == subjects["B"]
    assert final["B_truth_Y"]["value"] == "NOT_RESPONSIBLE"
    for key in {"A_location", "K_condition", "T"}:
        assert final[key]["logical_id"] == old[key]["logical_id"]
        assert final[key]["version"] == 2 and final[key]["supersedes_id"] == old[key]["id"]
    assert snapshots[2]["T"]["id"] == old["T"]["id"]  # Omission did not resolve the thread.
    assert final["T"]["value"] == "OPEN" and final["K_condition"]["value"] == "DESTROYED"
    assert trace[1]["memory"]["batch"]["skipped_candidate_ids"] == ["K_condition"]
    current_memory = core_client.get(project + "/memory").json()
    historical = core_client.get(project + "/memory?historical=true").json()
    current_ids = {entry["id"] for entry in current_memory}
    history_ids = {entry["id"] for entry in historical}
    for key in {"A_location", "K_condition", "T"}:
        assert old[key]["id"] not in current_ids and old[key]["id"] in history_ids
    assert earlier_belief["id"] not in current_ids and earlier_belief["id"] in history_ids
    historical_belief = next(entry for entry in historical if entry["id"] == earlier_belief["id"])
    assert historical_belief == earlier_belief
    assert not any(
        entry["memory_type"] == "CHARACTER_KNOWLEDGE"
        and entry["subject_id"] == subjects["B"]
        and entry["slot"] == "knowledgex"
        for entry in historical
    )
    assert not any(
        entry["memory_type"] == "CANON_FACT" and entry["value"] == "B_RESPONSIBLE"
        for entry in historical
    )
    assert scenario["entities"]["Z"]["value"] not in json.dumps(historical)
    for entry in historical:
        assert entry["authority_level"] == (
            "A6_DERIVED_MEMORY"
            if entry["memory_type"] in {"OPEN_THREAD", "DERIVED_CHAPTER_SUMMARY"}
            else "A3_CANON"
        )
    finalized_v2 = trace[3]["accepted_draft"]["id"]
    assert all(
        entry["chapter_version_id"] == finalized_v2 for entry in trace[3]["memory"]["entries"]
    )
    result = dict(
        eval_id="E2E-001",
        mode="OFFLINE_RECORDED_PROVIDER",
        real_provider_calls=0,
        project_id=project.split("/")[-1],
        approved_writing_profile=approved_profile,
        subject_ids=subjects,
        chapters=trace,
        current_memory=current_memory,
        historical_memory=historical,
    )
    output = ROOT / ".runtime/e2e001-offline-trace.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
