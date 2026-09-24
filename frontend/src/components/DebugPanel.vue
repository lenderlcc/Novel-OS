<script setup lang="ts">
import { computed, nextTick, onScopeDispose, ref, shallowRef, watch } from 'vue'
import { api } from '../api/console'
import { asError, type ApiError } from '../api/client'
import { writingProfiles, type Profile } from '../api/writingProfiles'
import type { Snapshot } from '../composables/useConsole'
import type { Context, Lineage, Run, Transition } from '../types/models'
import ErrorNotice from './ErrorNotice.vue'
import QualityComparison from './QualityComparison.vue'
const props = defineProps<{ snapshot: Snapshot; open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const loading = ref(false), selectedRun = ref('')
const closeButton = ref<HTMLButtonElement | null>(null)
const error = shallowRef<ApiError | null>(null), context = shallowRef<Context | null>(null), lineage = shallowRef<Lineage | null>(null)
const runs = ref<Run[]>([]), transitions = ref<Transition[]>([])
const profileVersions = ref<Profile[]>([])
let controller = new AbortController(), epoch = 0
const reset = () => { controller.abort(); controller = new AbortController(); return ++epoch }
async function inspect(id: string) {
  const token = reset(); selectedRun.value = id; context.value = null; lineage.value = null; error.value = null
  if (!id || !props.open) { loading.value = false; return }
  loading.value = true
  try {
    const [c, l] = await Promise.all([api.context(id, controller.signal), api.lineage(id, controller.signal)])
    if (token === epoch) { context.value = c; lineage.value = l }
  } catch (err) { if (token === epoch) error.value = asError(err) }
  finally { if (token === epoch) loading.value = false }
}
async function load() {
  const token = reset(); loading.value = false; error.value = null; context.value = null; lineage.value = null
  if (!props.open) return
  loading.value = true
  try {
    const [history, attempts, profiles] = await Promise.all([
      api.transitions(props.snapshot.workflow.id, controller.signal),
      Promise.all(props.snapshot.tasks.map(task => api.runs(task.task_id, controller.signal))),
      writingProfiles.versions(props.snapshot.chapter.project_id, controller.signal),
    ])
    if (token !== epoch) return
    transitions.value = history; runs.value = attempts.flat(); profileVersions.value = profiles
    await inspect(runs.value.some(r => r.run_id === selectedRun.value) ? selectedRun.value : runs.value.at(-1)?.run_id || '')
  } catch (err) { if (token === epoch) error.value = asError(err) }
  finally { if (token === epoch) loading.value = false }
}
watch(() => [props.open, props.snapshot.workflow.id, props.snapshot.workflow.state_version, props.snapshot.tasks.map(t => `${t.task_id}:${t.status}:${t.attempt_count}`).join(',')], load, { immediate: true })
watch(() => props.open, open => { if (open) void nextTick(() => closeButton.value?.focus()) }, { immediate: true })
onScopeDispose(reset)
const pins = computed(() => lineage.value ? [lineage.value.system_policy, lineage.value.agent_role, lineage.value.task_template, ...lineage.value.skills, lineage.value.quality_profile].filter(p => p !== null) : [])
const version = (v: number | null | undefined) => v ? `v${v}` : '无'
const json = (value: unknown) => JSON.stringify(value, null, 2)
</script>
<template>
  <div v-if="open" class="drawer-backdrop" @click.self="emit('close')" @keydown.esc="emit('close')">
    <aside id="debug-section" class="drawer debug-drawer" role="dialog" aria-modal="true" aria-labelledby="debug-title">
      <div class="drawer-header"><div><h2 id="debug-title">Debug</h2><p>Workflow、Agent、Context、Prompt 与原始证据</p></div><button ref="closeButton" class="quiet" @click="emit('close')">关闭</button></div>
      <button :disabled="loading" @click="load">刷新 Debug</button>
      <ErrorNotice v-if="error" :error="error" />
      <details open><summary>Workflow</summary><div class="debug-section">
        <dl class="human-values"><dt>Current State</dt><dd><code>{{ snapshot.workflow.current_state }}</code></dd><dt>State Version</dt><dd>{{ snapshot.workflow.state_version }}</dd><dt>Status</dt><dd>{{ snapshot.workflow.status }}</dd></dl>
        <table data-testid="version-pointers"><thead><tr><th>对象</th><th>Current</th><th>Approved</th></tr></thead><tbody><tr><td>ChapterPlan</td><td>{{ version(snapshot.chapter.current_plan_version) }}</td><td>{{ version(snapshot.chapter.approved_plan_version) }}</td></tr><tr><td>ChapterVersion</td><td>{{ version(snapshot.chapter.current_version) }}</td><td>{{ version(snapshot.chapter.approved_version) }}</td></tr></tbody></table>
        <details><summary>History / Human Gate</summary><pre>{{ json({ transitions, gates: snapshot.gates }) }}</pre></details>
      </div></details>
      <details><summary>Agent</summary><div class="debug-section">
        <h3>Agent Tasks</h3><table><thead><tr><th>Agent / Task</th><th>Type</th><th>Status</th><th>Attempts</th><th>Error</th></tr></thead><tbody><tr v-for="task in snapshot.tasks" :key="task.task_id"><td>{{ task.agent_id }}<br><code>{{ task.task_id }}</code></td><td>{{ task.task_type }}</td><td>{{ task.status }}</td><td>{{ task.attempt_count }} / {{ task.max_attempts }}</td><td>{{ task.last_error_code }} {{ task.last_error_message }}</td></tr></tbody></table>
        <h3>Agent Runs</h3><table><thead><tr><th>Run / Attempt</th><th>Status</th><th>Provider / Model</th><th>Duration</th><th>Error / Disposition</th></tr></thead><tbody><tr v-for="run in runs" :key="run.run_id"><td><button @click="inspect(run.run_id)">Attempt {{ run.attempt_number }}</button><br><code>{{ run.run_id }}</code></td><td>{{ run.status }}</td><td>{{ run.provider || '未调用' }} / {{ run.model || '—' }}</td><td>{{ run.duration_ms ?? '—' }} ms</td><td>{{ run.error_code }} {{ run.error_message }} {{ run.disposition }}</td></tr></tbody></table>
      </div></details>
      <details><summary>Context / Prompt</summary><div class="debug-section">
      <label for="debug-run">查看具体 Run 的 Context / Prompt</label>
      <select id="debug-run" :value="selectedRun" @change="inspect(($event.target as HTMLSelectElement).value)"><option value="">请选择 Run</option><option v-for="run in runs" :key="run.run_id" :value="run.run_id">{{ snapshot.tasks.find(t => t.task_id === run.task_id)?.agent_id }} · Attempt {{ run.attempt_number }} · {{ run.run_id }}</option></select>
      <p v-if="loading" role="status">读取 Debug 数据…</p>
      <h3>ContextPackage Inspector</h3>
      <template v-if="context">
        <dl class="values"><dt>Profile / Version</dt><dd>{{ context.package.profile_id }} v{{ context.package.profile_version }}</dd>
          <dt>Package Hash</dt><dd><code>{{ context.package.package_hash }}</code></dd>
          <dt>Build Status / 当前 Freshness</dt><dd>{{ context.package.build_status }} / {{ context.freshness }} {{ context.error_code }}</dd>
          <dt>Token Budget / Estimated</dt><dd>{{ context.package.token_budget }} / {{ context.package.estimated_tokens }}</dd>
        </dl>
        <p class="muted">Freshness 是当前时刻的校验。历史运行完成后可能变为 STALE；快照仍对应上方选定的 Run。</p>
        <h4>Included Items</h4>
        <table><thead><tr><th>Source / Version</th><th>Priority</th><th>Authority / Status</th><th>Selected Reason</th><th>Payload</th></tr></thead><tbody>
          <tr v-for="item in context.package.items" :key="item.context_item_id"><td>{{ item.source_type }}<br><code>{{ item.source_id }}</code> v{{ item.source_version }}</td><td>{{ item.priority }}</td><td>{{ item.authority_level }} / {{ item.status }}</td><td>{{ item.selected_reason }}</td><td><details><summary>查看内容</summary><pre>{{ item.payload_json }}</pre></details></td></tr>
        </tbody></table>
        <h4>Excluded Items</h4><table><thead><tr><th>Source</th><th>Reason</th></tr></thead><tbody><tr v-for="(item, index) in context.package.excluded_items" :key="index"><td>{{ item.source_type }} {{ item.source_id }} v{{ item.source_version }}</td><td>{{ item.reason }}</td></tr></tbody></table>
        <details><summary>Missing / Conflicts / Full Context JSON</summary><pre>{{ json(context) }}</pre></details>
      </template>
      <p v-else-if="!loading">此 Run 尚无 ContextPackage，或未选择 Run。</p>
      <h3>PromptLineage Inspector</h3>
      <template v-if="lineage">
        <table><thead><tr><th>Module ID</th><th>Version</th><th>Content / Execution Hash</th></tr></thead><tbody><tr v-for="pin in pins" :key="pin.module_id"><td>{{ pin.module_id }}</td><td>{{ pin.version }}</td><td><code>{{ pin.content_hash }}<br>{{ pin.execution_hash }}</code></td></tr></tbody></table>
        <dl class="values"><dt>ModelProfile</dt><dd>{{ lineage.model_profile_id }}<br><code>{{ lineage.model_profile_hash }}</code></dd><dt>Compiled Prompt Hash</dt><dd><code>{{ lineage.compiled_prompt_hash }}</code></dd></dl>
        <details><summary>ModelProfile / PromptLineage JSON</summary><pre>{{ json(lineage) }}</pre></details>
      </template>
      <p v-else-if="!loading">此 Run 尚无 PromptLineage，或未选择 Run。</p>
      </div></details>
      <details><summary>Chapter Quality Reviews</summary><div v-for="record in snapshot.qualityReviews ?? []" :key="record.id" class="debug-section"><h3>Review v{{ record.version }} / {{ record.freshness }}</h3><QualityComparison :review="record" /><details><summary>QualityIssue / Evidence / Binding / Lineage JSON</summary><pre>{{ json(record) }}</pre></details></div></details>
      <details><summary>Artifacts / Raw JSON</summary><div class="debug-section"><details><summary>CreativeBrief / Plan / Review</summary><pre>{{ json({ brief: snapshot.brief, plans: snapshot.plans, planning: snapshot.history }) }}</pre></details><details><summary>WritingResult / ChapterVersion</summary><pre>{{ json({ writing: snapshot.writing, drafts: snapshot.drafts }) }}</pre></details><details><summary>WritingProfile Versions</summary><pre>{{ json(profileVersions) }}</pre></details><details><summary>Workflow / Tasks / Runs</summary><pre>{{ json({ workflow: snapshot.workflow, gates: snapshot.gates, tasks: snapshot.tasks, runs }) }}</pre></details></div></details>
    </aside>
  </div>
</template>
