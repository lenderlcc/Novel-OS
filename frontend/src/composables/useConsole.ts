import { computed, onScopeDispose, ref, shallowRef } from 'vue'
import { api } from '../api/console'
import { writingProfiles } from '../api/writingProfiles'
import { ApiError, asError } from '../api/client'
import type { Project, Chapter, Workflow, Gate, Brief, Plan, PlanningHistory, Draft, Writing, Task, Decision, ExecutionConfig, QualityReview, Revision, Feedback } from '../types/models'
import { isReviewResume, isWritingWorkflow, pollDelay } from './workflowState'
import { reviewForDraft } from './revisionWorkspace'

export interface Snapshot {
  workflow: Workflow; chapter: Chapter; gates: Gate[]; brief: Brief | null;
  plans: Plan[]; history: PlanningHistory; drafts: Draft[]; writing: Writing[]; tasks: Task[]; qualityReviews?: QualityReview[]; revisions?: Revision[]; feedback?: Feedback[]
}

function generatedDraftVersion(s: Snapshot): number | null {
  // Reading selection follows the chapter pointer, not the workflow's source
  // version, which remains old while a revision/re-review is in progress.
  const qualityWorkspace = s.workflow.workflow_definition_version === 3 && (s.workflow.revision_request_id || s.workflow.human_feedback_id || s.workflow.resume_state === 'C13_USER_FEEDBACK_DIAGNOSIS' || s.workflow.resume_state === 'C09_INTERNAL_REVIEW' || ['C09_INTERNAL_REVIEW', 'C10_REVISION', 'C11_INTERNAL_PASS', 'C13_USER_FEEDBACK_DIAGNOSIS'].includes(s.workflow.current_state))
  if (qualityWorkspace && s.drafts.some(draft => draft.version === s.chapter.current_version)) return s.chapter.current_version
  const version = s.workflow.draft_version ?? null
  if (!isWritingWorkflow(s.workflow)) return version
  const draft = s.drafts.find(d => d.version === version)
  // Review may explicitly bind a user-authored version without a Writing generation.
  if (draft && s.workflow.workflow_definition_version === 3 && ['C09_INTERNAL_REVIEW', 'C10_REVISION', 'C11_INTERNAL_PASS', 'C13_USER_FEEDBACK_DIAGNOSIS'].includes(s.workflow.current_state)) return version
  return draft && (s.writing.some(w => w.chapter_version_id === draft.id) || s.revisions?.some(r => r.result?.chapter_version_id === draft.id)) ? version : null
}

