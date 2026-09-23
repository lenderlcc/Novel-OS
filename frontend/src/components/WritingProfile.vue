<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { writingProfiles, type Preferences, type ProfileState } from '../api/writingProfiles'
import { asError, type ApiError } from '../api/client'
import ErrorNotice from './ErrorNotice.vue'
import fixture from '../../../evals/writing/v0.1/case-01/web-fiction-test-profile.json'

const props = defineProps<{ projectId: string; disabled?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const state = ref<ProfileState | null>(null), error = ref<ApiError | null>(null), busy = ref(false)
const closeButton = ref<HTMLButtonElement | null>(null)
const form = ref<Preferences>({ target_audience: '' }), notes = ref(''), experience = ref(''), avoid = ref('')
let controller = new AbortController(), requestEpoch = 0
let disposed = false
function nextRead() {
  controller.abort()
  controller = new AbortController()
  return ++requestEpoch
}
onBeforeUnmount(() => { disposed = true; requestEpoch++; controller.abort() })
const common = [
  ['narrative_density', 'Narrative Density / 叙事密度'],
  ['description_density', 'Description Density / 描写密度'],
  ['dialogue_density', 'Dialogue Density / 对话密度'],
  ['literary_ornamentation', 'Literary Ornamentation / 文学修饰'],
  ['relationship_payoff_visibility', 'Relationship Payoff / 关系变化可感知度'],
] as const
const advanced = [
  ['emotional_explicitness', '情绪显性程度'], ['subtext_level', '潜台词程度'],
  ['scene_hook_strength', '场景吸引力'], ['chapter_ending_hook', '章末吸引力'],
  ['exposition_density', '解释密度'], ['naturalness', '自然感'],
] as const
const levels = ['VERY_LOW', 'LOW', 'LOW_MEDIUM', 'MEDIUM', 'MEDIUM_HIGH', 'HIGH', 'VERY_HIGH'] as const
const pacing = ['VERY_SLOW', 'SLOW', 'MEDIUM_SLOW', 'MEDIUM', 'MEDIUM_FAST', 'FAST', 'VERY_FAST'] as const
const locked = computed(() => props.disabled || busy.value || !state.value || Boolean(error.value))
const summary = computed(() => state.value?.approved ?? state.value?.current ?? null)
const levelLabels: Record<string, string> = {
  FIRST_PERSON: '第一人称', THIRD_PERSON: '第三人称',
  VERY_LOW: '很低', LOW: '低', LOW_MEDIUM: '偏低', MEDIUM: '中等', MEDIUM_HIGH: '偏高', HIGH: '高', VERY_HIGH: '很高',
  VERY_SLOW: '很慢', SLOW: '慢', MEDIUM_SLOW: '偏慢', MEDIUM_FAST: '偏快', FAST: '快', VERY_FAST: '很快',
}
const display = (value: string | null | undefined) => value ? levelLabels[value] ?? value : '未设置'
const changed = ref(false)
function fill(value: Preferences) {
  const { target_audience, narrative_perspective, pacing, reading_experience, guidance, avoid_tendencies } = value
  form.value = { target_audience: target_audience ?? '', narrative_perspective: narrative_perspective ?? null, pacing: pacing ?? null }
  for (const [key] of [...common, ...advanced]) form.value[key] = value[key] ?? null
  notes.value = (guidance ?? []).join('\n')
  experience.value = (reading_experience ?? []).join('\n')
  avoid.value = (avoid_tendencies ?? []).join('\n')
}
async function refresh() {
  const token = nextRead(), project = props.projectId
  busy.value = true; error.value = null; state.value = null; changed.value = false
  fill({ target_audience: '' })
  try {
    const value = await writingProfiles.state(project, controller.signal)
    if (disposed || token !== requestEpoch || project !== props.projectId) return
    state.value = value; fill(value.current ?? { target_audience: '' }); changed.value = false
  } catch (value) { if (!disposed && token === requestEpoch) error.value = asError(value) }
  finally { if (!disposed && token === requestEpoch) busy.value = false }
}
function loadExample() {
  fill(fixture as Preferences); changed.value = true
}
const lines = (value: string) => value.split('\n').map(v => v.trim()).filter(Boolean)
async function save() {
  if (locked.value || !state.value) return
  const project = props.projectId
  busy.value = true
  try {
    const draft = await writingProfiles.save(project, { ...form.value,
      guidance: lines(notes.value), reading_experience: lines(experience.value), avoid_tendencies: lines(avoid.value),
    }, state.value.current_profile_version ?? 0)
    if (disposed || project !== props.projectId) return
    state.value = { ...state.value, current: draft, current_profile_version: draft.version }
    changed.value = false
  } catch (value) { if (!disposed) error.value = asError(value) }
  finally { if (!disposed) busy.value = false }
}
async function approve() {
  if (locked.value || changed.value || state.value?.current?.status !== 'DRAFT') return
  const project = props.projectId, version = state.value.current.version
  busy.value = true
  try {
    const approved = await writingProfiles.approve(project, version)
    if (disposed || project !== props.projectId) return
    state.value = { current: approved, approved, current_profile_version: approved.version, approved_profile_version: approved.version }
  } catch (value) { if (!disposed) error.value = asError(value) }
  finally { if (!disposed) busy.value = false }
}
onMounted(refresh)
onMounted(() => { void nextTick(() => closeButton.value?.focus()) })
watch(() => props.projectId, refresh)
</script>

<template>
  <div class="drawer-backdrop" @click.self="emit('close')" @keydown.esc="emit('close')">
  <aside id="writing-profile-section" class="drawer profile-drawer" role="dialog" aria-modal="true" aria-labelledby="profile-title">
    <div class="drawer-header"><div><h2 id="profile-title">写作偏好</h2><p>批准后的设置会用于之后生成的方案和正文。</p></div><button ref="closeButton" class="quiet" @click="emit('close')">关闭</button></div>
    <div class="profile-toolbar"><span>当前 v{{ state?.current_profile_version ?? '—' }} · 已批准 v{{ state?.approved_profile_version ?? '—' }}</span><button type="button" :disabled="busy || disabled" @click="refresh">刷新</button></div>
    <ErrorNotice v-if="error" :error="error" />
    <dl v-if="summary" class="profile-summary">
      <dt>目标读者</dt><dd>{{ summary.target_audience || '未设置' }}</dd><dt>节奏</dt><dd>{{ display(summary.pacing) }}</dd>
      <dt>叙事人称</dt><dd>{{ display(summary.narrative_perspective) }}</dd>
      <dt>叙事密度</dt><dd>{{ display(summary.narrative_density) }}</dd><dt>描写密度</dt><dd>{{ display(summary.description_density) }}</dd>
      <dt>对白密度</dt><dd>{{ display(summary.dialogue_density) }}</dd><dt>文学感</dt><dd>{{ display(summary.literary_ornamentation) }}</dd>
      <dt>关系变化</dt><dd>{{ display(summary.relationship_payoff_visibility) }}</dd>
    </dl>
    <p v-else-if="state" class="muted">尚未设置写作偏好。</p>
    <details>
      <summary>编辑</summary>
      <button type="button" :disabled="locked" @click="loadExample">载入网文测试示例</button>
      <p class="muted">示例只会填表。保存新版本后仍需单独批准。</p>
      <form @submit.prevent="save" @input="changed = true" @change="changed = true">
        <fieldset :disabled="locked">
          <label for="profile-audience">目标读者</label>
          <input id="profile-audience" v-model="form.target_audience" maxlength="1000">
          <label for="profile-perspective">叙事人称</label>
          <select id="profile-perspective" v-model="form.narrative_perspective"><option :value="null">未指定</option><option value="THIRD_PERSON">第三人称</option><option value="FIRST_PERSON">第一人称</option></select>
          <label for="profile-pacing">节奏</label>
          <select id="profile-pacing" v-model="form.pacing"><option :value="null">未指定</option><option v-for="level in pacing" :key="level">{{ level }}</option></select>
          <div class="two-columns">
            <div v-for="[key, label] in common" :key="key"><label :for="`profile-${key}`">{{ label }}</label><select :id="`profile-${key}`" v-model="form[key]"><option :value="null">未指定</option><option v-for="level in levels" :key="level">{{ level }}</option></select></div>
          </div>
          <label for="profile-notes">写作指导（每行一条）</label><textarea id="profile-notes" v-model="notes" rows="4" />
          <details><summary>高级设置</summary>
            <div class="two-columns"><div v-for="[key, label] in advanced" :key="key"><label :for="`profile-${key}`">{{ label }}</label><select :id="`profile-${key}`" v-model="form[key]"><option :value="null">未指定</option><option v-for="level in levels" :key="level">{{ level }}</option></select></div></div>
            <label for="profile-experience">阅读体验（每行一条）</label><textarea id="profile-experience" v-model="experience" rows="4" />
            <label for="profile-avoid">应避免的倾向（每行一条）</label><textarea id="profile-avoid" v-model="avoid" rows="4" />
          </details>
          <button type="submit">保存新版本</button>
        </fieldset>
      </form>
    </details>
    <p v-if="changed" role="status">表单有未保存的修改，请先保存再批准。</p>
    <button v-if="state?.current?.status === 'DRAFT'" type="button" :disabled="locked || changed" @click="approve">批准 Profile v{{ state.current.version }}</button>
  </aside>
  </div>
</template>
