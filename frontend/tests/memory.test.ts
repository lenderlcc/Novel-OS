import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MemoryCompletion from '../src/components/MemoryCompletion.vue'
import { sample, clone } from './fixtures'
import type { MemoryHistory, Workflow } from '../src/types/models'

function setup(options: { conflict?: boolean; empty?: boolean; status?: Workflow['status']; historical?: boolean; stale?: boolean; ready?: boolean } = {}) {
  const draft = clone(sample.snapshot.drafts[0]!)
  const workflow = { ...clone(sample.snapshot.workflow), workflow_definition_version: 3, memory_request_id: 'request', current_state: 'C15_MEMORY_COMMIT' as const, status: options.status ?? 'WAITING_HUMAN' as const }
  const candidate = { id: 'knowledge', candidate_type: 'CHARACTER_KNOWLEDGE', statement: 'A 怀疑船长藏着钥匙', subject_ref: { name: 'A' }, epistemic_status: 'SUSPECTS', conflict_status: options.conflict ? 'AUTHORITY_CONFLICT' : 'NONE', conflict_reason: '与锁定设定冲突', previous_statement: 'A 不知道钥匙' }
  const memory = { request: { id: 'request', chapter_version_id: options.historical ? 'different-source' : draft.id, draft_version: 3 }, proposal: { id: 'proposal', candidates: options.empty ? [] : [candidate] }, status: options.stale ? 'STALE' : options.status === 'COMPLETED' ? 'COMMITTED' : 'PROPOSED' } as unknown as MemoryHistory
  if (options.ready) { workflow.memory_request_id = ''; workflow.current_state = 'C11_INTERNAL_PASS' as typeof workflow.current_state }
  return mount(MemoryCompletion, { props: { workflow, draft, currentVersion: draft.version, memory: options.ready ? undefined : memory, disabled: false } })
}
describe('chapter completion confirmation', () => {
  it('requires explicit click and preserves suspicion as suspicion', async () => {
    const w = setup()
    expect(w.emitted('confirm')).toBeUndefined()
    expect(w.text()).toContain('怀疑')
    await w.get('button.primary').trigger('click')
    expect(w.emitted('confirm')).toEqual([[['knowledge']]])
  })
  it('allows excluding candidates', async () => {
    const w = setup()
    await w.get('input').setValue(false)
    await w.get('button.primary').trigger('click')
    expect(w.emitted('confirm')).toEqual([[[]]])
  })
  it('does not preselect conflicts and blocks selected conflicts', async () => {
    const w = setup({ conflict: true })
    expect((w.get('input').element as HTMLInputElement).checked).toBe(false)
    expect(w.text()).toContain('已有设定')
    await w.get('input').setValue(true)
    expect(w.get('button.primary').attributes('disabled')).toBeDefined()
  })
  it('permits an explicit empty commit', async () => {
    const w = setup({ empty: true })
    expect(w.text()).toContain('没有需要新增的长期记忆')
    await w.get('button.primary').trigger('click')
    expect(w.emitted('confirm')).toEqual([[[]]])
  })
  it('cannot confirm while displaying another draft', () => {
    const w = setup({ historical: true })
    expect(w.text()).toContain('请返回正文 v3')
    expect(w.get('button.primary').attributes('disabled')).toBeDefined()
  })
  it('stale proposal only offers return', () => {
    const w = setup({ stale: true })
    expect(w.find('button.primary').exists()).toBe(false)
    expect(w.text()).toContain('本次候选尚未写入')
  })
  it('blocked extraction can return without another model call', async () => {
    const w = setup({ status: 'BLOCKED' })
    expect(w.text()).toContain('暂时无法整理')
    await w.get('button').trigger('click')
    expect(w.emitted('discard')).toEqual([[]])
  })
  it('terminal failed workflow has no unusable back control', () => {
    expect(setup({ status: 'FAILED' }).findAll('button')).toHaveLength(0)
  })
  it('completed chapter is read only', () => {
    const w = setup({ status: 'COMPLETED' })
    expect(w.text()).toContain('章节已完成')
    expect(w.findAll('button')).toHaveLength(0)
  })
  it('start completion shows model notice and requires user action', async () => {
    const w = setup({ ready: true })
    expect(w.text()).toContain('此操作会调用模型')
    expect(w.emitted('request')).toBeUndefined()
    await w.get('button').trigger('click')
    expect(w.emitted('request')).toEqual([[]])
  })
})
