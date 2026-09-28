<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useConsole } from '../composables/useConsole'
import BriefView from '../components/BriefView.vue'
import PlanView from '../components/PlanView.vue'
import DraftView from '../components/DraftView.vue'
import QualityReview from '../components/QualityReview.vue'
import HumanGate from '../components/HumanGate.vue'
import WorkflowProgress from '../components/WorkflowProgress.vue'
import DebugPanel from '../components/DebugPanel.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
import WritingProfile from '../components/WritingProfile.vue'
import WorkspaceSidebar from '../components/WorkspaceSidebar.vue'
import ManualCaseLoader from '../components/ManualCaseLoader.vue'
import HumanEvaluation from '../components/HumanEvaluation.vue'
import { manualCases, type ManualCase } from '../data/manualCases'

const {
  projects, chapters, workflows, executionConfig, projectId, chapterId, workflowId, snapshot, workflow,
  selectedPlan, selectedDraft, plan, generation, review, draft, gate, formal, error, busy, loading, conflict,
  loadProjects, selectProject, selectChapter, refresh, createProject, createChapter,
  start, submit, decide, control, revise, rereviewRevision,
} = useConsole()
const manualTestAvailable = import.meta.env.DEV
const storage = window.localStorage
const requirement = ref(''), loadedCase = ref<ManualCase | null>(null)
const profileOpen = ref(false), testsOpen = ref(manualTestAvailable && storage.getItem('novel-os.test-mode') === 'true'), evaluationOpen = ref(false)
const debugOpen = ref(storage.getItem('novel-os.debug-open') === 'true')
const currentChapter = computed(() => chapters.value.find(item => item.id === chapterId.value) ?? null)
const writingEnabled = computed(() => !executionConfig.value?.task_types || executionConfig.value.task_types.includes('WRITE_CHAPTER'))
const disabled = computed(() => busy.value || loading.value)
const active = computed(() => workflows.value.some(item => !['COMPLETED', 'FAILED', 'CANCELLED'].includes(item.status) && !['C08_DETERMINISTIC_CHECK', 'C10_REVISION', 'C11_INTERNAL_PASS'].includes(item.current_state)))
const state = computed(() => workflow.value?.current_state ?? '')
const requirementStage = computed(() => !workflow.value || state.value === 'C00_CREATED')
const processingStage = computed(() => /^C0[1-5]_/.test(state.value))
const planStage = computed(() => state.value === 'C06_PLAN_APPROVAL')
const writingStage = computed(() => state.value === 'C07_WRITING')
const draftStage = computed(() => ['C08_DETERMINISTIC_CHECK', 'C09_INTERNAL_REVIEW', 'C10_REVISION', 'C11_INTERNAL_PASS'].includes(state.value))
const qualityReview = computed(() => snapshot.value?.qualityReviews?.find(r => r.chapter_version_id === draft.value?.id && r.binding.workflow_id === workflowId.value) ?? null)
const revision = computed(() => snapshot.value?.revisions?.[0] ?? null)
const revising = computed(() => Boolean(workflow.value?.revision_request_id))
const reviewReady = computed(() =>
  !revising.value && workflow.value?.status === 'WAITING_HUMAN' &&
  ['C10_REVISION', 'C11_INTERNAL_PASS'].includes(state.value) && Boolean(qualityReview.value) &&
  draft.value?.version === snapshot.value?.chapter.current_version,
)
const revisionAvailable = computed(() => reviewReady.value && qualityReview.value?.body.overall_verdict !== 'PASS')
const revisionMissingProfile = computed(() => revisionAvailable.value && !qualityReview.value?.binding.profile_record_id)
const reviewNeedsRereview = computed(() => revisionMissingProfile.value || (reviewReady.value && qualityReview.value?.freshness === 'STALE'))
const canRevise = computed(() => revisionAvailable.value && !revisionMissingProfile.value && qualityReview.value?.freshness === 'CURRENT')
const revisionForDraft = computed(() => snapshot.value?.revisions?.find(r => r.result?.chapter_version_id === draft.value?.id))
const revisionNeedsRereview = computed(() => workflow.value?.status === 'BLOCKED' && workflow.value.resume_state === 'C10_REVISION' && revising.value && Boolean(revision.value?.result || snapshot.value?.tasks.filter(t => t.agent_id === 'A06_REVISION').at(-1)?.status === 'BLOCKED'))
const blockedReasons = computed(() => revision.value?.result?.body.blocked_reasons.length ? revision.value.result.body.blocked_reasons : revision.value?.plan?.body.blocked_reasons ?? [])
const overlayOpen = computed(() =>
  (profileOpen.value && Boolean(projectId.value)) ||
  (testsOpen.value && manualTestAvailable) ||
  (evaluationOpen.value && Boolean(draft.value)) ||
  (debugOpen.value && Boolean(snapshot.value)),
)

