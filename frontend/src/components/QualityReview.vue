<script setup lang="ts">
import { computed } from 'vue'
import type { QualityReview } from '../types/models'
const props = defineProps<{ review: QualityReview | null; pending?: boolean; rereviewing?: boolean }>()
const verdicts = { PASS: '通过', PASS_WITH_WARNINGS: '有改进空间', FAIL: '建议修改' }
const issues = computed(() => props.review ? [...props.review.body.hard_gate_issues, ...props.review.body.quality_issues] : [])
const audienceEvidence = computed(() => props.review && 'audience_evidence' in props.review.body ? props.review.body.audience_evidence : [])
const preferenceLabels: Record<string, string> = {
  target_audience: '目标读者', narrative_perspective: '叙述视角', pacing: '节奏',
  narrative_density: '叙事密度', description_density: '描写密度', dialogue_density: '对话密度',
  emotional_explicitness: '情绪显性程度', subtext_level: '潜台词程度', literary_ornamentation: '文学修饰',
  scene_hook_strength: '场景吸引力', chapter_ending_hook: '章末吸引力', relationship_payoff_visibility: '关系变化可感知度',
  exposition_density: '解释密度', naturalness: '自然感', reading_experience: '阅读体验', guidance: '写作指引', avoid_tendencies: '避免的倾向',
}
const preferenceValues: Record<string, string> = {
  FIRST_PERSON: '第一人称', THIRD_PERSON: '第三人称', VERY_LOW: '很低', LOW: '低', LOW_MEDIUM: '偏低',
  MEDIUM: '中等', MEDIUM_HIGH: '偏高', HIGH: '高', VERY_HIGH: '很高', VERY_SLOW: '很慢', SLOW: '慢',
  MEDIUM_SLOW: '偏慢', MEDIUM_FAST: '偏快', FAST: '快', VERY_FAST: '很快',
}
const displayPreference = (value: string | string[]) => Array.isArray(value) ? value.join('；') : preferenceValues[value] ?? value
</script>
<template>
  <section class="quality-review" aria-labelledby="quality-heading">
    <h2 id="quality-heading" tabindex="-1">正文审阅</h2>
    <p v-if="pending" role="status">{{ rereviewing ? 'AI 正在重新审阅…' : 'AI 正在审阅正文…' }} 正文可以先阅读，完成后将自动更新。</p>
    <p v-else-if="!review">这个版本尚无 AI 审阅结果。你可以先进行人工评价。</p>
    <template v-else>
      <p class="muted">Review v{{ review.version }} · 对应 Draft v{{ review.binding.draft_version }}</p>
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
      <details v-if="audienceEvidence.length" class="quality-issue">
        <summary>与已批准写作偏好的冲突</summary>
        <div v-for="item in audienceEvidence" :key="item.profile_field">
          <p><strong>{{ preferenceLabels[item.profile_field] ?? '写作偏好' }}</strong>（已批准 v{{ item.profile_ref.source_version }}）：{{ displayPreference(item.expected) }}</p>
          <p><strong>正文表现：</strong>{{ item.observed }}</p>
          <p><strong>影响：</strong>{{ item.reason }}</p>
        </div>
      </details>
      <template v-if="review.body.strengths.length">
        <h3>值得保留</h3>
        <ul><li v-for="(strength, index) in review.body.strengths" :key="index">{{ strength.description }} {{ strength.preservation_direction }}</li></ul>
      </template>
      <p class="muted">AI 审阅供你判断，人工评价独立保留。正文不会自动修改。</p>
    </template>
  </section>
</template>
