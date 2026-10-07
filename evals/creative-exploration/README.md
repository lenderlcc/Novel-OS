# Creative Exploration evaluation

These small assets separate offline contract checks from real creative evaluation.
They add no runner, scoring service, story template library, or automatic model call.

- `case-03.json` records the actual historical small-setback request and its A baseline references. It is different from `evals/manual/case-03.json`.
- `repetition-context.json` supplies a synthetic, concept-level recent-history scenario.
- `authority-boundary.json` supplies a synthetic major-change and knowledge-boundary scenario.
- `manual-evaluation.md` records qualitative A/B judgments and evidence.

Real Provider B generation is **NOT RUN**. The user must explicitly trigger it;
the previous E2E-001R authorization does not authorize this evaluation. Freeze the
same Requirement, approved Writing Profile, and comparable character/Canon context
before comparing historical A with B. Record differences before judging the result.
Historical profile v1 has no narrative-perspective field: do not silently replace it
with a newer approved profile and call that the same-context comparison.

Only authoritative inputs and recent approved-history projections belong in model
context. Baseline answers, human evaluation labels, expected assertions, rejected
concepts, and the rest of these files must not become Agent instructions or Canon.
Use the normal chapter-exploration workflow and existing Worker/runtime. Inspect
the internal artifact in Debug; normal users still approve only the final Plan.

Offline RecordedProvider tests establish contract, persistence, isolation, and
freshness behavior. They cannot establish creative novelty or human reading quality.
Do not use numeric creativity scores, exact-prose matching, keyword blacklists, or
automatic retries for ordinary creative quality. Record `SAFE_GENERIC_CREATIVE_CHOICE`
when a real output still makes that choice, without immediately tuning the Prompt.
