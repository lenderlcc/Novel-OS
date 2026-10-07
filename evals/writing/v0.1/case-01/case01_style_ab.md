# case01_style_ab — manual opt-in acceptance workflow

This workflow never runs as part of pytest. No paid call has been authorized by merely
loading the sample form. A/B real execution requires a new explicit user confirmation
as required by STYLE-001 section 34. Human Plan Approval remains a separate gate.

## A: immutable baseline

`baseline/manifest.json` pins the original Project/Chapter/Workflow, requirement hash,
model and artifact hashes. `approved-plan.json`, `draft.txt`, `writing-result.json`,
`context-package.json` and `prompt-lineage.json` preserve actual real-provider evidence.
The model is Lingzhi / gpt-5.6-sol. A has no ProjectWritingProfile.

From `backend/`, verify A without calling any model:

```sh
uv run --locked python ../scripts/case01_style_ab.py
```

## B: explicit user actions

1. Keep background Workers stopped while preparing. Open the Test Console and select
   Project `0767f00f-1d3a-4e82-a779-17e78d4f2888`, Chapter
   `ee59f19c-7815-4e91-99ca-619a10ebd311` (same scope as A).
2. In Project Writing Profile, select **Load Web Fiction Test Profile**. Review all fields,
   explicitly **Save Draft**, then explicitly **Approve Profile vN**. Loading alone does
   not persist anything. Record N and its hash. No feedback-learning operation is used.
3. Read `baseline/requirement.txt` verbatim. Do not add audience/style words to the requirement.
   Compare current effective Requirements/Decisions/Locks with A's context; if changed,
   stop and document the confound instead of silently restoring or modifying story data.
4. Obtain explicit user opt-in for this one B workflow: at most five planning-stage calls
   (one Requirement, up to two Planning + Review iterations), then at most one Writing call
   after human approval. Set `agent_max_attempts = 1` in local `backend/config.toml`;
   leave credentials in this file only. Confirm the execution model is still Lingzhi /
   gpt-5.6-sol and compare the full model profile to `baseline/prompt-lineage.json`.
5. The original C08 workflow occupies this Chapter. After preserving A, cancel that
   workflow through the existing cancel API with its freshly read state_version and a
   new event UUID. This closes the old workflow; it does not delete or rewrite A's Draft,
   Plan, Context or lineage. Create a new chapter-writing workflow on the **same Chapter**
   using exactly the baseline requirement and submit it via the existing USER_SUBMITTED
   action. Record the new Workflow ID. Do not create chapter 2 or leak baseline Draft as
   an approved previous chapter. Verify approved_version remains unchanged.
6. Before starting a Worker, verify this B workflow is the only runnable real-model work.
   Use `agent_execution_scope = "planning-only"` and `agent_max_attempts = 1` in TOML, then run
   `uv run --locked python -m novel_os.worker --config config.toml --once` once per scheduled
   task. Inspect each result before another invocation. Stop at C06 or any failure/block;
   no unbounded retries. The anti-loop policy caps automatic Planning at two iterations.
7. At C06, export planning evidence, compare MUST/FORBIDDEN/required outcome/major direction
   with A, and let the user **Approve the exact Plan** in the Test Console. Do not auto-approve.
   This is a newly generated Plan; it need not copy A's invented scene or prose mechanics.
8. After human Plan Approval, change only the local execution scope to `chapter-writing`,
   verify the pending Writing task belongs to B, then execute the Worker `--once` once.
   Stop at C08. No NOVEL-009, review, revision, automatic rewrite or chapter acceptance.
9. Export B evidence below. Compare model/provider and model parameters, raw requirement
   hash, hard-source versions, Plan/Profile versions, ContextPackage and PromptLineage.
   If model settings differ, flag the confound before interpreting the result.
10. Fill `evaluation/style-ab-human-review.md`; only a human chooses A / B / TIE.

## Read-only evidence export

From `backend/` (the HTTP server must be running):

```sh
uv run --locked python ../scripts/case01_style_ab.py --workflow-id B_WORKFLOW_UUID --output ../evals/writing/v0.1/case-01/variant-b
```

The exporter uses GET only, refuses to overwrite a directory, verifies the baseline hashes,
same Project/Chapter, exact raw requirement, same model/provider/parameters, and exact approved A5 profile bindings across Planning,
Review and Writing. All B stages must use the same Profile ID/version/hash. It saves all attempts including failed run metadata, immutable Context,
PromptLineage, exact Plan, WritingResult and Draft. At C06 add `--planning-only` and use a separate `planning-b` directory for human review;
the resulting bundle is explicitly incomplete for Writing. At C08 export to `variant-b`
without that flag; all three stage bindings and at least one matching Draft are required. No secrets or runtime TOML are exported.

Changed Prompt/Context versions and nondeterministic new Planning are explicit confounds:
this compares the STYLE-001 product behavior to historical A; it is not a profile-only ablation.
Engineering tests do not establish audience fit or a prose winner.
