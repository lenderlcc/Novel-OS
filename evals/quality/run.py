"""Read historical Writing inputs; evaluate twice only on explicit --real opt-in.

Run with backend/.venv/bin/python. Does not enqueue tasks or mutate the database.
Expected human themes are read only after both model calls finish.
"""

import argparse
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, text

from novel_os.agents.registry import QUALITY_STAGE_TASKS
from novel_os.agents.runtime import ExecutionResult
from novel_os.context.engine import ContextEngine
from novel_os.context.inputs import task_item
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.context.serialization import ContextSerializer
from novel_os.core.config import Settings
from novel_os.db.session import Database
from novel_os.domain.agents import AgentTask
from novel_os.domain.context import (
    CandidateBatch,
    ContextItem,
    ContextRequest,
    ContextScope,
    Priority,
    SourceRef,
    SourceType,
)
from novel_os.domain.core import now
from novel_os.domain.enums import Authority, ObjectType, Status
from novel_os.domain.quality import QualityPass
from novel_os.models.planning import CreativeBriefModel
from novel_os.prompts.contracts import canonical
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.providers.tokens import prompt_overhead
from novel_os.quality.policy import aggregate, paragraphs, validate_pass
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.writing import WritingRepository
from novel_os.runtime_factory import build_agent_runtime


def export_inputs(settings, project_id, chapter_id, version):
    database = Database(settings)
    try:
        with database.session() as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            core = CoreRepository(session)
            chapter = core.get_chapter(project_id, chapter_id)
            draft = core.get_version(ObjectType.CHAPTER_VERSION, project_id, chapter_id, version)
            generation = WritingRepository(session).for_version(project_id, chapter_id, draft.id)
            if generation is None or generation.brief_id is None:
                raise ValueError("Historical Draft has no complete Writing lineage")
            original = ContextPackageRepository(session).get(generation.context_package_id)
            brief = session.scalar(
                select(CreativeBriefModel).where(CreativeBriefModel.id == generation.brief_id)
            )
            if brief is None:
                raise ValueError("Historical CreativeBrief is missing")
            # These are the sources selected when this version was written, including its
            # then-approved Profile. Never substitute today's approved/current preferences.
            items = [
                ContextSerializer.snapshot(original)["items"][n]
                for n, i in enumerate(original.items)
                if i.source_type != SourceType.TASK_INPUT
            ]

            def item(
                source,
                id,
                logical,
                version,
                selector,
                payload,
                created,
                authority,
                status,
            ):
                return ContextItem(
                    context_item_id=uuid4(),
                    selector_id=selector,
                    source_type=source,
                    source_id=id,
                    logical_id=logical,
                    source_version=version,
                    project_id=project_id,
                    chapter_id=chapter_id,
                    chapter_sequence=chapter.sequence,
                    status=status,
                    authority_level=authority,
                    locked=False,
                    priority=Priority.P0,
                    scope=ContextScope.EXPLICIT
                    if source == SourceType.CREATIVE_BRIEF
                    else ContextScope.TARGET_CHAPTER,
                    payload_json=canonical(payload),
                    selected_reason="Historical Writing lineage export",
                    source_created_at=created,
                    source_updated_at=created,
                    provenance=("historical_writing_evidence", str(generation.id)),
                )

            from novel_os.context.serialization import ITEM_ADAPTER

            additions = [
                item(
                    SourceType.CHAPTER_VERSION,
                    draft.id,
                    chapter_id,
                    draft.version,
                    "target-version",
                    {
                        "content": draft.content,
                        "paragraphs": [
                            {"paragraph_index": n, "text": part}
                            for n, part in enumerate(paragraphs(draft.content), 1)
                        ],
                    },
                    draft.created_at,
                    Authority.A7_AI_INFERENCE,
                    Status.DRAFT,
                ),
                item(
                    SourceType.CREATIVE_BRIEF,
                    brief.id,
                    brief.workflow_id,
                    brief.version,
                    "review-creative-brief",
                    brief.body,
                    brief.created_at,
                    Authority.A7_AI_INFERENCE,
                    Status.ACTIVE,
                ),
            ]
            items += [ITEM_ADAPTER.dump_python(i, mode="json") for i in additions]
            return {
                "schema_version": "quality-eval-input.v1",
                "project_id": str(project_id),
                "chapter_id": str(chapter_id),
                "workflow_id": str(generation.workflow_id),
                "chapter_sequence": chapter.sequence,
                "draft_version": version,
                "writing_generation_id": str(generation.id),
                "writing_context_package_id": str(original.context_package_id),
                "items": items,
            }
    finally:
        database.dispose()


