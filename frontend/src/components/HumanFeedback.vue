<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Draft, ExecutionConfig } from '../types/models'
import type { Snapshot } from '../composables/useConsole'
import { currentTask, isStaleFeedback } from '../composables/workflowState'
const props = defineProps<{ snapshot: Snapshot; draft: Draft; disabled: boolean; config?: ExecutionConfig | null }>()
const emit = defineEmits<{ send: [text: string, replyTo?: string]; openProfile: []; replan: [text: string]; cancel: []; discard: [] }>()
const open = ref(false), text = ref(''), replanOpen = ref(false), requirement = ref('')
const replyTo = ref<string>()
const historical = computed(() => props.draft.version !== props.snapshot.chapter.current_version || !props.snapshot.drafts.some(draft => draft.id === props.draft.id && draft.version === props.snapshot.chapter.current_version))
const active = computed(() => {
  const workflow = props.snapshot.workflow
  if (workflow.human_feedback_id) return true
  if (!workflow.revision_request_id) return false
  const revision = props.snapshot.revisions?.find(item => item.request.id === workflow.revision_request_id)
  return !revision || revision.request.workflow_id !== workflow.id || revision.request.project_id !== props.snapshot.chapter.project_id ||
    revision.request.chapter_id !== props.snapshot.chapter.id || revision.result?.chapter_version_id !== props.draft.id
})
const runningTask = computed(() => props.snapshot.tasks.some(task => task.workflow_instance_id === props.snapshot.workflow.id && ['CLAIMED', 'RUNNING'].includes(task.status)))
const feedbackStage = computed(() => {
  const workflow = props.snapshot.workflow
  if (workflow.simulation || workflow.workflow_definition_id !== 'chapter-planning' || ![3, 4].includes(workflow.workflow_definition_version)) return false
  return (['C10_REVISION', 'C11_INTERNAL_PASS'].includes(workflow.current_state) && workflow.status === 'WAITING_HUMAN') ||
    (workflow.current_state === 'C09_INTERNAL_REVIEW' && (workflow.status === 'WAITING_AGENT' || (workflow.status === 'PAUSED' && workflow.resume_state === 'C09_INTERNAL_REVIEW')))
})
const canSend = computed(() => !historical.value && !active.value && !runningTask.value && !props.snapshot.workflow.memory_request_id && feedbackStage.value)
const unavailableReason = computed(() => {
  const workflow = props.snapshot.workflow
  if (historical.value) return '历史正文只读。返回当前版本后，可以提出新的修改要求。'
  if (workflow.status === 'COMPLETED' || workflow.current_state === 'C16_COMPLETED') return '章节已完成，当前不能提交修改意见。'
  if (workflow.memory_request_id || ['C14_MEMORY_PREPARATION', 'C15_MEMORY_COMMIT'].includes(workflow.current_state)) return '本章正在整理或确认记忆，暂不能提交修改意见。'
  if (active.value || workflow.current_state === 'C13_USER_FEEDBACK_DIAGNOSIS' || (workflow.current_state === 'C10_REVISION' && workflow.status === 'WAITING_AGENT')) return '当前反馈或正文修改尚未结束，暂不能提交新的修改意见。'
  if (runningTask.value) return '后台任务已领取或正在执行。请等待任务结束，再提交修改意见。'
  if (!feedbackStage.value) return '当前阶段暂不能提交修改意见。请先返回当前正文的审阅阶段。'
  if (props.disabled) return '正在同步正文状态，暂不能提交修改意见。'
  return ''
})
const history = computed(() => (props.snapshot.feedback ?? []).filter(item => item.feedback.source_chapter_version_id === props.draft.id))
const result = computed(() => history.value[0]?.interpretation?.body)
const source = computed(() => {
  const revision = props.snapshot.revisions?.find(r => r.result?.chapter_version_id === props.draft.id)
  return props.snapshot.feedback?.find(f => f.feedback.id === revision?.request.source_feedback_id)
})
const failed = computed(() => props.snapshot.workflow.human_feedback_id && ['FAILED', 'BLOCKED'].includes(props.snapshot.workflow.status))
const stale = computed(() => isStaleFeedback(props.snapshot.workflow, props.snapshot.tasks))
const feedbackProgress = computed(() => {
  const workflow = props.snapshot.workflow
  if (workflow.status === 'PAUSED') return '修改意见处理已暂停，现有正文已保留。'
  if (workflow.status !== 'WAITING_AGENT') return '修改意见尚未开始处理。请刷新查看流程状态。'
  const task = currentTask(workflow, props.snapshot.tasks)
  if (!task) return '修改意见已提交，等待任务调度。'
  if (task.status === 'PENDING') {
    if (props.config?.task_types && !props.config.task_types.includes(task.task_type)) return '当前阶段未在本机执行范围内，任务会保持等待。请调整设置后刷新。'
    return task.attempt_count > 0 ? '修改意见等待后台重试，当前没有模型任务在执行。' : '修改意见已提交，等待后台执行。'
  }
  if (task.status === 'CLAIMED') return '后台已领取修改意见任务，正在准备执行。'
  if (task.status === 'RUNNING' && task.task_type === 'INTERPRET_CHAPTER_FEEDBACK') return '正在理解你的反馈…'
  return '修改意见任务已结束，正在同步流程状态。'
})
const canDiscard = computed(() => Boolean(props.snapshot.workflow.human_feedback_id) && ['WAITING_AGENT', 'PAUSED', 'BLOCKED'].includes(props.snapshot.workflow.status))
const canCancel = computed(() => !canDiscard.value && active.value && ['WAITING_AGENT', 'PAUSED', 'BLOCKED'].includes(props.snapshot.workflow.status))
function resetForm() { open.value = false; text.value = ''; replyTo.value = undefined }
watch(() => props.snapshot.feedback?.length, (value, old) => { if (value !== old) resetForm() })
watch(() => props.draft.id, () => { resetForm(); replanOpen.value = false })
function openFeedback(clarification = false) {
  if (props.disabled || !canSend.value) return
  replyTo.value = clarification ? history.value[0]?.feedback.id : undefined; text.value = ''; open.value = true
}
function sendFeedback() {
  if (props.disabled || !canSend.value || !text.value.trim()) return
  if (replyTo.value) emit('send', text.value, replyTo.value)
  else emit('send', text.value)
}
function openReplan() {
  if (props.disabled || !canSend.value) return
  requirement.value = props.snapshot.brief?.raw_requirement ?? ''; replanOpen.value = true
}
</script>
<template>
  <section class="quality-review" aria-label="用户反馈修改">
    <details v-if="source"><summary>查看本次修改的原始意见</summary><p class="feedback-raw">{{ source.feedback.raw_feedback }}</p></details>
    <p v-if="unavailableReason" role="status">{{ unavailableReason }}</p>
    <p v-if="stale" role="status">正文或写作依据已变化。放弃本次反馈后，可以根据当前正文重新提交。</p>
    <p v-else-if="failed" role="status">暂时无法理解这条修改要求。现有正文已保留；可在 Debug 查看原因。</p>
    <p v-else-if="snapshot.workflow.current_state === 'C13_USER_FEEDBACK_DIAGNOSIS'" role="status">{{ feedbackProgress }}</p>
    <template v-if="result && !historical && !active">
      <div v-if="result.action === 'REPLAN_REQUIRED'" class="notice"><p>这个要求会改变已批准的章节方案。</p><p>{{ result.user_message }}</p><button :disabled="disabled || !canSend" @click="openReplan">修改章节方向</button></div>
      <div v-else-if="result.action === 'PROFILE_CHANGE_REQUIRED'" class="notice"><p>这个要求属于项目写作偏好修改。</p><p>{{ result.user_message }}</p><button :disabled="disabled" @click="emit('openProfile')">打开写作偏好</button></div>
      <div v-else-if="result.action === 'USER_DECISION_REQUIRED'" class="notice"><p>{{ result.user_message }}</p><p>{{ result.decision_question }}</p><p v-if="result.conflicts.some(c => c.boundary === 'LOCK')">这个方向当前已锁定。需要先解除锁定后才能修改。</p><button :disabled="disabled || !canSend" @click="openFeedback(true)">补充修改要求</button></div>
      <p v-else-if="result.action === 'NO_CHANGE'">{{ result.user_message }} 本次未修改正文。</p>
    </template>
    <form v-if="replanOpen && canSend" @submit.prevent="!disabled && requirement.trim() && emit('replan', requirement)">
      <label for="feedback-replan">调整章节需求</label><p>这会返回已有方案流程，重新生成并审批方案。原有正文会保留。请在原需求中明确新的方向。</p>
      <textarea id="feedback-replan" v-model="requirement" rows="8" maxlength="12000" required :disabled="disabled" />
      <button class="primary" :disabled="disabled || !requirement.trim()">提交新方向并重新规划</button>
    </form>
    <button v-if="!open && !historical" :disabled="disabled || !canSend" @click="openFeedback()">根据我的意见修改</button>
    <form v-if="open && canSend" @submit.prevent="sendFeedback">
      <label for="human-feedback">告诉 AI 哪里不满意，也可以说哪些地方不要动。</label>
      <p v-if="replyTo">补充回答会结合原修改要求处理，已有的保留要求仍然有效。</p>
      <textarea id="human-feedback" v-model="text" rows="5" maxlength="12000" required :disabled="disabled" placeholder="后半段对白还是有点程序化，前面不用动。" />
      <div class="reader-actions"><button class="primary" :disabled="disabled || !text.trim()">发送并修改</button><button type="button" :disabled="disabled" @click="open = false">收起</button><p>完成一次修改和重新审阅后停止。真实模型会消耗 API 额度。</p></div>
    </form>
    <button v-if="canDiscard" :disabled="disabled" @click="emit('discard')">放弃本次反馈，返回当前正文</button>
    <button v-if="canCancel" :disabled="disabled" @click="emit('cancel')">取消本次流程</button>
    <details v-if="history.length"><summary>反馈记录</summary><div v-for="item in history" :key="item.feedback.id"><p>针对正文 v{{ item.feedback.source_draft_version }}</p><p class="feedback-raw">{{ item.feedback.raw_feedback }}</p><p v-if="item.interpretation">{{ item.interpretation.body.user_message }}</p></div></details>
  </section>
</template>
<style scoped>
textarea { width: 100%; margin: 0.75rem 0; }
.feedback-raw { white-space: pre-wrap; }
</style>
