import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CharacterProfileEditor from '../src/components/CharacterProfile.vue'
import DebugPanel from '../src/components/DebugPanel.vue'
import WorkspaceSidebar from '../src/components/WorkspaceSidebar.vue'
import { characterProfiles, type Character, type CharacterProfile, type CharacterProfileState, type CharacterState } from '../src/api/characterProfiles'
import { writingProfiles } from '../src/api/writingProfiles'
import { api } from '../src/api/console'
import { ApiError } from '../src/api/client'
import { clone, sample } from './fixtures'
import type { Context, Lineage, Run, Task } from '../src/types/models'

const character = (id: string, name: string): Character => ({ id, project_id: 'project-1', name, normalized_name: name,
  kind: 'CHARACTER', aliases: [], batch_id: null, created_at: '2026-10-06T00:00:00Z', created_by: 'local-user' })
const people = [character('lin', '林'), character('jun', '君'), character('mei', '梅')]
const draft: CharacterProfile = { id: 'profile-1', logical_id: 'profile-logical-lin', profile_id: 'profile-logical-lin', project_id: 'project-1', character_id: 'lin', version: 1,
  status: 'DRAFT', authority_level: 'A7_AI_INFERENCE', source: 'USER', profile_hash: 'hash-1', supersedes_id: null, source_text: null,
  created_at: '2026-10-06T00:00:00Z', created_by: 'local-user', approved_at: null, approved_by: null, communication_style: '说话直接' }
const empty: CharacterProfileState = { current: null, approved: null, current_profile_version: null, approved_profile_version: null }
const committedState: CharacterState = { id: 'state-2', project_id: 'project-1', chapter_id: 'chapter-1', chapter_version_id: 'draft-1',
  batch_id: 'batch-1', candidate_id: 'candidate-2', logical_id: 'state-slot', version: 2, supersedes_id: 'state-1', subject_id: 'lin',
  memory_type: 'CHARACTER_STATE', slot: 'location', value: '旧车站', statement: '林仍困在旧车站。', epistemic_status: null,
  authority_level: 'A3_CANON', body: {} }
const profileState = (profile: CharacterProfile): CharacterProfileState => ({ current: profile, approved: profile.status === 'APPROVED' ? profile : null,
  current_profile_version: profile.version, approved_profile_version: profile.status === 'APPROVED' ? profile.version : null })
