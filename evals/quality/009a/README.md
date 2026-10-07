# NOVEL-009A acceptance fixtures

Each input is a read-only export of an existing immutable ChapterVersion and its original Writing context. `manifest.json` pins Draft/input hashes and actual approved Profile references. `before.json` copies existing runtime AI reports without altering them; Case 04 has no historical AI review. Human questions in `expected-themes.json` are read only after model execution and never included in Prompt/Context. Exact issue-code equality is not acceptance.

Case 04 uses project `23c028ee-cd94-4965-af85-731e560c9633`, chapter `119ae046-5b27-4b71-9ad2-eaae9518af99`, Draft v1. Case 05 uses the latest generated Draft in project `14c99102-f5b0-4a0f-82b6-be829fae15b5`, chapter `23208bf8-ecc7-4054-8ae9-46cf4bc15181`, Draft v1, not the older fifth chapter in the first project.

The latest Case 05 has no ProjectWritingProfile in DB or in its frozen review/Writing inputs. Case 04 has the first project's approved v1 Profile; its current v2 is an unapproved Draft. Do not cross-project copy a Profile. Audience mismatch behavior with HIGH naturalness/reading_experience is covered by isolated contract/integration fixtures. A future real test with a newly approved Case 05 Profile is a different, explicitly labelled input, not the same-input Before/After comparison.

Offline contract run from the repository root (no paid calls):

```sh
backend/.venv/bin/python evals/quality/run.py --input evals/quality/009a/case-04/input.json --output evals/quality/009a/case-04/after-mock --expected evals/quality/009a/case-04/expected-themes.json
backend/.venv/bin/python evals/quality/run.py --input evals/quality/009a/case-05/input.json --output evals/quality/009a/case-05/after-mock --expected evals/quality/009a/case-05/expected-themes.json
```

Only after an explicit user trigger, use fresh output directories and add `--real`: at most two calls per Case, no retry, no workflow mutation, no new Draft. Mock output demonstrates engineering contracts only; semantic improvement requires manual comparison of actual real outputs. Keep before/after identity, reasons/evidence, strengths, false positives and missing Profile limitations separate from label coverage.
