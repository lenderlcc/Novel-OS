import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { api } from '../src/api/console'
import { ApiError } from '../src/api/client'
import { useConsole } from '../src/composables/useConsole'
import ConsoleView from '../src/views/ConsoleView.vue'
import { clone, sample, waitingSnapshot } from './fixtures'
import type { Chapter, Dispatch, ExecutionConfig, Workflow, MemoryHistory } from '../src/types/models'

const fullExecution: ExecutionConfig = {
  model_profile: 'lingzhi-structured', provider: 'lingzhi', model: 'gpt-5.6-sol',
  task_types: ['PARSE_CHAPTER_REQUIREMENT', 'PLAN_CHAPTER', 'REVIEW_CHAPTER_PLAN', 'WRITE_CHAPTER'],
  max_attempts: 1,
}

function setup(initial = waitingSnapshot()) {
  const data = clone(initial)
  const client = {
    ...api, workflow: vi.fn(async () => data.workflow), chapter: vi.fn(async () => data.chapter),
    executionConfig: vi.fn(async () => fullExecution),
    gates: vi.fn(async () => data.gates), brief: vi.fn(async () => data.brief), plans: vi.fn(async () => data.plans),
    history: vi.fn(async () => data.history), drafts: vi.fn(async () => data.drafts), writing: vi.fn(async () => data.writing), tasks: vi.fn(async () => data.tasks),
    feedback: vi.fn(async () => []), memory: vi.fn(async () => data.memory ?? []),
    confirmMemory: vi.fn(api.confirmMemory),
    qualityReviews: vi.fn(async () => data.qualityReviews ?? []), revisions: vi.fn(async () => data.revisions ?? []), control: vi.fn(api.control),
    chapters: vi.fn<(id: string, signal?: AbortSignal) => Promise<Chapter[]>>(async () => [data.chapter]),
    decide: vi.fn(api.decide), start: vi.fn(api.start), submit: vi.fn(api.submit),
  }
  const scope = effectScope(), console = scope.run(() => useConsole(client))!
  console.projectId.value = data.chapter.project_id; console.chapterId.value = data.chapter.id; console.workflowId.value = data.workflow.id
  return { data, client, scope, console }
}
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })
describe('console state concurrency and polling', () => {
  it.each(['C09_INTERNAL_REVIEW', 'C10_REVISION', 'C11_INTERNAL_PASS'] as const)('shows the explicitly rebound user Draft in %s without inventing Writing lineage', async (state) => {
    const s = waitingSnapshot()
    s.workflow.workflow_definition_version = 3
    s.workflow.current_state = state; s.workflow.draft_version = 2
    s.workflow.status = state === 'C09_INTERNAL_REVIEW' ? 'WAITING_AGENT' : 'WAITING_HUMAN'
    s.chapter.current_version = 2
    s.drafts = [{ ...sample.snapshot.drafts[0]!, id: 'user-draft-v2', version: 2, content: '人工修改的正文' }]
    s.writing = []
    const { console: c, scope } = setup(s)
    await c.refresh()
    expect(c.selectedDraft.value).toBe(2)
    expect(c.draft.value?.id).toBe('user-draft-v2')
    expect(c.writing.value).toBeNull()
    scope.stop()
  })
  it('resumes Review with the loaded current Draft token only after a user action', async () => {
    const s = waitingSnapshot()
    s.workflow.workflow_definition_version = 3
    s.workflow.current_state = 'C90_BLOCKED'; s.workflow.status = 'BLOCKED'
    s.workflow.resume_state = 'C09_INTERNAL_REVIEW'; s.workflow.draft_version = 1
    s.chapter.current_version = 2
    const { console: c, client, scope, data } = setup(s)
    client.control.mockResolvedValue({ workflow: data.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await c.refresh()
    expect(client.control).not.toHaveBeenCalled()
    await c.control('resume', '人工重试审阅')
    expect(client.control).toHaveBeenCalledWith(expect.objectContaining({ draft_version: 1 }), 'resume', '人工重试审阅', 2)
    scope.stop()
  })
  it('does not silently refresh and retry when another Draft replaces the viewed version', async () => {
    const s = waitingSnapshot()
    s.workflow.workflow_definition_version = 3
    s.workflow.current_state = 'C90_BLOCKED'; s.workflow.status = 'BLOCKED'
    s.workflow.resume_state = 'C09_INTERNAL_REVIEW'; s.chapter.current_version = 2
    const { console: c, client, scope } = setup(s)
    await c.refresh()
    client.control.mockRejectedValue(new ApiError('VERSION_CONFLICT', 'reload', 'request-id', 409))
    await c.control('resume', '人工重试审阅')
    expect(client.control).toHaveBeenCalledTimes(1)
    expect(c.error.value?.code).toBe('VERSION_CONFLICT')
    expect(c.conflict.value).toBe(true)
    scope.stop()
  })
  it('reloads execution policy on manual refresh without adding it to polling', async () => {
    const { console: c, client, scope } = setup()
    const planningOnly = { ...fullExecution, task_types: fullExecution.task_types!.slice(0, 3) }
    client.executionConfig.mockResolvedValueOnce(planningOnly)
    await c.refresh()
    expect(c.executionConfig.value?.task_types).not.toContain('WRITE_CHAPTER')
    client.executionConfig.mockClear()
    await c.refresh(false)
    expect(client.executionConfig).not.toHaveBeenCalled()
    client.executionConfig.mockResolvedValueOnce(fullExecution)
    await c.refresh()
    expect(c.executionConfig.value?.task_types).toContain('WRITE_CHAPTER')
    scope.stop()
  })
  it('a late create response after unmount cannot submit the workflow or restart polling', async () => {
    vi.useFakeTimers()
    const { console: c, client, scope, data } = setup()
    let complete!: (d: Dispatch) => void
    client.start.mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    const pending = c.start('raw requirement')
    scope.stop()
    complete({ workflow: data.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await pending
    expect(client.submit).not.toHaveBeenCalled()
    expect(c.snapshot.value).toBeNull()
    await vi.advanceTimersByTimeAsync(10000)
    expect(client.workflow).not.toHaveBeenCalled()
  })
  it('publishes the durable C00 workflow when initial submission fails and retries without creating a duplicate', async () => {
    const s = waitingSnapshot()
    s.workflow.current_state = 'C00_CREATED'; s.workflow.state_version = 0; s.workflow.status = 'RUNNING'
    s.brief = null; s.plans = []; s.history = { briefs: [], plans: [], reviews: [] }; s.gates = []; s.tasks = []
    const { console: c, client, scope, data } = setup(s)
    client.start.mockResolvedValue({ workflow: data.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    client.submit.mockRejectedValueOnce(new ApiError('UPSTREAM_TIMEOUT', 'uncertain submission'))
    await c.start('raw requirement')
    expect(client.start).toHaveBeenCalledTimes(1)
    expect(c.workflow.value?.current_state).toBe('C00_CREATED')
    expect(c.error.value?.code).toBe('UPSTREAM_TIMEOUT')

    client.submit.mockResolvedValueOnce({ workflow: data.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await c.submit()
    expect(client.start).toHaveBeenCalledTimes(1)
    expect(client.submit).toHaveBeenCalledTimes(2)
    scope.stop()
  })
  it('loads simulation workflow without requesting unsupported business evidence', async () => {
    const s = waitingSnapshot(); s.workflow.simulation = true
    const { console: c, client, scope } = setup(s)
    client.brief.mockRejectedValue(new ApiError('INVALID_STATE', 'Business workflow only'))
    client.history.mockRejectedValue(new ApiError('INVALID_STATE', 'Business workflow only'))
    await c.refresh()
    expect(client.brief).not.toHaveBeenCalled(); expect(client.history).not.toHaveBeenCalled()
    expect(c.workflow.value?.id).toBe(s.workflow.id); expect(c.error.value).toBeNull()
    expect(c.formal.value).toBe(false); expect(c.gate.value).toBeNull()
    scope.stop()
  })
  it('stops at human gate; submission conflict does not retry or silently refresh', async () => {
    vi.useFakeTimers()
    const { console: c, client, scope } = setup()
    await c.refresh(); expect(c.gate.value).not.toBeNull()
    client.workflow.mockClear()
    await vi.advanceTimersByTimeAsync(10000); expect(client.workflow).not.toHaveBeenCalled()
    client.decide.mockRejectedValue(new ApiError('VERSION_CONFLICT', 'stale', 'req', 409))
    await c.decide('APPROVE', '')
    expect(client.decide).toHaveBeenCalledTimes(1); expect(client.workflow).not.toHaveBeenCalled()
    expect(c.conflict.value).toBe(true); expect(c.gate.value).toBeNull()
    await vi.advanceTimersByTimeAsync(20000); expect(client.decide).toHaveBeenCalledTimes(1)
    await c.refresh(); expect(c.conflict.value).toBe(false)
    scope.stop()
  })
  it('rechecks execution policy and refuses approval before creating a stranded Writing task', async () => {
    const { console: c, client, scope } = setup()
    await c.refresh()
    const planningOnly = { ...fullExecution, task_types: fullExecution.task_types!.slice(0, 3) }
    client.executionConfig.mockResolvedValueOnce(planningOnly)
    await c.decide('APPROVE', '')
    expect(client.decide).not.toHaveBeenCalled()
    expect(c.error.value?.code).toBe('EXECUTION_SCOPE_DISABLED')
    expect(c.executionConfig.value?.task_types).not.toContain('WRITE_CHAPTER')
    expect(c.workflow.value?.current_state).toBe('C06_PLAN_APPROVAL')
    scope.stop()
  })
  it('uses a neutral replanning request for an alternative with empty optional feedback', async () => {
    const { console: c, client, scope, data } = setup()
    await c.refresh()
    client.decide.mockResolvedValueOnce({ workflow: data.workflow, outcome: 'APPLIED', duplicate: false, error_code: null })
    await c.decide('REQUEST_ALTERNATIVE', '')
    expect(client.decide.mock.calls[0]?.[3]).toBe('人工请求一个不同方向的替代方案')
    scope.stop()
  })
  it('does not approve after unmount while the execution-policy preflight is pending', async () => {
    const { console: c, client, scope } = setup()
    await c.refresh()
    let complete!: (config: ExecutionConfig) => void
    client.executionConfig.mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    const pending = c.decide('APPROVE', '')
    scope.stop()
    complete(fullExecution)
    await pending
    expect(client.decide).not.toHaveBeenCalled()
  })
  it('polls active workflow, stops on scope disposal and never overlaps slow reads', async () => {
    vi.useFakeTimers()
    const s = waitingSnapshot(); s.workflow.current_state = 'C07_WRITING'; s.workflow.status = 'WAITING_AGENT'
    const { console: c, client, scope, data } = setup(s)
    await c.refresh(); client.workflow.mockClear()
    let complete!: (w: Workflow) => void
    client.workflow.mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    await vi.advanceTimersByTimeAsync(1500)
    expect(client.workflow).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(10000); expect(client.workflow).toHaveBeenCalledTimes(1)
    complete(data.workflow); await flushPromises()
    scope.stop(); client.workflow.mockClear()
    await vi.advanceTimersByTimeAsync(10000); expect(client.workflow).not.toHaveBeenCalled()
  })
  it('discards an old project response even if transport ignores abort', async () => {
    const { console: c, client, scope, data } = setup()
    let old!: (chapters: Chapter[]) => void
    client.chapters.mockImplementationOnce(() => new Promise(resolve => { old = resolve }))
    const slow = c.selectProject('old-project')
    await c.selectProject('new-project')
    old([{ ...data.chapter, id: 'stale-chapter' }]); await slow
    expect(c.projectId.value).toBe('new-project')
    expect(c.chapters.value[0]!.id).toBe(data.chapter.id)
    scope.stop()
  })
  it('drops an in-flight workflow snapshot when switching chapter', async () => {
    const { console: c, client, scope } = setup()
    let old!: (w: Workflow) => void
    client.workflow.mockImplementationOnce(() => new Promise(resolve => { old = resolve }))
    const pending = c.refresh()
    await c.selectChapter('')
    old(sample.snapshot.workflow); await pending
    expect(c.snapshot.value).toBeNull(); expect(c.workflowId.value).toBe('')
    scope.stop()
  })
  it('never substitutes current chapter draft for this workflow draft or its approved version', async () => {
    const s = clone(sample.snapshot)
    s.chapter.current_version = 2; s.chapter.approved_version = 1
    s.drafts.push({ ...s.drafts[0]!, id: 'another-draft', version: 2, content: 'other draft' })
    const { console: c, scope } = setup(s)
    await c.refresh()
    expect(c.draft.value?.version).toBe(1)
    expect(c.snapshot.value?.chapter.current_version).toBe(2)
    expect(c.snapshot.value?.chapter.approved_version).toBe(1)
    c.selectedDraft.value = 2; expect(c.writing.value).toBeNull()
    scope.stop()
  })
  it('new workflow seeded with an old draft pointer does not present it as a new writing result', async () => {
    const s = waitingSnapshot()
    s.workflow.draft_version = 1; s.chapter.current_version = 1
    s.drafts = sample.snapshot.drafts; s.writing = []
    const { console: c, scope } = setup(s)
    await c.refresh()
    expect(c.selectedDraft.value).toBeNull(); expect(c.draft.value).toBeNull()
    c.selectedDraft.value = 1
    expect(c.draft.value?.content).toBe(sample.snapshot.drafts[0]!.content)
    expect(c.writing.value).toBeNull()
    scope.stop()
  })
})

describe('writing workspace execution status', () => {
  it('shows queued, retrying, claimed and paused tasks without a Writing spinner', async () => {
    const s = waitingSnapshot()
    s.workflow.current_state = 'C07_WRITING'; s.workflow.status = 'WAITING_AGENT'
    const task = { ...sample.snapshot.tasks[0]!, task_type: 'WRITE_CHAPTER', workflow_instance_id: s.workflow.id, workflow_state: s.workflow.current_state, workflow_state_version: s.workflow.state_version, status: 'PENDING' as const, attempt_count: 0 }
    const old = { ...task, task_id: 'old', workflow_state_version: s.workflow.state_version - 1, status: 'RUNNING' as const }
    s.tasks = [old, task]
    const { data, client, scope } = setup(s)
    scope.stop()
    for (const method of ['workflow', 'chapter', 'executionConfig', 'gates', 'brief', 'plans', 'history', 'drafts', 'writing', 'tasks', 'qualityReviews', 'revisions', 'feedback'] as const) vi.spyOn(api, method).mockImplementation(client[method] as never)
    vi.spyOn(api, 'workflow').mockImplementation(async () => clone(data.workflow))
    vi.spyOn(api, 'projects').mockResolvedValue([{ id: s.chapter.project_id, name: 'Writing status regression' } as never])
    vi.spyOn(api, 'chapters').mockResolvedValue([data.chapter])
    vi.spyOn(api, 'workflows').mockResolvedValue([data.workflow])
    localStorage.setItem('novel-os.last-project', s.chapter.project_id)
    localStorage.setItem(`novel-os.last-chapter.${s.chapter.project_id}`, s.chapter.id)
    const wrapper = mount(ConsoleView)
    const refresh = async () => {
      await wrapper.findAll('button').find(button => button.text() === '刷新')!.trigger('click')
      await flushPromises()
    }
    const heading = () => wrapper.get('.writing-workspace h2').text()
    try {
      await flushPromises()
      expect(heading()).toBe('等待后台执行')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('AI 正在写作')
      data.tasks = [{ ...task, attempt_count: 1 }]
      await refresh()
      expect(heading()).toBe('等待后台重试')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      data.tasks = [{ ...task, status: 'CLAIMED' }]
      await refresh()
      expect(heading()).toBe('任务已领取，准备执行')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      data.tasks = [{ ...task, status: 'RUNNING' }]
      await refresh()
      expect(heading()).toBe('AI 正在写作…')
      expect(wrapper.find('.writing-indicator').exists()).toBe(true)
      client.executionConfig.mockResolvedValue({ ...fullExecution, task_types: ['PLAN_CHAPTER'] })
      await refresh()
      expect(heading()).toBe('AI 正在写作…')
      expect(wrapper.find('.writing-indicator').exists()).toBe(true)
      data.workflow.status = 'RUNNING'
      await refresh()
      expect(heading()).toBe('正文任务未在执行')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      data.workflow.status = 'PAUSED'
      await refresh()
      expect(heading()).toBe('流程已暂停')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('AI 正在写作')
      data.workflow.status = 'WAITING_AGENT'
      data.tasks = [task]
      client.executionConfig.mockResolvedValue({ ...fullExecution, task_types: ['PLAN_CHAPTER'] })
      await refresh()
      expect(heading()).toBe('本阶段执行已停用')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
      data.tasks = [old]
      client.executionConfig.mockResolvedValue(fullExecution)
      await refresh()
      expect(heading()).toBe('等待任务调度')
      expect(wrapper.find('.writing-indicator').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('AI 正在写作')
      expect(client.control).not.toHaveBeenCalled()
    } finally { wrapper.unmount(); localStorage.clear() }
  })
})


describe('memory confirmation command fencing', () => {
  function pending() {
    const s = clone(sample.snapshot)
    s.workflow.workflow_definition_version = 3
    s.workflow.current_state = 'C15_MEMORY_COMMIT'; s.workflow.status = 'WAITING_HUMAN'
    s.workflow.memory_request_id = 'memory-request'
    s.workflow.draft_version = s.drafts[0]!.version
    s.memory = [{ request: { id: 'memory-request', chapter_version_id: s.drafts[0]!.id }, proposal: { id: 'proposal', candidates: [] }, status: 'PROPOSED' } as unknown as MemoryHistory]
    return s
  }
  it('preserves proposal and reports commit failure without showing completed', async () => {
    const { console: c, client, scope } = setup(pending())
    await c.refresh()
    client.confirmMemory.mockRejectedValue(new ApiError('INTERNAL_ERROR', 'storage error', 'rid', 500))
    await c.confirmMemory([])
    expect(client.confirmMemory).toHaveBeenCalledTimes(1)
    expect(c.error.value?.message).toContain('本章记忆保存失败，章节尚未完成')
    expect(c.workflow.value?.status).toBe('WAITING_HUMAN')
    expect(c.snapshot.value?.memory?.[0]?.proposal?.id).toBe('proposal')
    scope.stop()
  })
  it('rejects confirmation when the visible source differs from the proposal', async () => {
    const s = pending()
    s.memory![0]!.request.chapter_version_id = 'another-draft'
    const { console: c, client, scope } = setup(s)
    await c.refresh()
    await c.confirmMemory([])
    expect(client.confirmMemory).not.toHaveBeenCalled()
    expect(c.error.value?.code).toBe('STALE_VIEW')
    scope.stop()
  })
})
