<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ value: unknown }>()
const entries = computed(() => props.value && typeof props.value === 'object'
  ? Object.entries(props.value).filter(([key]) => !['source_ref', 'source_refs', 'logical_id', 'source_id'].includes(key)) : [])
const labels: Record<string, string> = {
  text: '内容', reason: '原因', description: '说明', rationale: '理由', id: '标识', source_refs: '依据',
  allowed: '允许', forbidden: '禁止', level: '级别', scope: '范围', statement: '陈述', evidence: '证据',
  assumption: '假设', ambiguity: '歧义', question: '问题', impact: '影响', risk: '风险',
  user_decision_needed: '需要人工确认', requirement_id: '需求', covered: '已覆盖',
  covered_by: '覆盖方式', status: '状态', coverage: '覆盖情况', scene_ids: '关联场景',
  severity: '严重程度', recommendation: '建议', issue: '问题', type: '类型',
}
</script>
<template>
  <span v-if="value === null || value === undefined || value === ''">—</span>
  <template v-else-if="Array.isArray(value)">
    <span v-if="!value.length" class="muted">无</span>
    <ul v-else><li v-for="(item, index) in value" :key="index"><ValueView :value="item" /></li></ul>
  </template>
  <dl v-else-if="typeof value === 'object'" class="values">
    <template v-for="[key, item] in entries" :key="key"><dt>{{ labels[key] || key }}</dt><dd><ValueView :value="item" /></dd></template>
  </dl>
  <span v-else class="preserve">{{ value === true ? '是' : value === false ? '否' : value }}</span>
</template>
