<script setup lang="ts">
import { computed } from 'vue'
import type { Revision } from '../types/models'
const props = defineProps<{ record: Revision }>()
const plan = computed(() => {
  const body = props.record.plan?.body
  return body && 'revision_zones' in body ? body : null
})
const fidelity = computed(() => props.record.result?.body.fidelity)
const json = (value: unknown) => JSON.stringify(value, null, 2)
</script>
<template>
  <section class="debug-section" aria-label="Revision Fidelity">
    <h3>Source Fidelity: {{ fidelity?.verdict ?? '尚无结果' }}</h3>
    <template v-if="plan">
      <dl class="values"><dt>Revision Scope</dt><dd>{{ plan.scope }} / {{ plan.allowed_structural_change }}</dd><dt>CHANGE BUDGET</dt><dd>{{ plan.change_budget }}</dd></dl>
      <h4>KEEP</h4>
      <ul><li v-for="element in [...plan.preserve_scene_elements, ...plan.preserve_relationship_elements, ...plan.preserve_effective_details]" :key="element.element_id">{{ element.description }}</li></ul>
      <h4>Preserved Strengths</h4>
      <ul><li v-for="strength in plan.strength_preservation" :key="strength.strength_id">{{ strength.strength_id }} · {{ strength.mode }} · {{ strength.preservation_direction }}</li></ul>
      <h4>CHANGE</h4><ul><li v-for="target in plan.revision_targets" :key="target.issue_id">{{ target.problem }}：{{ target.revision_direction }}</li></ul>
      <h4>DO NOT CHANGE</h4><pre>{{ json(record.request.contract.do_not_change) }}</pre>
      <h4>REVISION ZONES</h4><ul><li v-for="(zone, index) in plan.revision_zones" :key="index">{{ zone.semantic_range }}<template v-if="zone.paragraph_start">（{{ zone.paragraph_start }}–{{ zone.paragraph_end }}）</template></li></ul>
      <details><summary>Strength Regression Risks / Structural Authorization</summary><pre>{{ json({ risks: plan.strength_regression_risks, authorization: plan.structural_authorization }) }}</pre></details>
    </template>
    <template v-if="fidelity">
      <ul><li v-for="(violation, index) in fidelity.violations" :key="index">{{ violation.code }} · {{ violation.check_ids.join(', ') }}：{{ violation.description }}</li></ul>
      <details><summary>Preserve Checks / Evidence / Affected Strengths</summary><pre>{{ json(fidelity.checks) }}</pre></details>
    </template>
  </section>
</template>
