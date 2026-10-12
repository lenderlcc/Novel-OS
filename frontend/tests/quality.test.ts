import { flushPromises, mount } from '@vue/test-utils'
import QualityComparison from '../src/components/QualityComparison.vue'
import { describe, expect, it } from 'vitest'
import QualityReviewView from '../src/components/QualityReview.vue'
import WorkflowProgress from '../src/components/WorkflowProgress.vue'
import { currentTask, isReviewResume, pollDelay } from '../src/composables/workflowState'
import type { QualityReview, Workflow } from '../src/types/models'
import { sample } from './fixtures'

const issue = { code: 'LOW_IMMERSION', severity: 'P2', category: 'NARRATIVE', title: '场景的感受不足', description: '选择主要通过总结说明。', impact: '读者难以感受到决定的分量。', revision_direction: '保留主线，用人物行动呈现代价。', confidence: 0.72, requires_revision: false, source_refs: [], evidence: [{ paragraph_index: 3, excerpt: '他把信放在桌角。', reason: '这里直接跳到了结论。' }] }
const record = { id: 'review', version: 1, binding: { draft_version: 1 }, freshness: 'CURRENT', body: { overall_verdict: 'PASS_WITH_WARNINGS', compliance_verdict: 'PASS', narrative_verdict: 'PASS_WITH_WARNINGS', audience_fit_verdict: 'PASS', hard_gate_issues: [], quality_issues: [issue], strengths: [{ description: '保留了关键选择。', preservation_direction: '继续保留角色作决定的主动性。', evidence: [] }] } } as unknown as QualityReview

describe('chapter quality review', () => {
  it('names the exact current Draft on explicit review recovery', async () => {
    const workflow = { ...sample.snapshot.workflow, workflow_definition_version: 3, current_state: 'C90_BLOCKED', resume_state: 'C09_INTERNAL_REVIEW', status: 'BLOCKED' } as Workflow
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [], currentDraftVersion: 2, canResume: true } })
    expect(wrapper.get('button').text()).toContain('重新审阅正文 v2')
    expect(wrapper.emitted('resume')).toBeUndefined()
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('resume')).toHaveLength(1)
    expect(isReviewResume({ ...workflow, workflow_definition_version: 2 }, [])).toBe(false)
    expect(isReviewResume({ ...workflow, resume_state: 'C08_DETERMINISTIC_CHECK' }, [])).toBe(false)
  })
  it('presents Chinese findings and strengths without technical scores or codes', () => {
    const wrapper = mount(QualityReviewView, { props: { review: record } })
    expect(wrapper.text()).toContain('有改进空间')
    expect(wrapper.text()).toContain('场景的感受不足')
    expect(wrapper.text()).toContain('保留了关键选择')
    for (const word of ['LOW_IMMERSION', 'P2', '0.72', 'paragraph_index', '评分']) expect(wrapper.text()).not.toContain(word)
    expect(wrapper.find('details summary').text()).toBe(issue.title)
    expect(wrapper.find('blockquote').text()).toContain('他把信放在桌角。')
    expect(wrapper.text()).toContain('保留主线，用人物行动呈现代价')
  })
  it('old chapters without a review still render', () => {
    expect(mount(QualityReviewView, { props: { review: null } }).text()).toContain('尚无 AI 审阅')
  })
  it('explains audience mismatch using approved preferences without exposing internal codes', () => {
    const current = { ...record, body: { ...record.body, reviewer_version: 'A05-quality.v2', audience_fit_verdict: 'PASS_WITH_WARNINGS', audience_evidence: [{ profile_field: 'naturalness', profile_ref: { source_type: 'PROJECT_WRITING_PROFILE', source_id: 'profile', source_version: 2, field: 'naturalness' }, expected: 'HIGH', observed: '人物连续以完整问答推进，交流显得程序化。', reason: '削弱了要求的自然交流感。' }, { profile_field: 'reading_experience', profile_ref: { source_type: 'PROJECT_WRITING_PROFILE', source_id: 'profile', source_version: 2, field: 'reading_experience' }, expected: ['自然交流', '低阅读阻力'], observed: '重复归纳增加阅读阻力。', reason: '与用户要求的阅读体验存在冲突。' }] } } as QualityReview
    const wrapper = mount(QualityReviewView, { props: { review: current } })
    expect(wrapper.text()).toContain('自然感（已批准 v2）：高')
    expect(wrapper.text()).toContain('自然交流；低阅读阻力')
    expect(wrapper.text()).toContain('人物连续以完整问答推进，交流显得程序化。')
    for (const internal of ['AUDIENCE_STYLE_MISMATCH', 'PROJECT_WRITING_PROFILE', 'naturalness', 'HIGH']) expect(wrapper.text()).not.toContain(internal)
  })
  it('retains legacy report display without fabricating audience evidence', () => {
    const wrapper = mount(QualityReviewView, { props: { review: record } })
    expect(wrapper.text()).not.toContain('与已批准写作偏好的冲突')
    expect(wrapper.text()).toContain('受众：通过')
    expect(wrapper.text()).toContain('保留了关键选择')
  })
  it('does not present a stale review as current acceptance', () => {
    expect(mount(QualityReviewView, { props: { review: { ...record, freshness: 'STALE' } } }).text()).toContain('仅供历史参考')
  })
  it('renders the fourth review step and polls only the formal review stage', () => {
    const workflow = { ...sample.snapshot.workflow, workflow_definition_version: 3, current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT' } as Workflow
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [] } })
    expect(wrapper.findAll('li')).toHaveLength(6)
    expect(wrapper.find('li[aria-current="step"]').text()).toContain('审阅')
    expect(pollDelay(workflow)).toBe(1500)
    expect(pollDelay({ ...workflow, current_state: 'C11_INTERNAL_PASS', status: 'WAITING_HUMAN' })).toBeNull()
    expect(pollDelay({ ...workflow, current_state: 'C10_REVISION', status: 'WAITING_HUMAN' })).toBeNull()
  })
  it('shows active narrative task after successful compliance in the same state', () => {
    const w = { ...sample.snapshot.workflow, workflow_definition_version: 3, current_state: 'C09_INTERNAL_REVIEW', status: 'WAITING_AGENT' } as Workflow
    const base = { ...sample.snapshot.tasks[0]!, workflow_instance_id: w.id, workflow_state: w.current_state, workflow_state_version: w.state_version }
    const first = { ...base, task_id: 'first', task_type: 'REVIEW_CHAPTER_COMPLIANCE', status: 'SUCCEEDED' as const }
    const second = { ...base, task_id: 'second', task_type: 'REVIEW_CHAPTER_NARRATIVE', status: 'PENDING' as const }
    expect(currentTask(w, [first, second])?.task_id).toBe('second')
    expect(pollDelay(w, [first, second], { model_profile: 'mock-default', provider: 'mock', model: 'mock', task_types: ['WRITE_CHAPTER'], max_attempts: null })).toBeNull()
  })
})


