<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { characterProfiles, type Behavior, type Character, type CharacterProfile, type CharacterProfileState, type CharacterState } from '../api/characterProfiles'
import { api } from '../api/console'
import { ApiError, asError } from '../api/client'
import type { Context, Lineage, Run, Task } from '../types/models'
import ErrorNotice from './ErrorNotice.vue'

const props = defineProps<{ projectId: string; disabled?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const characters = ref<Character[]>([]), characterId = ref('')
const state = ref<CharacterProfileState | null>(null), versions = ref<CharacterProfile[]>([])
const currentStates = ref<CharacterState[]>([]), statesLoading = ref(false), statesError = ref<ApiError | null>(null)
const busy = ref(false), interpreting = ref(false), error = ref<ApiError | null>(null), changed = ref(false)
const closeButton = ref<HTMLButtonElement | null>(null)
const debugOpen = ref(false), debugLoading = ref(false), debugError = ref<ApiError | null>(null)
const interpretations = ref<Task[]>([]), reportRuns = ref<Run[]>([]), reportTaskId = ref(''), reportRunId = ref('')
const reportContext = ref<Context | null>(null), reportLineage = ref<Lineage | null>(null)
const reportTask = computed(() => interpretations.value.find(task => task.task_id === reportTaskId.value))
const reportRun = computed(() => reportRuns.value.find(run => run.run_id === reportRunId.value))
let debugController = new AbortController(), debugEpoch = 0
const form = ref<Behavior>({}), text = ref(''), name = ref(''), aliases = ref('')
const common = [
  ['decision_tendency', '决策习惯'], ['conflict_response', '冲突反应'],
  ['communication_style', '表达方式'], ['emotional_defense', '情绪防御'], ['attention_bias', '关注倾向'],
] as const
const advanced = [['self_image', '自我认知'], ['vulnerability', '容易失衡的情境']] as const
const arrayFields = [
  ['default_assumptions', '习惯性的假设'], ['avoids_saying_directly', '不愿直接说的事'],
  ['behavioral_tells', '可能出现的行为'], ['guidance', '补充指导'], ['avoid_tendencies', '应避免的倾向'],
] as const
type ArrayField = typeof arrayFields[number][0]
const lists = ref<Record<ArrayField, string>>({ default_assumptions: '', avoids_saying_directly: '', behavioral_tells: '', guidance: '', avoid_tendencies: '' })
type RelationshipForm = { other_character_id: string; interaction_tendency: string; trust_expression: string; conflict_pattern: string; things_left_unsaid: string; guidance: string }
const relationships = ref<RelationshipForm[]>([])
const riskLabels: Record<string, string> = { LOW: '低', MEDIUM: '中等', HIGH: '高' }
const statusLabels: Record<string, string> = { DRAFT: '草稿', APPROVED: '已批准', SUPERSEDED: '已被替代' }
const selectedCharacter = computed(() => characters.value.find(c => c.id === characterId.value))
const otherCharacters = computed(() => characters.value.filter(c => c.id !== characterId.value))
const summary = computed(() => state.value?.approved ?? state.value?.current ?? null)
const locked = computed(() => props.disabled || busy.value || !state.value)
let controller = new AbortController(), epoch = 0, disposed = false
function nextRead() { controller.abort(); controller = new AbortController(); return ++epoch }
function current(token: number, project: string, character = characterId.value) {
  return !disposed && token === epoch && project === props.projectId && character === characterId.value
}
function nextDebugRead() { debugController.abort(); debugController = new AbortController(); return ++debugEpoch }
function clearDebug() {
  nextDebugRead(); debugLoading.value = false; debugError.value = null; interpretations.value = []; reportRuns.value = []
  reportTaskId.value = ''; reportRunId.value = ''; reportContext.value = null; reportLineage.value = null
}
function currentDebug(token: number, project: string, character: string) {
  return !disposed && debugOpen.value && token === debugEpoch && project === props.projectId && character === characterId.value
}
async function loadInterpretations() {
  clearDebug()
  const token = debugEpoch, project = props.projectId, character = characterId.value
  if (!debugOpen.value || !character) return
  debugLoading.value = true
  try {
    const tasks = await characterProfiles.interpretations(project, character, debugController.signal)
    if (!currentDebug(token, project, character)) return
    if (tasks.some(task => task.project_id !== project || task.report_character_id !== character)) throw new ApiError('INVALID_RESPONSE', '解读记录与所选人物不匹配。')
    interpretations.value = tasks
  } catch (value) { if (currentDebug(token, project, character)) debugError.value = asError(value) }
  finally { if (currentDebug(token, project, character)) debugLoading.value = false }
}
async function inspectReportTask(taskId: string) {
  if (!interpretations.value.some(task => task.task_id === taskId)) return
  const token = nextDebugRead(), project = props.projectId, character = characterId.value
  reportTaskId.value = taskId; reportRunId.value = ''; reportRuns.value = []; reportContext.value = null; reportLineage.value = null
  debugLoading.value = true; debugError.value = null
  try {
    const runs = await api.runs(taskId, debugController.signal)
    if (!currentDebug(token, project, character)) return
    if (runs.some(run => run.task_id !== taskId)) throw new ApiError('INVALID_RESPONSE', 'Run 与所选解读任务不匹配。')
    reportRuns.value = runs
  } catch (value) { if (currentDebug(token, project, character)) debugError.value = asError(value) }
  finally { if (currentDebug(token, project, character)) debugLoading.value = false }
}
async function inspectReportRun(runId: string) {
  if (!reportRuns.value.some(run => run.run_id === runId)) return
  const token = nextDebugRead(), project = props.projectId, character = characterId.value, taskId = reportTaskId.value
  reportRunId.value = runId; reportContext.value = null; reportLineage.value = null; debugLoading.value = true; debugError.value = null
  try {
    const [context, lineage] = await Promise.all([api.context(runId, debugController.signal), api.lineage(runId, debugController.signal)])
    if (!currentDebug(token, project, character)) return
    if ((context && (context.package.task_id !== taskId || context.package.project_id !== project)) ||
      (lineage && (lineage.task_id !== taskId || lineage.agent_run_id !== runId))) throw new ApiError('INVALID_RESPONSE', 'Context 或 PromptLineage 与所选 Run 不匹配。')
    reportContext.value = context; reportLineage.value = lineage
  } catch (value) { if (currentDebug(token, project, character)) debugError.value = asError(value) }
  finally { if (currentDebug(token, project, character)) debugLoading.value = false }
}
function toggleDebug(event: Event) {
  const open = (event.target as HTMLDetailsElement).open
  if (open === debugOpen.value) return
  debugOpen.value = open
  if (open) void loadInterpretations()
  else clearDebug()
}
const json = (value: unknown) => JSON.stringify(value, null, 2)
function fill(value: Behavior = {}) {
  form.value = {}
  for (const [key] of [...common, ...advanced]) form.value[key] = value[key] ?? null
  form.value.risk_tolerance = value.risk_tolerance ?? null
  for (const [key] of arrayFields) lists.value[key] = (value[key] ?? []).join('\n')
  relationships.value = (value.relationship_modifiers ?? []).map(r => ({
    other_character_id: r.other_character_id, interaction_tendency: r.interaction_tendency ?? '',
    trust_expression: r.trust_expression ?? '', conflict_pattern: r.conflict_pattern ?? '',
    things_left_unsaid: (r.things_left_unsaid ?? []).join('\n'), guidance: (r.guidance ?? []).join('\n'),
  }))
  changed.value = false
}
async function selectCharacter(id: string) {
  const token = nextRead(), project = props.projectId
  characterId.value = id; state.value = null; versions.value = []; error.value = null; text.value = ''; fill()
  clearDebug()
  currentStates.value = []; statesError.value = null; statesLoading.value = false
  if (!id) { busy.value = false; return }
  busy.value = true
  void loadCurrentStates()
  if (debugOpen.value) void loadInterpretations()
  try {
    const [value, history] = await Promise.all([
      characterProfiles.state(project, id, controller.signal), characterProfiles.versions(project, id, controller.signal),
    ])
    if (!current(token, project, id)) return
    state.value = value; versions.value = history; fill(value.current ?? {})
  } catch (value) { if (current(token, project, id)) error.value = asError(value) }
  finally { if (current(token, project, id)) busy.value = false }
}
async function loadCurrentStates() {
  const token = epoch, project = props.projectId, character = characterId.value
  if (!character) return
  statesLoading.value = true; statesError.value = null
  try {
    const value = await characterProfiles.currentStates(project, character, controller.signal)
    if (current(token, project, character)) currentStates.value = value
  } catch (value) { if (current(token, project, character)) statesError.value = asError(value) }
  finally { if (current(token, project, character)) statesLoading.value = false }
}
async function refresh() {
  const token = nextRead(), project = props.projectId, selected = characterId.value
  busy.value = true; state.value = null; versions.value = []; characters.value = []; error.value = null; fill()
  clearDebug()
  currentStates.value = []; statesError.value = null; statesLoading.value = false
  try {
    const value = await characterProfiles.characters(project, controller.signal)
    if (!current(token, project, selected)) return
    characters.value = value
    await selectCharacter(value.some(c => c.id === selected) ? selected : value[0]?.id ?? '')
  } catch (value) { if (!disposed && token === epoch) error.value = asError(value) }
  finally { if (!disposed && token === epoch) busy.value = false }
}
const lines = (value: string) => value.split('\n').map(v => v.trim()).filter(Boolean)
function updateDraft(draft: CharacterProfile) {
  if (!state.value) return
  state.value = { ...state.value, current: draft, current_profile_version: draft.version }
  versions.value = [draft, ...versions.value.filter(v => v.id !== draft.id)]
  fill(draft)
}
async function createCharacter() {
  if (busy.value || props.disabled || !name.value.trim()) return
  const token = epoch, project = props.projectId, selected = characterId.value
  busy.value = true; error.value = null
  try {
    const value = await characterProfiles.createCharacter(project, name.value.trim(), lines(aliases.value))
    if (!current(token, project, selected)) return
    characters.value = [...characters.value, value]; name.value = ''; aliases.value = ''
    await selectCharacter(value.id)
  } catch (value) { if (current(token, project, selected)) error.value = asError(value) }
  finally { if (current(token, project, selected)) busy.value = false }
}
async function save() {
  if (locked.value || !state.value) return
  const token = epoch, project = props.projectId, character = characterId.value
  busy.value = true; error.value = null
  const profile: Behavior = { ...form.value, relationship_modifiers: relationships.value.map(r => ({
    other_character_id: r.other_character_id, interaction_tendency: r.interaction_tendency.trim() || null,
    trust_expression: r.trust_expression.trim() || null, conflict_pattern: r.conflict_pattern.trim() || null,
    things_left_unsaid: lines(r.things_left_unsaid), guidance: lines(r.guidance),
  })) }
  for (const [key] of [...common, ...advanced]) profile[key] = form.value[key]?.trim() || null
  for (const [key] of arrayFields) profile[key] = lines(lists.value[key])
  try {
    const draft = await characterProfiles.save(project, character, profile, state.value.current_profile_version ?? 0)
    if (current(token, project, character)) updateDraft(draft)
  } catch (value) { if (current(token, project, character)) error.value = asError(value) }
  finally { if (current(token, project, character)) busy.value = false }
}
async function interpret() {
  if (locked.value || changed.value || !state.value || !text.value.trim()) return
  const token = epoch, project = props.projectId, character = characterId.value
  busy.value = true; interpreting.value = true; error.value = null
  try {
    const draft = await characterProfiles.interpret(project, character, text.value, state.value.current_profile_version ?? 0)
    if (current(token, project, character)) updateDraft(draft)
  } catch (value) { if (current(token, project, character)) error.value = asError(value) }
  finally { if (current(token, project, character)) { busy.value = false; interpreting.value = false; if (debugOpen.value) void loadInterpretations() } }
}
async function approve() {
  if (locked.value || changed.value || state.value?.current?.status !== 'DRAFT') return
  const token = epoch, project = props.projectId, character = characterId.value, version = state.value.current.version
  busy.value = true; error.value = null
  try {
    const approved = await characterProfiles.approve(project, character, version)
    if (!current(token, project, character)) return
    state.value = { current: approved, approved, current_profile_version: approved.version, approved_profile_version: approved.version }
    versions.value = versions.value.map(v => v.id === approved.id ? approved : v.status === 'APPROVED' ? { ...v, status: 'SUPERSEDED' } : v)
  } catch (value) { if (current(token, project, character)) error.value = asError(value) }
  finally { if (current(token, project, character)) busy.value = false }
}
function addRelationship() {
  relationships.value.push({ other_character_id: '', interaction_tendency: '', trust_expression: '', conflict_pattern: '', things_left_unsaid: '', guidance: '' })
  changed.value = true
}
function removeRelationship(index: number) { relationships.value.splice(index, 1); changed.value = true }
onMounted(refresh)
onMounted(() => { void nextTick(() => closeButton.value?.focus()) })
watch(() => props.projectId, () => { characterId.value = ''; interpreting.value = false; void refresh() })
onBeforeUnmount(() => { disposed = true; nextRead(); clearDebug() })
</script>

<template>
  <div class="drawer-backdrop" @click.self="emit('close')" @keydown.esc="emit('close')">
    <aside id="character-profile-section" class="drawer profile-drawer" role="dialog" aria-modal="true" aria-labelledby="character-profile-title">
      <div class="drawer-header"><h2 id="character-profile-title">人物表现</h2><button ref="closeButton" class="quiet" @click="emit('close')">关闭</button></div>
      <button type="button" :disabled="busy || disabled" @click="refresh">刷新人物</button>
      <ErrorNotice v-if="error" :error="error" />
      <p v-if="busy" role="status">{{ interpreting ? '正在整理人物表现…' : '正在读取人物…' }}</p>
      <label for="profile-character">人物</label>
      <select id="profile-character" :value="characterId" :disabled="busy || disabled" @change="selectCharacter(($event.target as HTMLSelectElement).value)">
        <option value="">选择人物</option><option v-for="character in characters" :key="character.id" :value="character.id">{{ character.name }}</option>
      </select>
      <p v-if="!busy && !error && !characters.length" class="muted">此项目还没有人物。</p>
      <details class="character-create"><summary>添加人物</summary>
        <form @submit.prevent="createCharacter"><fieldset :disabled="busy || disabled"><label for="character-name">姓名</label><input id="character-name" v-model="name" required maxlength="200"><label for="character-aliases">别名（每行一个，可留空）</label><textarea id="character-aliases" v-model="aliases" rows="2" /><button :disabled="!name.trim()">添加人物</button></fieldset></form>
      </details>
      <section v-if="selectedCharacter" class="character-identity" aria-label="基础信息">
        <h3>基础信息</h3><dl class="profile-summary"><dt>姓名</dt><dd>{{ selectedCharacter.name }}</dd><dt>别名</dt><dd>{{ selectedCharacter.aliases.join('、') || '无' }}</dd></dl>
      </section>
      <section v-if="selectedCharacter" class="character-current-state" aria-label="当前状态">
        <h3>当前状态</h3>
        <p v-if="statesLoading" role="status">正在读取当前状态…</p>
        <div v-else-if="statesError"><p>暂时无法读取当前状态。</p><ErrorNotice :error="statesError" /><button type="button" :disabled="disabled" @click="loadCurrentStates">重新读取当前状态</button></div>
        <ul v-else-if="currentStates.length"><li v-for="entry in currentStates" :key="entry.id ?? `${entry.logical_id}:${entry.version}`">{{ entry.statement }}</li></ul>
        <p v-else class="muted">尚无已确认的人物状态。</p>
      </section>
      <template v-if="state && selectedCharacter">
        <h3>人物表现</h3>
        <div class="profile-toolbar"><span>当前 v{{ state.current_profile_version ?? '—' }} · 已批准 v{{ state.approved_profile_version ?? '—' }}</span></div>
        <p>批准后的表现用于之后的创作。它描述通常的倾向，具体反应仍取决于情境。</p>
        <dl v-if="summary" class="profile-summary" data-testid="character-profile-summary">
          <dt>查看版本</dt><dd>v{{ summary.version }} · {{ statusLabels[summary.status] }}</dd>
          <dt>决策习惯</dt><dd>{{ summary.decision_tendency || '未指定' }}</dd><dt>风险倾向</dt><dd>{{ summary.risk_tolerance ? riskLabels[summary.risk_tolerance] : '未指定' }}</dd>
          <template v-for="[key, label] in common.slice(1)" :key="key"><dt>{{ label }}</dt><dd>{{ summary[key] || '未指定' }}</dd></template>
        </dl>
        <p v-else class="muted">尚未定义人物表现，可以先用一段话描述。</p>
        <form class="character-interpret" @submit.prevent="interpret">
          <label for="character-profile-text">用一段话描述人物</label>
          <textarea id="character-profile-text" v-model="text" rows="4" maxlength="10000" :disabled="locked" placeholder="平时说话直接，害怕时会绕开说；遇到风险先做再调整，面对某个人时更不愿示弱。" />
          <button type="submit" :disabled="locked || changed || !text.trim()">用 AI 整理为草稿（调用模型）</button>
        </form>
        <details class="character-edit" :open="!state.approved || state.current?.status === 'DRAFT'"><summary>编辑人物表现{{ state.current ? ` v${state.current.version} · ${statusLabels[state.current.status]}` : '' }}</summary>
          <p v-if="state.current?.status === 'DRAFT'" class="muted">检查这份草稿后再批准。已批准的版本会继续用于创作。</p>
          <p v-if="state.current?.source_text" class="character-source">原始描述：{{ state.current.source_text }}</p>
          <form @submit.prevent="save" @input="changed = true" @change="changed = true"><fieldset :disabled="locked">
            <label for="character-decision_tendency">决策习惯</label><textarea id="character-decision_tendency" v-model="form.decision_tendency" rows="2" maxlength="2000" />
            <label for="character-risk_tolerance">风险倾向</label><select id="character-risk_tolerance" v-model="form.risk_tolerance"><option :value="null">未指定</option><option v-for="(label, value) in riskLabels" :key="value" :value="value">{{ label }}</option></select>
            <template v-for="[key, label] in common.slice(1)" :key="key"><label :for="`character-${key}`">{{ label }}</label><textarea :id="`character-${key}`" v-model="form[key]" rows="2" maxlength="2000" /></template>
            <details class="character-advanced"><summary>高级设置</summary>
              <template v-for="[key, label] in advanced" :key="key"><label :for="`character-${key}`">{{ label }}</label><textarea :id="`character-${key}`" v-model="form[key]" rows="2" maxlength="2000" /></template>
              <template v-for="[key, label] in arrayFields" :key="key"><label :for="`character-${key}`">{{ label }}（每行一条，可留空）</label><textarea :id="`character-${key}`" v-model="lists[key]" rows="2" /></template>
              <h3>面对不同人物</h3>
              <p class="muted">只添加需要区别的互动方式。</p>
              <fieldset v-for="(relationship, index) in relationships" :key="index" class="character-relationship">
                <legend>互动 {{ index + 1 }}</legend>
                <label :for="`character-other-${index}`">面对的人物</label><select :id="`character-other-${index}`" v-model="relationship.other_character_id" required><option value="">选择人物</option><option v-for="character in otherCharacters" :key="character.id" :value="character.id" :disabled="relationships.some((r, otherIndex) => otherIndex !== index && r.other_character_id === character.id)">{{ character.name }}</option></select>
                <label :for="`character-interaction-${index}`">互动倾向</label><textarea :id="`character-interaction-${index}`" v-model="relationship.interaction_tendency" rows="2" maxlength="2000" />
                <details><summary>补充互动细节</summary>
                  <label :for="`character-trust-${index}`">如何表达信任</label><textarea :id="`character-trust-${index}`" v-model="relationship.trust_expression" rows="2" maxlength="2000" />
                  <label :for="`character-conflict-${index}`">冲突时的相处方式</label><textarea :id="`character-conflict-${index}`" v-model="relationship.conflict_pattern" rows="2" maxlength="2000" />
                  <label :for="`character-unsaid-${index}`">没有说出口的事（每行一条）</label><textarea :id="`character-unsaid-${index}`" v-model="relationship.things_left_unsaid" rows="2" />
                  <label :for="`character-relationship-guidance-${index}`">补充指导（每行一条）</label><textarea :id="`character-relationship-guidance-${index}`" v-model="relationship.guidance" rows="2" />
                </details>
                <button type="button" @click="removeRelationship(index)">移除此互动</button>
              </fieldset>
              <button type="button" :disabled="!otherCharacters.length" @click="addRelationship">添加互动差异</button>
            </details>
            <button type="submit">保存新草稿版本</button>
          </fieldset></form>
        </details>
        <p v-if="changed" role="status">有未保存的修改，请先保存，再整理或批准。</p>
        <button v-if="state.current?.status === 'DRAFT'" type="button" :disabled="locked || changed" @click="approve">批准人物表现 v{{ state.current.version }}</button>
        <details v-if="versions.length" class="character-versions"><summary>版本记录</summary><table><thead><tr><th>版本</th><th>状态</th><th>表达方式</th></tr></thead><tbody><tr v-for="profile in versions" :key="profile.id"><td>v{{ profile.version }}</td><td>{{ statusLabels[profile.status] }}</td><td>{{ profile.communication_style || '未指定' }}</td></tr></tbody></table></details>
      </template>
      <details v-if="selectedCharacter" class="character-debug" :open="debugOpen" @toggle="toggleDebug">
        <summary>Debug / 人物解读记录</summary>
        <button type="button" :disabled="debugLoading" @click="loadInterpretations">刷新解读记录</button>
        <p v-if="debugLoading" role="status">正在读取解读证据…</p>
        <ErrorNotice v-if="debugError" :error="debugError" />
        <p v-if="!debugLoading && !debugError && !interpretations.length" class="muted">尚无人物解读记录。</p>
        <ul data-testid="interpretation-tasks"><li v-for="task in interpretations" :key="task.task_id"><button type="button" @click="inspectReportTask(task.task_id)">{{ task.status }} · {{ task.created_at }}</button> <code>{{ task.task_id }}</code><span v-if="task.last_error_code"> · {{ task.last_error_code }}</span><span v-if="task.result_metadata.profile_record_id"> · 草稿记录 <code>{{ task.result_metadata.profile_record_id }}</code></span></li></ul>
        <details v-if="reportTask" data-testid="interpretation-task"><summary>Task / Raw JSON</summary><pre>{{ json(reportTask) }}</pre></details>
        <template v-if="reportTask && !debugLoading && !debugError && !reportRuns.length"><p class="muted">此任务尚无 Run。</p></template>
        <ul data-testid="interpretation-runs"><li v-for="run in reportRuns" :key="run.run_id"><button type="button" @click="inspectReportRun(run.run_id)">Attempt {{ run.attempt_number }} · {{ run.status }}</button> <code>{{ run.run_id }}</code><span v-if="run.error_code"> · {{ run.error_code }}</span></li></ul>
        <details v-if="reportRun" data-testid="interpretation-run"><summary>AgentRun / Raw JSON</summary><pre>{{ json(reportRun) }}</pre></details>
        <template v-if="reportRun && !debugLoading && !debugError">
          <details v-if="reportContext" data-testid="interpretation-context"><summary>ContextPackage / {{ reportContext.package.profile_id }} v{{ reportContext.package.profile_version }}</summary><pre>{{ json(reportContext) }}</pre></details>
          <p v-else class="muted">此 Run 尚无 ContextPackage。</p>
          <details v-if="reportLineage" data-testid="interpretation-lineage"><summary>PromptLineage / {{ reportLineage.model_profile_id }}</summary><pre>{{ json(reportLineage) }}</pre></details>
          <p v-else class="muted">此 Run 尚无 PromptLineage。</p>
        </template>
      </details>
    </aside>
  </div>
</template>

<style scoped>
.character-create, .character-edit, .character-versions { margin: 16px 0; padding: 12px 0; border-top: 1px solid var(--border); }
.character-interpret { margin: 16px 0; }
.character-advanced { margin: 16px 0; }
.character-advanced > h3 { margin-top: 16px; }
.character-relationship details { margin: 12px 0; }
.character-source { white-space: pre-wrap; }
</style>
