<template>
  <section class="detail-panel floating-panel" v-loading="loading">
    <el-empty v-if="!document" description="请选择或上传知识文档" />

    <template v-else>
      <div class="detail-header">
        <div>
          <h2>{{ document.title }}</h2>
          <p>{{ document.original_filename }} / {{ document.file_type.toUpperCase() }} / {{ statusText(document.status) }}</p>
          <div class="detail-tags">
            <el-tag v-if="document.project">{{ document.project }}</el-tag>
            <el-tag v-if="document.module" type="success">{{ document.module }}</el-tag>
            <el-tag v-for="tag in tagList" :key="tag" type="info">{{ tag }}</el-tag>
          </div>
        </div>
        <div class="generate-tools">
          <el-button :icon="Refresh" @click="emit('reindex', document.id)">重建索引</el-button>
          <el-input-number v-model="maxCases" :min="1" :max="30" size="small" />
          <el-button type="primary" :icon="MagicStick" @click="emit('generate', maxCases)">生成用例草稿</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="概览" name="overview">
          <div class="overview-grid">
            <section>
              <h3>摘要</h3>
              <p>{{ document.summary || '暂无摘要' }}</p>
            </section>
            <section>
              <h3>关键词</h3>
              <p>{{ document.keywords || '暂无关键词' }}</p>
            </section>
            <section>
              <h3>处理任务</h3>
              <div class="job-list">
                <div v-for="job in document.parse_jobs" :key="job.id" class="job-row">
                  <el-tag :type="job.status === 'success' ? 'success' : job.status === 'running' ? 'warning' : 'danger'">
                    {{ stageText(job.stage) }} / {{ jobStatusText(job.status) }}
                  </el-tag>
                  <span>{{ job.message }}</span>
                </div>
              </div>
            </section>
            <section>
              <h3>版本</h3>
              <div class="job-list">
                <div v-for="version in document.versions" :key="version.id" class="job-row">
                  <el-tag>v{{ version.version_no }}</el-tag>
                  <span>{{ version.file_hash.slice(0, 12) }} / {{ formatSize(version.file_size) }}</span>
                </div>
              </div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="解析内容" name="content">
          <pre class="parsed-text">{{ document.content_text || '暂无解析文本' }}</pre>
          <div v-if="document.images.length" class="image-list">
            <div v-for="image in document.images" :key="image.id" class="image-row">
              <el-tag>{{ image.filename }}</el-tag>
              <span>{{ image.ocr_text || 'OCR 待处理' }}</span>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="知识切片" name="chunks">
          <div class="chunk-list">
            <el-card v-for="chunk in document.chunks" :key="chunk.id" shadow="never" class="chunk-card">
              <div class="chunk-head">
                <strong>#{{ chunk.chunk_index }} {{ chunk.title_path }}</strong>
                <el-tag type="info">{{ chunk.keywords || '暂无关键词' }}</el-tag>
              </div>
              <p>{{ chunk.content }}</p>
            </el-card>
            <el-empty v-if="!document.chunks.length" description="暂无切片" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="测试用例草稿" name="cases">
          <div class="case-list">
            <el-card v-for="item in cases" :key="item.id" shadow="never" class="case-card">
              <el-form label-width="88px" label-position="left">
                <div class="case-title-line">
                  <el-input v-model="item.title" placeholder="用例标题" />
                  <el-select v-model="item.priority" class="priority-select">
                    <el-option label="P0" value="P0" />
                    <el-option label="P1" value="P1" />
                    <el-option label="P2" value="P2" />
                    <el-option label="P3" value="P3" />
                  </el-select>
                  <el-select v-model="item.status" class="status-select">
                    <el-option label="草稿" value="draft" />
                    <el-option label="已确认" value="confirmed" />
                  </el-select>
                </div>
                <el-row :gutter="12">
                  <el-col :span="6"><el-input v-model="item.project" placeholder="项目" /></el-col>
                  <el-col :span="6"><el-input v-model="item.module" placeholder="模块" /></el-col>
                  <el-col :span="8"><el-input v-model="item.api_path" placeholder="接口路径" /></el-col>
                  <el-col :span="4">
                    <el-select v-model="item.method" clearable placeholder="方法">
                      <el-option label="GET" value="GET" />
                      <el-option label="POST" value="POST" />
                      <el-option label="PUT" value="PUT" />
                      <el-option label="PATCH" value="PATCH" />
                      <el-option label="DELETE" value="DELETE" />
                    </el-select>
                  </el-col>
                </el-row>
                <el-form-item label="前置条件"><el-input v-model="item.precondition" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="步骤"><el-input v-model="item.steps" type="textarea" :rows="4" /></el-form-item>
                <el-form-item label="预期结果"><el-input v-model="item.expected_result" type="textarea" :rows="3" /></el-form-item>
                <div class="case-footer">
                  <el-tag type="info">{{ item.source }}</el-tag>
                  <el-button :icon="Check" type="success" @click="emit('save-case', item)">保存</el-button>
                </div>
              </el-form>
            </el-card>
            <el-empty v-if="!cases.length" description="暂无测试用例草稿" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="AI 问答" name="chat">
          <KnowledgeChat :document="document" @select-document="emit('select-document', $event)" />
        </el-tab-pane>
      </el-tabs>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, MagicStick, Refresh } from '@element-plus/icons-vue'
import KnowledgeChat from './KnowledgeChat.vue'
import type { KnowledgeDocument, TestCaseDraft } from '../api/types'

const props = defineProps<{
  document: KnowledgeDocument | null
  cases: TestCaseDraft[]
  loading: boolean
}>()

const emit = defineEmits<{
  generate: [maxCases: number]
  'save-case': [item: TestCaseDraft]
  'select-document': [documentId: number]
  reindex: [documentId: number]
}>()

const maxCases = ref(8)
const activeTab = ref('overview')
const tagList = computed(() => (props.document?.tags || '').split(',').map((tag) => tag.trim()).filter(Boolean))

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

function stageText(stage: string) {
  const map: Record<string, string> = {
    parse: '解析',
    index: '索引',
    upload: '上传'
  }
  return map[stage] || stage
}

function jobStatusText(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    success: '成功',
    failed: '失败'
  }
  return map[status] || status
}
</script>
