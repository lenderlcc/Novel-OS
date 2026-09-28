<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

const props = defineProps<{
  projectId: string
  chapterId: string
  workflowId: string
  draftVersion: number
  caseId?: string | null
}>()
defineEmits<{ close: [] }>()
type Rating = 'GOOD' | 'OK' | 'BAD' | ''
const understanding = ref<Rating>(''), planning = ref<Rating>(''), audience = ref<Rating>('')
const aiFeel = ref<'LOW' | 'MEDIUM' | 'HIGH' | ''>(''), overall = ref<'ACCEPT' | 'REVISE' | 'REJECT' | ''>('')
const notes = ref(''), selectedTags = ref<string[]>([]), exported = ref(false)
const closeButton = ref<HTMLButtonElement | null>(null)
const tags = ['AUDIENCE_STYLE_MISMATCH', 'REQUIREMENT_MISS', 'FORBIDDEN_VIOLATION', 'LOW_AUTONOMY',
  'PLAN_TOO_GENERIC', 'PLAN_OVER_SPECIFIED', 'MAJOR_DIRECTION_VIOLATION', 'KNOWLEDGE_LEAK', 'MECHANICAL_PROSE']
const complete = computed(() => understanding.value && planning.value && audience.value && aiFeel.value && overall.value)
onMounted(() => { void nextTick(() => closeButton.value?.focus()) })
function download() {
  if (!complete.value) return
  const value = {
    schema_version: 'ux-001.v1', created_at: new Date().toISOString(), case_id: props.caseId || null,
    project_id: props.projectId, chapter_id: props.chapterId, workflow_id: props.workflowId,
    draft_version: props.draftVersion,
    ratings: { requirement_understanding: understanding.value, planning_quality: planning.value,
      writing_audience_fit: audience.value, ai_writing_feel: aiFeel.value, overall: overall.value },
    failure_tags: selectedTags.value, notes: notes.value.trim(),
  }
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url; link.download = `${props.caseId || 'manual'}-draft-v${props.draftVersion}-evaluation.json`; link.click()
  URL.revokeObjectURL(url); exported.value = true
}
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <section class="modal evaluation" role="dialog" aria-modal="true" aria-labelledby="evaluation-title">
      <div class="drawer-header"><div><h2 id="evaluation-title">人工评价 · 正文 v{{ draftVersion }}</h2><p>结果将下载为本地 JSON，不会改变正文或 Workflow。</p></div><button ref="closeButton" class="quiet" @click="$emit('close')">关闭</button></div>
      <div class="evaluation-grid">
        <fieldset><legend>需求理解</legend><label v-for="value in (['GOOD','OK','BAD'] as const)" :key="value"><input v-model="understanding" type="radio" name="understanding" :value="value">{{ value }}</label></fieldset>
        <fieldset><legend>方案质量</legend><label v-for="value in (['GOOD','OK','BAD'] as const)" :key="value"><input v-model="planning" type="radio" name="planning" :value="value">{{ value }}</label></fieldset>
        <fieldset><legend>受众匹配</legend><label v-for="value in (['GOOD','OK','BAD'] as const)" :key="value"><input v-model="audience" type="radio" name="audience" :value="value">{{ value }}</label></fieldset>
        <fieldset><legend>AI 写作感</legend><label v-for="value in (['LOW','MEDIUM','HIGH'] as const)" :key="value"><input v-model="aiFeel" type="radio" name="ai-feel" :value="value">{{ value }}</label></fieldset>
        <fieldset><legend>总体结论</legend><label v-for="value in (['ACCEPT','REVISE','REJECT'] as const)" :key="value"><input v-model="overall" type="radio" name="overall" :value="value">{{ value }}</label></fieldset>
      </div>
      <fieldset v-if="caseId" class="failure-tags"><legend>Failure Tags</legend><label v-for="tag in tags" :key="tag"><input v-model="selectedTags" type="checkbox" :value="tag">{{ tag }}</label></fieldset>
      <label for="evaluation-notes">备注</label><textarea id="evaluation-notes" v-model="notes" rows="5" placeholder="记录具体段落、问题和判断依据。" />
      <div class="modal-actions"><span v-if="exported" role="status">评价文件已下载</span><button class="primary" :disabled="!complete" @click="download">导出评价 JSON</button></div>
    </section>
  </div>
</template>
