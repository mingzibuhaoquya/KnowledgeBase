<template>
  <aside class="document-panel">
    <div class="panel-actions">
      <el-input
        v-model="keyword"
        :prefix-icon="Search"
        clearable
        placeholder="Search title, tags, or content"
        @keyup.enter="emit('search', keyword)"
        @clear="emit('search', '')"
      />
      <el-button :icon="Search" @click="emit('search', keyword)" />
    </div>

    <el-form class="upload-meta" label-position="top">
      <el-row :gutter="8">
        <el-col :span="12"><el-input v-model="project" placeholder="Project" /></el-col>
        <el-col :span="12"><el-input v-model="module" placeholder="Module" /></el-col>
      </el-row>
      <el-input v-model="tags" placeholder="Tags, comma separated" />
    </el-form>

    <el-upload
      class="upload-box"
      drag
      :http-request="upload"
      :show-file-list="false"
      accept=".txt,.md,.docx,.pdf,.xlsx,.csv"
    >
      <el-icon><UploadFilled /></el-icon>
      <div class="upload-title">Upload Knowledge</div>
      <div class="upload-subtitle">Supports txt, md, docx, pdf, xlsx, csv</div>
    </el-upload>

    <el-scrollbar class="document-list" v-loading="loading">
      <button
        v-for="item in documents"
        :key="item.id"
        class="document-item"
        :class="{ active: item.id === activeId }"
        @click="emit('select', item.id)"
      >
        <span class="doc-title">{{ item.title }}</span>
        <span class="doc-meta">
          {{ item.file_type.toUpperCase() }} · {{ formatSize(item.file_size) }} · {{ item.status }}
        </span>
        <span class="doc-meta">Chunks {{ item.chunk_count }} · Images {{ item.image_count }} · Cases {{ item.test_case_count }}</span>
        <span class="doc-meta">{{ item.project || 'No project' }} / {{ item.module || 'No module' }}</span>
        <span v-if="item.tags" class="doc-tags">{{ item.tags }}</span>
      </button>
      <el-empty v-if="!documents.length && !loading" description="No documents" />
    </el-scrollbar>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import { Search, UploadFilled } from '@element-plus/icons-vue'
import { uploadDocument } from '../api/knowledge'
import type { KnowledgeDocumentListItem } from '../api/types'

defineProps<{
  documents: KnowledgeDocumentListItem[]
  activeId?: number
  loading: boolean
}>()

const emit = defineEmits<{
  search: [keyword: string]
  uploaded: [documentId: number]
  select: [documentId: number]
}>()

const keyword = ref('')
const project = ref('')
const module = ref('')
const tags = ref('')

async function upload(options: UploadRequestOptions) {
  try {
    const data = new FormData()
    data.append('file', options.file)
    if (project.value) data.append('project', project.value)
    if (module.value) data.append('module', module.value)
    if (tags.value) data.append('tags', tags.value)
    const document = await uploadDocument(data)
    ElMessage.success('Document uploaded and indexed')
    emit('uploaded', document.id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'Upload failed. Check file type and backend service.')
  }
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>
