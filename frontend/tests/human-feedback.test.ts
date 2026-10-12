import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HumanFeedback from '../src/components/HumanFeedback.vue'
import WorkflowProgress from '../src/components/WorkflowProgress.vue'
import { pollDelay, progressLabel } from '../src/composables/workflowState'
import type { Feedback, Revision, Task } from '../src/types/models'
import { sample, clone } from './fixtures'

function setup() {
  const s = clone(sample.snapshot)
  Object.assign(s.workflow, { workflow_definition_version: 3, current_state: 'C11_INTERNAL_PASS', status: 'WAITING_HUMAN', human_feedback_id: null, revision_request_id: null })
  s.chapter.current_version = s.drafts[0]!.version
  s.feedback = []
  return s
}
describe('human feedback workspace', () => {
  it('opens an empty natural-language form and submits no technical controls', async () => {
    const s = setup(), wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    expect(wrapper.text()).toContain('根据我的意见修改')
    await wrapper.find('button').trigger('click')
    expect(wrapper.find('textarea').element.value).toBe('')
    await wrapper.find('textarea').setValue('中间对话自然一点，开头不要动。')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('send')).toEqual([['中间对话自然一点，开头不要动。']])
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.text()).not.toMatch(/A02|A06|ContextPackage|Scope Enum/)
  })
  it('history is readonly and cannot submit an old Draft', () => {
    const s = setup(); s.chapter.current_version = s.drafts[0]!.version + 1
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    expect(wrapper.text()).toContain('历史正文只读')
    expect(wrapper.text()).not.toContain('根据我的意见修改')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })
  it.each([
    ['REPLAN_REQUIRED', '这个要求会改变已批准的章节方案。', '修改章节方向'],
    ['PROFILE_CHANGE_REQUIRED', '这个要求属于项目写作偏好修改。', '打开写作偏好'],
    ['USER_DECISION_REQUIRED', '两项要求冲突', '补充修改要求'],
    ['NO_CHANGE', '本次未修改正文。', '根据我的意见修改'],
  ])('explains %s without auto-dispatching', (action, message, button) => {
    const s = setup(); s.feedback = [{ feedback: { id: 'f1', source_chapter_version_id: s.drafts[0]!.id, source_draft_version: 1, raw_feedback: '真实反馈' }, interpretation: { body: { action, user_message: '两项要求冲突', decision_question: '保留哪项？', conflicts: [] } } } as unknown as Feedback]
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    expect(wrapper.text()).toContain(message); expect(wrapper.text()).toContain(button)
    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.text()).toContain('真实反馈')
  })
  it('polls during interpretation, stops on failure, offers safe cancel', () => {
    const s = setup(); Object.assign(s.workflow, { current_state: 'C13_USER_FEEDBACK_DIAGNOSIS', status: 'WAITING_AGENT', human_feedback_id: 'f1' })
    expect(pollDelay(s.workflow)).toBe(1500)
    expect(progressLabel(s.workflow, [{ workflow_instance_id: s.workflow.id, workflow_state: s.workflow.current_state, workflow_state_version: s.workflow.state_version, status: 'RUNNING' } as never])).toBe('正在理解你的反馈')
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    expect(wrapper.text()).toContain('放弃本次反馈')
    expect(wrapper.findAll('button').find(button => button.text() === '根据我的意见修改')!.attributes('disabled')).toBeDefined()
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED' })
    expect(pollDelay(s.workflow)).toBeNull()
  })
  it('describes queued feedback as waiting and only calls a RUNNING attempt interpretation', async () => {
    const s = setup()
    Object.assign(s.workflow, { current_state: 'C13_USER_FEEDBACK_DIAGNOSIS', status: 'WAITING_AGENT', human_feedback_id: 'feedback' })
    const task = { ...s.tasks[0]!, task_type: 'INTERPRET_CHAPTER_FEEDBACK', workflow_instance_id: s.workflow.id, workflow_state: s.workflow.current_state, workflow_state_version: s.workflow.state_version, status: 'PENDING', attempt_count: 0 } as Task
    const old = { ...task, task_id: 'old', workflow_state_version: s.workflow.state_version - 1, status: 'RUNNING' as const }
    s.tasks = [old, task]
    const config = { model_profile: 'lingzhi-structured', provider: 'lingzhi', model: 'gpt-5.6-sol', task_types: ['INTERPRET_CHAPTER_FEEDBACK'], max_attempts: 1 }
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false, config } })
    try {
      expect(wrapper.text()).toContain('修改意见已提交，等待后台执行。')
      expect(wrapper.text()).not.toContain('正在理解你的反馈')
      await wrapper.setProps({ snapshot: { ...s, tasks: [{ ...task, status: 'CLAIMED' }] } })
      expect(wrapper.text()).toContain('后台已领取修改意见任务，正在准备执行。')
      expect(wrapper.text()).not.toContain('正在理解你的反馈')
      await wrapper.setProps({ snapshot: { ...s, tasks: [{ ...task, status: 'RUNNING' }] } })
      expect(wrapper.text()).toContain('正在理解你的反馈…')
      await wrapper.setProps({ snapshot: s, config: { ...config, task_types: ['PLAN_CHAPTER'] } })
      expect(wrapper.text()).toContain('当前阶段未在本机执行范围内')
      expect(wrapper.text()).not.toContain('正在理解你的反馈')
      await wrapper.setProps({ snapshot: { ...s, tasks: [{ ...task, status: 'RUNNING' }] } })
      expect(wrapper.text()).toContain('正在理解你的反馈…')
      await wrapper.setProps({ snapshot: { ...s, workflow: { ...s.workflow, status: 'PAUSED' } } })
      expect(wrapper.text()).toContain('修改意见处理已暂停')
      expect(wrapper.text()).not.toContain('正在理解你的反馈')
      await wrapper.setProps({ snapshot: { ...s, tasks: [old] }, config })
      expect(wrapper.text()).toContain('等待任务调度')
      expect(wrapper.text()).not.toContain('正在理解你的反馈')
      expect(wrapper.emitted('send')).toBeUndefined()
    } finally { wrapper.unmount() }
  })
  it.each(['C11_INTERNAL_PASS', 'C10_REVISION'] as const)('links a clarification answer in %s to the displayed question, but keeps new requests independent', async state => {
    const s = setup()
    s.workflow.current_state = state
    s.feedback = [{ feedback: { id: 'question-id', source_chapter_version_id: s.drafts[0]!.id, raw_feedback: '开头不动；结尾不好。' }, interpretation: { body: { action: 'USER_DECISION_REQUIRED', decision_question: '改方向还是写法？', conflicts: [] } } } as unknown as Feedback]
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    await wrapper.findAll('button').find(b => b.text() === '补充修改要求')!.trigger('click')
    expect(wrapper.find('textarea').element.value).toBe('')
    await wrapper.find('textarea').setValue('只改写法')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('send')).toEqual([['只改写法', 'question-id']])
    await wrapper.findAll('button').find(b => b.text() === '收起')!.trigger('click')
    await wrapper.findAll('button').find(b => b.text() === '根据我的意见修改')!.trigger('click')
    await wrapper.find('textarea').setValue('一个独立的新要求')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('send')?.[1]).toEqual(['一个独立的新要求'])
  })
  it('offers discard instead of a guaranteed-failing retry for stale feedback', async () => {
    const s = setup()
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', resume_state: 'C13_USER_FEEDBACK_DIAGNOSIS', status: 'BLOCKED', human_feedback_id: 'f1', block_reason: 'CONTEXT_STALE' })
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    expect(wrapper.text()).toContain('正文或写作依据已变化')
    await wrapper.findAll('button').find(b => b.text().includes('放弃本次反馈'))!.trigger('click')
    expect(wrapper.emitted('discard')).toEqual([[]])
    const progress = mount(WorkflowProgress, { props: { workflow: s.workflow, tasks: s.tasks, canResume: true } })
    expect(progress.text()).not.toContain('重试本阶段')
    expect(progress.text()).toContain('请放弃本次反馈')
  })
  it.each(['WAITING_AGENT', 'PAUSED'] as const)('allows current Draft feedback before AI Review in %s after the previous revision finished', async status => {
    const s = setup()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', status, resume_state: status === 'PAUSED' ? 'C09_INTERNAL_REVIEW' : null, revision_request_id: 'finished' })
    s.qualityReviews = []
    s.revisions = [{ request: { id: 'finished', project_id: s.chapter.project_id, chapter_id: s.chapter.id, workflow_id: s.workflow.id }, result: { chapter_version_id: s.drafts[0]!.id } } as Revision]
    s.tasks = [{ ...s.tasks[0]!, workflow_instance_id: s.workflow.id, workflow_state: s.workflow.current_state, workflow_state_version: s.workflow.state_version, status: 'PENDING' } as Task]
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    try {
      const button = wrapper.findAll('button').find(item => item.text() === '根据我的意见修改')!
      expect(button.attributes('disabled')).toBeUndefined()
      expect(wrapper.emitted('send')).toBeUndefined()
      await button.trigger('click')
      await wrapper.get('#human-feedback').setValue('  中间太赶，只修改中间。  ')
      await wrapper.get('form').trigger('submit')
      expect(wrapper.emitted('send')).toEqual([['  中间太赶，只修改中间。  ']])
    } finally { wrapper.unmount() }
  })
  it.each(['CLAIMED', 'RUNNING'] as const)('explains why feedback cannot interrupt a %s task', status => {
    const s = setup()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT' })
    s.tasks = [{ ...s.tasks[0]!, workflow_instance_id: s.workflow.id, workflow_state_version: s.workflow.state_version - 1, status } as Task]
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    try {
      expect(wrapper.findAll('button').find(item => item.text() === '根据我的意见修改')!.attributes('disabled')).toBeDefined()
      expect(wrapper.text()).toContain('后台任务已领取或正在执行')
      expect(wrapper.find('form').exists()).toBe(false)
      expect(wrapper.emitted('send')).toBeUndefined()
    } finally { wrapper.unmount() }
  })
  it('ignores another workflow running task but rejects a different record for the current Draft version', async () => {
    const s = setup()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT' })
    s.tasks = [{ ...s.tasks[0]!, workflow_instance_id: 'other-workflow', status: 'RUNNING' } as Task]
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    try {
      expect(wrapper.findAll('button').find(item => item.text() === '根据我的意见修改')!.attributes('disabled')).toBeUndefined()
      await wrapper.setProps({ draft: { ...s.drafts[0]!, id: 'different-record' } })
      expect(wrapper.text()).toContain('历史正文只读')
      expect(wrapper.find('form').exists()).toBe(false)
    } finally { wrapper.unmount() }
  })
  it.each(['missing revision', 'unfinished revision', 'other result', 'other revision workflow', 'active revision stage', 'feedback diagnosis', 'memory', 'completed', 'other paused state', 'invalid review human state', 'simulation', 'old definition'])('explains the unavailable feedback entry for %s', scenario => {
    const s = setup()
    Object.assign(s.workflow, { current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT' })
    s.revisions = []
    if (['missing revision', 'unfinished revision', 'other result', 'other revision workflow'].includes(scenario)) {
      s.workflow.revision_request_id = 'active-revision'
      if (scenario !== 'missing revision') s.revisions = [{ request: { id: 'active-revision', project_id: s.chapter.project_id, chapter_id: s.chapter.id, workflow_id: scenario === 'other revision workflow' ? 'other' : s.workflow.id }, result: scenario === 'other result' ? { chapter_version_id: 'other-draft' } : scenario === 'other revision workflow' ? { chapter_version_id: s.drafts[0]!.id } : null } as Revision]
    }
    if (scenario === 'active revision stage') s.workflow.current_state = 'C10_REVISION'
    if (scenario === 'feedback diagnosis') Object.assign(s.workflow, { current_state: 'C13_USER_FEEDBACK_DIAGNOSIS', human_feedback_id: 'feedback' })
    if (scenario === 'memory') s.workflow.memory_request_id = 'memory'
    if (scenario === 'completed') Object.assign(s.workflow, { current_state: 'C16_COMPLETED', status: 'COMPLETED' })
    if (scenario === 'other paused state') Object.assign(s.workflow, { status: 'PAUSED', resume_state: 'C10_REVISION' })
    if (scenario === 'invalid review human state') s.workflow.status = 'WAITING_HUMAN'
    if (scenario === 'simulation') s.workflow.simulation = true
    if (scenario === 'old definition') s.workflow.workflow_definition_version = 2
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    try {
      expect(wrapper.findAll('button').find(item => item.text() === '根据我的意见修改')!.attributes('disabled')).toBeDefined()
      expect(wrapper.findAll('[role="status"]').some(item => item.text().includes('不能提交'))).toBe(true)
      expect(wrapper.find('form').exists()).toBe(false)
    } finally { wrapper.unmount() }
  })
  it('preserves an open form while synchronizing but refuses submission', async () => {
    const s = setup(), wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    try {
      await wrapper.findAll('button').find(item => item.text() === '根据我的意见修改')!.trigger('click')
      await wrapper.get('#human-feedback').setValue('只改最后一句。')
      await wrapper.setProps({ disabled: true })
      await wrapper.get('form').trigger('submit')
      expect(wrapper.emitted('send')).toBeUndefined()
      expect(wrapper.text()).toContain('正在同步正文状态')
      await wrapper.setProps({ disabled: false })
      expect(wrapper.get('#human-feedback').element).toHaveProperty('value', '只改最后一句。')
      await wrapper.get('form').trigger('submit')
      expect(wrapper.emitted('send')).toEqual([['只改最后一句。']])
    } finally { wrapper.unmount() }
  })
})