const projectKey = 'novel-os.last-project'
const chapterKey = (project: string) => `novel-os.last-chapter.${project}`
const draftKey = (chapter: string) => `novel-os.requirement-draft.${chapter}`
const caseKey = (chapter: string) => `novel-os.manual-case.${chapter}`
const workflowCaseKey = (workflow: string) => `novel-os.manual-case.workflow.${workflow}`
const evaluationCaseId = computed(() => workflowId.value ? storage.getItem(workflowCaseKey(workflowId.value)) : null)

async function chooseProject(id: string, restore = true) {
  await selectProject(id)
  if (!id) { storage.removeItem(projectKey); return }
  storage.setItem(projectKey, id)
  if (restore) {
    const saved = storage.getItem(chapterKey(id))
    if (saved && chapters.value.some(item => item.id === saved)) await chooseChapter(saved)
  }
}
async function chooseChapter(id: string) {
  await selectChapter(id)
  if (!id) return
  storage.setItem(chapterKey(projectId.value), id)
  if (workflowId.value) loadedCase.value = null
}
async function initialize() {
  await loadProjects()
  const saved = storage.getItem(projectKey)
  const target = projects.value.some(item => item.id === saved) ? saved! : projects.value.length === 1 ? projects.value[0]!.id : ''
  if (target) await chooseProject(target)
}
async function addProject(name: string) {
  await createProject(name)
  if (!error.value && projectId.value) storage.setItem(projectKey, projectId.value)
}
async function addChapter(title: string, sequence: number) {
  await createChapter(title, sequence)
  if (!error.value && chapterId.value) storage.setItem(chapterKey(projectId.value), chapterId.value)
}
async function begin() {
  const submittedCase = loadedCase.value?.requirement === requirement.value ? loadedCase.value.id : null
  await start(requirement.value)
  if (workflowId.value) {
    if (submittedCase) storage.setItem(workflowCaseKey(workflowId.value), submittedCase)
    else storage.removeItem(workflowCaseKey(workflowId.value))
  }
  if (!error.value) {
    storage.removeItem(draftKey(chapterId.value))
    storage.removeItem(caseKey(chapterId.value))
  }
}
function loadCase(value: ManualCase) {
  if (!currentChapter.value || workflow.value) return
  loadedCase.value = value; requirement.value = value.requirement; testsOpen.value = false
  storage.setItem('novel-os.test-mode', 'false')
  if (chapterId.value) storage.setItem(caseKey(chapterId.value), value.id)
}
function toggleDebug() {
  debugOpen.value = !debugOpen.value; storage.setItem('novel-os.debug-open', String(debugOpen.value))
}
function toggleTests() {
  if (!manualTestAvailable || !currentChapter.value || workflow.value) return
  testsOpen.value = true; storage.setItem('novel-os.test-mode', 'true')
}
function closeTests() {
  testsOpen.value = false; storage.setItem('novel-os.test-mode', 'false')
}
watch(chapterId, id => {
  requirement.value = id ? storage.getItem(draftKey(id)) ?? '' : ''
  const selected = id ? storage.getItem(caseKey(id)) : null
  const restored = manualCases.find(item => item.id === selected) ?? null
  loadedCase.value = restored?.requirement === requirement.value ? restored : null
  if (id && selected && !loadedCase.value) storage.removeItem(caseKey(id))
}, { flush: 'sync' })
watch(requirement, value => {
  if (!chapterId.value) return
  storage.setItem(draftKey(chapterId.value), value)
  if (loadedCase.value && loadedCase.value.requirement !== value) {
    loadedCase.value = null
    storage.removeItem(caseKey(chapterId.value))
  }
})
onMounted(initialize)
</script>

