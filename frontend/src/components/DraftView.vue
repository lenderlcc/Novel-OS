<script setup lang="ts">
import type { Draft } from '../types/models'
defineProps<{ draft: Draft; chapterNumber?: number; reviewHref?: string; versions?: Draft[]; currentVersion?: number | null }>()
defineEmits<{ evaluate: []; selectVersion: [version: number] }>()
</script>
<template>
  <article class="reader" data-testid="draft">
    <header class="reader-header"><div><p>第 {{ chapterNumber ?? '—' }} 章</p><h2>正文草稿</h2></div>
      <div class="draft-meta">
        <template v-if="versions?.length">
          <label class="sr-only" for="draft-version">正文版本</label>
          <select id="draft-version" :value="draft.version" @change="$emit('selectVersion', Number(($event.target as HTMLSelectElement).value))">
            <option v-for="item in [...versions].sort((a, b) => b.version - a.version)" :key="item.id" :value="item.version">Draft v{{ item.version }}{{ item.version === currentVersion ? ' · 当前' : item.version === 1 ? ' · 原稿' : ' · 历史' }}</option>
          </select>
        </template>
        <span v-else>Draft v{{ draft.version }} · {{ draft.status }}</span>
      </div>
    </header>
    <p v-if="currentVersion && draft.version !== currentVersion" class="muted" role="status">正在阅读历史正文 v{{ draft.version }}。当前正文仍为 v{{ currentVersion }}。</p>
    <slot name="before-prose" />
    <div class="prose" tabindex="0" aria-label="章节正文">{{ draft.content }}</div>
    <footer class="reader-actions">
      <a v-if="reviewHref" :href="reviewHref">查看 AI 审阅</a>
      <slot name="actions" />
      <button class="primary" type="button" @click="$emit('evaluate')">人工评价</button>
      <p>人工评价只对应正在查看的正文版本。</p>
    </footer>
  </article>
</template>
