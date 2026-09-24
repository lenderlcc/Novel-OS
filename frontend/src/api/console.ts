import { optional, pages, request } from './client'
import type { Project, Chapter, Workflow, Gate, Brief, Plan, Planning, PlanningHistory, Draft, Writing, Task, Run, Transition, Context, Lineage, Dispatch, Decision, ExecutionConfig, QualityReview } from '../types/models'

const chapterPath = (p: string, c: string) => `/projects/${p}/chapters/${c}`
const workflowPath = (w: string) => `/workflows/${w}`
export const api = {
  executionConfig: (signal?: AbortSignal) => request<ExecutionConfig>('/agent-execution/config', { signal }),
  projects: (signal?: AbortSignal) => pages<Project>('/projects', signal),
  createProject: (name: string) => request<Project>('/projects', { body: { name } }),
  chapters: (p: string, signal?: AbortSignal) => pages<Chapter>(`/projects/${p}/chapters`, signal),
  createChapter: (p: string, title: string, sequence: number) => request<Chapter>(`/projects/${p}/chapters`, { body: { title, sequence } }),
  chapter: (p: string, c: string, signal?: AbortSignal) => request<Chapter>(chapterPath(p, c), { signal }),
  workflows: (p: string, c: string, signal?: AbortSignal) => pages<Workflow>(`${chapterPath(p, c)}/workflows`, signal),
  workflow: (w: string, signal?: AbortSignal) => request<Workflow>(workflowPath(w), { signal }),
  gates: (w: string, signal?: AbortSignal) => pages<Gate>(`${workflowPath(w)}/human-gates`, signal),
  brief: (w: string, signal?: AbortSignal) => optional(request<Brief>(`${workflowPath(w)}/creative-brief`, { signal })),
  plans: (p: string, c: string, signal?: AbortSignal) => pages<Plan>(`${chapterPath(p, c)}/plans`, signal),
  planning: (w: string, v: number, signal?: AbortSignal) => optional(request<Planning>(`${workflowPath(w)}/planning/plan/versions/${v}`, { signal })),
  history: async (w: string, signal?: AbortSignal): Promise<PlanningHistory> => {
    const all: PlanningHistory = { briefs: [], plans: [], reviews: [] }
    for (let offset = 0; ; offset += 200) {
      const page = await request<PlanningHistory>(`${workflowPath(w)}/planning/history?limit=200&offset=${offset}`, { signal })
      all.briefs.push(...page.briefs); all.plans.push(...page.plans); all.reviews.push(...page.reviews)
      if (Math.max(page.briefs.length, page.plans.length, page.reviews.length) < 200) return all
    }
  },
  drafts: (p: string, c: string, signal?: AbortSignal) => pages<Draft>(`${chapterPath(p, c)}/versions`, signal),
  qualityReviews: (p: string, c: string, signal?: AbortSignal) => pages<QualityReview>(`${chapterPath(p, c)}/quality-reviews`, signal),
  writing: (w: string, signal?: AbortSignal) => pages<Writing>(`${workflowPath(w)}/writing/history`, signal),
  tasks: (w: string, signal?: AbortSignal) => pages<Task>(`${workflowPath(w)}/agent-tasks`, signal),
  transitions: (w: string, signal?: AbortSignal) => pages<Transition>(`${workflowPath(w)}/history`, signal),
  runs: (t: string, signal?: AbortSignal) => pages<Run>(`/agent-tasks/${t}/runs`, signal),
  context: (r: string, signal?: AbortSignal) => optional(request<Context>(`/agent-runs/${r}/context`, { signal })),
  lineage: (r: string, signal?: AbortSignal) => optional(request<Lineage>(`/agent-runs/${r}/prompt-lineage`, { signal })),
  start: (project_id: string, chapter_id: string, raw_requirement: string, event_id: string) => request<Dispatch>('/workflows/chapter-quality', { body: { event_id, project_id, chapter_id, raw_requirement } }),
  submit: (w: Workflow, event_id: string) => request<Dispatch>(`${workflowPath(w.id)}/events`, { body: { event_id, expected_state_version: w.state_version, event_type: 'USER_SUBMITTED', reason: '提交章节自然语言需求' } }),
  decide: (w: Workflow, gate: Gate, decision: Decision, reason: string, event_id: string) => request<Dispatch>(`/human-gates/${gate.id}/decision`, { body: { event_id, expected_state_version: w.state_version, expected_artifact_version: gate.artifact_version, decision, reason } }),
  control: (w: Workflow, action: 'pause' | 'resume' | 'cancel', reason: string, expectedDraftVersion?: number) => request<Dispatch>(`${workflowPath(w.id)}/${action}`, { body: { event_id: crypto.randomUUID(), expected_state_version: w.state_version, reason, ...(action === 'resume' && expectedDraftVersion !== undefined ? { expected_draft_version: expectedDraftVersion } : {}) } }),
}
