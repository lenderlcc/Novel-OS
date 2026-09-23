<script setup lang="ts">
import type { Plan, PlanningHistory, Review } from '../types/models'
defineProps<{ plan: Plan; generation: PlanningHistory['plans'][number] | null; review: Review | null }>()

function text(value: unknown): string {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') {
    const item = value as Record<string, unknown>
    for (const key of ['text', 'description', 'scope_description', 'explanation', 'value']) if (typeof item[key] === 'string') return item[key]
  }
  return String(value ?? '')
}
const list = (value: unknown) => Array.isArray(value) ? value.map(text).filter(Boolean) : value ? [text(value)] : []
</script>

<template>
  <article class="plan" data-testid="plan">
    <section class="plan-lead"><h3>目标</h3><p>{{ plan.objective }}</p><h3>必须达成</h3><p>{{ plan.required_outcome }}</p></section>
    <template v-if="generation">
      <section><h3>故事推进</h3><ol class="scene-list">
        <li v-for="(scene, index) in generation.body.scenes" :key="scene.id" class="scene">
          <h4>场景 {{ index + 1 }}</h4>
          <dl class="human-values"><dt>目的</dt><dd>{{ scene.purpose }}</dd><dt>冲突</dt><dd>{{ scene.conflict }}</dd><dt>关键变化</dt><dd>{{ scene.key_change }}</dd></dl>
          <details><summary>场景详情</summary><dl class="human-values"><dt>释放的信息</dt><dd>{{ list(scene.information_release).join('；') || '无' }}</dd><dt>人物变化</dt><dd>{{ text(scene.character_state_change) }}</dd><dt>场景结束状态</dt><dd>{{ scene.exit_condition }}</dd></dl></details>
        </li>
      </ol></section>
      <div class="plan-columns">
        <section><h3>人物变化</h3><ul v-if="list(generation.body.character_progression).length"><li v-for="item in list(generation.body.character_progression)" :key="item">{{ item }}</li></ul><p v-else>由具体场景自然推进。</p></section>
        <section><h3>结尾状态</h3><p>{{ text(generation.body.ending_state) }}</p></section>
        <section><h3>注意事项</h3><ul v-if="list(generation.body.constraints).length"><li v-for="item in list(generation.body.constraints)" :key="item">{{ item }}</li></ul><p v-else>无额外限制。</p></section>
        <section><h3>AI 自由发挥范围</h3><p>{{ text(generation.body.creative_freedom) }}</p></section>
      </div>
    </template>
    <template v-else><section><h3>故事推进</h3><p>该历史方案没有当前 Workflow 的完整展示数据，可在 Debug 中查看原始记录。</p></section></template>
    <p v-if="review" class="review-summary" data-testid="plan-review">方案检查：{{ review.verdict === 'PASS' ? '通过' : review.verdict === 'PASS_WITH_WARNINGS' ? '通过，有提醒' : '需要调整' }}</p>
  </article>
</template>
