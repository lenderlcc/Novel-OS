# Requirement semantic evaluation v0.1

This evaluation is separate from Writing acceptance. R001 preserves the user's
Case 01 input verbatim, with a SHA-256 hash and human review anchors. Production
code must never load the annotations or use them as a fallback response.

## Evidence and acceptance levels

- `cases/R001.json`: exact raw input and expected semantic distinctions. These
  are review anchors; sensible quote boundaries and category granularity can vary.
- `results/before/trace.json`: original Mock run, persisted Brief, ContextPackage
  and PromptLineage. `provider-output.json` is a replay of that historical Mock
  response, verified equal to the saved Brief after parsing.
- `results/<timestamp>-<id>/`: one explicitly opted-in real Requirement attempt.
  `request.json` records compiled messages and module pins, without credentials.
  `trace.json` records task/run/context/lineage and persistence. Provider output,
  usage and parsed output exist only if those stages were reached.

Offline annotated responses test **transport, parsing, evidence validation and
persistence**, not natural-language understanding. Mock is a deterministic
contract fixture; its confidence is zero to denote unmeasured semantics, and its
result carries `MOCK_SEMANTICS_NOT_EVALUATED`. A passing fixture test is not an AI
Behavior Acceptance result.

## Offline regression

From `backend/`:

```bash
uv run pytest tests/core/workflow -k requirement_semantics
```

This skips the external call. Full `uv run pytest` also skips paid tests.

## One explicitly authorized real attempt

Configure the ignored, local `backend/config.toml` credential and
`requirement_smoke_profile`. `openai-structured` uses the official OpenAI adapter;
`lingzhi-requirement` uses Lingzhi Responses with `gpt-5.6-sol`. The gateway profile
uses `lingzhi_api_key` and `lingzhi_base_url = "https://lingzhi.agibot.com/v1"`,
never environment variables or the OpenAI credential. Its limits are 120 seconds
and 8192 output tokens in `backend/novel_os/providers/profiles.toml`. Keep the
background Worker stopped. Only after explicit authorization for an API attempt:

```bash
uv run pytest tests/core/workflow/test_requirement_semantics.py::test_case01_one_live_requirement_attempt --live-model -s
```

The test executes one Requirement worker attempt in an isolated schema in the
test database, writes evidence, and removes that schema afterwards. Planning may
be queued by the normal state transition but is never executed. No Writing runs.
There is no transport retry; running this command again is a new paid attempt
and requires authorization. Do not run the whole suite with `--live-model`.

The local gateway model-list GET succeeded, but no Lingzhi content-generation
request has been executed yet. Model-list access does not prove generation or
Structured Outputs compatibility; the next authorized single attempt verifies it.

## Human semantic review

Record PASS / PARTIAL / FAIL / NOT OBSERVED for:

1. Core goals and mandatory actions remain MUST without copying the whole input.
2. Negatives and prohibited end states remain FORBIDDEN with their full scope.
3. SHOULD guidance remains negotiable; optional preferences remain optional.
4. Creative delegation is explicit and bounded by timing, plot and relationship
   constraints; it does not become an invented obligation.
5. Intent, objective, required outcome and reader effect serve separate purposes.
6. Each constraint has minimal sufficient contiguous evidence, preserving
   negation, conditionality and timing. Existing structured Requirements retain
   their full approved content and category.
7. Confidence reflects stated semantic uncertainty and agrees between envelope
   and Brief; unresolved assumptions are visible.

A single successful sample supports only a case-level observation. Confidence
bands in the prompt are self-reporting conventions, not statistically calibrated
probabilities. Calibration requires more independently labeled samples.
