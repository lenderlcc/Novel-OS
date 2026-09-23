<script setup lang="ts">
import { ref } from 'vue'
import type { Chapter, Project } from '../types/models'

const props = withDefaults(defineProps<{
  projects: Project[]
  chapters: Chapter[]
  projectId: string
  chapterId: string
  disabled: boolean
  testDisabled?: boolean
  testAvailable?: boolean
}>(), { testDisabled: false, testAvailable: true })
const emit = defineEmits<{
  selectProject: [id: string]
  selectChapter: [id: string]
  createProject: [name: string]
  createChapter: [title: string, sequence: number]
  openProfile: []
  openTests: []
}>()
const projectName = ref(''), chapterTitle = ref(''), chapterSequence = ref(1)
function projectLabel(project: Project) {
  const matches = props.projects.filter(item => item.name === project.name)
  return matches.length > 1 ? `${project.name} (${matches.findIndex(item => item.id === project.id) + 1})` : project.name
}
function addProject() {
  const name = projectName.value.trim()
  if (!name) return
  emit('createProject', name); projectName.value = ''
}
function addChapter() {
  const title = chapterTitle.value.trim()
  if (!title) return
  emit('createChapter', title, chapterSequence.value); chapterTitle.value = ''
}
</script>

<template>
  <aside class="workspace-sidebar" aria-label="项目与章节">
    <div class="brand">Novel OS</div>
    <label class="sidebar-label" for="project">项目</label>
    <select id="project" :value="projectId" :disabled="disabled" @change="emit('selectProject', ($event.target as HTMLSelectElement).value)">
      <option value="">选择项目</option>
      <option v-for="project in projects" :key="project.id" :value="project.id">{{ projectLabel(project) }}</option>
    </select>

    <nav class="chapter-nav" aria-label="章节">
      <div class="sidebar-label">章节</div>
      <button v-for="chapter in chapters" :key="chapter.id" type="button" class="chapter-link"
        :class="{ selected: chapter.id === chapterId }" :disabled="disabled"
        @click="emit('selectChapter', chapter.id)">
        <span>第 {{ chapter.sequence }} 章</span>
        <span>{{ chapter.title }}</span>
      </button>
      <p v-if="projectId && !chapters.length" class="sidebar-empty">还没有章节</p>
    </nav>

    <details class="sidebar-create">
      <summary>＋ 新建章节</summary>
      <form @submit.prevent="addChapter">
        <label for="new-chapter">章节标题</label>
        <input id="new-chapter" v-model="chapterTitle" required maxlength="300" :disabled="disabled || !projectId">
        <label for="sequence">章节序号</label>
        <input id="sequence" v-model.number="chapterSequence" type="number" min="1" max="2147483647" required :disabled="disabled || !projectId">
        <button :disabled="disabled || !projectId || !chapterTitle.trim()">创建章节</button>
      </form>
    </details>

    <details class="sidebar-create">
      <summary>＋ 新建项目</summary>
      <form @submit.prevent="addProject">
        <label for="new-project">项目名称</label>
        <input id="new-project" v-model="projectName" required maxlength="200" :disabled="disabled">
        <button :disabled="disabled || !projectName.trim()">创建项目</button>
      </form>
    </details>

    <div class="sidebar-actions">
      <button type="button" :disabled="!projectId" @click="emit('openProfile')">写作偏好</button>
      <button v-if="testAvailable !== false" type="button" :disabled="!chapterId || testDisabled" @click="emit('openTests')">测试</button>
    </div>
  </aside>
</template>
