import { computed, type Ref } from 'vue'
import type { Draft, QualityReview } from '../types/models'
import type { Snapshot } from './useConsole'

// A chapter may have several reviews of the same immutable version. Select by
// identity and the backend review revision, never by response array order.
export function reviewForDraft(reviews: QualityReview[], draftId?: string): QualityReview | null {
  return reviews.filter(review => review.chapter_version_id === draftId)
    .reduce<QualityReview | null>((latest, review) => !latest || review.version > latest.version ? review : latest, null)
}

export function useRevisionWorkspace(snapshot: Ref<Snapshot | null>, draft: Ref<Draft | null>) {
  const workflow = computed(() => snapshot.value?.workflow)
  const qualityReview = computed(() => reviewForDraft(snapshot.value?.qualityReviews ?? [], draft.value?.id))
  const revising = computed(() => Boolean(workflow.value?.revision_request_id))
  const revision = computed(() => snapshot.value?.revisions?.find(item => item.request.id === workflow.value?.revision_request_id) ?? null)
  const historical = computed(() => Boolean(draft.value && draft.value.version !== snapshot.value?.chapter.current_version))
  const reviewReady = computed(() => !historical.value && !revising.value && workflow.value?.status === 'WAITING_HUMAN' &&
    ['C10_REVISION', 'C11_INTERNAL_PASS'].includes(workflow.value.current_state) &&
    qualityReview.value?.binding.workflow_id === workflow.value.id)
  const revisionAvailable = computed(() => reviewReady.value && qualityReview.value?.body.overall_verdict !== 'PASS')
  const revisionMissingProfile = computed(() => revisionAvailable.value && !qualityReview.value?.binding.profile_record_id)
  const reviewNeedsRereview = computed(() => revisionMissingProfile.value || (reviewReady.value && qualityReview.value?.freshness === 'STALE'))
  const canRevise = computed(() => revisionAvailable.value && !revisionMissingProfile.value && qualityReview.value?.freshness === 'CURRENT')
  const revisionForDraft = computed(() => snapshot.value?.revisions?.find(item => item.result?.chapter_version_id === draft.value?.id))
  const fidelityFailed = computed(() => revising.value && revision.value?.result?.body.fidelity?.verdict === 'FAIL')
  // The stop transition increments state_version once. Ignore earlier attempts
  // and other workflows; Fidelity is owned by A05, not A06.
  const stoppedTask = computed(() => snapshot.value?.tasks.find(task => workflow.value &&
    task.workflow_instance_id === workflow.value.id && task.workflow_state === workflow.value.resume_state &&
    task.workflow_state_version === workflow.value.state_version - 1 && ['BLOCKED', 'FAILED'].includes(task.status)))
  const contextBudgetBlocked = computed(() => revising.value && workflow.value?.status === 'BLOCKED' && stoppedTask.value?.last_error_code === 'CONTEXT_BUDGET_EXCEEDED')
  const revisionNeedsRereview = computed(() => workflow.value?.status === 'BLOCKED' && workflow.value.resume_state === 'C10_REVISION' && revising.value && Boolean(
    revision.value?.result || (stoppedTask.value?.status === 'BLOCKED' &&
      ['PLAN_CHAPTER_REVISION', 'REVISE_CHAPTER', 'VALIDATE_REVISION_FIDELITY'].includes(stoppedTask.value.task_type)),
  ))
  const blockedReasons = computed(() => {
    const item = revision.value
    return [item?.result?.body.blocked_reasons, item?.candidate?.body.blocked_reasons, item?.plan?.body.blocked_reasons].find(reasons => reasons?.length) ?? []
  })
  const revisionStopped = computed(() => Boolean(workflow.value && ['BLOCKED', 'FAILED', 'CANCELLED', 'PAUSED'].includes(workflow.value.status)))
  const reviewPending = computed(() => workflow.value?.current_state === 'C09_INTERNAL_REVIEW' && workflow.value.status === 'WAITING_AGENT' && draft.value?.version === workflow.value.draft_version)
  const revisionHeading = computed(() => {
    if (workflow.value?.status === 'PAUSED') return '修改已暂停'
    if (workflow.value?.status === 'CANCELLED') return '修改已取消'
    if (revisionNeedsRereview.value) return '修改需要处理'
    if (revisionStopped.value) return workflow.value?.resume_state === 'C09_INTERNAL_REVIEW' ? '重新审阅失败' : '修改正文失败'
    return workflow.value?.current_state === 'C09_INTERNAL_REVIEW' ? 'AI 正在重新审阅…' : 'AI 正在修改正文…'
  })
  return { qualityReview, revising, revision, historical, revisionMissingProfile, reviewNeedsRereview, canRevise,
    revisionForDraft, fidelityFailed, contextBudgetBlocked, revisionNeedsRereview, blockedReasons, revisionStopped, reviewPending, revisionHeading }
}
