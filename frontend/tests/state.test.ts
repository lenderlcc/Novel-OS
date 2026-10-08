import { describe, expect, it } from 'vitest'
import { pollDelay, stateLabel } from '../src/composables/workflowState'
import type { Workflow } from '../src/types/models'
import { sample } from './fixtures'

const workflow = (current_state: string, status = 'WAITING_AGENT') => ({ current_state, status, simulation: false, workflow_definition_id: 'chapter-planning', workflow_definition_version: 2 }) as Workflow
describe('workflow presentation and polling policy', () => {
  it('stops polling when the current task is excluded by execution policy', () => {
    const w = { ...sample.snapshot.workflow, current_state: 'C04_CHAPTER_PLANNING' as const, status: 'WAITING_AGENT' as const }
    const task = { ...sample.snapshot.tasks[0]!, workflow_instance_id: w.id, workflow_state: w.current_state, workflow_state_version: w.state_version, task_type: 'PLAN_CHAPTER', status: 'PENDING' as const }
    const config = { model_profile: 'lingzhi-requirement', provider: 'lingzhi', model: 'gpt-5.6-sol', task_types: ['PARSE_CHAPTER_REQUIREMENT'], max_attempts: 1 }
    expect(pollDelay(w, [task], config)).toBeNull()
    expect(pollDelay(w, [task])).toBe(1500)
    const enabled = { ...config, model_profile: 'lingzhi-structured', task_types: ['PARSE_CHAPTER_REQUIREMENT', 'PLAN_CHAPTER', 'REVIEW_CHAPTER_PLAN', 'WRITE_CHAPTER'] }
    expect(pollDelay(w, [task], enabled)).toBe(1500)
    expect(pollDelay({ ...w, current_state: 'C06_PLAN_APPROVAL' }, [], enabled)).toBeNull()
  })
  it.each(['C01_REQUIREMENT_INTAKE', 'C02_CONTEXT_ASSEMBLY', 'C03_REQUIREMENT_READY', 'C04_CHAPTER_PLANNING', 'C05_PLAN_REVIEW', 'C07_WRITING'])('polls active %s at 1.5 seconds', state => {
    expect(pollDelay(workflow(state))).toBe(1500)
    expect(stateLabel(state)).not.toContain('暂不提供')
  })
  it.each(['C00_CREATED', 'C06_PLAN_APPROVAL', 'C08_DETERMINISTIC_CHECK', 'C90_BLOCKED', 'C91_FAILED', 'C92_CANCELLED', 'C09_REVIEW', 'FUTURE_STATE'])('stops at %s without crashing', state => {
    expect(pollDelay(workflow(state))).toBeNull()
    expect(stateLabel(state)).toBeTruthy()
  })
  it('stops while paused or on historical/simulation definitions', () => {
    expect(pollDelay(workflow('C07_WRITING', 'PAUSED'))).toBeNull()
    expect(pollDelay({ ...workflow('C07_WRITING'), simulation: true })).toBeNull()
    expect(pollDelay({ ...workflow('C07_WRITING'), workflow_definition_version: 1 })).toBeNull()
    expect(pollDelay(null)).toBeNull()
  })
})
