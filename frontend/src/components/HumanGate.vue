<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Decision, Gate } from '../types/models'
const props = defineProps<{ gate: Gate; busy: boolean; writingEnabled: boolean }>()
const emit = defineEmits<{ decide: [decision: Decision, reason: string] }>()
const mode = ref<'alternative' | 'modify' | null>(null), feedback = ref('')
watch(() => props.gate.id, () => { mode.value = null; feedback.value = '' })
function submit(decision: Decision) {
  if (decision === 'MODIFY' && !feedback.value.trim()) return
  emit('decide', decision, feedback.value)
}
</script>
<template>
  <section class="human-gate" data-testid="human-gate">
    <div class="gate-actions">
      <button class="primary" :disabled="busy || !writingEnabled" @click="submit('APPROVE')">批准并开始写作</button>
      <button :disabled="busy" @click="mode = mode === 'alternative' ? null : 'alternative'; feedback = ''">换一个方案</button>
      <button :disabled="busy" @click="mode = mode === 'modify' ? null : 'modify'; feedback = ''">我想修改</button>
    </div>
    <div v-if="mode" class="gate-feedback">
      <label for="feedback">{{ mode === 'modify' ? '告诉 AI 哪些地方需要调整' : '如果你有要求，可以告诉 AI；也可以直接重新生成' }}</label>
      <textarea id="feedback" v-model="feedback" rows="4" maxlength="2000" :placeholder="mode === 'modify' ? '例如：冲突突然一点，双方都要有合理立场，其他方向不变。' : '可选'" :disabled="busy" />
      <div class="gate-feedback-actions"><button :disabled="busy || (mode === 'modify' && !feedback.trim())" @click="submit(mode === 'modify' ? 'MODIFY' : 'REQUEST_ALTERNATIVE')">重新生成方案</button><button class="quiet" @click="mode = null">取消</button></div>
    </div>
    <p v-if="!writingEnabled" class="notice" role="status">Writing 当前未开放。启用 WRITE_CHAPTER 并刷新后才能批准。</p>
  </section>
</template>
