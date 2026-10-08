import { effectScope } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/api/console'
import { writingProfiles } from '../src/api/writingProfiles'
import { ApiError } from '../src/api/client'
import { useConsole } from '../src/composables/useConsole'
import { pollDelay, progressLabel } from '../src/composables/workflowState'
import ConsoleView from '../src/views/ConsoleView.vue'
import DebugPanel from '../src/components/DebugPanel.vue'
import type { Chapter, Dispatch, QualityReview, Revision, Task } from '../src/types/models'
import { clone, sample } from './fixtures'

function setup(verdict = 'FAIL') {
  const s = clone(sample.snapshot)
  Object.assign(s.workflow, { workflow_definition_version: 3, current_state: 'C10_REVISION', status: 'WAITING_HUMAN', revision_request_id: null, draft_version: 1 })
  s.chapter.current_version = 1
  s.drafts = [{ ...s.drafts[0]!, version: 1 }]
  s.qualityReviews = [{ id: 'r1', version: 1, chapter_version_id: s.drafts[0]!.id, freshness: 'CURRENT', binding: { workflow_id: s.workflow.id, draft_version: 1, profile_record_id: 'approved-profile' }, body: { overall_verdict: verdict, compliance_verdict: 'PASS', narrative_verdict: verdict, audience_fit_verdict: 'PASS', hard_gate_issues: [], quality_issues: [], strengths: [], revision_priorities: [] } } as unknown as QualityReview]
  s.revisions = []
  const client = { ...api,
    workflow: vi.fn(async () => clone(s.workflow)), chapter: vi.fn(async () => clone(s.chapter)),
    executionConfig: vi.fn(async () => ({ model_profile: 'mock-default', provider: 'mock', model: 'mock', task_types: null, max_attempts: null })),
    gates: vi.fn(async () => clone(s.gates)), brief: vi.fn(async () => clone(s.brief)), plans: vi.fn(async () => clone(s.plans)),
    history: vi.fn(async () => clone(s.history)), drafts: vi.fn(async () => clone(s.drafts)), writing: vi.fn(async () => clone(s.writing)), tasks: vi.fn(async () => clone(s.tasks)),
    feedback: vi.fn(async () => []),
    qualityReviews: vi.fn(async () => clone(s.qualityReviews!)), revisions: vi.fn(async () => clone(s.revisions!)), revise: vi.fn(api.revise),
  }
  const scope = effectScope(), c = scope.run(() => useConsole(client))!
  c.projectId.value = s.chapter.project_id; c.chapterId.value = s.chapter.id; c.workflowId.value = s.workflow.id
  return { s, client, scope, c }
}
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear() })

