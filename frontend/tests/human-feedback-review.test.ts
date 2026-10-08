import { effectScope } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/api/console'
import { ApiError } from '../src/api/client'
import HumanFeedback from '../src/components/HumanFeedback.vue'
import ConsoleView from '../src/views/ConsoleView.vue'
import { useConsole } from '../src/composables/useConsole'
import type { Dispatch, Feedback } from '../src/types/models'
import { clone, sample } from './fixtures'

function setup() {
  const s = clone(sample.snapshot)
  Object.assign(s.workflow, { workflow_definition_version: 3, current_state: 'C11_INTERNAL_PASS', status: 'WAITING_HUMAN', revision_request_id: null, human_feedback_id: null, draft_version: 1 })
  s.chapter.current_version = 1
  s.drafts = [{ ...s.drafts[0]!, version: 1 }]
  s.feedback = []; s.revisions = []; s.qualityReviews = []
  const client = { ...api,
    workflow: vi.fn(async () => clone(s.workflow)), chapter: vi.fn(async () => clone(s.chapter)),
    executionConfig: vi.fn(async () => ({ model_profile: 'mock-default', provider: 'mock', model: 'mock', task_types: null, max_attempts: null })),
    gates: vi.fn(async () => clone(s.gates)), brief: vi.fn(async () => clone(s.brief)), plans: vi.fn(async () => clone(s.plans)),
    history: vi.fn(async () => clone(s.history)), drafts: vi.fn(async () => clone(s.drafts)), writing: vi.fn(async () => clone(s.writing)), tasks: vi.fn(async () => clone(s.tasks)),
    qualityReviews: vi.fn(async () => []), revisions: vi.fn(async () => []), feedback: vi.fn(async () => clone(s.feedback!)),
    sendFeedback: vi.fn(api.sendFeedback), workflows: vi.fn(async () => []),
  }
  const scope = effectScope(), c = scope.run(() => useConsole(client))!
  c.projectId.value = s.chapter.project_id; c.chapterId.value = s.chapter.id; c.workflowId.value = s.workflow.id
  return { s, client, scope, c }
}
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear() })

