<script setup lang="ts">
import type { Draft } from '../types/models'
defineProps<{ draft: Draft; chapterNumber?: number }>()
defineEmits<{ evaluate: [] }>()
</script>
<template>
  <article class="reader" data-testid="draft">
    <header class="reader-header"><div><p>第 {{ chapterNumber ?? '—' }} 章</p><h2>正文草稿</h2></div><div class="draft-meta">Draft v{{ draft.version }} · {{ draft.status }}</div></header>
    <div class="prose" tabindex="0" aria-label="章节正文">{{ draft.content }}</div>
    <footer class="reader-actions"><button class="primary" type="button" @click="$emit('evaluate')">人工评价</button><p>人工评价只对应当前正文版本。</p></footer>
  </article>
</template>