export function useConsole(client = api) {
  const projects = ref<Project[]>([]), chapters = ref<Chapter[]>([]), workflows = ref<Workflow[]>([])
  const executionConfig = shallowRef<ExecutionConfig | null>(null)
  const projectId = ref(''), chapterId = ref(''), workflowId = ref('')
  const snapshot = shallowRef<Snapshot | null>(null)
  const selectedPlan = ref<number | null>(null), viewingVersion = ref<number | null>(null)
  let followCurrentDraft = true
  let selectionRevision = 0
  const currentBackendVersion = computed(() => snapshot.value?.chapter.current_version ?? null)
  const selectedDraft = computed({
    get: () => viewingVersion.value,
    set: (version: number | null) => { followCurrentDraft = false; viewingVersion.value = version; selectionRevision++ },
  })
  const error = shallowRef<ApiError | null>(null), busy = ref(false), loading = ref(false), conflict = ref(false)
  let epoch = 0, controller = new AbortController(), timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  let revisionCommand: { key: string; id: string } | null = null
  const stop = () => { clearTimeout(timer); timer = undefined }
  function invalidate() { stop(); controller.abort(); controller = new AbortController(); return ++epoch }
  const workflow = computed(() => snapshot.value?.workflow ?? null)
  const plan = computed(() => snapshot.value?.plans.find(p => p.version === selectedPlan.value) ?? null)
  const generation = computed(() => snapshot.value?.history.plans.find(p => p.plan_id === plan.value?.id) ?? null)
  const review = computed(() => snapshot.value?.history.reviews.filter(r => r.plan_id === plan.value?.id).at(-1) ?? null)
  const draft = computed(() => snapshot.value?.drafts.find(d => d.version === selectedDraft.value) ?? null)
  const writing = computed(() => snapshot.value?.writing.find(w => w.chapter_version_id === draft.value?.id) ?? null)
  const gate = computed(() => {
    const s = snapshot.value
    if (!s || conflict.value || !isWritingWorkflow(s.workflow) || s.workflow.current_state !== 'C06_PLAN_APPROVAL' || !generation.value) return null
    return s.gates.find(g => g.status === 'WAITING' && g.gate_type === 'PLAN_APPROVAL' &&
      g.artifact_id === plan.value?.id && g.artifact_version === plan.value?.version &&
      g.artifact_version === s.workflow.plan_version && g.opened_state_version === s.workflow.state_version) ?? null
  })
  const formal = computed(() => workflow.value ? isWritingWorkflow(workflow.value) : false)

  function schedule() {
    stop()
    const delay = pollDelay(workflow.value, snapshot.value?.tasks, executionConfig.value)
    if (!disposed && delay !== null && !error.value) timer = setTimeout(() => { void refresh(false) }, delay)
  }

  async function refresh(manual = true) {
    if (disposed || !workflowId.value) return
    const token = invalidate(), signal = controller.signal
    const p = projectId.value, c = chapterId.value, w = workflowId.value
    if (manual) loading.value = true
    try {
      const [current, latestConfig] = await Promise.all([
        client.workflow(w, signal),
        manual ? client.executionConfig(signal) : Promise.resolve(executionConfig.value),
      ])
      const [chapter, gates, brief, plans, history, drafts, writing, tasks, qualityReviews, revisions, feedback] = await Promise.all([
        client.chapter(p, c, signal), client.gates(w, signal), current.simulation ? null : client.brief(w, signal), client.plans(p, c, signal),
        current.simulation ? { briefs: [], plans: [], reviews: [] } : client.history(w, signal),
        client.drafts(p, c, signal), client.writing(w, signal), client.tasks(w, signal),
        current.workflow_definition_version === 3 && !current.simulation ? client.qualityReviews(p, c, signal) : [],
        current.workflow_definition_version === 3 && !current.simulation ? client.revisions(w, signal) : [],
        current.workflow_definition_version === 3 && !current.simulation ? client.feedback(w, signal) : [],
      ])
      // Do not publish a mixed snapshot if the worker advanced while reading artifacts.
      const after = await client.workflow(w, signal)
      if (token !== epoch) return
      if (after.state_version !== current.state_version) {
        loading.value = false
        timer = setTimeout(() => { void refresh(manual) }, 300)
        return
      }
      const next: Snapshot = { workflow: current, chapter, gates, brief, plans, history, drafts, writing, tasks, qualityReviews, revisions, feedback }
      const previous = snapshot.value
      if (!previous || selectedPlan.value === previous.workflow.plan_version) selectedPlan.value = current.plan_version
      // Explicit reading selection is pinned, even if it was current when a
      // poll began. A late response must not switch the reader to another text.
      if (followCurrentDraft) viewingVersion.value = generatedDraftVersion(next)
      snapshot.value = next
      if (manual) executionConfig.value = latestConfig
      workflows.value = workflows.value.map(item => item.id === w ? current : item)
      chapters.value = chapters.value.map(item => item.id === c ? chapter : item)
      if (manual) { error.value = null; conflict.value = false }
      schedule()
    } catch (err) {
      if (token === epoch && !signal.aborted) error.value = asError(err)
    } finally { if (token === epoch) loading.value = false }
  }

  async function loadProjects() {
    if (disposed) return
    const token = invalidate(); loading.value = true
    try {
      const [result, config] = await Promise.all([client.projects(controller.signal), client.executionConfig(controller.signal)])
      if (token === epoch) { projects.value = result; executionConfig.value = config; error.value = null }
    }
    catch (err) { if (token === epoch) error.value = asError(err) }
    finally { if (token === epoch) loading.value = false }
  }
  function clearWorkflow() {
    workflowId.value = ''; snapshot.value = null; selectedPlan.value = null; viewingVersion.value = null; followCurrentDraft = true
    error.value = null; conflict.value = false
  }
  async function selectProject(id: string) {
    if (disposed) return
    const token = invalidate(); projectId.value = id; chapterId.value = ''; chapters.value = []; workflows.value = []; clearWorkflow()
    if (!id) { loading.value = false; return }
    loading.value = true
    try { const result = await client.chapters(id, controller.signal); if (token === epoch) chapters.value = result }
    catch (err) { if (token === epoch) error.value = asError(err) }
    finally { if (token === epoch) loading.value = false }
  }
  async function selectChapter(id: string) {
    if (disposed) return
    const token = invalidate(); chapterId.value = id; workflows.value = []; clearWorkflow()
    if (!id) { loading.value = false; return }
    loading.value = true
    try {
      const result = await client.workflows(projectId.value, id, controller.signal)
      if (token !== epoch) return
      workflows.value = result
      if (result[0]) await selectWorkflow(result[0].id)
    } catch (err) { if (token === epoch) error.value = asError(err) }
    finally { if (token === epoch) loading.value = false }
  }
  async function selectWorkflow(id: string) {
    if (disposed) return
    invalidate(); clearWorkflow(); workflowId.value = id
    if (id) await refresh()
    else loading.value = false
  }
  async function mutate(action: () => Promise<void>) {
    if (disposed || busy.value) return
    const operationProject = projectId.value, operationChapter = chapterId.value
    invalidate(); busy.value = true; loading.value = false; error.value = null
    try { await action() }
    catch (err) {
      if (disposed || projectId.value !== operationProject || chapterId.value !== operationChapter) return
      error.value = asError(err)
      if (error.value.code === 'VERSION_CONFLICT') conflict.value = true
    } finally { busy.value = false }
  }
  const createProject = (name: string) => mutate(async () => {
    const project = await client.createProject(name)
    if (disposed) return
    projects.value = [...projects.value, project]; await selectProject(project.id)
  })
  const createChapter = (title: string, sequence: number) => mutate(async () => {
    const chapter = await client.createChapter(projectId.value, title, sequence)
    if (disposed) return
    chapters.value = [...chapters.value, chapter]; await selectChapter(chapter.id)
  })
  const start = (raw: string) => mutate(async () => {
    // After an uncertain create, the tester refreshes chapter workflows before submitting again.
    const result = await client.start(projectId.value, chapterId.value, raw, crypto.randomUUID())
    if (disposed) return
    clearWorkflow(); workflowId.value = result.workflow.id; workflows.value.unshift(result.workflow)
    try {
      const submitted = await client.submit(result.workflow, crypto.randomUUID())
      if (submitted.error_code) throw new ApiError(submitted.error_code, '需求提交未完成，请刷新查看流程。')
    } catch (submitError) {
      // The create is already durable. Publish C00 so the user can retry USER_SUBMITTED
      // instead of creating another workflow or being stranded behind the active guard.
      if (!disposed) await refresh()
      throw submitError
    }
    await refresh()
  })
  const submit = () => mutate(async () => {
    if (!workflow.value) return
    const result = await client.submit(workflow.value, crypto.randomUUID())
    if (result.error_code) throw new ApiError(result.error_code, '提交失败，请刷新。')
    await refresh()
  })
  const decide = (decision: Decision, reason: string) => mutate(async () => {
    const currentWorkflow = workflow.value, currentGate = gate.value
    if (!currentWorkflow || !currentGate) throw new ApiError('STALE_VIEW', '请打开当前待审批方案后再操作。')
    if (decision === 'APPROVE') {
      const latestConfig = await client.executionConfig(controller.signal)
      if (disposed) return
      executionConfig.value = latestConfig
      if (latestConfig.task_types && !latestConfig.task_types.includes('WRITE_CHAPTER')) {
        throw new ApiError('EXECUTION_SCOPE_DISABLED', 'Writing 当前未开放。请启用 WRITE_CHAPTER 后刷新并重新审批。')
      }
    }
    const normalizedReason = reason.trim() || (decision === 'APPROVE'
      ? '人工批准当前方案'
      : decision === 'REQUEST_ALTERNATIVE'
        ? '人工请求一个不同方向的替代方案'
        : '')
    if (!normalizedReason) throw new ApiError('INVALID_INPUT', '请说明希望修改的内容。')
    const result = await client.decide(currentWorkflow, currentGate, decision, normalizedReason, crypto.randomUUID())
    if (result.error_code) throw new ApiError(result.error_code, '审批未完成，请刷新后检查流程。')
    await refresh()
  })
  const control = (action: 'pause' | 'resume' | 'cancel', reason: string) => mutate(async () => {
    if (!workflow.value) return
    const w = workflow.value, s = snapshot.value
    const reviewResume = action === 'resume' && isReviewResume(w, s?.tasks ?? [])
    // Bind the version actually loaded in this snapshot. A concurrent edit must return 409.
    const result = reviewResume && s?.chapter.current_version
      ? await client.control(w, action, reason, s.chapter.current_version)
      : await client.control(w, action, reason)
    if (result.error_code) throw new ApiError(result.error_code, '操作未完成，请刷新后检查流程。')
    await refresh()
  })
  const revise = () => mutate(async () => {
    const w = workflow.value, currentDraft = draft.value, s = snapshot.value
    const selectionAtRequest = selectionRevision
    const currentReview = reviewForDraft(s?.qualityReviews ?? [], currentDraft?.id)
    if (!w || !currentDraft || !currentReview || currentReview.binding.workflow_id !== w.id || currentReview.freshness !== 'CURRENT' || currentReview.body.overall_verdict === 'PASS' || currentDraft.version !== s?.chapter.current_version || w.status !== 'WAITING_HUMAN' || w.revision_request_id) throw new ApiError('STALE_VIEW', '请打开当前正文及有效审阅后再修改。')
    if (!currentReview.binding.profile_record_id) throw new ApiError('CONTEXT_MISSING', '请先批准写作偏好，再重新审阅当前正文。')
    const config = await client.executionConfig(controller.signal)
    if (disposed || workflow.value?.id !== w.id) return
    executionConfig.value = config
    if (config.task_types && ['PLAN_CHAPTER_REVISION', 'REVISE_CHAPTER', 'VALIDATE_REVISION_FIDELITY', 'REVIEW_CHAPTER_COMPLIANCE', 'REVIEW_CHAPTER_NARRATIVE'].some(type => !config.task_types!.includes(type))) throw new ApiError('EXECUTION_SCOPE_DISABLED', '本机尚未启用修改与重新审阅，请检查执行配置。')
    const key = `${w.id}:${w.state_version}:${currentReview.id}:${currentDraft.id}`
    if (revisionCommand?.key !== key) revisionCommand = { key, id: crypto.randomUUID() }
    const result = await client.revise(w, currentReview, currentDraft.version, revisionCommand.id)
    if (disposed || workflow.value?.id !== w.id) return
    if (result.error_code) throw new ApiError(result.error_code, '修改请求未完成，请刷新检查。')
    revisionCommand = null
    if (selectionAtRequest === selectionRevision) followCurrentDraft = true
    await refresh()
  })
  let feedbackCommand: { key: string; id: string } | null = null
  const sendFeedback = (raw: string, replyTo?: string) => mutate(async () => {
    const w = workflow.value, source = draft.value, s = snapshot.value
    const selectionAtRequest = selectionRevision
    if (!w || !source || !raw.trim() || source.version !== s?.chapter.current_version || w.status !== 'WAITING_HUMAN' || !['C10_REVISION', 'C11_INTERNAL_PASS'].includes(w.current_state) || w.revision_request_id || w.human_feedback_id) throw new ApiError('STALE_VIEW', '请在当前正文的空闲状态提交修改要求。')
    const config = await client.executionConfig(controller.signal)
    if (disposed || workflow.value?.id !== w.id) return
    executionConfig.value = config
    if (config.task_types && ['INTERPRET_CHAPTER_FEEDBACK', 'PLAN_CHAPTER_REVISION', 'REVISE_CHAPTER', 'VALIDATE_REVISION_FIDELITY', 'REVIEW_CHAPTER_COMPLIANCE', 'REVIEW_CHAPTER_NARRATIVE'].some(t => !config.task_types!.includes(t))) throw new ApiError('EXECUTION_SCOPE_DISABLED', '本机尚未启用反馈修改与重新审阅。')
    const key = JSON.stringify([w.id, w.state_version, source.id, raw, replyTo])
    if (feedbackCommand?.key !== key) feedbackCommand = { key, id: crypto.randomUUID() }
    const result = await client.sendFeedback(w, source.id, raw, feedbackCommand.id, replyTo)
    if (disposed || workflow.value?.id !== w.id) return
    if (result.error_code) throw new ApiError(result.error_code, '反馈未能提交，请刷新检查。')
    feedbackCommand = null
    if (selectionAtRequest === selectionRevision) followCurrentDraft = true
    await refresh()
  })
  const discardFeedback = () => mutate(async () => {
    const w = workflow.value
    if (!w?.human_feedback_id) throw new ApiError('STALE_VIEW', '请刷新查看当前反馈。')
    const result = await client.discardFeedback(w, w.human_feedback_id, crypto.randomUUID())
    if (disposed || workflow.value?.id !== w.id) return
    if (result.error_code) throw new ApiError(result.error_code, '未能放弃本次反馈，请刷新检查。')
    followCurrentDraft = true
    await refresh()
  })
  const replan = (raw: string) => mutate(async () => {
    const w = workflow.value, brief = snapshot.value?.brief
    if (!w || !brief || w.status !== 'WAITING_HUMAN' || draft.value?.version !== currentBackendVersion.value || !raw.trim()) throw new ApiError('STALE_VIEW', '请先返回当前正文。')
    const result = await client.replan(w, brief, raw, crypto.randomUUID())
    if (result.error_code) throw new ApiError(result.error_code, '返回方案流程失败，请刷新检查。')
    await refresh()
  })
  const rereviewRevision = () => mutate(async () => {
    const w = workflow.value, version = snapshot.value?.chapter.current_version
    const completed = w?.status === 'WAITING_HUMAN' && ['C10_REVISION', 'C11_INTERNAL_PASS', 'C13_USER_FEEDBACK_DIAGNOSIS'].includes(w.current_state)
    if (!w || !version || !(completed || (w.revision_request_id && w.status === 'BLOCKED'))) throw new ApiError('STALE_VIEW', '请刷新当前正文后再重新审阅。')
    if (completed) {
      const profile = await writingProfiles.state(w.project_id, controller.signal)
      if (disposed || workflow.value?.id !== w.id) return
      if (!profile.approved) throw new ApiError('CONTEXT_MISSING', '请先保存并批准写作偏好，再重新审阅正文。')
    }
    const config = await client.executionConfig(controller.signal)
    if (disposed || workflow.value?.id !== w.id) return
    executionConfig.value = config
    if (config.task_types && ['REVIEW_CHAPTER_COMPLIANCE', 'REVIEW_CHAPTER_NARRATIVE'].some(type => !config.task_types!.includes(type))) throw new ApiError('EXECUTION_SCOPE_DISABLED', '本机尚未启用正文审阅。')
    const key = `review:${w.id}:${w.state_version}:${version}`
    if (revisionCommand?.key !== key) revisionCommand = { key, id: crypto.randomUUID() }
    const result = await client.rereview(w, version, revisionCommand.id)
    if (result.error_code) throw new ApiError(result.error_code, '重新审阅请求未完成，请刷新检查。')
    revisionCommand = null
    await refresh()
  })
  onScopeDispose(() => { disposed = true; invalidate() })
  return { projects, chapters, workflows, executionConfig, projectId, chapterId, workflowId, snapshot, workflow,
    selectedPlan, selectedDraft, currentBackendVersion, plan, generation, review, draft, writing, gate, formal,
    error, busy, loading, conflict, loadProjects, selectProject, selectChapter, selectWorkflow,
    refresh, createProject, createChapter, start, submit, decide, control, revise, rereviewRevision, sendFeedback, discardFeedback, replan }
}
