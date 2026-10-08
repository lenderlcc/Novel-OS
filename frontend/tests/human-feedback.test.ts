import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HumanFeedback from '../src/components/HumanFeedback.vue'
import WorkflowProgress from '../src/components/WorkflowProgress.vue'
import { pollDelay, progressLabel } from '../src/composables/workflowState'
import type { Feedback } from '../src/types/models'
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
    expect(wrapper.text()).toContain('我想修改')
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
    expect(wrapper.text()).not.toContain('我想修改')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })
  it.each([
    ['REPLAN_REQUIRED', '这个要求会改变已批准的章节方案。', '修改章节方向'],
    ['PROFILE_CHANGE_REQUIRED', '这个要求属于项目写作偏好修改。', '打开写作偏好'],
    ['USER_DECISION_REQUIRED', '两项要求冲突', '补充修改要求'],
    ['NO_CHANGE', '本次未修改正文。', '我想修改'],
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
    expect(wrapper.text()).toContain('放弃本次反馈'); expect(wrapper.text()).not.toContain('我想修改')
    Object.assign(s.workflow, { current_state: 'C90_BLOCKED', status: 'BLOCKED' })
    expect(pollDelay(s.workflow)).toBeNull()
  })
  it('links a clarification answer to the displayed question, but keeps new requests independent', async () => {
    const s = setup()
    s.feedback = [{ feedback: { id: 'question-id', source_chapter_version_id: s.drafts[0]!.id, raw_feedback: '开头不动；结尾不好。' }, interpretation: { body: { action: 'USER_DECISION_REQUIRED', decision_question: '改方向还是写法？', conflicts: [] } } } as unknown as Feedback]
    const wrapper = mount(HumanFeedback, { props: { snapshot: s, draft: s.drafts[0]!, disabled: false } })
    await wrapper.findAll('button').find(b => b.text() === '补充修改要求')!.trigger('click')
    expect(wrapper.find('textarea').element.value).toBe('')
    await wrapper.find('textarea').setValue('只改写法')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('send')).toEqual([['只改写法', 'question-id']])
    await wrapper.findAll('button').find(b => b.text() === '收起')!.trigger('click')
    await wrapper.findAll('button').find(b => b.text() === '我想修改')!.trigger('click')
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
})
