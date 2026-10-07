# Quality evaluation v1

This is an offline/explicit-opt-in evaluator, separate from Workflow persistence and Human Evaluation. Human themes live under `cases/`; they are never passed to A05. No label-perfect metric or numeric prose score. Case snapshots are not synthesized to satisfy expectations.

From the repository root, first export one exact historical Draft and its original Writing context (read-only DB, no provider call):

```sh
backend/.venv/bin/python evals/quality/run.py \
  --export /tmp/case-01-review-input.json \
  --project-id PROJECT_UUID --chapter-id CHAPTER_UUID --draft-version 1
```

This requires a Draft with WritingGeneration, exact Brief and original ContextPackage. The Profile comes from the original Writing snapshot, even if today's approval changed. Missing historical canon/character knowledge/recent history is not fabricated. Pre-STYLE drafts have no invented Profile or POV rule.

Default Mock contract evaluation (no API usage):

```sh
backend/.venv/bin/python evals/quality/run.py \
  --input /tmp/case-01-review-input.json --output /tmp/case-01-quality-mock \
  --expected evals/quality/cases/case-01/expected-themes.json
```

Only after explicit human authorization, the same command with `--real` uses the model profile and credential in `backend/config.toml`. It performs at most two calls, one per pass; failures stop without retries. Output directories must be new. This command is an opt-in, not an automatically scheduled eval.

Outputs: pass reports, exact ContextPackage, prompt module/version/hash and compiled hash, ModelProfile, local evaluation task/run/lineage UUIDs, aggregate review and AI codes versus human expected themes. Evaluation UUIDs are file artifact identifiers, not rows in the runtime DB. No data is approved or modified. Runtime review records retain DB lineage separately.

## Human comparison

For each Case 01–05, record:

- Exact Draft/Plan/Profile input IDs, versions, hashes and original Writing lineage.
- Whether the AI detected the expected *theme*, with its actual excerpt/reason.
- Unsupported claims and false positives, especially canon, character knowledge and narration vs dialogue.
- Whether major direction and human sovereignty were preserved.
- Useful strengths and proposed directions; whether they would worsen another dimension.
- Reviewer confidence compared with evidence clarity; disagreement explained in prose.
- Engineering validity, AI behavior and human prose quality as separate conclusions.

Case 03's historical POV finding is conditional, not a forced expected failure. A historical input with only one preceding chapter cannot support a repeated SAFE_GENERIC_CREATIVE_CHOICE claim; record that limitation.

The workspace Debug drawer can import an exported `ux-001.v1` human evaluation and display its tags/notes alongside AI findings only when Project/Chapter/Workflow/Draft version match. It never overwrites the export or the AI report.
# Phase 2 entry

CHECKPOINT-001 的 suite 使用现有 `evals/e2e/multi-chapter/run.py --allow-real-provider --worker-stopped`，由标准 Worker 执行并停止在真实 human gates。本目录 `--real` 保留作单独授权的历史 Draft 诊断，不是 Phase 2 编排入口；默认不调用真实模型。
