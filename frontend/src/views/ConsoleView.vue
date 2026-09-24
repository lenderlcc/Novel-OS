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
  selectedPlan, plan, generation, review, draft, gate, formal, error, busy, loading, conflict,
  loadProjects, selectProject, selectChapter, refresh, createProject, createChapter,
  start, submit, decide, control,
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
        <WorkflowProgress v-if="workflow && (!draftStage || workflow.workflow_definition_version === 3)" :workflow="workflow" :tasks="snapshot?.tasks ?? []" :config="executionConfig" :current-draft-version="snapshot?.chapter.current_version" :can-resume="formal && !disabled && !conflict" @resume="control('resume', '人工继续当前创作流程')" />

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

        <section v-else-if="draftStage && draft">
          <QualityReview :review="qualityReview" :pending="state === 'C09_INTERNAL_REVIEW'" />
          <DraftView :draft="draft" :chapter-number="currentChapter.sequence" @evaluate="evaluationOpen = true" />
        </section>

      </template>
    </main>

    <WritingProfile v-if="profileOpen && projectId" :key="projectId" :project-id="projectId" :disabled="disabled" @close="profileOpen = false" />
    <ManualCaseLoader v-if="testsOpen && manualTestAvailable" :cases="manualCases" :selected-id="loadedCase?.id" :can-load="Boolean(currentChapter && !workflow)" @load="loadCase" @close="closeTests" />
    <HumanEvaluation v-if="evaluationOpen && draft" :project-id="projectId" :chapter-id="chapterId" :workflow-id="workflowId" :draft-version="draft.version" :case-id="evaluationCaseId" @close="evaluationOpen = false" />
    <DebugPanel v-if="snapshot" :snapshot="snapshot" :open="debugOpen" @close="toggleDebug" />
  </div>
</template>