describe('human evaluation comparison', () => {
  const review = { ...record, project_id: 'project', chapter_id: 'chapter', binding: { workflow_id: 'workflow', draft_version: 2 } } as QualityReview
  const evaluation = { schema_version: 'ux-001.v1', project_id: 'project', chapter_id: 'chapter', workflow_id: 'workflow', draft_version: 2, failure_tags: ['人工发现的代入问题'], notes: '<b>人工独立评价</b>' }
  async function upload(wrapper: ReturnType<typeof mount>, value: unknown, size = 100) {
    const input = wrapper.find('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [{ size, text: async () => JSON.stringify(value) }], configurable: true })
    await input.trigger('change')
    await flushPromises()
  }
  it('compares matching human themes without changing AI output or rendering note HTML', async () => {
    const before = JSON.stringify(review)
    const wrapper = mount(QualityComparison, { props: { review } })
    await upload(wrapper, evaluation)
    expect(wrapper.text()).toContain('LOW_IMMERSION')
    expect(wrapper.text()).toContain('人工发现的代入问题')
    expect(wrapper.text()).toContain('<b>人工独立评价</b>')
    expect(wrapper.find('b').exists()).toBe(false)
    expect(JSON.stringify(review)).toBe(before)
  })
  it('rejects a human evaluation of a different Draft version', async () => {
    const wrapper = mount(QualityComparison, { props: { review } })
    await upload(wrapper, { ...evaluation, draft_version: 1 })
    expect(wrapper.get('[role=alert]').text()).toContain('版本不一致')
    expect(wrapper.find('dl').exists()).toBe(false)
  })
  it('rejects oversized input before reading its content', async () => {
    const wrapper = mount(QualityComparison, { props: { review } })
    await upload(wrapper, evaluation, 100001)
    expect(wrapper.get('[role=alert]').text()).toContain('文件过大')
    expect(wrapper.find('dl').exists()).toBe(false)
  })
})
