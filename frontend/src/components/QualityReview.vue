<script setup lang="ts">
import { computed } from 'vue'
import type { QualityReview } from '../types/models'
const props = defineProps<{ review: QualityReview | null; pending?: boolean }>()
const verdicts = { PASS: '通过', PASS_WITH_WARNINGS: '有改进空间', FAIL: '建议修改' }
const issues = computed(() => props.review ? [...props.review.body.hard_gate_issues, ...props.review.body.quality_issues] : [])
</script>
<template>
  <section class="quality-review" aria-labelledby="quality-heading">
    <h2 id="quality-heading">正文审阅</h2>
    <p v-if="!review">{{ pending ? '正在检查约束、叙事和受众匹配。正文可以先阅读，完成后将自动更新。' : '这个版本尚无 AI 审阅结果。你可以先进行人工评价。' }}</p>
    <template v-else>
      <p v-if="review.freshness === 'STALE'" role="status">这份审阅的依据已变化，仅供历史参考。</p>
      <h3>{{ verdicts[review.body.overall_verdict] }}</h3>
      <p class="quality-dimensions">约束：{{ verdicts[review.body.compliance_verdict] }} · 叙事：{{ verdicts[review.body.narrative_verdict] }} · 受众：{{ verdicts[review.body.audience_fit_verdict] }}</p>
      <template v-if="issues.length">
        <h3>主要问题</h3>
        <details v-for="issue in issues" :key="issue.code" class="quality-issue">
          <summary>{{ issue.title }}</summary>
          <p>{{ issue.description }}</p>
          <blockquote v-for="(evidence, index) in issue.evidence" :key="index"><p>{{ evidence.excerpt }}</p><p class="muted">{{ evidence.reason }}</p></blockquote>
          <p><strong>影响：</strong>{{ issue.impact }}</p>
          <p><strong>建议方向：</strong>{{ issue.revision_direction }}</p>
        </details>
      </template>
      <p v-else>本轮审阅未发现需要指出的问题。</p>
      <template v-if="review.body.strengths.length">
        <h3>值得保留</h3>
        <ul><li v-for="(strength, index) in review.body.strengths" :key="index">{{ strength.description }} {{ strength.preservation_direction }}</li></ul>
      </template>
      <p class="muted">AI 审阅供你判断，人工评价独立保留。正文不会自动修改。</p>
    </template>
  </section>
</template>
