import fixture from './fixtures/writing.json'
import type { Snapshot } from '../src/composables/useConsole'
import type { Context, Lineage, Run, Transition } from '../src/types/models'

// Actual API responses from the isolated Mock E2E schema; no credentials or user data.
export const sample = fixture as unknown as { snapshot: Snapshot; context: Context; lineage: Lineage; runs: Run[]; transitions: Transition[] }
export const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
export function waitingSnapshot(): Snapshot {
  const s = clone(sample.snapshot)
  s.workflow.current_state = 'C06_PLAN_APPROVAL'; s.workflow.status = 'WAITING_HUMAN'
  s.workflow.state_version = s.gates[0]!.opened_state_version; s.workflow.draft_version = null
  s.gates[0]!.status = 'WAITING'; s.plans[0]!.status = 'PROPOSED'
  s.chapter.approved_plan_version = null; s.chapter.current_version = null
  s.drafts = []; s.writing = []
  return s
}
