import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import WritingProfile from '../src/components/WritingProfile.vue'
import { writingProfiles, type Profile, type ProfileState } from '../src/api/writingProfiles'
import { ApiError } from '../src/api/client'

const empty: ProfileState = { current: null, approved: null, current_profile_version: null, approved_profile_version: null }
const draft: Profile = { id: 'record-1', profile_id: 'project-1', project_id: 'project-1', version: 1,
  status: 'DRAFT', target_audience: '主流中文网络小说读者', authority_level: 'A5_USER_PREFERENCE', source: 'USER',
  profile_hash: 'hash', created_at: '2026-09-16T00:00:00Z', created_by: 'local-user', approved_at: null, approved_by: null }
const button = (wrapper: ReturnType<typeof mount>, text: string) => wrapper.findAll('button').find(b => b.text().includes(text))!
afterEach(() => vi.restoreAllMocks())

describe('project writing preference manual approval', () => {
  it.each([['FIRST_PERSON', '第一人称'], ['THIRD_PERSON', '第三人称']] as const)('saves %s as a new draft and requires exact-version approval', async (perspective, label) => {
    const approved = { ...draft, status: 'APPROVED' as const }
    const next = { ...draft, version: 2, narrative_perspective: perspective }
    vi.spyOn(writingProfiles, 'state').mockResolvedValue({ current: approved, approved, current_profile_version: 1, approved_profile_version: 1 })
    const save = vi.spyOn(writingProfiles, 'save').mockResolvedValue(next)
    const approve = vi.spyOn(writingProfiles, 'approve').mockResolvedValue({ ...next, status: 'APPROVED' })
    const wrapper = mount(WritingProfile, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.get('.profile-summary').text()).toContain('叙事人称未设置')
    expect((wrapper.get('#profile-perspective').element as HTMLSelectElement).selectedOptions[0]!.text).toBe('未指定')
    expect(wrapper.get(`#profile-perspective option[value="${perspective}"]`).text()).toBe(label)
    await wrapper.get('#profile-perspective').setValue(perspective)
    expect(save).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(save).toHaveBeenCalledExactlyOnceWith('project-1', expect.objectContaining({ narrative_perspective: perspective }), 1)
    expect(wrapper.text()).toContain('当前 v2 · 已批准 v1')
    expect(wrapper.get('.profile-summary').text()).toContain('叙事人称未设置')
    expect(approve).not.toHaveBeenCalled()
    await button(wrapper, '批准 Profile v2').trigger('click'); await flushPromises()
    expect(approve).toHaveBeenCalledExactlyOnceWith('project-1', 2)
    expect(wrapper.get('.profile-summary').text()).toContain(`叙事人称${label}`)
    wrapper.unmount()
  })
  it('loads an existing perspective and can explicitly clear it in the next draft', async () => {
    const approved = { ...draft, status: 'APPROVED' as const, narrative_perspective: 'THIRD_PERSON' as const }
    vi.spyOn(writingProfiles, 'state').mockResolvedValue({ current: approved, approved, current_profile_version: 1, approved_profile_version: 1 })
    const save = vi.spyOn(writingProfiles, 'save').mockResolvedValue({ ...draft, version: 2, narrative_perspective: null })
    const approve = vi.spyOn(writingProfiles, 'approve')
    const wrapper = mount(WritingProfile, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect((wrapper.get('#profile-perspective').element as HTMLSelectElement).value).toBe('THIRD_PERSON')
    await wrapper.get('#profile-perspective').setValue('未指定')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(save).toHaveBeenCalledExactlyOnceWith('project-1', expect.objectContaining({ narrative_perspective: null }), 1)
    expect(approve).not.toHaveBeenCalled()
    expect(wrapper.get('.profile-summary').text()).toContain('叙事人称第三人称')
    wrapper.unmount()
  })
  it('loading example only fills form; save and approve are separate exact-version commands', async () => {
    vi.spyOn(writingProfiles, 'state').mockResolvedValue(empty)
    const save = vi.spyOn(writingProfiles, 'save').mockResolvedValue(draft)
    const approve = vi.spyOn(writingProfiles, 'approve').mockResolvedValue({ ...draft, status: 'APPROVED' })
    const wrapper = mount(WritingProfile, { props: { projectId: 'project-1' } })
    await flushPromises()
    expect(wrapper.text()).toContain('尚未设置写作偏好')
    await button(wrapper, '载入网文测试示例').trigger('click')
    expect(save).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    expect((wrapper.get('#profile-audience').element as HTMLInputElement).value).toBe('主流中文网络小说读者')
    expect((wrapper.get('#profile-pacing').element as HTMLSelectElement).value).toBe('MEDIUM_FAST')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(save).toHaveBeenCalledWith('project-1', expect.objectContaining({ pacing: 'MEDIUM_FAST', relationship_payoff_visibility: 'MEDIUM_HIGH' }), 0)
    expect(approve).not.toHaveBeenCalled()
    await button(wrapper, '批准 Profile v1').trigger('click'); await flushPromises()
    expect(approve).toHaveBeenCalledExactlyOnceWith('project-1', 1)
    expect(wrapper.text()).toContain('已批准 v1')
    wrapper.unmount()
  })
  it('editing approved profile saves v2 draft while approved v1 remains visible', async () => {
    const approved = { ...draft, status: 'APPROVED' as const }
    vi.spyOn(writingProfiles, 'state').mockResolvedValue({ current: approved, approved, current_profile_version: 1, approved_profile_version: 1 })
    const save = vi.spyOn(writingProfiles, 'save').mockResolvedValue({ ...draft, version: 2 })
    vi.spyOn(writingProfiles, 'approve').mockResolvedValue(approved)
    const wrapper = mount(WritingProfile, { props: { projectId: 'project-1' } })
    await flushPromises()
    await wrapper.get('#profile-audience').setValue('新偏好')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(save.mock.calls[0]![2]).toBe(1)
    expect(wrapper.text()).toContain('当前 v2 · 已批准 v1')
    await wrapper.get('#profile-audience').setValue('未保存修改')
    expect(button(wrapper, '批准 Profile v2').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('stale approval requires explicit reload and never retries automatically', async () => {
    vi.spyOn(writingProfiles, 'state').mockResolvedValue({ ...empty, current: draft, current_profile_version: 1 })
    const approve = vi.spyOn(writingProfiles, 'approve').mockRejectedValue(new ApiError('VERSION_CONFLICT', 'changed', 'test', 409))
    const wrapper = mount(WritingProfile, { props: { projectId: 'project-1' } })
    await flushPromises(); await button(wrapper, '批准 Profile').trigger('click'); await flushPromises()
    expect(approve).toHaveBeenCalledTimes(1)
    expect(button(wrapper, '批准 Profile').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('VERSION_CONFLICT')
    wrapper.unmount()
  })
  it('project change clears old state and ignores a late response in the same component', async () => {
    let complete!: (v: ProfileState) => void
    const load = vi.spyOn(writingProfiles, 'state').mockImplementationOnce(() => new Promise(resolve => { complete = resolve })).mockResolvedValue(empty)
    const save = vi.spyOn(writingProfiles, 'save')
    const approve = vi.spyOn(writingProfiles, 'approve')
    const current = mount(WritingProfile, { props: { projectId: 'old' } })
    await current.setProps({ projectId: 'new' })
    await flushPromises()
    complete({ ...empty, current: draft, current_profile_version: 1 }); await flushPromises()
    expect(load).toHaveBeenCalledWith('new', expect.any(AbortSignal))
    expect(current.text()).toContain('当前 v—')
    expect(save).not.toHaveBeenCalled(); expect(approve).not.toHaveBeenCalled()
    current.unmount()
  })
})
