<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { QualityReview } from '../types/models'
const props = defineProps<{ review: QualityReview }>()
const tags = ref<string[] | null>(null), notes = ref(''), error = ref('')
watch(() => props.review.id, () => { tags.value = null; notes.value = ''; error.value = '' })
const ai = computed(() => [...props.review.body.hard_gate_issues, ...props.review.body.quality_issues].map(i => i.code))
async function read(event: Event) {
  tags.value = null; notes.value = ''; error.value = ''
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    if (file.size > 100_000) throw new Error('评价文件过大')
    const value = JSON.parse(await file.text())
    if (value.schema_version !== 'ux-001.v1' || value.project_id !== props.review.project_id || value.chapter_id !== props.review.chapter_id || value.workflow_id !== props.review.binding.workflow_id || value.draft_version !== props.review.binding.draft_version) throw new Error('人工评价与这份审阅的章节或正文版本不一致')
    if (!Array.isArray(value.failure_tags) || value.failure_tags.length > 100 || !value.failure_tags.every((s: unknown) => typeof s === 'string' && s.length <= 100) || typeof value.notes !== 'string' || value.notes.length > 20_000) throw new Error('评价文件格式不正确')
    tags.value = value.failure_tags; notes.value = value.notes
  } catch (e) { error.value = e instanceof Error ? e.message : '无法读取评价文件' }
}
</script>
<template>
  <section>
    <h3>Human Evaluation 对照</h3>
    <p>仅在本页读取导出的人工评价。标签可帮助比较主题，不按标签完全相同判定对错。</p>
    <label>导入同版本人工评价 JSON<input type="file" accept="application/json,.json" @change="read"></label>
    <p v-if="error" role="alert">{{ error }}</p>
    <dl v-if="tags" class="values"><dt>AI Review</dt><dd>{{ ai.join('、') || '无问题' }}</dd><dt>Human Tags</dt><dd>{{ tags.join('、') || '无标签' }}</dd><dt>Human Notes</dt><dd class="preserve">{{ notes }}</dd></dl>
  </section>
</template>
