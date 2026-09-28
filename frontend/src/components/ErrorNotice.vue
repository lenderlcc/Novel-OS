<script setup lang="ts">
import { computed } from 'vue'
import type { ApiError } from '../api/client'
const props = defineProps<{ error: ApiError }>()
const copy: Record<string, [string, string]> = {
  VERSION_CONFLICT: ['内容已经变化', '当前内容已经发生变化，请刷新页面后再操作。'],
  MODEL_UNAVAILABLE: ['模型服务暂时不可用', '生成没有完成，请稍后再试。'],
  MODEL_TIMEOUT: ['生成等待超时', '模型响应时间过长，请稍后再试。'],
  MODEL_AUTH_ERROR: ['模型服务配置有误', '当前无法调用模型，请检查本机配置。'],
  EXECUTION_SCOPE_DISABLED: ['当前阶段尚未开放', '当前操作尚未启用，请调整本机执行设置后刷新。'],
  NETWORK_ERROR: ['无法连接服务', '请确认后台服务正在运行，然后刷新页面。'],
}
const message = computed(() => copy[props.error.code] ?? ['操作没有完成', props.error.message])
</script>
<template>
  <section class="error-notice" role="alert">
    <h2>{{ message[0] }}</h2><p>{{ message[1] }}</p>
    <details><summary>查看技术详情</summary><dl class="human-values"><dt>错误代码</dt><dd><code>{{ error.code }}</code></dd><dt>Request ID</dt><dd><code>{{ error.requestId || '服务未提供' }}</code></dd></dl><pre v-if="error.details">{{ JSON.stringify(error.details, null, 2) }}</pre></details>
  </section>
</template>
