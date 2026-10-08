import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import ConsoleView from '../src/views/ConsoleView.vue'
import { api } from '../src/api/console'
import { writingProfiles } from '../src/api/writingProfiles'
import { clone, sample } from './fixtures'
import { revisionOutputFailure } from '../src/composables/revisionWorkspace'
import type { QualityReview, Revision, Task } from '../src/types/models'

async function openWorkspace() {
  const s = clone(sample.snapshot)
  Object.assign(s.workflow, { workflow_definition_version: 3, current_state: 'C10_REVISION', status: 'WAITING_AGENT', state_version: 10, revision_request_id: 'req', draft_version: 1 })
  s.chapter.current_version = 1
  s.drafts = [{ ...s.drafts[0]!, version: 1 }]
  s.qualityReviews = [{ id: 'review1', version: 1, chapter_version_id: s.drafts[0]!.id, freshness: 'CURRENT', binding: { workflow_id: s.workflow.id, draft_version: 1, profile_record_id: 'profile' }, body: { overall_verdict: 'FAIL', compliance_verdict: 'PASS', narrative_verdict: 'FAIL', audience_fit_verdict: 'PASS', hard_gate_issues: [], quality_issues: [], strengths: [], revision_priorities: [] } } as unknown as QualityReview]
  s.revisions = [{ request: { id: 'req' }, plan: null, candidate: null, result: null } as Revision]
  const responses = { feedback: () => [], workflow: () => s.workflow, chapter: () => s.chapter, gates: () => s.gates, brief: () => s.brief, plans: () => s.plans, history: () => s.history, drafts: () => s.drafts, writing: () => s.writing, tasks: () => s.tasks, qualityReviews: () => s.qualityReviews, revisions: () => s.revisions }
  for (const [key, get] of Object.entries(responses)) vi.spyOn(api, key as keyof typeof responses).mockImplementation(async () => clone(get()) as never)
  vi.spyOn(api, 'executionConfig').mockResolvedValue({ model_profile: 'mock-default', provider: 'mock', model: 'mock', task_types: null, max_attempts: null })
  vi.spyOn(api, 'projects').mockResolvedValue([{ id: s.chapter.project_id, name: 'Review probe' } as never])
  vi.spyOn(api, 'chapters').mockImplementation(async () => [clone(s.chapter)])
  vi.spyOn(api, 'workflows').mockImplementation(async () => [clone(s.workflow)])
  localStorage.setItem('novel-os.last-project', s.chapter.project_id)
  localStorage.setItem(`novel-os.last-chapter.${s.chapter.project_id}`, s.chapter.id)
  const wrapper = mount(ConsoleView)
  await flushPromises()
  return { s, wrapper }
}

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear() })

it.each(['SCHEMA_PARSE_ERROR', 'FORMAT_ERROR', 'MODEL_OUTPUT_INVALID', 'REVISION_EVIDENCE_MISMATCH'])('shows planning output failure instead of ongoing prose revision: %s', async code => {
  const { s, wrapper } = await openWorkspace()
  try {
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', state_version: 11, resume_state: 'C10_REVISION' })
    s.tasks = [{ ...s.tasks[0]!, task_id: 'planning-failure', workflow_instance_id: s.workflow.id, workflow_state: 'C10_REVISION', workflow_state_version: 10, agent_id: 'A06_REVISION', task_type: 'PLAN_CHAPTER_REVISION', status: 'FAILED', last_error_code: code } as Task]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('修改任务未能开始。')
    expect(wrapper.text()).toContain(code === 'REVISION_EVIDENCE_MISMATCH' ? '引用证据定位失败' : '尚未修改正文')
    expect(wrapper.text()).not.toContain('AI 正在修改正文')
    expect(wrapper.text()).not.toContain('修改进行中…')
    const reason = code === 'REVISION_EVIDENCE_MISMATCH' ? 'Evidence Binding Failed' : 'Output Validation Failed'
    expect(revisionOutputFailure(s.tasks[0])).toEqual({ stage: 'Revision Planning', errorCode: code, reason })
    vi.spyOn(api, 'transitions').mockResolvedValue([])
    vi.spyOn(api, 'runs').mockResolvedValue([])
    vi.spyOn(writingProfiles, 'versions').mockResolvedValue([])
    await wrapper.findAll('button').find(b => b.text() === 'Debug')!.trigger('click'); await flushPromises()
    const debug = wrapper.get('[aria-labelledby="debug-title"]')
    expect(debug.text()).toContain('Revision Planning')
    expect(debug.text()).toContain(reason)
    expect(debug.text()).toContain(code)
  } finally { wrapper.unmount() }
})

it('does not label genuine authority or an old failure as current output failure', async () => {
  const { s, wrapper } = await openWorkspace()
  try {
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', state_version: 11, resume_state: 'C10_REVISION' })
    const current = { ...s.tasks[0]!, task_id: 'authority-failure', workflow_instance_id: s.workflow.id, workflow_state: 'C10_REVISION', workflow_state_version: 10, task_type: 'PLAN_CHAPTER_REVISION', status: 'BLOCKED', last_error_code: 'AUTHORITY_DENIED' } as Task
    s.tasks = [{ ...current, task_id: 'old', workflow_state_version: 5, last_error_code: 'SCHEMA_PARSE_ERROR' }, current]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).not.toContain('修改任务未能开始。')
    expect(revisionOutputFailure(current)).toBeNull()
  } finally { wrapper.unmount() }
})

