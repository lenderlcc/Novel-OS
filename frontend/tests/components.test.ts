import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import BriefView from '../src/components/BriefView.vue'
import PlanView from '../src/components/PlanView.vue'
import HumanGate from '../src/components/HumanGate.vue'
import DraftView from '../src/components/DraftView.vue'
import ErrorNotice from '../src/components/ErrorNotice.vue'
import WorkflowProgress from '../src/components/WorkflowProgress.vue'
import DebugPanel from '../src/components/DebugPanel.vue'
import ManualCaseLoader from '../src/components/ManualCaseLoader.vue'
import HumanEvaluation from '../src/components/HumanEvaluation.vue'
import WorkspaceSidebar from '../src/components/WorkspaceSidebar.vue'
import { manualCases } from '../src/data/manualCases'
import { ApiError } from '../src/api/client'
import { api } from '../src/api/console'
import { writingProfiles } from '../src/api/writingProfiles'
import { clone, sample, waitingSnapshot } from './fixtures'
import type { Project } from '../src/types/models'

afterEach(() => vi.restoreAllMocks())
describe('readable artifacts and human decisions', () => {
  it('does not report an old review schema error as the current revision business block', () => {
    const workflow = { ...sample.snapshot.workflow, current_state: 'C90_BLOCKED' as const, status: 'BLOCKED' as const, state_version: 21, block_reason: 'EXTERNAL_CONDITION', resume_state: 'C10_REVISION' as const }
    const old = { ...sample.snapshot.tasks[0]!, workflow_instance_id: workflow.id, workflow_state_version: 16, status: 'BLOCKED' as const, last_error_code: 'SCHEMA_PARSE_ERROR' }
    const current = { ...old, task_id: 'current', workflow_state_version: 20, workflow_state: 'C10_REVISION' as const, status: 'BLOCKED' as const, last_error_code: null }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [current, old] } })
    expect(wrapper.text()).toContain('当前流程未满足继续条件')
    expect(wrapper.text()).not.toContain('未通过格式校验')
    expect(wrapper.text()).not.toContain('SCHEMA_PARSE_ERROR')
    wrapper.unmount()
  })
  it('uses only the failing attempt immediately before the workflow stop', () => {
    const workflow = { ...sample.snapshot.workflow, current_state: 'C90_BLOCKED' as const, status: 'BLOCKED' as const, state_version: 21, block_reason: 'EXTERNAL_CONDITION' }
    const current = { ...sample.snapshot.tasks[0]!, workflow_instance_id: workflow.id, workflow_state_version: 20, status: 'BLOCKED' as const, last_error_code: 'MODEL_TIMEOUT' }
    const old = { ...current, task_id: 'old', workflow_state_version: 16, last_error_code: 'SCHEMA_PARSE_ERROR' }
    const unrelated = { ...current, task_id: 'other', workflow_instance_id: 'another', last_error_code: 'MODEL_AUTH_ERROR' }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [unrelated, current, old] } })
    expect(wrapper.text()).toContain('模型响应时间过长')
    expect(wrapper.text()).not.toContain('未通过格式校验')
    expect(wrapper.text()).not.toContain('模型服务配置有误')
    wrapper.unmount()
  })
  it('shows queued vs running vs paused and resumes only on an explicit click', async () => {
    const workflow = { ...sample.snapshot.workflow, current_state: 'C01_REQUIREMENT_INTAKE' as const, status: 'WAITING_AGENT' as const }
    const task = { ...sample.snapshot.tasks[0]!, workflow_instance_id: workflow.id, workflow_state: workflow.current_state, workflow_state_version: workflow.state_version, status: 'PENDING' as const, attempt_count: 0 }
    const config = { model_profile: 'lingzhi-requirement', provider: 'lingzhi', model: 'gpt-5.6-sol', task_types: ['PARSE_CHAPTER_REQUIREMENT'], max_attempts: 1 }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [task], config, canResume: true } })
    expect(wrapper.get('h2').text()).toBe('等待后台执行')
    await wrapper.setProps({ tasks: [{ ...task, status: 'RUNNING' }] })
    expect(wrapper.get('h2').text()).toBe('正在理解需求')
    await wrapper.setProps({ workflow: { ...workflow, status: 'PAUSED' } })
    expect(wrapper.get('h2').text()).toBe('流程已暂停')
    expect(wrapper.emitted('resume')).toBeUndefined()
    expect(wrapper.get('button').text()).toContain('会调用模型')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('resume')).toHaveLength(1)
    await wrapper.setProps({ canResume: false })
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('ignores historical running tasks and explains disabled Planning', () => {
    const workflow = { ...sample.snapshot.workflow, current_state: 'C04_CHAPTER_PLANNING' as const, status: 'WAITING_AGENT' as const }
    const task = { ...sample.snapshot.tasks[0]!, workflow_instance_id: workflow.id, task_type: 'PLAN_CHAPTER', workflow_state: workflow.current_state, workflow_state_version: workflow.state_version, status: 'PENDING' as const }
    const old = { ...task, task_id: 'old', workflow_state_version: workflow.state_version - 1, status: 'RUNNING' as const }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [old, task], config: { model_profile: 'lingzhi-requirement', provider: 'lingzhi', model: 'gpt-5.6-sol', task_types: ['PARSE_CHAPTER_REQUIREMENT'], max_attempts: 1 } } })
    expect(wrapper.get('h2').text()).toBe('本阶段执行已停用')
    expect(wrapper.text()).toContain('当前阶段未在本机执行范围内')
    wrapper.unmount()
  })
  it('describes Writing from its current task instead of treating the stage as execution', async () => {
    const workflow = { ...sample.snapshot.workflow, current_state: 'C07_WRITING' as const, status: 'WAITING_AGENT' as const }
    const task = { ...sample.snapshot.tasks[0]!, task_type: 'WRITE_CHAPTER', workflow_instance_id: workflow.id, workflow_state: workflow.current_state, workflow_state_version: workflow.state_version, status: 'PENDING' as const, attempt_count: 0 }
    const config = { model_profile: 'lingzhi-structured', provider: 'lingzhi', model: 'gpt-5.6-sol', task_types: ['WRITE_CHAPTER'], max_attempts: 1 }
    const old = { ...task, task_id: 'old', workflow_state_version: workflow.state_version - 1, status: 'RUNNING' as const }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [old, task], config } })
    try {
      expect(wrapper.get('h2').text()).toBe('等待后台执行')
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
      await wrapper.setProps({ tasks: [{ ...task, attempt_count: 1 }] })
      expect(wrapper.get('h2').text()).toBe('等待后台重试')
      expect(wrapper.text()).toContain('当前没有模型任务在执行')
      await wrapper.setProps({ tasks: [{ ...task, status: 'CLAIMED' }] })
      expect(wrapper.get('h2').text()).toBe('任务已领取，准备执行')
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
      await wrapper.setProps({ tasks: [{ ...task, status: 'RUNNING' }] })
      expect(wrapper.get('h2').text()).toBe('正在写作')
      expect(wrapper.text()).toContain('AI 正在生成正文')
      await wrapper.setProps({ config: { ...config, task_types: ['PLAN_CHAPTER'] } })
      expect(wrapper.get('h2').text()).toBe('正在写作')
      expect(wrapper.text()).toContain('AI 正在生成正文')
      await wrapper.setProps({ workflow: { ...workflow, status: 'RUNNING' } })
      expect(wrapper.get('h2').text()).toBe('正文任务未在执行')
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
      await wrapper.setProps({ workflow: { ...workflow, status: 'PAUSED' } })
      expect(wrapper.get('h2').text()).toBe('流程已暂停')
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
      await wrapper.setProps({ workflow, tasks: [task], config: { ...config, task_types: ['PLAN_CHAPTER'] } })
      expect(wrapper.get('h2').text()).toBe('本阶段执行已停用')
      expect(wrapper.text()).toContain('当前阶段未在本机执行范围内')
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
      await wrapper.setProps({ tasks: [old], config })
      expect(wrapper.get('h2').text()).toBe('等待任务调度')
      expect(wrapper.text()).not.toContain('AI 正在生成正文')
    } finally { wrapper.unmount() }
  })
  it('keeps C09 at Review after completed revisions instead of marking Review done', async () => {
    const workflow = { ...sample.snapshot.workflow, workflow_definition_version: 3, current_state: 'C09_INTERNAL_REVIEW' as const, status: 'WAITING_AGENT' as const, revision_count: 2, revision_request_id: null }
    const task = { ...sample.snapshot.tasks[0]!, task_type: 'REVIEW_CHAPTER_COMPLIANCE', workflow_instance_id: workflow.id, workflow_state: workflow.current_state, workflow_state_version: workflow.state_version, status: 'PENDING' as const }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [task] } })
    try {
      const stages = wrapper.findAll('.progress li')
      expect(stages[3]!.text()).toContain('审阅')
      expect(stages[3]!.attributes('aria-current')).toBe('step')
      expect(stages[3]!.classes()).not.toContain('done')
      expect(stages[4]!.classes()).not.toContain('active')
      await wrapper.setProps({ workflow: { ...workflow, revision_request_id: 'completed-revision' } })
      expect(stages[3]!.attributes('aria-current')).toBe('step')
      expect(stages[4]!.classes()).not.toContain('active')
    } finally { wrapper.unmount() }
  })
  it('shows C13 feedback diagnosis in Modification without requiring a revision pointer', () => {
    const workflow = { ...sample.snapshot.workflow, workflow_definition_version: 3, current_state: 'C13_USER_FEEDBACK_DIAGNOSIS' as const, status: 'WAITING_AGENT' as const, revision_count: 0, revision_request_id: null, human_feedback_id: 'feedback' }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [] } })
    try {
      const stages = wrapper.findAll('.progress li')
      expect(stages[4]!.text()).toContain('修改')
      expect(stages[4]!.attributes('aria-current')).toBe('step')
      expect(stages[5]!.classes()).not.toContain('active')
    } finally { wrapper.unmount() }
  })
  it.each(['C04_CHAPTER_PLANNING', 'C06_PLAN_APPROVAL', 'C07_WRITING'] as const)('does not imply a paid call when resuming excluded or human stage %s', state => {
    const workflow = { ...sample.snapshot.workflow, current_state: state, resume_state: state, status: 'PAUSED' as const }
    const config = { model_profile: 'lingzhi-requirement', provider: 'lingzhi', model: 'gpt-5.6-sol', task_types: ['PARSE_CHAPTER_REQUIREMENT'], max_attempts: 1 }
    const wrapper = mount(WorkflowProgress, { props: { workflow, tasks: [], config, canResume: true } })
    expect(wrapper.get('button').text()).toBe('继续')
    wrapper.unmount()
  })
  it('renders Brief constraints and ambiguities as text/lists, not raw JSON', () => {
    const brief = clone(sample.snapshot.brief!)
    brief.body.unresolved_ambiguities = [{ issue: '雨势的具体程度未定', impact: 'LOW', confidence: 0.6,
      can_safely_infer: true, impact_explanation: '可由写作自由决定', user_decision_needed: '无' }]
    const wrapper = mount(BriefView, { props: { brief } })
    expect(wrapper.text()).toContain(brief.body.intent_summary)
    expect(wrapper.text()).toContain(brief.body.required_outcome)
    expect(wrapper.findAll('li').length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('雨势的具体程度未定')
    expect(wrapper.text()).not.toContain('[object Object]')
    expect(wrapper.find('pre').exists()).toBe(false)
    wrapper.unmount()
  })
  it('renders every scene and review in human language without internal source references', () => {
    const wrapper = mount(PlanView, { props: { plan: sample.snapshot.plans[0]!, generation: sample.snapshot.history.plans[0]!, review: sample.snapshot.history.reviews[0]! } })
    expect(wrapper.text()).toContain('场景 1')
    expect(wrapper.text()).toContain(sample.snapshot.history.plans[0]!.body.scenes[0]!.key_change)
    expect(wrapper.text()).toContain('AI 自由发挥范围')
    expect(wrapper.get('[data-testid="plan-review"]').text()).toContain('通过')
    expect(wrapper.text()).not.toContain('source_refs')
    wrapper.unmount()
  })
  it('requires feedback for negative decisions and emits original natural language', async () => {
    const wrapper = mount(HumanGate, { props: { gate: waitingSnapshot().gates[0]!, busy: false, writingEnabled: true } })
    expect(wrapper.text()).not.toContain('Project')
    expect(wrapper.text()).not.toContain('Workflow')
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[0]!.attributes('disabled')).toBeUndefined()
    await buttons[2]!.trigger('click')
    await wrapper.get('textarea').setValue('  不要改变结尾，增加冲突。  ')
    await wrapper.findAll('button').find(button => button.text() === '重新生成方案')!.trigger('click')
    expect(wrapper.emitted('decide')).toEqual([['MODIFY', '  不要改变结尾，增加冲突。  ']])
    await buttons[1]!.trigger('click')
    await wrapper.findAll('button').find(button => button.text() === '重新生成方案')!.trigger('click')
    expect(wrapper.emitted('decide')?.at(-1)).toEqual(['REQUEST_ALTERNATIVE', ''])
    await wrapper.setProps({ busy: true })
    expect(wrapper.findAll('button').filter(button => !button.classes('quiet')).every(b => b.attributes('disabled') !== undefined)).toBe(true)
    await wrapper.setProps({ busy: false, writingEnabled: false })
    expect(wrapper.findAll('button')[0]!.attributes('disabled')).toBeDefined()
    expect(wrapper.get('[role="status"]').text()).toContain('启用 WRITE_CHAPTER')
    wrapper.unmount()
  })
  it('renders Draft as a reader, escapes model HTML and keeps lineage out of the reading surface', async () => {
    const draft = { ...sample.snapshot.drafts[0]!, content: '第一段。\n\n<script>alert(1)</script>\n第二段。' }
    const wrapper = mount(DraftView, { props: { draft, chapterNumber: 3 } })
    expect(wrapper.get('.prose').text()).toBe(draft.content)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.text()).toContain('第 3 章')
    expect(wrapper.text()).not.toContain('knowledge_risk_flags')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('evaluate')).toHaveLength(1)
    wrapper.unmount()
  })
  it('shows actionable version conflict with request ID', () => {
    const wrapper = mount(ErrorNotice, { props: { error: new ApiError('VERSION_CONFLICT', 'stale', 'request-example', 409) } })
    expect(wrapper.get('[role="alert"]').text()).toContain('当前内容已经发生变化，请刷新页面后再操作。')
    expect(wrapper.get('details').attributes('open')).toBeUndefined()
    expect(wrapper.text()).toContain('request-example')
    wrapper.unmount()
  })
  it('shows blocked reason and failed code, and handles unknown future states', async () => {
    const w = clone(sample.snapshot.workflow)
    w.current_state = 'C90_BLOCKED'; w.block_reason = 'Required context missing'; w.blocked_guard = 'CONTEXT_BLOCKED'
    const wrapper = mount(WorkflowProgress, { props: { workflow: w, tasks: [] } })
    expect(wrapper.get('[role="status"]').text()).toContain('Required context missing')
    expect(wrapper.text()).not.toContain('正在读取')
    await wrapper.setProps({ workflow: { ...w, current_state: 'FUTURE_STATE' as typeof w.current_state } })
    expect(wrapper.text()).toContain('当前阶段暂不提供操作')
    wrapper.unmount()
  })
  it('Debug is lazy, binds exact run, shows current/approved independently and cancels on close', async () => {
    vi.spyOn(api, 'transitions').mockResolvedValue(sample.transitions)
    vi.spyOn(api, 'runs').mockImplementation(async id => sample.runs.filter(r => r.task_id === id))
    const contexts = vi.spyOn(api, 'context').mockResolvedValue(sample.context)
    vi.spyOn(api, 'lineage').mockResolvedValue(sample.lineage)
    vi.spyOn(writingProfiles, 'versions').mockResolvedValue([])
    const s = clone(sample.snapshot)
    s.chapter.current_plan_version = 2; s.chapter.approved_plan_version = 1
    s.chapter.current_version = 3; s.chapter.approved_version = 2
    const wrapper = mount(DebugPanel, { props: { snapshot: s, open: false } })
    expect(contexts).not.toHaveBeenCalled()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await wrapper.setProps({ open: true }); await flushPromises()
    expect(contexts.mock.calls[0]?.[0]).toBe(sample.runs.at(-1)!.run_id)
    expect(wrapper.get('[data-testid="version-pointers"]').text()).toContain('ChapterPlanv2v1')
    expect(wrapper.get('[data-testid="version-pointers"]').text()).toContain('ChapterVersionv3v2')
    expect(wrapper.text()).toContain(sample.lineage.compiled_prompt_hash)
    expect(wrapper.text()).toContain(sample.context.package.items[0]!.selected_reason)
    const signal = contexts.mock.calls[0]?.[1]
    await wrapper.setProps({ open: false }); await flushPromises()
    expect(signal?.aborted).toBe(true)
    wrapper.unmount()
  })
  it('loads Debug immediately when its remembered open state mounts as open', async () => {
    vi.spyOn(api, 'transitions').mockResolvedValue(sample.transitions)
    const runs = vi.spyOn(api, 'runs').mockImplementation(async id => sample.runs.filter(r => r.task_id === id))
    vi.spyOn(api, 'context').mockResolvedValue(sample.context)
    vi.spyOn(api, 'lineage').mockResolvedValue(sample.lineage)
    vi.spyOn(writingProfiles, 'versions').mockResolvedValue([])
    const wrapper = mount(DebugPanel, { props: { snapshot: sample.snapshot, open: true } })
    await flushPromises()
    expect(runs).toHaveBeenCalled()
    expect(wrapper.get('#debug-run').element).toHaveProperty('value', sample.runs.at(-1)!.run_id)
    wrapper.unmount()
  })
  it('loads only a raw manual-case requirement and never supplies expected agent artifacts', async () => {
    const wrapper = mount(ManualCaseLoader, { props: { cases: manualCases, selectedId: null } })
    expect(wrapper.findAll('.case-item')).toHaveLength(5)
    expect(wrapper.text()).toContain('建议使用独立测试项目运行该 Case')
    await wrapper.findAll('.case-item')[0]!.get('button').trigger('click')
    expect(wrapper.emitted('load')?.[0]?.[0]).toEqual(manualCases[0])
    expect(JSON.stringify(manualCases[0])).not.toContain('creative_brief')
    expect(JSON.stringify(manualCases[0])).not.toContain('chapter_plan')
    await wrapper.setProps({ canLoad: false })
    expect(wrapper.findAll('.case-item button').every(item => item.attributes('disabled') !== undefined)).toBe(true)
    wrapper.unmount()
  })
  it('keeps project and chapter navigation human-readable without exposing UUIDs', async () => {
    const project = { id: sample.snapshot.chapter.project_id, project_id: sample.snapshot.chapter.project_id, name: '测试项目' } as Project
    const wrapper = mount(WorkspaceSidebar, { props: { projects: [project], chapters: [sample.snapshot.chapter], projectId: project.id, chapterId: sample.snapshot.chapter.id, disabled: false } })
    expect(wrapper.text()).toContain(project.name)
    expect(wrapper.text()).toContain('第 1 章')
    expect(wrapper.text()).not.toContain(project.id)
    await wrapper.get('.chapter-link').trigger('click')
    expect(wrapper.emitted('selectChapter')?.[0]).toEqual([sample.snapshot.chapter.id])
    wrapper.unmount()
  })
  it('exports a complete manual evaluation as local JSON without an API call', async () => {
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:evaluation')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mount(HumanEvaluation, { props: { projectId: 'p', chapterId: 'c', workflowId: 'w', draftVersion: 2, caseId: 'case-01' } })
    await wrapper.get('input[name="understanding"][value="GOOD"]').setValue(true)
    await wrapper.get('input[name="planning"][value="OK"]').setValue(true)
    await wrapper.get('input[name="audience"][value="BAD"]').setValue(true)
    await wrapper.get('input[name="ai-feel"][value="LOW"]').setValue(true)
    await wrapper.get('input[name="overall"][value="ACCEPT"]').setValue(true)
    await wrapper.findAll('input[value="KNOWLEDGE_LEAK"]')[0]!.setValue(true)
    await wrapper.get('#evaluation-notes').setValue('具体证据')
    await wrapper.get('button.primary').trigger('click')
    expect(createObjectURL).toHaveBeenCalledTimes(1); expect(click).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[role="status"]').text()).toContain('已下载')
    wrapper.unmount()
  })
})
