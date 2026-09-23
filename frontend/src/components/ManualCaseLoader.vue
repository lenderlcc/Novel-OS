<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import type { ManualCase } from '../data/manualCases'
withDefaults(defineProps<{ cases: ManualCase[]; selectedId?: string | null; canLoad?: boolean }>(), { canLoad: true })
defineEmits<{ load: [value: ManualCase]; close: [] }>()
const closeButton = ref<HTMLButtonElement | null>(null)
onMounted(() => { void nextTick(() => closeButton.value?.focus()) })
</script>

<template>
  <div class="drawer-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="test-mode-title">
      <div class="drawer-header">
        <div><h2 id="test-mode-title">人工测试</h2><p>只会填入自然语言需求，后续仍走真实流程。</p></div>
        <button ref="closeButton" class="quiet" aria-label="关闭人工测试" @click="$emit('close')">关闭</button>
      </div>
      <p class="notice">建议使用独立测试项目运行该 Case，避免已批准的前文章节影响本次测试。载入操作只填入当前案例需求。</p>
      <div class="case-list">
        <article v-for="item in cases" :key="item.id" class="case-item" :class="{ selected: item.id === selectedId }">
          <div><h3>{{ item.id.replace('-', ' ').replace('case', 'Case') }} · {{ item.name }}</h3><p>{{ item.purpose }}</p></div>
          <button type="button" :disabled="canLoad === false" @click="$emit('load', item)">载入需求</button>
        </article>
      </div>
      <p v-if="canLoad === false" class="notice" role="status">当前章节已开始创作。请在新章节的需求页载入测试案例。</p>
    </aside>
  </div>
</template>
