# UX-001 — Personal Creative Workspace

Date: 2026-09-16
Acceptance: **PASS**

## 1. Background

The DEV-UI-001 console exposed Project, Chapter, Workflow, CreativeBrief, ChapterPlan, HumanGate,
Draft, WritingProfile, Agent runs, Context, Prompt lineage and raw JSON on one long page. It was
useful for engineering verification but required a personal author to understand implementation
concepts before completing an ordinary writing flow.

UX-001 replaces that presentation with a single-user creative workspace. The backend workflow,
authority boundaries, versioning, persistence and agent execution contracts remain unchanged.

## 2. Scope

Implemented only the personal desktop workspace and development evaluation utilities:

- Project and Chapter navigation.
- Requirement, Plan and Draft stage views.
- Human Plan approval, alternative and modification actions.
- Project Writing Profile settings.
- Development-only Case Loader.
- Local JSON export for human evaluation.
- Lazy Debug Drawer preserving engineering evidence.
- Local browser preferences for the last Project, last Chapter, requirement draft, selected manual
  case and Debug state. A submitted Case is then bound locally to that exact Workflow for evaluation
  provenance; a later Chapter draft label cannot relabel an older Draft.

No login, User domain, RBAC, collaboration, sharing, publishing, Review Agent, Revision Agent,
Human Feedback domain or NOVEL-009+ behavior was added.

## 3. Before / After Information Architecture

Before:

`Project → Chapter → Workflow → CreativeBrief → Plan → Gate → Draft → Agent/Context/Prompt/JSON`

All layers were visible together and the user selected Workflow records directly.

After:

`Project → Chapter → Requirement → Plan → Draft`

The workspace automatically opens the latest Chapter workflow. The current decision owns the main
surface. Workflow records, state versions, IDs, runs, ContextPackages, PromptLineages and raw data
are available only after opening Debug.

## 4. Workspace Layout

The page uses a 244 px desktop sidebar and a large content area. The sidebar is a solid, scrollable,
sticky navigation surface. The main area has a simple Chapter header, Refresh and Debug controls.
There are no dashboards, card grids, decorative gradients, glass effects, theme system or complex
router.

A narrower desktop breakpoint reduces the sidebar and content padding. Manual inspection at the
in-app browser's narrow desktop width showed no horizontal page scroll and kept the writing profile
and test actions inside the viewport.

## 5. Chapter Navigation

The sidebar contains a simple Project select, Chapter list and small create forms. A sole or last-used
Project is selected automatically. The last Chapter is restored per Project. Duplicate Project names
are disambiguated with ordinal labels such as `测试 (1)` and `测试 (2)` without exposing UUIDs.

Project and Chapter IDs remain API values and are not rendered in the normal interface.

## 6. Requirement Experience

A Chapter without an active workflow shows one centered natural-language textarea and one
`生成方案` action. It does not expose MUST/SHOULD/FORBIDDEN fields, Context selectors, JSON or
agent settings. An unfinished local textarea draft is stored per Chapter in `localStorage`; starting
the workflow clears the stored draft without changing backend source of truth.

All submission still uses the existing chapter-writing Workflow endpoints and idempotent event
contract. If workflow creation succeeds but the first `USER_SUBMITTED` request fails, the durable
`C00_CREATED` workflow is restored and the interface offers `继续生成方案`; retrying does not
create a second workflow or pretend that local textarea edits would update the saved request.

## 7. Requirement Understanding View

CreativeBrief is presented as `AI 对需求的理解` with a default human summary:

- Goal.
- Must do.
- Must not happen.
- Preferences.
- Creative freedom.

Intent, required outcome, reader effect, should items, assumptions and ambiguities are available in
a nested detail. Source references, logical IDs and raw structured records remain in Debug.

## 8. Plan Experience

The Plan surface prioritizes objective, required outcome and story progression. Each scene shows
purpose, conflict and key change. Information release, character change and exit state are placed in
a small scene detail. Character progression, ending state, cautions and creative freedom use human
labels.

The current Plan is the only Plan body on screen. When older versions exist, `查看历史方案` opens a
small version picker; choosing v1 replaces v2 in the same surface instead of stacking both versions.

## 9. Human Plan Actions

The HumanGate exposes exactly three primary choices:

- `批准并开始写作` → `APPROVE`.
- `换一个方案` → `REQUEST_ALTERNATIVE`, with optional feedback.
- `我想修改` → `MODIFY`, with required natural-language feedback.

The user never edits Plan JSON, version, gate ID or workflow state. Approval re-fetches the execution
policy and is disabled while `WRITE_CHAPTER` is unavailable, preventing a stranded Writing task.
All decisions continue through the formal HumanGate endpoint with expected state and artifact
versions.

## 10. Draft Reading Experience

Draft is a centered reader with a 720 px text measure, 17 px Chinese text, 2.0 line height, preserved
paragraphs and long-page scrolling. The surface shows Chapter number, Draft version and lifecycle
status. Writing metadata and lineage do not compete with prose.

The only current action is `人工评价`. The page states that formal revision and regeneration remain
for NOVEL-010; no bypass or hidden revision endpoint was introduced.

## 11. WritingProfile UX

Writing Profile moved to `写作偏好` in the Project sidebar. The default summary shows target
audience, pacing, narrative density, description density, dialogue density, literary feel and
relationship-change visibility. Editing and advanced fields remain collapsed.

Save and approval remain distinct, exact-version API commands. The UI never turns preferences into
story authority. Complete immutable Profile version records are inspectable in Debug through the
existing read endpoint.

## 12. Manual Test Mode

The development Test drawer provides five fixtures from `evals/manual/`:

- Case 01 — Baseline / Audience Style.
- Case 02 — Hard Constraints.
- Case 03 — Creative Autonomy.
- Case 04 — Plan Feedback.
- Case 05 — Authority Boundary.

JSON is used instead of YAML because Vite and TypeScript import it natively without adding a parser
dependency. Each fixture contains only `id`, `name`, `purpose` and raw natural-language
`requirement`. Loading a case only fills the Requirement textarea. It does not supply a
CreativeBrief, Plan, expected output or database mutation. The Test entry is available only while
Vite runs in development mode; production builds hide it. Fixture presence does not change formal
workflow behavior. A Case can be loaded only before the Chapter has started a workflow. Editing the
loaded requirement clears its pending Case identity, and evaluation derives `case_id` from the
submitted Workflow binding rather than current UI state.

## 13. Human Evaluation

Draft evaluation is a small modal containing Requirement Understanding, Planning Quality, Writing
Audience Fit, AI Writing Feel, Overall, Notes and optional test failure tags. A complete form exports
an `ux-001.v1` JSON artifact through the browser download API.

No backend write occurs. The artifact includes trace IDs for later evaluation analysis, while those
IDs are not rendered in the creative workspace. No NOVEL-011 feedback model or review lifecycle was
created.

## 14. Debug Drawer

Debug is a lazy right-side drawer, closed by default. Opening it fetches transitions, AgentRuns,
ContextPackage, PromptLineage and WritingProfile versions. It groups evidence into:

- Workflow: machine state, state version, current/approved pointers, transition history and gate.
- Agent: tasks, runs, provider, model, durations and failures.
- Context / Prompt: exact run selection, profile, included/excluded items, module pins and hashes.
- Artifacts / Raw JSON: CreativeBrief, Plan, Review, WritingResult, ChapterVersion, Profile versions,
  Workflow, gates, tasks and runs.

Closing the drawer aborts in-flight inspection. Opening a remembered Debug state loads evidence
immediately; a remembered flag without a recoverable snapshot cannot make the workspace inert. The
normal workspace contains no UUID, hash, AgentRun ID, ContextPackage ID, PromptLineage ID or state
version.

## 15. Error / Blocked / Failed UX

Common errors map to a human title and recovery message. `VERSION_CONFLICT` asks the user to refresh.
Provider authentication, availability and timeout failures use specific Chinese explanations.
Error code, request ID and details are collapsed under `查看技术详情`.

Blocked, failed and cancelled workflows stop loading and show a terminal state. A safely resumable
blocked workflow exposes `继续`; AgentRun evidence stays in Debug.

## 16. Polling

The existing polling implementation remains:

- Active agent states poll every 1.5 seconds.
- Human approval, Draft ready and terminal states stop.
- Tasks outside the configured execution scope stop polling.
- Refreshes verify workflow state version before publishing a mixed snapshot.
- Component disposal, Project/Chapter switch and replacement requests abort or ignore late results.
- Approval policy preflight cannot submit after component disposal.