<template>
  <div class="workspace-shell">
    <WorkspaceSidebar :inert="overlayOpen || undefined" :projects="projects" :chapters="chapters" :project-id="projectId" :chapter-id="chapterId" :disabled="disabled" :test-disabled="Boolean(workflow)" :test-available="manualTestAvailable"
      @select-project="chooseProject" @select-chapter="chooseChapter" @create-project="addProject" @create-chapter="addChapter"
      @open-profile="profileOpen = true" @open-tests="toggleTests" />

    <main class="workspace-main" :inert="overlayOpen || undefined">
      <header class="workspace-header">
        <div>
          <template v-if="currentChapter"><p>第 {{ currentChapter.sequence }} 章</p><h1>{{ currentChapter.title }}</h1></template>
          <template v-else><h1>选择一个章节</h1><p>从左侧开始，或新建章节。</p></template>
        </div>
        <div class="header-actions"><button v-if="workflowId" :disabled="disabled" @click="refresh()">刷新</button><button v-if="snapshot" :aria-expanded="debugOpen" @click="toggleDebug">Debug</button></div>
      </header>

      <div v-if="loading && !snapshot" class="workspace-loading" role="status">正在打开章节…</div>
      <ErrorNotice v-if="error" :error="error" />

      <section v-if="!currentChapter && !loading" class="empty-workspace"><h2>开始创作</h2><p>选择左侧章节后，可以用自然语言描述这一章。</p></section>

      <template v-else-if="currentChapter">
        <WorkflowProgress v-if="workflow && (!draftStage || workflow.workflow_definition_version === 3)" :workflow="workflow" :tasks="snapshot?.tasks ?? []" :config="executionConfig" :current-draft-version="snapshot?.chapter.current_version" :hide-resume="revisionNeedsRereview" :can-resume="formal && !disabled && !conflict && !revisionNeedsRereview" @resume="control('resume', '人工继续当前创作流程')" />

        <section v-if="requirementStage" class="requirement-workspace">
          <div class="section-heading"><h2>章节需求</h2><p>说说这一章你希望发生什么。具体结构和细节交给 AI 理解。</p></div>
          <form @submit.prevent="workflow ? submit() : begin()">
            <label v-if="!workflow" class="sr-only" for="requirement">章节需求</label>
            <textarea v-if="!workflow" id="requirement" v-model="requirement" rows="12" maxlength="12000" required :disabled="disabled" placeholder="说说这一章你希望发生什么……" />
            <div v-else class="resume-submission"><h3>需求已保存</h3><p>流程已创建，但上次提交未完成。可以从原需求继续，不会重复创建流程。</p></div>
            <div class="requirement-actions"><span v-if="loadedCase">已载入 {{ loadedCase.id.replace('-', ' ').replace('case', 'Case') }}</span><button class="primary" :disabled="disabled || (active && state !== 'C00_CREATED') || (!workflow && !requirement.trim())">{{ workflow ? '继续生成方案' : '生成方案' }}</button></div>
          </form>
        </section>

        <section v-else-if="processingStage" class="focused-stage">
          <BriefView v-if="snapshot?.brief" :brief="snapshot.brief" />
          <div v-else class="processing-copy"><h2>{{ state === 'C04_CHAPTER_PLANNING' || state === 'C05_PLAN_REVIEW' ? 'AI 正在设计方案' : 'AI 正在理解需求' }}</h2><p>完成后页面会自动更新，可以暂时离开这个窗口。</p></div>
        </section>

        <section v-else-if="planStage && snapshot" class="plan-workspace">
          <BriefView v-if="snapshot.brief" :brief="snapshot.brief" />
          <div class="section-heading plan-heading"><div><h2>章节方案</h2><p>方案 v{{ plan?.version ?? snapshot.workflow.plan_version }}</p></div>
            <details v-if="snapshot.plans.length > 1" class="version-history"><summary>查看历史方案</summary><div class="version-list"><button v-for="item in snapshot.plans" :key="item.id" :class="{ selected: selectedPlan === item.version }" @click="selectedPlan = item.version">v{{ item.version }} · {{ item.version === snapshot.workflow.plan_version ? 'Current' : item.status }}</button></div></details>
          </div>
          <PlanView v-if="plan" :plan="plan" :generation="generation" :review="review" />
          <button v-if="selectedPlan !== snapshot.workflow.plan_version" @click="selectedPlan = snapshot.workflow.plan_version">返回当前方案</button>
          <HumanGate v-if="gate" :gate="gate" :busy="disabled" :writing-enabled="writingEnabled" @decide="decide" />
          <p v-else class="notice">正在查看历史方案。返回当前方案后才能操作。</p>
        </section>

        <section v-else-if="writingStage" class="writing-workspace"><div class="writing-indicator" aria-hidden="true">···</div><h2>AI 正在写作…</h2><p>需求、方案和审批已经完成。正文生成可能需要一些时间。</p></section>

        <section v-else-if="(draftStage || revising) && draft">
          <section v-if="revising" class="quality-review" aria-label="修改进度">
            <h2>{{ workflow?.status === 'BLOCKED' ? '修改需要处理' : 'AI 正在修改正文…' }}</h2>
            <p v-if="revisionNeedsRereview">本次修改已停止。需要补充依据或重新审阅后，才能发起新的修改。</p>
            <p v-else-if="workflow?.status !== 'BLOCKED'">{{ state === 'C09_INTERNAL_REVIEW' ? '正在重新审阅' : revision?.plan ? '正在修改正文' : '正在分析修改范围' }}</p>
            <button v-if="workflow?.status === 'BLOCKED' && workflow.resume_state === 'C10_REVISION'" :disabled="disabled" @click="rereviewRevision">重新审阅正文 v{{ snapshot?.chapter.current_version }}（会调用模型）</button>
            <ul v-if="blockedReasons.length"><li v-for="item in blockedReasons" :key="item.issue_id">{{ item.reason }}</li></ul>
          </section>
          <details v-if="snapshot && snapshot.drafts.length > 1" class="version-history"><summary>查看上一版 / 切换正文版本</summary><div class="version-list"><button v-for="item in snapshot.drafts" :key="item.id" :class="{ selected: selectedDraft === item.version }" @click="selectedDraft = item.version">v{{ item.version }}{{ item.version === snapshot.chapter.current_version ? ' · 当前正文' : '' }}</button></div></details>
          <section v-if="revisionForDraft?.result" class="quality-review"><h2>本次修改重点</h2><ul><li v-for="(change, index) in revisionForDraft.result.body.declared_changes" :key="index">{{ change }}</li></ul><p>是否改善请结合重新审阅结果和正文判断。</p></section>
          <QualityReview :review="qualityReview" :pending="state === 'C09_INTERNAL_REVIEW' && draft.version === workflow?.draft_version" />
          <div v-if="reviewNeedsRereview" class="reader-actions">
            <p v-if="revisionMissingProfile">这份审阅没有绑定已批准的写作偏好。请先创建并批准写作偏好，再重新审阅当前正文。</p>
            <p v-else>审阅依据已变化。请重新审阅当前正文，再根据最新结果决定是否修改。</p>
            <button v-if="revisionMissingProfile" :disabled="disabled" @click="profileOpen = true">设置写作偏好</button>
            <button :disabled="disabled || conflict" @click="rereviewRevision">重新审阅正文 v{{ snapshot?.chapter.current_version }}（会调用模型）</button>
          </div>
          <div v-if="canRevise" class="reader-actions"><button class="primary" :disabled="disabled || conflict" @click="revise">根据审阅修改</button><p>进行一次修改并重新审阅，完成后停止。真实模型会消耗 API 额度。</p></div>
          <DraftView :draft="draft" :chapter-number="currentChapter.sequence" @evaluate="evaluationOpen = true" />
        </section>

      </template>
    </main>

    <WritingProfile v-if="profileOpen && projectId" :key="projectId" :project-id="projectId" :disabled="disabled" @close="profileOpen = false" />
    <ManualCaseLoader v-if="testsOpen && manualTestAvailable" :cases="manualCases" :selected-id="loadedCase?.id" :can-load="Boolean(currentChapter && !workflow)" @load="loadCase" @close="closeTests" />
    <HumanEvaluation v-if="evaluationOpen && draft" :key="draft.id" :project-id="projectId" :chapter-id="chapterId" :workflow-id="workflowId" :draft-version="draft.version" :case-id="evaluationCaseId" @close="evaluationOpen = false" />
    <DebugPanel v-if="snapshot" :snapshot="snapshot" :open="debugOpen" @close="toggleDebug" />
  </div>
</template>