const button = (wrapper: ReturnType<typeof mount>, text: string) => wrapper.findAll('button').find(b => b.text().includes(text))!
function reads(value: CharacterProfileState = empty) {
  vi.spyOn(characterProfiles, 'characters').mockResolvedValue(people)
  vi.spyOn(characterProfiles, 'state').mockResolvedValue(value)
  vi.spyOn(characterProfiles, 'versions').mockResolvedValue(value.current ? [value.current] : [])
  vi.spyOn(characterProfiles, 'currentStates').mockResolvedValue([])
}
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('character behavior settings', () => {
  it('opens from the existing sidebar and lists human-readable characters with an optional identity form', async () => {
    const sidebar = mount(WorkspaceSidebar, { props: { projects: [], chapters: [], projectId: 'project-1', chapterId: '', disabled: false } })
    await button(sidebar, '人物表现').trigger('click')
    expect(sidebar.emitted('openCharacters')).toEqual([[]])
    sidebar.unmount()
    reads()
    const create = vi.spyOn(characterProfiles, 'createCharacter').mockResolvedValue(character('new', '新人物'))
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('#profile-character').findAll('option').map(o => o.text())).toEqual(['选择人物', '林', '君', '梅'])
    expect(wrapper.text()).toContain('尚未定义人物表现')
    expect(wrapper.get('.character-current-state').text()).toContain('尚无已确认的人物状态')
    expect(wrapper.get('.character-advanced').attributes('open')).toBeUndefined()
    expect(wrapper.find('.character-relationship').exists()).toBe(false)
    await wrapper.get('#character-name').setValue('新人物')
    await wrapper.get('#character-aliases').setValue('阿新\n 小新 ')
    await wrapper.get('.character-create form').trigger('submit'); await flushPromises()
    expect(create).toHaveBeenCalledExactlyOnceWith('project-1', '新人物', ['阿新', '小新'])
    expect(wrapper.get('#profile-character').element).toHaveProperty('value', 'new')
    wrapper.unmount()
  })
  it('shows basic aliases and current committed state separately from character behavior', async () => {
    reads(profileState(draft))
    vi.spyOn(characterProfiles, 'characters').mockResolvedValue([{ ...people[0]!, aliases: ['林哥', '小林'] }, ...people.slice(1)])
    const states = vi.spyOn(characterProfiles, 'currentStates').mockResolvedValue([committedState])
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('.character-identity').text()).toContain('姓名林别名林哥、小林')
    expect(wrapper.get('.character-current-state').text()).toContain('林仍困在旧车站。')
    expect(wrapper.get('.character-current-state').find('input, textarea, select').exists()).toBe(false)
    expect(wrapper.get('[data-testid="character-profile-summary"]').text()).toContain('说话直接')
    expect(states).toHaveBeenCalledExactlyOnceWith('project-1', 'lin', expect.any(AbortSignal))
    wrapper.unmount()
  })
  it('shows a state read failure independently and retries without losing profile edits', async () => {
    reads(profileState(draft))
    const states = vi.spyOn(characterProfiles, 'currentStates').mockRejectedValueOnce(new ApiError('NETWORK_ERROR', 'unavailable'))
      .mockResolvedValueOnce([committedState])
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('.character-current-state').text()).toContain('暂时无法读取当前状态')
    expect(wrapper.get('.character-current-state').text()).not.toContain('尚无已确认的人物状态')
    expect(wrapper.get('.character-edit fieldset').attributes('disabled')).toBeUndefined()
    await wrapper.get('#character-communication_style').setValue('仍可编辑的表现')
    await button(wrapper, '重新读取当前状态').trigger('click'); await flushPromises()
    expect(wrapper.get('.character-current-state').text()).toContain('林仍困在旧车站。')
    expect(wrapper.get('.character-current-state').find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.get('#character-communication_style').element).toHaveProperty('value', '仍可编辑的表现')
    expect(states).toHaveBeenCalledTimes(2)
    expect(characterProfiles.state).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('allows profile editing during a state read and discards late state from a previously selected character', async () => {
    reads(profileState(draft))
    vi.spyOn(characterProfiles, 'state').mockResolvedValueOnce(profileState(draft)).mockResolvedValueOnce(empty)
    let complete!: (value: CharacterState[]) => void
    const states = vi.spyOn(characterProfiles, 'currentStates').mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
      .mockResolvedValueOnce([])
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('.character-current-state').text()).toContain('正在读取当前状态')
    expect(wrapper.get('.character-edit fieldset').attributes('disabled')).toBeUndefined()
    await wrapper.get('#profile-character').setValue('jun'); await flushPromises()
    complete([committedState]); await flushPromises()
    expect(wrapper.get('.character-identity').text()).toContain('姓名君')
    expect(wrapper.get('.character-current-state').text()).toContain('尚无已确认的人物状态')
    expect(wrapper.get('.character-current-state').text()).not.toContain('旧车站')
    expect(states.mock.calls.map(call => call.slice(0, 2))).toEqual([['project-1', 'lin'], ['project-1', 'jun']])
    expect(states.mock.calls[0]?.[2]?.aborted).toBe(true)
    wrapper.unmount()
  })
  it('keeps the subject and memory-type filters on every page of the existing memory query', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(Array.from({ length: 200 }, () => committedState))))
      .mockResolvedValueOnce(new Response('[]'))
    vi.stubGlobal('fetch', fetch)
    expect(await characterProfiles.currentStates('project-1', 'lin')).toHaveLength(200)
    expect(fetch.mock.calls.map(call => call[0])).toEqual([
      '/api/v1/projects/project-1/memory?subject_id=lin&memory_type=CHARACTER_STATE&limit=200&offset=0',
      '/api/v1/projects/project-1/memory?subject_id=lin&memory_type=CHARACTER_STATE&limit=200&offset=200',
    ])
  })
  it('interprets one natural-language description only on explicit model submit, then requires exact-version approval', async () => {
    reads()
    let complete!: (profile: CharacterProfile) => void
    const interpret = vi.spyOn(characterProfiles, 'interpret').mockImplementation(() => new Promise(resolve => { complete = resolve }))
    const save = vi.spyOn(characterProfiles, 'save')
    const approve = vi.spyOn(characterProfiles, 'approve').mockResolvedValue({ ...draft, status: 'APPROVED', authority_level: 'A3_CANON' })
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    const text = '他平时说话直接，涉及自己的害怕时会绕开。'
    expect(wrapper.get('#character-profile-text').attributes('maxlength')).toBe('10000')
    await wrapper.get('#character-profile-text').setValue(text)
    expect(interpret).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    await wrapper.get('.character-interpret').trigger('submit')
    expect(wrapper.text()).toContain('正在整理人物表现')
    expect(interpret).toHaveBeenCalledExactlyOnceWith('project-1', 'lin', text, 0)
    complete({ ...draft, source_text: text, avoids_saying_directly: ['自己的害怕'] }); await flushPromises()
    expect(save).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    expect(wrapper.get('#character-communication_style').element).toHaveProperty('value', '说话直接')
    expect(wrapper.get('#character-avoids_saying_directly').element).toHaveProperty('value', '自己的害怕')
    expect(wrapper.text()).toContain(`原始描述：${text}`)
    await button(wrapper, '批准人物表现 v1').trigger('click'); await flushPromises()
    expect(approve).toHaveBeenCalledExactlyOnceWith('project-1', 'lin', 1)
    expect(wrapper.text()).toContain('当前 v1 · 已批准 v1')
    wrapper.unmount()
  })
  it('creates immutable draft versions from a sparse edit and keeps approved behavior visible until approval', async () => {
    const approved = { ...draft, status: 'APPROVED' as const, authority_level: 'A3_CANON' as const }
    reads(profileState(approved))
    const next = { ...draft, id: 'profile-2', version: 2, communication_style: '话少，先听别人说' }
    const save = vi.spyOn(characterProfiles, 'save').mockResolvedValue(next)
    const approve = vi.spyOn(characterProfiles, 'approve').mockResolvedValue({ ...next, status: 'APPROVED', authority_level: 'A3_CANON' })
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('[data-testid="character-profile-summary"]').text()).toContain('说话直接')
    expect(wrapper.get('.character-advanced').attributes('open')).toBeUndefined()
    await wrapper.get('#character-communication_style').setValue('话少，先听别人说')
    await wrapper.get('#character-decision_tendency').setValue('   ')
    await button(wrapper, '添加互动差异').trigger('click')
    expect(wrapper.findAll('.character-relationship')).toHaveLength(1)
    expect(wrapper.get('#character-other-0').find('option[value="lin"]').exists()).toBe(false)
    await wrapper.get('#character-other-0').setValue('jun')
    await wrapper.get('#character-interaction-0').setValue('面对君更不愿示弱')
    await wrapper.get('#character-unsaid-0').setValue('害怕失去他\n 不想独自决定 ')
    await wrapper.get('.character-edit form').trigger('submit'); await flushPromises()
    expect(save).toHaveBeenCalledExactlyOnceWith('project-1', 'lin', expect.objectContaining({ decision_tendency: null,
      communication_style: '话少，先听别人说', relationship_modifiers: [{ other_character_id: 'jun', interaction_tendency: '面对君更不愿示弱',
        trust_expression: null, conflict_pattern: null, things_left_unsaid: ['害怕失去他', '不想独自决定'], guidance: [] }] }), 1)
    expect(wrapper.text()).toContain('当前 v2 · 已批准 v1')
    expect(wrapper.get('[data-testid="character-profile-summary"]').text()).toContain('说话直接')
    expect(wrapper.get('.character-edit').attributes('open')).toBeDefined()
    expect(approve).not.toHaveBeenCalled()
    await button(wrapper, '批准人物表现 v2').trigger('click'); await flushPromises()
    expect(wrapper.get('[data-testid="character-profile-summary"]').text()).toContain('话少，先听别人说')
    expect(wrapper.get('.character-versions').text()).toContain('已被替代')
    wrapper.unmount()
  })
  it('editing a draft blocks approval and model interpretation until saved; stale approval never retries automatically', async () => {
    reads(profileState(draft))
    const next = { ...draft, id: 'profile-2', version: 2 }
    const save = vi.spyOn(characterProfiles, 'save').mockResolvedValue(next)
    const approve = vi.spyOn(characterProfiles, 'approve').mockRejectedValue(new ApiError('VERSION_CONFLICT', 'changed', 'req', 409))
    const interpret = vi.spyOn(characterProfiles, 'interpret')
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    await wrapper.get('#character-conflict_response').setValue('先去做事')
    await wrapper.get('#character-profile-text').setValue('新描述')
    expect(button(wrapper, '批准人物表现').attributes('disabled')).toBeDefined()
    expect(button(wrapper, '用 AI 整理').attributes('disabled')).toBeDefined()
    await wrapper.get('.character-edit form').trigger('submit'); await flushPromises()
    expect(save).toHaveBeenCalledWith('project-1', 'lin', expect.objectContaining({ conflict_response: '先去做事' }), 1)
    await button(wrapper, '批准人物表现').trigger('click'); await flushPromises()
    expect(approve).toHaveBeenCalledExactlyOnceWith('project-1', 'lin', 2)
    expect(wrapper.get('[role="alert"]').text()).toContain('VERSION_CONFLICT')
    expect(button(wrapper, '批准人物表现').attributes('disabled')).toBeUndefined()
    expect(interpret).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('preserves a failed manual edit so it can be corrected and saved without refreshing', async () => {
    reads(profileState(draft))
    let complete!: (profile: CharacterProfile) => void
    const save = vi.spyOn(characterProfiles, 'save').mockRejectedValueOnce(new ApiError('VALIDATION_ERROR', 'invalid', 'req', 422))
      .mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await wrapper.get('#character-communication_style').setValue('第一次编辑')
    await wrapper.get('.character-edit form').trigger('submit'); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('VALIDATION_ERROR')
    expect(wrapper.get('#character-communication_style').element).toHaveProperty('value', '第一次编辑')
    expect(wrapper.get('.character-edit fieldset').attributes('disabled')).toBeUndefined()
    await wrapper.get('#character-communication_style').setValue('修正后的表达方式')
    await wrapper.get('.character-edit form').trigger('submit')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    complete({ ...draft, id: 'profile-2', version: 2, communication_style: '修正后的表达方式' }); await flushPromises()
    expect(save).toHaveBeenCalledTimes(2)
    expect(save).toHaveBeenLastCalledWith('project-1', 'lin', expect.objectContaining({ communication_style: '修正后的表达方式' }), 1)
    expect(wrapper.text()).toContain('当前 v2 · 已批准 v—')
    expect(characterProfiles.state).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('preserves a failed natural-language description for correction and an explicit model retry', async () => {
    reads(profileState(draft))
    let complete!: (profile: CharacterProfile) => void
    const interpret = vi.spyOn(characterProfiles, 'interpret').mockRejectedValueOnce(new ApiError('MODEL_INVALID_RESPONSE', 'invalid output', 'req', 502))
      .mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    const approve = vi.spyOn(characterProfiles, 'approve')
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await wrapper.get('#character-profile-text').setValue('初次描述')
    await wrapper.get('.character-interpret').trigger('submit'); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('MODEL_INVALID_RESPONSE')
    expect(wrapper.get('#character-profile-text').element).toHaveProperty('value', '初次描述')
    expect(button(wrapper, '用 AI 整理').attributes('disabled')).toBeUndefined()
    expect(interpret).toHaveBeenCalledTimes(1)
    await wrapper.get('#character-profile-text').setValue('更明确的描述')
    await wrapper.get('.character-interpret').trigger('submit')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    complete({ ...draft, id: 'profile-2', version: 2, source_text: '更明确的描述' }); await flushPromises()
    expect(interpret).toHaveBeenCalledTimes(2)
    expect(interpret).toHaveBeenLastCalledWith('project-1', 'lin', '更明确的描述', 1)
    expect(approve).not.toHaveBeenCalled()
    expect(characterProfiles.state).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('preserves a draft after failed approval and retries the same displayed version only on another click', async () => {
    reads(profileState(draft))
    let complete!: (profile: CharacterProfile) => void
    const approve = vi.spyOn(characterProfiles, 'approve').mockRejectedValueOnce(new ApiError('NETWORK_ERROR', 'unavailable', 'req', 503))
      .mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await button(wrapper, '批准人物表现 v1').trigger('click'); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('NETWORK_ERROR')
    expect(wrapper.get('#character-communication_style').element).toHaveProperty('value', '说话直接')
    expect(button(wrapper, '批准人物表现 v1').attributes('disabled')).toBeUndefined()
    expect(approve).toHaveBeenCalledTimes(1)
    await button(wrapper, '批准人物表现 v1').trigger('click')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    complete({ ...draft, status: 'APPROVED', authority_level: 'A3_CANON' }); await flushPromises()
    expect(approve.mock.calls).toEqual([['project-1', 'lin', 1], ['project-1', 'lin', 1]])
    expect(wrapper.text()).toContain('当前 v1 · 已批准 v1')
    expect(characterProfiles.state).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('keeps profile operations unavailable when the initial state could not be loaded', async () => {
    reads()
    vi.spyOn(characterProfiles, 'state').mockRejectedValue(new ApiError('NETWORK_ERROR', 'unavailable'))
    const save = vi.spyOn(characterProfiles, 'save'), interpret = vi.spyOn(characterProfiles, 'interpret'), approve = vi.spyOn(characterProfiles, 'approve')
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('NETWORK_ERROR')
    expect(wrapper.find('.character-edit').exists()).toBe(false)
    expect(wrapper.find('.character-interpret').exists()).toBe(false)
    expect(save).not.toHaveBeenCalled(); expect(interpret).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('ignores a late profile response after a project change', async () => {
    reads()
    let complete!: (value: CharacterProfileState) => void
    vi.spyOn(characterProfiles, 'state').mockImplementationOnce(() => new Promise(resolve => { complete = resolve })).mockResolvedValue(empty)
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    await wrapper.setProps({ projectId: 'project-2' }); await flushPromises()
    complete(profileState(draft)); await flushPromises()
    expect(wrapper.get('#profile-character').element).toHaveProperty('value', 'lin')
    expect(wrapper.text()).toContain('当前 v— · 已批准 v—')
    expect(wrapper.find('[data-testid="character-profile-summary"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('ignores a late interpretation response after a project change', async () => {
    reads()
    let complete!: (value: CharacterProfile) => void
    vi.spyOn(characterProfiles, 'interpret').mockImplementation(() => new Promise(resolve => { complete = resolve }))
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await wrapper.get('#character-profile-text').setValue('先行动后调整')
    await wrapper.get('.character-interpret').trigger('submit')
    await wrapper.setProps({ projectId: 'project-2' }); await flushPromises()
    complete(draft); await flushPromises()
    expect(wrapper.text()).toContain('当前 v— · 已批准 v—')
    expect(wrapper.find('[data-testid="character-profile-summary"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('sends natural-language interpretation through the shared client with a model-call timeout', async () => {
    const timeout = vi.spyOn(AbortSignal, 'timeout')
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(draft)))
    vi.stubGlobal('fetch', fetch)
    await characterProfiles.interpret('project-1', 'lin', '自然语言', 4)
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/v1/projects/project-1/characters/lin/behavior-profile/interpret')
    expect(JSON.parse(fetch.mock.calls[0]?.[1].body)).toEqual({ text: '自然语言', expected_version: 4 })
    expect(timeout).toHaveBeenCalledWith(360000)
  })
})

describe('character context inspection', () => {
  it('shows frozen profile versions, authority, relevant modifiers and selected/excluded reasons in the existing inspector', async () => {
    vi.spyOn(api, 'transitions').mockResolvedValue(sample.transitions)
    vi.spyOn(api, 'runs').mockImplementation(async id => sample.runs.filter(r => r.task_id === id))
    vi.spyOn(api, 'lineage').mockResolvedValue(sample.lineage)
    vi.spyOn(writingProfiles, 'versions').mockResolvedValue([])
    const context = clone(sample.context), base = context.package.items[0]!
    const item = (id: string, selector: string, payload: unknown) => ({ ...base, context_item_id: id, source_id: id, selector_id: selector, source_version: 3, payload_json: JSON.stringify(payload) })
    context.package.items.push(
      { ...item('profile', 'approved-character-behavior-profiles', { kind: 'CHARACTER_BEHAVIOR_PROFILE', character_id: 'lin', character_profile_id: 'profile-logical-lin', character_profile_version: 3, profile: { relationship_modifiers: [{ other_character_id: 'jun', interaction_tendency: '不愿示弱' }] } }), source_type: 'EXTENSION', authority_level: 'A3_CANON', status: 'APPROVED', selected_reason: 'scene_character_profile' },
      item('identity', 'memory-subjects', { subject: { name: '林' }, role: 'IDENTITY_ONLY' }),
      item('state', 'committed-memory', { memory_type: 'CHARACTER_STATE', subject_id: 'lin' }),
      item('knowledge', 'committed-memory', { memory_type: 'CHARACTER_KNOWLEDGE', subject_id: 'lin' }),
    )
    context.package.excluded_items.push({ source_type: 'EXTENSION', source_id: 'unrelated-profile', source_version: 4, selector_id: 'approved-character-behavior-profiles', reason: 'OUT_OF_SCOPE' })
    vi.spyOn(api, 'context').mockResolvedValue(context)
    const wrapper = mount(DebugPanel, { props: { snapshot: sample.snapshot, open: true } })
    await flushPromises(); await wrapper.get('#debug-character-context').setValue(true)
    const included = wrapper.get('[data-testid="context-included-items"]')
    expect(included.findAll('tbody tr')).toHaveLength(4)
    expect(included.text()).toContain('profile v3')
    expect(included.text()).toContain('A3_CANON / APPROVED')
    expect(included.text()).toContain('scene_character_profile')
    expect(included.text()).toContain('静态身份'); expect(included.text()).toContain('动态状态'); expect(included.text()).toContain('人物知识')
    expect(included.text()).toContain('不愿示弱')
    expect(wrapper.get('[data-testid="context-excluded-items"]').text()).toContain('unrelated-profile v4OUT_OF_SCOPE')
    wrapper.unmount()
  })
})

describe('standalone character interpretation debug', () => {
  const report = (id = 'report-task', status: Task['status'] = 'SUCCEEDED'): Task => ({ ...clone(sample.snapshot.tasks[0]!),
    task_id: id, project_id: 'project-1', report_character_id: 'lin', workflow_instance_id: null, workflow_state: null,
    workflow_state_version: null, target_ref: null, agent_id: 'A02_REQUIREMENT', task_type: 'INTERPRET_CHARACTER_PROFILE', status,
    expected_output_schema: 'character-profile-draft.v1', result_metadata: status === 'SUCCEEDED' ? { profile_record_id: draft.id } : {},
    last_error_code: status === 'FAILED' ? 'MODEL_TIMEOUT' : null })
  const attempt = (id = 'report-run', task = 'report-task', status: Run['status'] = 'SUCCEEDED'): Run => ({ ...clone(sample.runs[0]!),
    run_id: id, task_id: task, status, error_code: status === 'FAILED' ? 'MODEL_TIMEOUT' : null,
    result_status: status === 'FAILED' ? null : sample.runs[0]!.result_status })
  function trace(task = 'report-task', run = 'report-run') {
    const context: Context = clone(sample.context), lineage: Lineage = clone(sample.lineage)
    context.package.project_id = 'project-1'; context.package.task_id = task; context.package.workflow_id = null
    context.package.profile_id = 'CP-010'; context.package.profile_version = 1; context.package.package_hash = `context-hash-${run}`
    lineage.task_id = task; lineage.agent_run_id = run; lineage.compiled_prompt_hash = `prompt-hash-${run}`
    return { context, lineage }
  }
  async function openDebug(wrapper: ReturnType<typeof mount>, open = true) {
    const fold = wrapper.get('.character-debug')
    ;(fold.element as HTMLDetailsElement).open = open
    await fold.trigger('toggle'); await flushPromises()
  }
  async function clickTask(wrapper: ReturnType<typeof mount>, index = 0) {
    await wrapper.get('[data-testid="interpretation-tasks"]').findAll('button')[index]!.trigger('click'); await flushPromises()
  }
  async function clickRun(wrapper: ReturnType<typeof mount>, index = 0) {
    await wrapper.get('[data-testid="interpretation-runs"]').findAll('button')[index]!.trigger('click'); await flushPromises()
  }
  it.each(['SUCCEEDED', 'FAILED'] as const)('lazily reads exact standalone Task/Run/Context/Prompt lineage for %s without mutating profiles', async status => {
    reads(profileState(draft))
    const task = report('report-task', status), run = attempt('report-run', task.task_id, status), frozen = trace()
    const tasks = vi.spyOn(characterProfiles, 'interpretations').mockResolvedValue([task])
    const runs = vi.spyOn(api, 'runs').mockResolvedValue([run])
    const contexts = vi.spyOn(api, 'context').mockResolvedValue(frozen.context)
    const lineages = vi.spyOn(api, 'lineage').mockResolvedValue(frozen.lineage)
    const interpret = vi.spyOn(characterProfiles, 'interpret'), save = vi.spyOn(characterProfiles, 'save'), approve = vi.spyOn(characterProfiles, 'approve')
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(tasks).not.toHaveBeenCalled(); expect(runs).not.toHaveBeenCalled(); expect(contexts).not.toHaveBeenCalled()
    await openDebug(wrapper)
    expect(tasks).toHaveBeenCalledExactlyOnceWith('project-1', 'lin', expect.any(AbortSignal))
    await clickTask(wrapper); await clickRun(wrapper)
    expect(runs).toHaveBeenCalledExactlyOnceWith(task.task_id, expect.any(AbortSignal))
    expect(contexts).toHaveBeenCalledExactlyOnceWith(run.run_id, expect.any(AbortSignal))
    expect(lineages).toHaveBeenCalledExactlyOnceWith(run.run_id, expect.any(AbortSignal))
    expect(JSON.parse(wrapper.get('[data-testid="interpretation-task"] pre').text()).workflow_instance_id).toBeNull()
    expect(wrapper.get('[data-testid="interpretation-context"]').text()).toContain('context-hash-report-run')
    expect(wrapper.get('[data-testid="interpretation-lineage"]').text()).toContain('prompt-hash-report-run')
    if (status === 'SUCCEEDED') expect(wrapper.get('[data-testid="interpretation-tasks"]').text()).toContain(`草稿记录 ${draft.id}`)
    else expect(wrapper.get('[data-testid="interpretation-run"]').text()).toContain('MODEL_TIMEOUT')
    expect(interpret).not.toHaveBeenCalled(); expect(save).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('shows terminal Run evidence honestly when a failed Run has no Context or Prompt snapshot', async () => {
    reads(); vi.spyOn(characterProfiles, 'interpretations').mockResolvedValue([report('report-task', 'FAILED')])
    vi.spyOn(api, 'runs').mockResolvedValue([attempt('report-run', 'report-task', 'FAILED')])
    vi.spyOn(api, 'context').mockResolvedValue(null); vi.spyOn(api, 'lineage').mockResolvedValue(null)
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await openDebug(wrapper); await clickTask(wrapper); await clickRun(wrapper)
    expect(wrapper.get('[data-testid="interpretation-run"]').text()).toContain('MODEL_TIMEOUT')
    expect(wrapper.get('.character-debug').text()).toContain('此 Run 尚无 ContextPackage。')
    expect(wrapper.get('.character-debug').text()).toContain('此 Run 尚无 PromptLineage。')
    expect(wrapper.find('[data-testid="interpretation-context"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it.each(['project', 'character'] as const)('ignores a late Task list after switching %s', async scope => {
    reads()
    let complete!: (tasks: Task[]) => void
    const tasks = vi.spyOn(characterProfiles, 'interpretations').mockImplementationOnce(() => new Promise(resolve => { complete = resolve })).mockResolvedValueOnce([])
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await openDebug(wrapper)
    if (scope === 'project') await wrapper.setProps({ projectId: 'project-2' })
    else await wrapper.get('#profile-character').setValue('jun')
    await flushPromises(); complete([report()]); await flushPromises()
    expect(wrapper.get('[data-testid="interpretation-tasks"]').text()).not.toContain('report-task')
    expect(wrapper.get('.character-debug').text()).toContain('尚无人物解读记录')
    expect(tasks.mock.calls[0]?.[2]?.aborted).toBe(true)
    wrapper.unmount()
  })
  it('ignores a late Run list after selecting another Task', async () => {
    reads(); vi.spyOn(characterProfiles, 'interpretations').mockResolvedValue([report('first-task'), report('second-task')])
    let complete!: (runs: Run[]) => void
    const runs = vi.spyOn(api, 'runs').mockImplementationOnce(() => new Promise(resolve => { complete = resolve })).mockResolvedValueOnce([])
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await openDebug(wrapper); await clickTask(wrapper); await clickTask(wrapper, 1)
    complete([attempt('first-run', 'first-task')]); await flushPromises()
    expect(JSON.parse(wrapper.get('[data-testid="interpretation-task"] pre').text()).task_id).toBe('second-task')
    expect(wrapper.get('[data-testid="interpretation-runs"]').text()).not.toContain('first-run')
    expect(runs.mock.calls[0]?.[1]?.aborted).toBe(true)
    wrapper.unmount()
  })
  it('keeps the selected Run snapshot when an older Context response arrives later, and aborts on closing Debug', async () => {
    reads(); vi.spyOn(characterProfiles, 'interpretations').mockResolvedValue([report()])
    vi.spyOn(api, 'runs').mockResolvedValue([attempt('first-run'), attempt('second-run')])
    const first = trace('report-task', 'first-run'), second = trace('report-task', 'second-run')
    let complete!: (context: Context) => void
    const contexts = vi.spyOn(api, 'context').mockImplementationOnce(() => new Promise(resolve => { complete = resolve })).mockResolvedValueOnce(second.context)
    vi.spyOn(api, 'lineage').mockResolvedValueOnce(first.lineage).mockResolvedValueOnce(second.lineage)
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await openDebug(wrapper); await clickTask(wrapper); await clickRun(wrapper); await clickRun(wrapper, 1)
    complete(first.context); await flushPromises()
    expect(wrapper.get('[data-testid="interpretation-context"]').text()).toContain('context-hash-second-run')
    expect(wrapper.get('[data-testid="interpretation-lineage"]').text()).toContain('prompt-hash-second-run')
    expect(contexts.mock.calls[0]?.[1]?.aborted).toBe(true)
    await openDebug(wrapper, false)
    expect(contexts.mock.calls[1]?.[1]?.aborted).toBe(true)
    expect(wrapper.find('[data-testid="interpretation-run"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('isolates a mismatched trace error from usable profile editing', async () => {
    reads(profileState(draft)); vi.spyOn(characterProfiles, 'interpretations').mockResolvedValue([report()])
    vi.spyOn(api, 'runs').mockResolvedValue([attempt()])
    const frozen = trace(); frozen.lineage.agent_run_id = 'wrong-run'
    vi.spyOn(api, 'context').mockResolvedValue(frozen.context); vi.spyOn(api, 'lineage').mockResolvedValue(frozen.lineage)
    const wrapper = mount(CharacterProfileEditor, { props: { projectId: 'project-1' } })
    await flushPromises(); await openDebug(wrapper); await clickTask(wrapper); await clickRun(wrapper)
    expect(wrapper.get('.character-debug [role="alert"]').text()).toContain('INVALID_RESPONSE')
    expect(wrapper.find('[data-testid="interpretation-context"]').exists()).toBe(false)
    expect(wrapper.get('.character-edit fieldset').attributes('disabled')).toBeUndefined()
    await wrapper.get('#character-communication_style').setValue('调试失败仍可编辑')
    expect(wrapper.get('#character-communication_style').element).toHaveProperty('value', '调试失败仍可编辑')
    wrapper.unmount()
  })
  it('uses the existing paginated GET endpoint for standalone interpretations', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([report()])))
    vi.stubGlobal('fetch', fetch)
    expect(await characterProfiles.interpretations('project-1', 'lin')).toHaveLength(1)
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/v1/projects/project-1/characters/lin/behavior-profile/interpretations?limit=200&offset=0')
    expect(fetch.mock.calls[0]?.[1].method).toBe('GET')
    expect(fetch.mock.calls[0]?.[1].body).toBeUndefined()
  })
})
