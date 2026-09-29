<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Draft } from '../types/models'
import type { Snapshot } from '../composables/useConsole'
import { isStaleFeedback } from '../composables/workflowState'
const props = defineProps<{ snapshot: Snapshot; draft: Draft; disabled: boolean }>()
const emit = defineEmits<{ send: [text: string, replyTo?: string]; openProfile: []; replan: [text: string]; cancel: []; discard: [] }>()
const open = ref(false), text = ref(''), replanOpen = ref(false), requirement = ref('')
const replyTo = ref<string>()
const historical = computed(() => props.draft.version !== props.snapshot.chapter.current_version)
const active = computed(() => Boolean(props.snapshot.workflow.human_feedback_id || props.snapshot.workflow.revision_request_id))
const canSend = computed(() => !historical.value && !active.value && props.snapshot.workflow.status === 'WAITING_HUMAN' && ['C10_REVISION', 'C11_INTERNAL_PASS'].includes(props.snapshot.workflow.current_state))
const history = computed(() => (props.snapshot.feedback ?? []).filter(item => item.feedback.source_chapter_version_id === props.draft.id))
const result = computed(() => history.value[0]?.interpretation?.body)
const source = computed(() => {
  const revision = props.snapshot.revisions?.find(r => r.result?.chapter_version_id === props.draft.id)
  return props.snapshot.feedback?.find(f => f.feedback.id === revision?.request.source_feedback_id)
})
const failed = computed(() => props.snapshot.workflow.human_feedback_id && ['FAILED', 'BLOCKED'].includes(props.snapshot.workflow.status))
const stale = computed(() => isStaleFeedback(props.snapshot.workflow, props.snapshot.tasks))
const canDiscard = computed(() => Boolean(props.snapshot.workflow.human_feedback_id) && ['WAITING_AGENT', 'PAUSED', 'BLOCKED'].includes(props.snapshot.workflow.status))
const canCancel = computed(() => !canDiscard.value && active.value && ['WAITING_AGENT', 'PAUSED', 'BLOCKED'].includes(props.snapshot.workflow.status))
function resetForm() { open.value = false; text.value = ''; replyTo.value = undefined }
watch(() => props.snapshot.feedback?.length, (value, old) => { if (value !== old) resetForm() })
watch(() => props.draft.id, () => { resetForm(); replanOpen.value = false })
function openFeedback(clarification = false) { replyTo.value = clarification ? history.value[0]?.feedback.id : undefined; text.value = ''; open.value = true }
function openReplan() { requirement.value = props.snapshot.brief?.raw_requirement ?? ''; replanOpen.value = true }
</script>
<template>
  <section class="quality-review" aria-label="用户反馈修改">
    <p v-if="source">用户反馈修改 · 来源：{{ source.feedback.raw_feedback }}</p>
    <p v-if="historical" class="muted">历史正文只读。返回当前版本后，可以提出新的修改要求。</p>
    <p v-if="stale" role="status">正文或写作依据已变化。放弃本次反馈后，可以根据当前正文重新提交。</p>
    <p v-else-if="failed" role="status">暂时无法理解这条修改要求。现有正文已保留；可在 Debug 查看原因。</p>
    <p v-else-if="snapshot.workflow.current_state === 'C13_USER_FEEDBACK_DIAGNOSIS'" role="status">正在理解你的反馈…</p>
    <template v-if="result && !historical && !active">
      <div v-if="result.action === 'REPLAN_REQUIRED'" class="notice"><p>这个要求会改变已批准的章节方案。</p><p>{{ result.user_message }}</p><button :disabled="disabled || !canSend" @click="openReplan">修改章节方向</button></div>
      <div v-else-if="result.action === 'PROFILE_CHANGE_REQUIRED'" class="notice"><p>这个要求属于项目写作偏好修改。</p><p>{{ result.user_message }}</p><button :disabled="disabled" @click="emit('openProfile')">打开写作偏好</button></div>
      <div v-else-if="result.action === 'USER_DECISION_REQUIRED'" class="notice"><p>{{ result.user_message }}</p><p>{{ result.decision_question }}</p><p v-if="result.conflicts.some(c => c.boundary === 'LOCK')">这个方向当前已锁定。需要先解除锁定后才能修改。</p><button :disabled="disabled || !canSend" @click="openFeedback(true)">补充修改要求</button></div>
      <p v-else-if="result.action === 'NO_CHANGE'">{{ result.user_message }} 本次未修改正文。</p>
    </template>
    <form v-if="replanOpen && canSend" @submit.prevent="emit('replan', requirement)">
      <label for="feedback-replan">调整章节需求</label><p>这会返回已有方案流程，重新生成并审批方案。原有正文会保留。请在原需求中明确新的方向。</p>
      <textarea id="feedback-replan" v-model="requirement" rows="8" maxlength="12000" required :disabled="disabled" />
      <button class="primary" :disabled="disabled || !requirement.trim()">提交新方向并重新规划</button>
    </form>
    <button v-if="canSend && !open" :disabled="disabled" @click="openFeedback()">我想修改</button>
    <form v-if="open && canSend" @submit.prevent="replyTo ? emit('send', text, replyTo) : emit('send', text)">
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