it('keeps an open human evaluation pinned while revision produces the successor', async () => {
  vi.useFakeTimers()
  const { s, wrapper } = await openWorkspace()
  try {
    await wrapper.findAll('button').find(b => b.text() === '人工评价')!.trigger('click')
    await wrapper.get('#evaluation-notes').setValue('只针对原稿 v1 的评价')
    await wrapper.get('input[name="understanding"][value="GOOD"]').setValue()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', state_version: 11, draft_version: 2 })
    s.chapter.current_version = 2
    s.drafts.push({ ...s.drafts[0]!, id: 'draft2', version: 2, content: '修订稿' })
    s.revisions![0]!.result = { chapter_version_id: 'draft2', body: { declared_changes: [] } } as never
    await vi.advanceTimersByTimeAsync(1500); await flushPromises()
    expect({ version: wrapper.findComponent({ name: 'HumanEvaluation' }).props('draftVersion'), notes: (wrapper.get('#evaluation-notes').element as HTMLTextAreaElement).value }).toEqual({ version: 1, notes: '只针对原稿 v1 的评价' })
    expect(wrapper.get('input[name="understanding"][value="GOOD"]').element).toHaveProperty('checked', true)
    expect(wrapper.get('#evaluation-title').text()).toContain('正文 v1')
    expect(wrapper.findComponent({ name: 'DraftView' }).props('draft').version).toBe(2)
    await wrapper.findAll('button').find(b => b.text() === '关闭')!.trigger('click')
    await wrapper.findAll('button').find(b => b.text() === '人工评价')!.trigger('click')
    expect(wrapper.findComponent({ name: 'HumanEvaluation' }).props('draftVersion')).toBe(2)
    expect(wrapper.get('#evaluation-notes').element).toHaveProperty('value', '')
  } finally { wrapper.unmount() }
})

it('offers a new-source recovery after Fidelity context budget fails before result', async () => {
  const { s, wrapper } = await openWorkspace()
  try {
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', state_version: 13, resume_state: 'C10_REVISION', block_reason: 'EXTERNAL_CONDITION' })
    s.tasks = [
      { ...s.tasks[0]!, task_id: 'execution', workflow_instance_id: s.workflow.id, workflow_state: 'C10_REVISION', workflow_state_version: 11, agent_id: 'A06_REVISION', task_type: 'REVISE_CHAPTER', status: 'SUCCEEDED', last_error_code: null },
      { ...s.tasks[0]!, task_id: 'fidelity', workflow_instance_id: s.workflow.id, workflow_state: 'C10_REVISION', workflow_state_version: 12, agent_id: 'A05_REVIEW', task_type: 'VALIDATE_REVISION_FIDELITY', status: 'BLOCKED', last_error_code: 'CONTEXT_BUDGET_EXCEEDED' },
    ] as Task[]
    s.revisions = [{ request: { id: 'req' }, plan: { body: { blocked_reasons: [] } }, candidate: { body: { blocked_reasons: [], content: '待检查候选稿' } }, result: null } as unknown as Revision]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('配置修复后可重新审阅')
    expect(wrapper.findAll('button').filter(b => b.text().startsWith('重新审阅正文'))).toHaveLength(1)
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重试本阶段'))).toBe(false)
    const rereview = vi.spyOn(api, 'rereview').mockResolvedValue({ workflow: s.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    expect(rereview).not.toHaveBeenCalled()
    await wrapper.findAll('button').find(b => b.text().startsWith('重新审阅正文'))!.trigger('click')
    await flushPromises()
    expect(rereview).toHaveBeenCalledWith(expect.objectContaining({ id: s.workflow.id, state_version: 13 }), 1, expect.any(String))
  } finally { wrapper.unmount() }
})

it.each(['earlier attempt', 'other workflow'])('ignores a budget block from an %s when Fidelity needs a technical retry', async source => {
  const { s, wrapper } = await openWorkspace()
  try {
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', state_version: 13, resume_state: 'C10_REVISION' })
    const current = { ...s.tasks[0]!, task_id: 'fidelity', workflow_instance_id: s.workflow.id, workflow_state: 'C10_REVISION', workflow_state_version: 12, agent_id: 'A05_REVIEW', task_type: 'VALIDATE_REVISION_FIDELITY', status: 'FAILED', last_error_code: 'MODEL_TIMEOUT' } as Task
    const unrelated = { ...current, task_id: 'old', agent_id: 'A06_REVISION', task_type: 'REVISE_CHAPTER', status: 'BLOCKED', last_error_code: 'CONTEXT_BUDGET_EXCEEDED', workflow_state_version: source === 'earlier attempt' ? 9 : 12, workflow_instance_id: source === 'other workflow' ? 'other' : s.workflow.id } as Task
    s.tasks = [current, unrelated]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重新审阅正文'))).toBe(false)
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重试本阶段'))).toBe(true)
    expect(wrapper.text()).not.toContain('修改所需内容超出当前处理预算')
  } finally { wrapper.unmount() }
})