## 17. Backend Changes

None. UX-001 added no endpoint, model, migration, service, repository or state mutation. The frontend
continues to use the typed API client and existing Workflow, HumanGate and WritingProfile services.

## 18. Tests

Final verification:

| Check | Result |
| --- | --- |
| Frontend Vitest | PASS — 54 tests / 5 files |
| Frontend TypeScript | PASS — `vue-tsc --noEmit` |
| Frontend ESLint | PASS |
| Frontend production build | PASS — 48 modules, 45.86 kB JS gzip |
| Browser Playwright | PASS — 10/10 |
| Backend full pytest | PASS — 919 passed, 4 explicit paid-provider skips, 2 upstream warnings; 720.27 s |
| Ruff check | PASS |
| Ruff format check | PASS — 261 files already formatted |
| Git diff check | PASS |

The four skipped backend tests require explicit real-model opt-in. UX verification did not invoke a
paid provider.

## 19. Browser Manual Acceptance

- A — Case 01: Browser E2E loaded only the Case fixture requirement, ran Requirement → Plan →
  approval → Writing → Draft, opened evaluation and downloaded JSON.
- B — Plan modification: Browser E2E submitted the ticket's feedback through `MODIFY`, generated
  Plan v2, retained v1 in history, displayed only one Plan body and completed Writing from v2.
- C — Provider failure: Browser E2E produced a mock provider failure, showed a human recovery
  message, stopped loading and exposed `MODEL_AUTH_ERROR` only in technical detail / Debug.
- D — Debug: Manual in-app browser inspection confirmed the Draft reader contains no internal IDs;
  opening Debug exposed current/approved pointers and grouped evidence.
- E — Recovery and provenance: browser and unit regressions verified C00 retry without duplicate
  workflow creation, exact Workflow-to-Case evaluation binding, clearing a Case label after editing,
  disabling Case replacement for an existing Draft, Escape-to-close, and non-blocking remembered
  Debug state.

## 20. Case 01 Result

**PASS.** The user can choose the Chapter, load Case 01, inspect natural language, start the formal
workflow, read the Requirement summary and Plan, approve Writing, read the Draft, export a human
evaluation and inspect complete lineage without copying a UUID. The browser run used the repository's
isolated Mock E2E provider. The existing real Case 01 B Draft v2 was also visually inspected in the
new reader without making a new model call.

## 21. Case 04 Result

**PASS.** The exact feedback used was:

> 这个方案太平，希望冲突突然一点，双方都应该有合理立场，其他方向不变。

The request went through HumanGate `MODIFY`. Plan v1 remained available through history, Plan v2
became the only current Plan body, and approving v2 produced the Draft. No Plan record was edited in
place.

## 22. Architecture Deviations

No confirmed product architecture was changed. Two implementation choices are documented:

1. Manual fixtures use JSON rather than the illustrative YAML layout to avoid adding a runtime or
   build dependency.
2. Human evaluation uses browser download rather than a dev-only backend endpoint, keeping UX-001
   outside the NOVEL-011 feedback domain.

Independent code review found no remaining Critical or Required issue after fixes. It specifically
re-verified workflow recovery, cross-project Profile isolation, alternative-plan semantics,
ambiguity rendering, initial Debug loading, overlay isolation and Workflow-bound Case provenance.

## 23. Known Issues

- Human evaluation is a downloaded local artifact; the application does not index or aggregate it.
- Revision and regenerate remain unavailable until NOVEL-010.
- The layout targets desktop and common Mac browser widths; mobile optimization was intentionally
  excluded.
- Two existing Starlette/httpx/anyio deprecation warnings remain in backend tests.

## 24. Deferred Items

Review, quality aggregation, revision, formal Chapter acceptance, memory, multi-user identity,
sharing, publishing, analytics and evaluation aggregation remain deferred to their own tickets.
NOVEL-009 was not started.

## 25. Acceptance Result

**UX-001 = PASS.**

A user who does not know Novel OS internals can select a Chapter, describe it in natural language,
review and modify a Plan, approve Writing and read a Draft. Engineering evidence remains available
without occupying the creative workflow.