describe('independent human feedback review', () => {
  it('sends the parent question id and returns to current Draft after discard', async () => {
    const { s, client, scope, c } = setup()
    try {
      await c.refresh()
      client.sendFeedback.mockResolvedValueOnce({ workflow: s.workflow } as Dispatch)
      await c.sendFeedback('只改写法', 'question-id')
      expect(client.sendFeedback.mock.calls[0]![4]).toBe('question-id')
      Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: 'C13_USER_FEEDBACK_DIAGNOSIS', human_feedback_id: 'active-feedback' })
      s.chapter.current_version = 2
      s.drafts.push({ ...s.drafts[0]!, id: 'new-draft', version: 2 })
      await c.refresh(); c.selectedDraft.value = 1
      const discard = vi.spyOn(client, 'discardFeedback').mockImplementation(async () => {
        Object.assign(s.workflow, { current_state: 'C11_INTERNAL_PASS', status: 'WAITING_HUMAN', resume_state: null, human_feedback_id: null, draft_version: 2 })
        return { workflow: s.workflow } as Dispatch
      })
      await c.discardFeedback()
      expect(discard.mock.calls[0]![1]).toBe('active-feedback')
      expect(c.draft.value?.id).toBe('new-draft')
      expect(c.workflow.value?.status).toBe('WAITING_HUMAN')
      expect(c.error.value).toBeNull()
    } finally { scope.stop() }
  })
  it('rejects historical feedback before dispatch', async () => {
    const { s, client, scope, c } = setup()
    try {
      s.chapter.current_version = 2
      s.drafts.push({ ...s.drafts[0]!, id: 'd2', version: 2 })
      await c.refresh(); c.selectedDraft.value = 1
      await c.sendFeedback('只改对话')
      expect(c.error.value?.code).toBe('STALE_VIEW')
      expect(client.sendFeedback).not.toHaveBeenCalled()
      const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
      expect(wrapper.find('form').exists()).toBe(false)
      expect(wrapper.text()).toContain('历史正文只读')
      wrapper.unmount()
    } finally { scope.stop() }
  })

  it('shares one event id for duplicate clicks and uncertain delivery', async () => {
    const { client, scope, c } = setup()
    try {
      await c.refresh()
      let reject!: (reason: unknown) => void
      client.sendFeedback.mockImplementationOnce(() => new Promise<Dispatch>((_, r) => { reject = r }))
      const pending = c.sendFeedback('只改对话')
      await flushPromises(); await c.sendFeedback('只改对话')
      expect(client.sendFeedback).toHaveBeenCalledTimes(1)
      const event = client.sendFeedback.mock.calls[0]![3]
      reject(new ApiError('NETWORK_ERROR', 'uncertain')); await pending
      client.sendFeedback.mockRejectedValueOnce(new ApiError('NETWORK_ERROR', 'uncertain again'))
      await c.sendFeedback('只改对话')
      expect(client.sendFeedback.mock.calls[1]![3]).toBe(event)
    } finally { scope.stop() }
  })

  it('does not publish a late feedback error into another chapter', async () => {
    const { client, scope, c } = setup()
    try {
      await c.refresh()
      let reject!: (reason: unknown) => void
      client.sendFeedback.mockImplementationOnce(() => new Promise<Dispatch>((_, r) => { reject = r }))
      const pending = c.sendFeedback('只改对话')
      await flushPromises(); await c.selectChapter('another-chapter')
      reject(new ApiError('VERSION_CONFLICT', 'old chapter')); await pending
      expect(c.chapterId.value).toBe('another-chapter')
      expect(c.error.value).toBeNull()
      expect(c.conflict.value).toBe(false)
    } finally { scope.stop() }
  })

  it('keeps a user-authored current Draft visible after feedback interpretation is blocked', async () => {
    const { s, scope, c } = setup()
    try {
      s.writing = []
      Object.assign(s.workflow, { current_state: 'C13_USER_FEEDBACK_DIAGNOSIS', status: 'WAITING_AGENT', human_feedback_id: 'feedback' })
      await c.refresh()
      expect(c.draft.value?.id).toBe(s.drafts[0]!.id)
      Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: 'C13_USER_FEEDBACK_DIAGNOSIS', state_version: s.workflow.state_version + 1 })
      await c.refresh()
      expect(c.draft.value?.id).toBe(s.drafts[0]!.id)
    } finally { scope.stop() }
  })

  it('offers an explicit retry when a low-confidence attempt saved no interpretation', async () => {
    const { s, scope, client } = setup()
    let wrapper: ReturnType<typeof mount> | undefined
    try {
      Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED', resume_state: 'C13_USER_FEEDBACK_DIAGNOSIS', human_feedback_id: 'feedback' })
      s.feedback = [{ feedback: { id: 'feedback', source_chapter_version_id: s.drafts[0]!.id }, interpretation: null } as unknown as Feedback]
      for (const method of ['workflow', 'chapter', 'executionConfig', 'gates', 'brief', 'plans', 'history', 'drafts', 'writing', 'tasks', 'qualityReviews', 'revisions', 'feedback'] as const) vi.spyOn(api, method).mockImplementation(client[method] as never)
      vi.spyOn(api, 'projects').mockResolvedValue([{ id: s.chapter.project_id, name: '离线测试' } as never])
      vi.spyOn(api, 'chapters').mockResolvedValue([s.chapter])
      vi.spyOn(api, 'workflows').mockResolvedValue([s.workflow])
      localStorage.setItem(`novel-os.last-chapter.${s.chapter.project_id}`, s.chapter.id)
      wrapper = mount(ConsoleView)
      await flushPromises()
      expect(wrapper.text()).toContain('暂时无法理解这条修改要求')
      const retry = wrapper.findAll('button').find(button => button.text().includes('重试本阶段'))
      expect(retry?.exists()).toBe(true)
      expect(retry?.attributes('disabled')).toBeUndefined()
    } finally { wrapper?.unmount(); scope.stop() }
  })
})
