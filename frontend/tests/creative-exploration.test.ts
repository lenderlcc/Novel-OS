import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { api } from '../src/api/console'
import { writingProfiles } from '../src/api/writingProfiles'
import DebugPanel from '../src/components/DebugPanel.vue'
import PlanView from '../src/components/PlanView.vue'
import WorkflowProgress from '../src/components/WorkflowProgress.vue'
import { currentTask, isWritingWorkflow, pollDelay } from '../src/composables/workflowState'
import type { PlanningHistory } from '../src/types/models'
import { sample, waitingSnapshot } from './fixtures'

type Exploration = NonNullable<PlanningHistory['explorations']>[number]
function evidence(): Exploration {
  const s = sample.snapshot
  const candidate = {
    id: 'SELECTED', concept_summary: 'Selected mechanism', core_event: 'Bounded event',
    conflict_engine: 'Conflicting local choices', character_pressure: 'A costly decision',
    story_progression: 'A limited consequence', reader_interest: 'An uncertain choice',
    continuity_fit: 'Fits supplied facts', requirement_fit: 'Within the Brief',
    creative_freedom_fit: 'Within granted operations', audience_fit: 'Approved preference',
    execution_feasibility: 'Local scope', required_new_elements: [],
    major_change_risk: 'LOW' as const, major_change_reason: 'No new Canon',
    similarity_risk: 'LOW' as const, similarity_reason: 'Distinct causal pressure',
    authority_fit: 'WITHIN_BOUNDS' as const, authority_reason: 'Subordinate to authority',
    strengths: ['Character choice'], risks: [],
  }
  return {
    id: 'exploration-record', project_id: s.chapter.project_id, chapter_id: s.chapter.id,
    workflow_id: s.workflow.id, agent_run_id: sample.runs[0]!.run_id,
    prompt_lineage_id: sample.lineage.lineage_id ?? "prompt-id", context_package_id: sample.context.package.context_package_id ?? "context-id",
    brief_id: s.brief!.id, source_versions: [], created_at: s.brief!.created_at,
    status: 'READY', authority_level: 'A7_AI_INFERENCE', freshness: 'READY',
    body: {
      kind: 'creative_exploration', brief_id: s.brief!.id, mode: 'DIVERGENT', focused_reason: null,
      candidates: [candidate, { ...candidate, id: 'REJECTED', core_event: 'Rejected mechanism' }],
      selected_candidate_id: 'SELECTED', selection_reason: 'Best local fit',
      rejected_reasons: [{ candidate_id: 'REJECTED', code: 'REPETITION_RISK', reason: 'Repeats prior pressure' }],
      source_refs: [], blocked_reason: null,
    },
  }
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
describe('internal A03 exploration', () => {
  it('starts v4 through the existing creation payload without client authority fields', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ workflow: sample.snapshot.workflow, outcome: 'APPLIED', duplicate: false }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetcher)
    await api.start('project', 'chapter', 'Original user requirement', 'event')
    expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/workflows/chapter-exploration')
    const options = fetcher.mock.calls[0]?.[1] as RequestInit
    expect(JSON.parse(options.body as string)).toEqual({ project_id: 'project', chapter_id: 'chapter', raw_requirement: 'Original user requirement', event_id: 'event' })
  })
  it('shows candidates and exact lineage only in Debug, keeping normal Plan singular', async () => {
    vi.spyOn(api, 'transitions').mockResolvedValue([])
    vi.spyOn(api, 'runs').mockResolvedValue([])
    vi.spyOn(writingProfiles, 'versions').mockResolvedValue([])
    const s = waitingSnapshot(); s.workflow.workflow_definition_version = 4
    s.history.explorations = [evidence()]
    const debug = mount(DebugPanel, { props: { snapshot: s, open: true } })
    await flushPromises()
    expect(debug.text()).toContain('A03 Creative Exploration')
    expect(debug.text()).toContain('Rejected mechanism')
    expect(debug.text()).toContain('Repeats prior pressure')
    expect(debug.text()).toContain('exploration-record')
    expect(debug.text()).toContain('A7_AI_INFERENCE')
    const plan = mount(PlanView, { props: { plan: s.plans[0]!, generation: s.history.plans[0]!, review: s.history.reviews[0]! } })
    expect(plan.text()).not.toContain('Rejected mechanism')
    expect(plan.text()).not.toContain('Selected mechanism')
    expect(plan.findAll('[data-testid="plan-review"]')).toHaveLength(1)
    debug.unmount(); plan.unmount()
  })
  it('polls the active formal task when exploration shares the same workflow state version', () => {
    const w = { ...sample.snapshot.workflow, workflow_definition_version: 4, current_state: 'C04_CHAPTER_PLANNING' as const, status: 'WAITING_AGENT' as const }
    const base = { ...sample.snapshot.tasks[0]!, workflow_instance_id: w.id, workflow_state: w.current_state, workflow_state_version: w.state_version }
    const tasks = [{ ...base, task_id: 'explore', task_type: 'EXPLORE_CHAPTER_CONCEPTS', status: 'SUCCEEDED' as const }, { ...base, task_id: 'plan', task_type: 'PLAN_CHAPTER', status: 'PENDING' as const, attempt_count: 0 }]
    expect(isWritingWorkflow(w)).toBe(true)
    expect(currentTask(w, tasks)?.task_id).toBe('plan')
    expect(pollDelay(w, tasks)).toBe(1500)
    const progress = mount(WorkflowProgress, { props: { workflow: w, tasks } })
    expect(progress.text()).toContain('等待后台执行')
    expect(progress.findAll('.progress li')).toHaveLength(6)
    progress.unmount()
  })
})