def evaluate(settings, inputs, output, *, real=False, expected=None):
    from novel_os.context.serialization import ITEM_ADAPTER

    if real and ModelProfileRegistry().get(settings.agent_model_profile).provider == "mock":
        raise ValueError("--real requires a configured real Model Profile")
    runtime = build_agent_runtime(
        settings, model_profile=settings.agent_model_profile if real else "mock-default"
    )
    profile = ContextProfileRegistry().for_task("REVIEW_CHAPTER_COMPLIANCE")
    selectors = {s.selector_id: s for s in profile.selectors}
    items = []
    for value in inputs["items"]:
        item = ITEM_ADAPTER.validate_python(value)
        # The historical Writer only selected one previous chapter. Do not invent an
        # absent recent history merely to justify a repetition/novelty complaint.
        if item.selector_id == "previous-approved-chapter":
            item = replace(item, selector_id="recent-approved-chapters")
        if item.selector_id in selectors:
            items.append(item)
    output.mkdir(parents=True, exist_ok=False)
    results, passes = [], []
    for kind in ("REVIEW_CHAPTER_COMPLIANCE", "REVIEW_CHAPTER_NARRATIVE"):
        mapping = QUALITY_STAGE_TASKS[kind]
        task = AgentTask(
            project_id=UUID(inputs["project_id"]),
            workflow_instance_id=UUID(inputs["workflow_id"]),
            workflow_state=mapping.state,
            workflow_state_version=1,
            agent_id=mapping.agent_id,
            task_type=kind,
            objective="独立审阅这个历史正文版本",
            target_ref=UUID(inputs["chapter_id"]),
            capabilities=[mapping.capability.value],
            expected_output_schema=mapping.result_schema,
            attempt_count=1,
        )
        request = ContextRequest(
            project_id=task.project_id,
            task_id=task.task_id,
            task_type=kind,
            chapter_id=task.target_ref,
            workflow_id=task.workflow_instance_id,
            workflow_state_version=1,
            attempt_number=1,
            chapter_sequence=inputs["chapter_sequence"],
            target_version=inputs["draft_version"],
            explicit_refs=tuple(
                SourceRef(
                    source_type=i.source_type,
                    logical_id=i.logical_id,
                    version=i.source_version,
                )
                for i in items
            ),
            required_future_refs=tuple(i.ref for i in items if i.future_knowledge),
        )
        skeleton = runtime.prepare(task)
        if isinstance(skeleton, ExecutionResult):
            raise RuntimeError(skeleton.error_code)  # noqa: TRY004 - preparation failure result
        candidates = [*items, task_item(request, selectors["task-input"], now())]
        built = ContextEngine().build(
            request,
            profile,
            CandidateBatch(items=tuple(candidates)),
            prompt_overhead=prompt_overhead(skeleton),
            output_reservation=skeleton.profile.max_output_tokens,
        )
        if built.status != "READY":
            raise ValueError(built.error_code)
        package = built.package
        prepared = runtime.prepare(task, package)
        if isinstance(prepared, ExecutionResult):
            raise RuntimeError(prepared.error_code)  # noqa: TRY004 - preparation failure result
        run_id, lineage_id = uuid4(), uuid4()
        artifact = {
            "agent_task_id": str(task.task_id),
            "agent_run_id": str(run_id),
            "prompt_lineage_id": str(lineage_id),
            "context_package": ContextSerializer.snapshot(package),
            "model_profile": prepared.profile.model_dump(mode="json"),
            "compiled_prompt_hash": prepared.prompt.compiled_hash,
            "modules": [m.module.model_dump(mode="json") for m in prepared.prompt.modules],
        }
        write(output / (kind.lower() + ".lineage.json"), artifact)
        result = runtime.execute(task, prepared)  # One attempt, no automatic paid retries.
        if result.error_code:
            write(
                output / "failure.json",
                {"task_type": kind, "error_code": result.error_code},
            )
            raise ValueError(result.error_code)
        if (
            result.result.proposed_changes
            or result.result.memory_proposals
            or result.result.status != "SUCCESS"
        ):
            raise ValueError("Review did not return a successful read-only report")
        validate_pass(result.result.result, package)
        write(output / (kind.lower() + ".json"), result.result.model_dump(mode="json"))
        results.append(result.result.result)
        passes.append(
            QualityPass(
                binding_id=UUID(inputs["writing_generation_id"]),
                pass_name=kind.rsplit("_", 1)[-1],
                task_id=task.task_id,
                run_id=run_id,
                prompt_lineage_id=lineage_id,
                context_package_id=package.context_package_id,
                body=result.result.result.model_dump(mode="json"),
            )
        )
    review = aggregate(*results, *passes, now())
    write(output / "review.json", review.model_dump(mode="json"))
    # Human expectations never enter any prompt or model-visible ContextPackage.
    themes = json.loads(expected.read_text()) if expected else {}
    write(
        output / "comparison.json",
        {
            "mode": "REAL" if real else "MOCK_CONTRACT_ONLY",
            "human_expected_themes": themes,
            "ai_detected_codes": [i.code for i in review.hard_gate_issues + review.quality_issues],
            "manual_assessment": None,
            "exact_label_match_is_not_acceptance": True,
        },
    )


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("backend/config.toml"))
    parser.add_argument("--export", type=Path)
    parser.add_argument("--project-id", type=UUID)
    parser.add_argument("--chapter-id", type=UUID)
    parser.add_argument("--draft-version", type=int)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected", type=Path)
    parser.add_argument(
        "--real",
        action="store_true",
        help="Explicit consent to at most two paid model calls for this exact input",
    )
    args = parser.parse_args()
    settings = Settings.from_file(args.config)
    if args.export:
        if args.real or not all((args.project_id, args.chapter_id, args.draft_version)):
            parser.error("Export needs exact project/chapter/version and never calls a model")
        args.export.parent.mkdir(parents=True, exist_ok=True)
        if args.export.exists():
            parser.error("Refusing to overwrite an existing input")
        write(
            args.export,
            export_inputs(settings, args.project_id, args.chapter_id, args.draft_version),
        )
    else:
        if not args.input or not args.output:
            parser.error("Evaluation needs --input and --output")
        evaluate(
            settings,
            json.loads(args.input.read_text()),
            args.output,
            real=args.real,
            expected=args.expected,
        )


if __name__ == "__main__":
    main()
