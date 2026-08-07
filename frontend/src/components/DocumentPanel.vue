<template>
  <aside class="document-panel floating-panel">
    <div class="panel-title">
      <div>
        <strong>文档列表</strong>
        <p>上传、筛选和维护知识资产</p>
      </div>
      <span>{{ documents.length }} 个</span>
    </div>

    <div class="panel-actions">
      <el-select
        :model-value="activeProject"
        clearable
        placeholder="全部项目"
        @update:model-value="(value: string) => emit('project-change', value || '')"
      >
        <el-option v-for="item in projects" :key="item.project" :label="`${item.project}（${item.document_count}）`" :value="item.project" />
      </el-select>
      <el-input
        v-model="keyword"
        :prefix-icon="Search"
        clearable
        placeholder="搜索标题、标签或正文"
        @keyup.enter="emit('search', keyword)"
        @clear="emit('search', '')"
      />
      <el-button type="primary" :icon="Search" @click="emit('search', keyword)" />
    </div>

    <el-form class="upload-meta" label-position="top">
      <el-row :gutter="8">
        <el-col :span="12"><el-input v-model="project" placeholder="项目" /></el-col>
        <el-col :span="12"><el-input v-model="module" placeholder="模块" /></el-col>
      </el-row>
      <el-input v-model="tags" placeholder="标签，多个用逗号分隔" />
    </el-form>

    <el-upload
      class="upload-box"
      drag
      :http-request="upload"
      :show-file-list="false"
      accept=".txt,.md,.docx,.pdf,.xlsx,.csv"
    >
      <el-icon><UploadFilled /></el-icon>
      <div class="upload-title">上传知识文档</div>
      <div class="upload-subtitle">支持 txt、md、docx、pdf、xlsx、csv</div>
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
          <el-tag size="small" :type="statusTagType(item.status)">{{ statusText(item.status) }}</el-tag>
          <span>{{ item.file_type.toUpperCase() }} / {{ formatSize(item.file_size) }}</span>
        </span>
        <span class="doc-meta">切片 {{ item.chunk_count }} / 图片 {{ item.image_count }}</span>
        <span class="doc-meta">{{ item.project || '未设置项目' }} / {{ item.module || '未设置模块' }}</span>
        <span v-if="item.tags" class="doc-tags">{{ item.tags }}</span>
      </button>
      <el-empty v-if="!documents.length && !loading" description="暂无文档" />
    </el-scrollbar>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import { Search, UploadFilled } from '@element-plus/icons-vue'
import { uploadDocument } from '../api/knowledge'
import type { KnowledgeDocumentListItem, ProjectSummary } from '../api/types'

const props = defineProps<{
  documents: KnowledgeDocumentListItem[]
  projects: ProjectSummary[]
  activeProject: string
  activeId?: number
  loading: boolean
}>()

const emit = defineEmits<{
  search: [keyword: string]
  'project-change': [project: string]
  uploaded: [documentId: number]
  select: [documentId: number]
}>()

const keyword = ref('')
const project = ref('')
const module = ref('')
const tags = ref('')

watch(
  () => props.activeProject,
  (value) => {
    if (value && !project.value) project.value = value
  },
  { immediate: true }
)

async function upload(options: UploadRequestOptions) {
  try {
    const data = new FormData()
    data.append('file', options.file)
    if (project.value) data.append('project', project.value)
    if (module.value) data.append('module', module.value)
    if (tags.value) data.append('tags', tags.value)
    const document = await uploadDocument(data)
    ElMessage.success('文档已上传并完成索引')
    emit('uploaded', document.id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '上传失败，请检查文件类型或后端服务')
  }
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function statusText(status: string) {
  const map: Record<string, string> = {
    uploaded: '已上传',
    parsing: '解析中',
    parsed: '已解析',
    chunking: '切片中',
    indexed: '已索引',
    failed: '失败'
  }
  return map[status] || status
}

function statusTagType(status: string) {
  if (status === 'indexed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'parsing' || status === 'chunking') return 'warning'
  return 'info'
}
</script>