describe('revision execution control', () => {
  it('refresh never requests Revision automatically', async () => {
    const { c, client, scope } = setup()
    await c.refresh(); await c.refresh()
    expect(client.revise).not.toHaveBeenCalled()
    expect(c.draft.value?.version).toBe(1)
    scope.stop()
  })
  it('pins an explicit reading choice made during a slow poll, even when it was current', async () => {
    const { c, s, client, scope } = setup()
    await c.refresh()
    let finish!: (chapter: Chapter) => void
    client.chapter.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    s.chapter.current_version = 2; s.workflow.draft_version = 2
    s.drafts.push({ ...s.drafts[0]!, id: 'd2', version: 2, content: '修改正文' })
    const pending = c.refresh(false)
    await flushPromises()
    c.selectedDraft.value = 1
    finish(clone(s.chapter)); await pending
    expect(c.currentBackendVersion.value).toBe(2)
    expect(c.selectedDraft.value).toBe(1)
    expect(c.draft.value?.id).toBe(s.drafts[0]!.id)
    expect(client.revise).not.toHaveBeenCalled()
    scope.stop()
  })
  it('a new explicit Revision follows its successor until the user selects a version', async () => {
    const { c, s, client, scope } = setup()
    await c.refresh(); c.selectedDraft.value = 1
    client.revise.mockImplementationOnce(async () => {
      s.chapter.current_version = 2; s.workflow.draft_version = 2
      s.workflow.current_state = 'C09_INTERNAL_REVIEW'; s.workflow.status = 'WAITING_AGENT'
      s.drafts.push({ ...s.drafts[0]!, id: 'd2', version: 2 })
      return { workflow: s.workflow, outcome: 'APPLIED', duplicate: false, error_code: null }
    })
    await c.revise()
    expect(c.draft.value?.id).toBe('d2')
    expect(client.revise).toHaveBeenCalledTimes(1)
    scope.stop()
  })
  it('uses the latest review revision of the exact Draft, regardless of response ordering', async () => {
    const { c, s, client, scope } = setup()
    s.qualityReviews!.push({ ...s.qualityReviews![0]!, id: 'r2', version: 2 })
    s.qualityReviews!.unshift({ ...s.qualityReviews![0]!, id: 'another-draft-review', version: 99, chapter_version_id: 'another-draft' })
    await c.refresh()
    client.revise.mockResolvedValue({ workflow: s.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await c.revise()
    expect(client.revise.mock.calls[0]![1].id).toBe('r2')
    scope.stop()
  })
  it('rejects an exact Draft review from another workflow before dispatch', async () => {
    const { c, s, client, scope } = setup()
    s.qualityReviews![0]!.binding.workflow_id = 'other-workflow'
    await c.refresh(); await c.revise()
    expect(c.error.value?.code).toBe('STALE_VIEW')
    expect(client.revise).not.toHaveBeenCalled()
    scope.stop()
  })
  it('polls through re-review and stops on FAIL without a second Revision', async () => {
    vi.useFakeTimers()
    const { c, s, client, scope } = setup()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT', revision_request_id: 'request', draft_version: 2 })
    s.chapter.current_version = 2
    s.drafts.push({ ...s.drafts[0]!, id: 'd2', version: 2 })
    await c.refresh()
    expect(c.draft.value?.id).toBe('d2')
    Object.assign(s.workflow, { current_state: 'C10_REVISION', status: 'WAITING_HUMAN', revision_request_id: null })
    await vi.advanceTimersByTimeAsync(1500)
    const reads = client.workflow.mock.calls.length
    await vi.advanceTimersByTimeAsync(30000)
    expect(client.workflow).toHaveBeenCalledTimes(reads)
    expect(client.revise).not.toHaveBeenCalled()
    scope.stop()
  })
  it('duplicate clicks use one request and retain its id after uncertain delivery', async () => {
    const { c, client, scope } = setup()
    await c.refresh()
    let reject!: (reason: unknown) => void
    client.revise.mockImplementationOnce(() => new Promise<Dispatch>((_, r) => { reject = r }))
    const first = c.revise()
    await flushPromises()
    await c.revise()
    expect(client.revise).toHaveBeenCalledTimes(1)
    const event = client.revise.mock.calls[0]![3]
    reject(new ApiError('NETWORK_ERROR', 'uncertain'))
    await first
    client.revise.mockRejectedValueOnce(new ApiError('NETWORK_ERROR', 'uncertain again'))
    await c.revise()
    expect(client.revise.mock.calls[1]![3]).toBe(event)
    scope.stop()
  })
  it('does not retry stale version requests', async () => {
    const { c, client, scope } = setup()
    await c.refresh()
    client.revise.mockRejectedValueOnce(new ApiError('VERSION_CONFLICT', 'refresh', null, 409))
    await c.revise()
    expect(client.revise).toHaveBeenCalledTimes(1)
    expect(c.conflict.value).toBe(true)
    scope.stop()
  })
  it('shows revised Draft even when re-review is blocked, and supports previous version', async () => {
    const { c, s, scope } = setup()
    s.workflow.current_state = 'C90_BLOCKED'; s.workflow.status = 'BLOCKED'; s.workflow.draft_version = 2; s.workflow.revision_request_id = 'request'
    s.chapter.current_version = 2
    s.drafts.unshift({ ...s.drafts[0]!, id: 'd2', version: 2, content: '修订后的正文' })
    s.revisions = [{ result: { chapter_version_id: 'd2' } } as Revision]
    await c.refresh()
    expect(c.draft.value?.content).toBe('修订后的正文')
    c.selectedDraft.value = 1
    expect(c.draft.value?.id).not.toBe('d2')
    await c.refresh()
    expect(c.selectedDraft.value).toBe(1)
    scope.stop()
  })
  it.each(['PLAN_CHAPTER_REVISION', 'REVISE_CHAPTER'])('polls and labels %s across refresh', async taskType => {
    const { c, s, scope } = setup()
    Object.assign(s.workflow, { status: 'WAITING_AGENT', revision_request_id: 'request' })
    s.tasks = [{ ...s.tasks[0]!, task_type: taskType, workflow_instance_id: s.workflow.id, workflow_state: s.workflow.current_state, workflow_state_version: s.workflow.state_version, status: 'RUNNING' } as Task]
    await c.refresh()
    expect(pollDelay(c.workflow.value, s.tasks)).toBe(1500)
    expect(progressLabel(s.workflow, s.tasks)).toBe(taskType === 'PLAN_CHAPTER_REVISION' ? '正在确定修改范围' : '正在修改正文')
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW' })
    expect(progressLabel(s.workflow, [])).toBe('正在重新审阅')
    scope.stop()
  })
})

async function workspace(verdict = 'FAIL') {
  const { s, client, scope } = setup(verdict)
  scope.stop()
  for (const method of ['workflow', 'chapter', 'executionConfig', 'gates', 'brief', 'plans', 'history', 'drafts', 'writing', 'tasks', 'qualityReviews', 'revisions', 'feedback'] as const) vi.spyOn(api, method).mockImplementation(client[method] as never)
  vi.spyOn(api, 'projects').mockResolvedValue([{ id: s.chapter.project_id, name: '离线测试' } as never])
  vi.spyOn(api, 'chapters').mockResolvedValue([s.chapter])
  vi.spyOn(api, 'workflows').mockResolvedValue([s.workflow])
  localStorage.setItem(`novel-os.last-chapter.${s.chapter.project_id}`, s.chapter.id)
  const wrapper = mount(ConsoleView)
  await flushPromises()
  return { wrapper, s, client }
}

describe('revision workspace', () => {
  it('binds human evaluation to the selected immutable Draft without carrying v1 inputs to v2', async () => {
    const { wrapper, s } = await workspace()
    s.chapter.current_version = 2; s.workflow.draft_version = 2
    s.drafts.push({ ...s.drafts[0]!, id: 'd2', version: 2 })
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    await wrapper.get('#draft-version').setValue('1')
    await wrapper.findAll('button').find(b => b.text() === '人工评价')!.trigger('click')
    expect(wrapper.findComponent({ name: 'HumanEvaluation' }).props('draftVersion')).toBe(1)
    await wrapper.get('#evaluation-notes').setValue('只属于原稿的评价')
    await wrapper.findAll('button').find(b => b.text() === '关闭')!.trigger('click')
    await wrapper.get('#draft-version').setValue('2')
    await wrapper.findAll('button').find(b => b.text() === '人工评价')!.trigger('click')
    expect(wrapper.findComponent({ name: 'HumanEvaluation' }).props('draftVersion')).toBe(2)
    expect(wrapper.get('#evaluation-notes').element).toHaveProperty('value', '')
    wrapper.unmount()
  })
  it('explains why a legacy Draft without quality review cannot be revised', async () => {
    const { wrapper, s } = await workspace()
    Object.assign(s.workflow, { workflow_definition_version: 2, current_state: 'C08_DETERMINISTIC_CHECK', status: 'WAITING_AGENT' })
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('尚未接入正文审阅与修改')
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    expect(wrapper.get('#draft-version').element).toBeDefined()
    wrapper.unmount()
  })
  it('keeps v2 readable while re-review runs and restores progress on reload without dispatch', async () => {
    const { wrapper, s } = await workspace()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT', revision_request_id: 'active', draft_version: 2 })
    s.chapter.current_version = 2
    s.drafts.push({ ...s.drafts[0]!, id: 'd2', version: 2, content: '重审中的新正文' })
    s.revisions = [{ request: { id: 'older' }, result: null }, { request: { id: 'active' }, result: { chapter_version_id: 'd2', body: { declared_changes: [] } } }] as Revision[]
    const revise = vi.spyOn(api, 'revise')
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('AI 正在重新审阅')
    expect(wrapper.get('[aria-label="章节正文"]').text()).toBe('重审中的新正文')
    expect(wrapper.findComponent({ name: 'QualityReview' }).props('review')).toBeNull()
    expect(wrapper.findAll('button').find(b => b.text() === '修改进行中…')!.attributes('disabled')).toBeDefined()
    await wrapper.get('#draft-version').setValue('1')
    expect(wrapper.findComponent({ name: 'QualityReview' }).props('review').id).toBe('r1')
    expect(wrapper.get('[aria-label="修改进度"] h2').text()).toBe('AI 正在重新审阅…')
    expect(wrapper.text()).toContain('当前正文仍为 v2')
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重新审阅正文'))).toBe(false)
    expect(revise).not.toHaveBeenCalled()
    wrapper.unmount()
    const restored = mount(ConsoleView); await flushPromises()
    expect(restored.get('#draft-version').element).toHaveProperty('value', '2')
    expect(restored.text()).toContain('AI 正在重新审阅')
    expect(revise).not.toHaveBeenCalled()
    restored.unmount()
  })
  it.each(['FAILED', 'CANCELLED', 'PAUSED'] as const)('never describes stopped %s Revision as running', async status => {
    const { wrapper, s } = await workspace()
    Object.assign(s.workflow, { status, current_state: status === 'FAILED' ? 'C91_FAILED' : status === 'CANCELLED' ? 'C92_CANCELLED' : 'C10_REVISION', revision_request_id: 'request' })
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).not.toContain('AI 正在修改正文')
    expect(wrapper.text()).not.toContain('正在确定修改范围')
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    if (status === 'FAILED') expect(wrapper.text()).toContain('修改正文失败')
    wrapper.unmount()
  })
  it.each([
    ['FAIL', 'C10_REVISION'],
    ['PASS_WITH_WARNINGS', 'C11_INTERNAL_PASS'],
    ['PASS', 'C11_INTERNAL_PASS'],
  ] as const)('offers explicit re-review of stale %s after an approved Profile changes', async (verdict, state) => {
    const { wrapper, s } = await workspace(verdict)
    s.workflow.current_state = state
    s.qualityReviews![0]!.freshness = 'STALE'
    vi.spyOn(writingProfiles, 'state').mockResolvedValue({ current: null, approved: { id: 'approved-profile-v2' } } as never)
    const revise = vi.spyOn(api, 'revise')
    const rereview = vi.spyOn(api, 'rereview').mockResolvedValue({ workflow: s.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('依据已变化')
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    expect(wrapper.findAll('button').some(b => b.text() === '设置写作偏好')).toBe(false)
    expect(rereview).not.toHaveBeenCalled()
    const button = wrapper.findAll('button').find(b => b.text().startsWith('重新审阅正文'))
    expect(button).toBeDefined()
    await button!.trigger('click'); await flushPromises()
    expect(rereview).toHaveBeenCalledTimes(1)
    expect(rereview).toHaveBeenCalledWith(expect.objectContaining({ id: s.workflow.id, state_version: s.workflow.state_version }), 1, expect.any(String))
    expect(revise).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('does not offer re-review from a historical Draft with a stale Review', async () => {
    const { wrapper, s } = await workspace()
    s.qualityReviews![0]!.freshness = 'STALE'
    s.drafts.unshift({ ...s.drafts[0]!, id: 'd2', version: 2, content: '当前正文' })
    s.chapter.current_version = 2
    s.workflow.draft_version = 2
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    await wrapper.get('#draft-version').setValue('1')
    expect(wrapper.text()).toContain('Review v1 · 对应 Draft v1')
    expect(wrapper.text()).toContain('依据已变化')
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重新审阅正文'))).toBe(false)
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    wrapper.unmount()
  })
  it.each(['C09_INTERNAL_REVIEW', 'C10_REVISION'] as const)('does not offer stale re-review while %s is running', async state => {
    const { wrapper, s } = await workspace()
    Object.assign(s.workflow, { current_state: state, status: 'WAITING_AGENT', revision_request_id: state === 'C10_REVISION' ? 'request' : null })
    s.qualityReviews![0]!.freshness = 'STALE'
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重新审阅正文'))).toBe(false)
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    wrapper.unmount()
  })
  it.each([false, true])('requires approved preferences before re-reviewing a profile-less source: %s', async approved => {
    const { wrapper, s } = await workspace()
    s.qualityReviews![0]!.binding.profile_record_id = null
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    expect(wrapper.text()).toContain('请先创建并批准写作偏好')
    vi.spyOn(writingProfiles, 'state').mockResolvedValue({ current: null, approved: approved ? { id: 'approved-profile' } : null } as never)
    const rereview = vi.spyOn(api, 'rereview').mockResolvedValue({ workflow: s.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await wrapper.findAll('button').find(b => b.text().startsWith('重新审阅正文'))!.trigger('click'); await flushPromises()
    expect(rereview).toHaveBeenCalledTimes(approved ? 1 : 0)
    if (!approved) expect(wrapper.text()).toContain('请先保存并批准写作偏好')
    wrapper.unmount()
  })
  it.each(['FAIL', 'PASS_WITH_WARNINGS'])('offers explicit CTA for %s', async verdict => {
    const { wrapper } = await workspace(verdict)
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(true)
    wrapper.unmount()
  })
  it('hides the primary CTA on PASS', async () => {
    const { wrapper } = await workspace('PASS')
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    wrapper.unmount()
  })
  it('binds review to the selected Draft and shows a readable blocked reason', async () => {
    const { wrapper, s } = await workspace()
    s.drafts.unshift({ ...s.drafts[0]!, id: 'd2', version: 2, content: '新正文内容' })
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: 'C10_REVISION', revision_request_id: 'request', draft_version: 2 })
    s.chapter.current_version = 2
    s.qualityReviews!.unshift({ ...s.qualityReviews![0]!, id: 'r2', version: 2, binding: { ...s.qualityReviews![0]!.binding, draft_version: 2 }, chapter_version_id: 'd2', body: { ...s.qualityReviews![0]!.body, overall_verdict: 'PASS' } })
    s.revisions = [{ request: { id: 'request' }, result: { chapter_version_id: 'd2', body: { declared_changes: ['压缩重复解释'], blocked_reasons: [{ issue_id: 'issue', reason: '当前证据不足，不能新增重大设定。' }] } } } as unknown as Revision]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('新正文内容')
    expect(wrapper.text()).toContain('Review v2 · 对应 Draft v2')
    expect(wrapper.text()).toContain('不能新增重大设定')
    await wrapper.get('#draft-version').setValue('1')
    expect(wrapper.text()).not.toContain('新正文内容')
    expect(wrapper.findComponent({ name: 'QualityReview' }).props('review').id).toBe('r1')
    expect(wrapper.text()).toContain('Review v1 · 对应 Draft v1')
    wrapper.unmount()
  })
  it('keeps exact revision lineage accessible in Debug', async () => {
    const { s, scope } = setup(); scope.stop()
    vi.spyOn(api, 'transitions').mockResolvedValue([])
    vi.spyOn(api, 'runs').mockResolvedValue([])
    s.revisions = [{ request: { id: 'exact-revision-request' }, plan: { context_package_id: 'exact-context' } } as Revision]
    const wrapper = mount(DebugPanel, { props: { open: true, snapshot: s } })
    await flushPromises()
    expect(wrapper.text()).toContain('Revision / Lineage')
    expect(wrapper.text()).toContain('exact-context')
    wrapper.unmount()
  })
})

describe('revision recovery actions', () => {
  it('keeps the current text and history visible after a standalone re-review fails', async () => {
    const { wrapper, s } = await workspace()
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: 'C09_INTERNAL_REVIEW', revision_request_id: null })
    s.writing = []
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.get('[aria-label="章节正文"]').element.textContent).toBe(s.drafts[0]!.content)
    expect(wrapper.get('#draft-version').element).toHaveProperty('value', '1')
    expect(wrapper.text()).toContain('Review v1 · 对应 Draft v1')
    expect(wrapper.findAll('button').some(b => b.text() === '根据审阅修改')).toBe(false)
    wrapper.unmount()
  })
  it.each([
    ['BLOCKED', 'C10_REVISION', true],
    ['FAILED', 'C10_REVISION', false],
    ['BLOCKED', 'C04_CHAPTER_PLANNING', false],
  ] as const)('routes %s with recovery %s to the correct user action', async (status, resumeState, needsReview) => {
    const { wrapper, s } = await workspace()
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: resumeState, revision_request_id: 'request' })
    s.tasks = [{ ...s.tasks[0]!, workflow_instance_id: s.workflow.id, workflow_state: 'C10_REVISION', workflow_state_version: s.workflow.state_version - 1, agent_id: 'A06_REVISION', task_type: 'REVISE_CHAPTER', status }]
    s.revisions = [{ request: { id: 'request' }, plan: null, result: null } as Revision]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重新审阅正文'))).toBe(needsReview)
    expect(wrapper.findAll('button').some(b => b.text().startsWith('重试本阶段'))).toBe(status === 'FAILED' || resumeState !== 'C10_REVISION')
    const rereview = vi.spyOn(api, 'rereview').mockResolvedValue({ workflow: s.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    expect(rereview).not.toHaveBeenCalled()
    if (needsReview) {
      await wrapper.findAll('button').find(b => b.text().startsWith('重新审阅正文'))!.trigger('click'); await flushPromises()
      expect(rereview).toHaveBeenCalledTimes(1)
      expect(rereview).toHaveBeenCalledWith(expect.objectContaining({ id: s.workflow.id }), 1, expect.any(String))
    }
    wrapper.unmount()
  })
})

describe('revision fidelity gate', () => {
  it('shows rejected proposal separately and keeps original Draft without auto retry', async () => {
    const { wrapper, s } = await workspace()
    const revise = vi.spyOn(api, 'revise')
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: 'C10_REVISION', revision_request_id: 'req-fidelity' })
    s.revisions = [{ request: { id: 'req-fidelity' }, plan: null, candidate: { body: { content: '不被采用的另一个场景', blocked_reasons: [] } }, result: { chapter_version_id: null, body: { blocked_reasons: [], fidelity: { verdict: 'FAIL', violations: [{ code: 'UNAUTHORIZED_SCENE_REPLACEMENT' }] } } } } as unknown as Revision]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('这次修改范围过大，未替换当前正文。')
    expect(wrapper.text()).toContain('查看未采用的修改稿')
    expect(wrapper.findComponent({ name: 'DraftView' }).props('draft').version).toBe(1)
    expect(wrapper.findComponent({ name: 'DraftView' }).props('draft').content).not.toBe('不被采用的另一个场景')
    expect(wrapper.findAll('button').some(b => b.text() === '继续执行')).toBe(false)
    expect(revise).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('keeps successful Revision UX free of fidelity jargon', async () => {
    const { wrapper, s } = await workspace('PASS_WITH_WARNINGS')
    s.revisions = [{ request: { id: 'req' }, result: { chapter_version_id: s.drafts[0]!.id, body: { declared_changes: ['压缩局部重复说明'], fidelity: { verdict: 'PASS' } } } } as unknown as Revision]
    await wrapper.findAll('button').find(b => b.text() === '刷新')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('压缩局部重复说明')
    expect(wrapper.text()).not.toContain('Source Fidelity')
    expect(wrapper.text()).not.toContain('修改范围过大')
    wrapper.unmount()
  })
  it('exposes KEEP CHANGE boundaries zones budget and rejected strengths in Debug', async () => {
    const { default: RevisionDebug } = await import('../src/components/RevisionDebug.vue')
    const record = { request: { contract: { do_not_change: { ending: '保留原结局' } } }, plan: { body: { scope: 'TARGETED', allowed_structural_change: 'LOCAL', change_budget: 'MINIMAL', preserve_scene_elements: [{ element_id: 's', description: '原场景装置' }], preserve_relationship_elements: [{ element_id: 'r', description: '同行关系' }], preserve_effective_details: [{ element_id: 'd', description: '有效动作' }], strength_preservation: [{ strength_id: 'strength:0', mode: 'FUNCTIONAL', preservation_direction: '保留真实动摇' }], revision_targets: [{ issue_id: 'issue', problem: '说明重复', revision_direction: '删减' }], revision_zones: [{ semantic_range: '中段对话' }], strength_regression_risks: [], structural_authorization: null } }, result: { body: { fidelity: { verdict: 'FAIL', checks: [], violations: [{ code: 'REVISION_STRENGTH_REGRESSION', check_ids: ['strength:0'], description: '关系吸引力丢失' }] } } } } as unknown as Revision
    const wrapper = mount(RevisionDebug, { props: { record } })
    for (const text of ['KEEP', 'CHANGE', 'DO NOT CHANGE', 'REVISION ZONES', 'CHANGE BUDGET', 'MINIMAL', 'LOCAL', '原场景装置', '同行关系', '有效动作', '保留真实动摇', '中段对话', 'REVISION_STRENGTH_REGRESSION', 'Source Fidelity: FAIL']) expect(wrapper.text()).toContain(text)
    wrapper.unmount()
  })
})

it('requires fidelity execution permission before requesting paid revision', async () => {
  const { c, client, scope } = setup()
  client.executionConfig.mockResolvedValue({ model_profile: 'mock-default', provider: 'mock', model: 'mock', task_types: ['PLAN_CHAPTER_REVISION', 'REVISE_CHAPTER', 'REVIEW_CHAPTER_COMPLIANCE', 'REVIEW_CHAPTER_NARRATIVE'], max_attempts: null } as never)
  await c.refresh()
  await c.revise()
  expect(client.revise).not.toHaveBeenCalled()
  expect(c.error.value?.code).toBe('EXECUTION_SCOPE_DISABLED')
  scope.stop()
})
