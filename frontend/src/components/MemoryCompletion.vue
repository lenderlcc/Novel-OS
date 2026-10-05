<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Draft, MemoryHistory, Workflow } from '../types/models'

const props = defineProps<{ workflow: Workflow; draft: Draft; currentVersion: number | null; memory?: MemoryHistory; disabled: boolean }>()
const emit = defineEmits<{ request: []; confirm: [ids: string[]]; discard: [] }>()
const selected = ref<string[]>([])
const candidates = computed(() => props.memory?.proposal?.candidates ?? [])
const pending = computed(() => Boolean(props.workflow.memory_request_id) && props.workflow.status !== 'COMPLETED')
const completed = computed(() => props.workflow.status === 'COMPLETED' && props.memory?.status === 'COMMITTED')
const exactSource = computed(() => props.draft.id === props.memory?.request.chapter_version_id)
const stopped = computed(() => ['BLOCKED', 'FAILED', 'CANCELLED', 'PAUSED'].includes(props.workflow.status))
const canRequest = computed(() => props.draft.version === props.currentVersion && props.workflow.status === 'WAITING_HUMAN' && ['C10_REVISION', 'C11_INTERNAL_PASS'].includes(props.workflow.current_state) && !props.workflow.revision_request_id && !props.workflow.human_feedback_id && !pending.value)
const blocked = (status: string) => ['CONTRADICTION', 'AUTHORITY_CONFLICT', 'AMBIGUOUS'].includes(status)
const conflictCount = computed(() => candidates.value.filter(c => selected.value.includes(c.id) && blocked(c.conflict_status)).length)
const groups = [
  ['CANON_FACT', '重要事实'], ['CHARACTER_STATE', '人物状态'], ['CHARACTER_KNOWLEDGE', '人物认知'],
  ['RELATIONSHIP_STATE', '关系变化'], ['OPEN_THREAD', '待处理事项'],
] as const
const epistemic: Record<string, string> = { KNOWS: '知道', BELIEVES: '相信', SUSPECTS: '怀疑', DOUBTS: '存疑' }
watch(() => props.memory?.proposal?.id, () => {
  selected.value = candidates.value.filter(c => !blocked(c.conflict_status)).map(c => c.id)
}, { immediate: true })
</script>

<template>
  <section v-if="canRequest || pending || completed" class="quality-review memory-completion" aria-label="完成本章">
    <template v-if="completed"><h2>章节已完成。</h2><p>已确认的记忆已保存，后续章节可以使用。此章节的正文版本已固定。</p></template>
    <template v-else-if="pending">
      <h2>{{ memory?.proposal ? '本章将记住' : '整理本章记忆' }}</h2>
      <p v-if="memory?.status === 'STALE'" role="status">正文或已有设定已变化。请返回后重新整理，本次候选尚未写入。</p>
      <p v-else-if="stopped" role="status">暂时无法整理本章记忆。现有正文和长期记忆均已保留。</p>
      <p v-else-if="!memory?.proposal" role="status">AI 正在整理本章需要记住的信息…</p>
      <template v-else>
        <p v-if="!exactSource" role="status">正在查看历史正文。请返回正文 v{{ memory.request.draft_version }} 后确认本章记忆。</p>
        <p>只勾选你希望后续章节记住的内容。不确定的项目可以取消，或返回正文处理。</p>
        <p v-if="!candidates.length">本章没有需要新增的长期记忆，仍可确认完成。</p>
        <template v-for="[type, label] in groups" :key="type">
          <fieldset v-if="candidates.some(c => c.candidate_type === type)"><legend>{{ label }}</legend>
            <div v-for="candidate in candidates.filter(c => c.candidate_type === type)" :key="candidate.id" class="memory-item">
              <label class="memory-choice"><input v-model="selected" type="checkbox" :value="candidate.id" :disabled="disabled" />
                <span><template v-if="candidate.epistemic_status">{{ candidate.subject_ref?.name }} · {{ epistemic[candidate.epistemic_status] }}：</template>{{ candidate.statement }}</span>
              </label>
              <div v-if="blocked(candidate.conflict_status)" class="notice" role="status"><p>{{ candidate.conflict_reason }}</p><p v-if="candidate.previous_statement">已有设定：{{ candidate.previous_statement }}</p><p>本章产生：{{ candidate.statement }}</p><p>取消勾选可保留已有设定；也可以返回正文修改。</p></div>
              <p v-else-if="candidate.conflict_status === 'DUPLICATE'" class="muted">已有相同记忆，将跳过重复项。</p>
            </div>
          </fieldset>
        </template>
        <details v-if="candidates.some(c => c.candidate_type === 'DERIVED_CHAPTER_SUMMARY')"><summary>章节摘要</summary><label v-for="candidate in candidates.filter(c => c.candidate_type === 'DERIVED_CHAPTER_SUMMARY')" :key="candidate.id" class="memory-choice"><input v-model="selected" type="checkbox" :value="candidate.id" :disabled="disabled" /><span>{{ candidate.statement }}</span></label><p class="muted">摘要用于后续检索，不会替代已确认的事实。</p></details>
        <p v-if="conflictCount" role="status">有 {{ conflictCount }} 项设定冲突尚未处理。</p>
        <button class="primary" :disabled="disabled || !exactSource || conflictCount > 0 || memory.status !== 'PROPOSED'" @click="emit('confirm', selected)">确认并完成</button>
      </template>
      <button v-if="!['COMPLETED', 'CANCELLED', 'FAILED'].includes(workflow.status)" :disabled="disabled" @click="emit('discard')">返回正文</button>
    </template>
    <template v-else-if="canRequest"><button :disabled="disabled" @click="emit('request')">完成本章</button><p class="muted">AI 会先整理长期记忆，由你确认后保存。此操作会调用模型。</p></template>
  </section>
</template>

<style scoped>
.memory-completion fieldset { border: 0; padding: 0; margin: 1.5rem 0; }
.memory-completion legend { font-weight: 600; margin-bottom: .5rem; }
.memory-choice { display: flex; align-items: baseline; gap: .6rem; font-weight: normal; }
.memory-choice input { width: auto; flex: 0 0 auto; }
.memory-item { margin: .8rem 0; }
.memory-completion button + button { margin-left: .75rem; }
</style>
