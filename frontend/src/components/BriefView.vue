<script setup lang="ts">
import type { Brief } from '../types/models'
defineProps<{ brief: Brief }>()

function text(value: unknown): string {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') {
    const item = value as Record<string, unknown>
    for (const key of ['text', 'description', 'scope_description', 'value', 'issue']) if (typeof item[key] === 'string') return item[key]
  }
  return String(value ?? '')
}
const list = (value: unknown) => Array.isArray(value) ? value.map(text).filter(Boolean) : value ? [text(value)] : []
</script>

<template>
  <section class="brief-summary" data-testid="brief">
    <h2>AI 对需求的理解</h2>
    <div class="brief-content">
      <section><h3>目标</h3><p>{{ brief.body.chapter_objective }}</p></section>
      <section v-if="list(brief.body.must).length"><h3>必须做到</h3><ul><li v-for="item in list(brief.body.must)" :key="item">{{ item }}</li></ul></section>
      <section v-if="list(brief.body.forbidden).length"><h3>不能发生</h3><ul><li v-for="item in list(brief.body.forbidden)" :key="item">{{ item }}</li></ul></section>
      <section v-if="list(brief.body.preferences).length"><h3>偏好</h3><ul><li v-for="item in list(brief.body.preferences)" :key="item">{{ item }}</li></ul></section>
      <section><h3>AI 可以自由发挥</h3><p>{{ text(brief.body.creative_freedom) }}</p></section>
      <details class="brief-details">
        <summary>查看详细理解</summary>
        <dl class="human-values">
          <dt>创作意图</dt><dd>{{ brief.body.intent_summary }}</dd>
          <dt>必须达成</dt><dd>{{ brief.body.required_outcome }}</dd>
          <dt>读者感受</dt><dd>{{ brief.body.desired_reader_effect }}</dd>
          <dt>应该做到</dt><dd><ul v-if="list(brief.body.should).length"><li v-for="item in list(brief.body.should)" :key="item">{{ item }}</li></ul><span v-else>无</span></dd>
          <dt>假设</dt><dd><ul v-if="list(brief.body.assumptions).length"><li v-for="item in list(brief.body.assumptions)" :key="item">{{ item }}</li></ul><span v-else>无</span></dd>
          <dt>待澄清</dt><dd><ul v-if="list(brief.body.unresolved_ambiguities).length"><li v-for="item in list(brief.body.unresolved_ambiguities)" :key="item">{{ item }}</li></ul><span v-else>无</span></dd>
        </dl>
      </details>
    </div>
  </section>
</template>
