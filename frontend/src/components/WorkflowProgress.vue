<script setup lang="ts">
import { computed } from 'vue'
import type { Workflow, Task, ExecutionConfig } from '../types/models'
import { currentTask, isReviewResume, progressLabel, resumeCallsModel } from '../composables/workflowState'
const props = defineProps<{ workflow: Workflow; tasks: Task[]; config?: ExecutionConfig | null; canResume?: boolean; hideResume?: boolean; currentDraftVersion?: number | null }>()
defineEmits<{ resume: [] }>()
const task = computed(() => currentTask(props.workflow, props.tasks))
const requirementOnly = computed(() => props.config?.task_types?.length === 1 && props.config.task_types[0] === 'PARSE_CHAPTER_REQUIREMENT')
const stateNumber = computed(() => Number(props.workflow.current_state.slice(1, 3)))
const phase = computed(() => props.workflow.revision_request_id || props.workflow.revision_count > 0 ? 4 : stateNumber.value <= 3 ? 0 : stateNumber.value <= 6 ? 1 : stateNumber.value <= 8 ? 2 : 3)
// A terminal workflow transition advances the state version once. Errors from
// earlier review/revision attempts must not describe the current stop reason.
const failedTask = computed(() => props.tasks.find(t => t.workflow_instance_id === props.workflow.id &&
  t.workflow_state_version === props.workflow.state_version - 1 && ['FAILED', 'BLOCKED'].includes(t.status) && t.last_error_code))
const stopped = computed(() => stateNumber.value >= 90)
const reviewResume = computed(() => isReviewResume(props.workflow, props.tasks))
const stages = computed(() => props.workflow.workflow_definition_version === 3 && !props.workflow.simulation ? ['需求', '方案', '正文', '审阅', '修改'] : ['需求', '方案', '正文'])
const technicalCode = computed(() => failedTask.value?.last_error_code || props.workflow.block_reason || props.workflow.blocked_guard || props.workflow.current_state)
const failureMessage = computed(() => {
  const copy: Record<string, string> = {
    MODEL_AUTH_ERROR: '模型服务配置有误，请检查本机配置后重试。',
    MODEL_UNAVAILABLE: '模型服务暂时不可用，请稍后再试。',
    MODEL_TIMEOUT: '模型响应时间过长，请稍后再试。',
    CONTEXT_BUDGET_EXCEEDED: '所需内容超出当前处理预算，现有正文已保留。',
    CONTEXT_STALE: '任务依据已经变化，现有正文已保留。请刷新查看。',
    SCHEMA_PARSE_ERROR: '模型返回的内容未通过格式校验，现有正文已保留。',
    REVISION_EVIDENCE_MISMATCH: '引用证据定位失败：引文与所标段落不匹配，现有正文已保留。',
    EXTERNAL_CONDITION: '当前流程未满足继续条件，已有正文已保留。请查看下方原因。',
  }
  return copy[technicalCode.value] || '当前流程未能完成，已保留现有内容。请查看详情或使用允许的恢复操作。'
})
</script>
<template>
  <section class="process-status" aria-label="创作进度">
    <h2>{{ progressLabel(workflow, tasks, config) }}</h2>
    <ol class="progress" :style="{ gridTemplateColumns: `repeat(${stages.length}, 1fr)` }"><li v-for="(name, index) in stages" :key="name" :class="{ done: !stopped && index < phase, active: !stopped && index === phase }" :aria-current="!stopped && index === phase ? 'step' : undefined"><span>{{ !stopped && index < phase ? '✓' : index + 1 }}</span>{{ name }}</li></ol>
    <div v-if="stopped" class="blocked" role="status">
      <h3>{{ workflow.current_state === 'C90_BLOCKED' ? '当前流程暂停' : workflow.current_state === 'C91_FAILED' ? '生成失败' : '流程已停止' }}</h3>
      <p>{{ failureMessage }}</p>
      <details><summary>查看技术详情</summary><p><code>{{ technicalCode }}</code></p><p v-if="workflow.block_reason">{{ workflow.block_reason }}</p><p>关联运行记录可在 Debug 中查看。</p></details>
      <button v-if="workflow.current_state === 'C90_BLOCKED' && !hideResume" :disabled="!canResume" @click="$emit('resume')">{{ reviewResume && currentDraftVersion ? `重新审阅正文 v${currentDraftVersion}` : '重试本阶段' }}（会调用模型）</button>
    </div>
    <div v-else-if="workflow.status === 'PAUSED'" class="paused"><p>已保留当前内容，可以继续这个流程。</p><button :disabled="!canResume" @click="$emit('resume')">{{ reviewResume && currentDraftVersion ? `重新审阅正文 v${currentDraftVersion}` : requirementOnly && workflow.current_state === 'C01_REQUIREMENT_INTAKE' ? '继续理解需求' : '继续' }}{{ resumeCallsModel(workflow, config, tasks) ? '（会调用模型）' : '' }}</button></div>
    <p v-else-if="workflow.current_state === 'C06_PLAN_APPROVAL'">方案已经准备好，请确认下一步。</p>
    <p v-else-if="workflow.current_state === 'C07_WRITING'">AI 正在生成正文，可能需要一些时间。</p>
    <p v-else-if="task?.status === 'PENDING' && config?.task_types && !config.task_types.includes(task.task_type)" class="notice">当前阶段未在本机执行范围内，任务会保持等待。请调整设置后刷新。</p>
    <p v-else-if="task?.status === 'PENDING'">等待后台开始执行。</p>
  </section>
</template>
