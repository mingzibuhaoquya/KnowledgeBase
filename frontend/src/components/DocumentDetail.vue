<template>
  <section class="detail-panel" v-loading="loading">
    <el-empty v-if="!document" description="Select or upload a knowledge document" />

    <template v-else>
      <div class="detail-header">
        <div>
          <h2>{{ document.title }}</h2>
          <p>{{ document.original_filename }} · {{ document.file_type.toUpperCase() }} · {{ document.status }}</p>
          <div class="detail-tags">
            <el-tag v-if="document.project">{{ document.project }}</el-tag>
            <el-tag v-if="document.module" type="success">{{ document.module }}</el-tag>
            <el-tag v-for="tag in tagList" :key="tag" type="info">{{ tag }}</el-tag>
          </div>
        </div>
        <div class="generate-tools">
          <el-button :icon="Refresh" @click="emit('reindex', document.id)">Reindex</el-button>
          <el-input-number v-model="maxCases" :min="1" :max="30" size="small" />
          <el-button type="primary" :icon="MagicStick" @click="emit('generate', maxCases)">Draft Cases</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="Overview" name="overview">
          <div class="overview-grid">
            <section>
              <h3>Summary</h3>
              <p>{{ document.summary || 'No summary yet' }}</p>
            </section>
            <section>
              <h3>Keywords</h3>
              <p>{{ document.keywords || 'No keywords yet' }}</p>
            </section>
            <section>
              <h3>Processing Jobs</h3>
              <div class="job-list">
                <div v-for="job in document.parse_jobs" :key="job.id" class="job-row">
                  <el-tag :type="job.status === 'success' ? 'success' : job.status === 'running' ? 'warning' : 'danger'">
                    {{ job.stage }} · {{ job.status }}
                  </el-tag>
                  <span>{{ job.message }}</span>
                </div>
              </div>
            </section>
            <section>
              <h3>Versions</h3>
              <div class="job-list">
                <div v-for="version in document.versions" :key="version.id" class="job-row">
                  <el-tag>v{{ version.version_no }}</el-tag>
                  <span>{{ version.file_hash.slice(0, 12) }} · {{ formatSize(version.file_size) }}</span>
                </div>
              </div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Parsed Content" name="content">
          <pre class="parsed-text">{{ document.content_text || 'No parsed text' }}</pre>
          <div v-if="document.images.length" class="image-list">
            <div v-for="image in document.images" :key="image.id" class="image-row">
              <el-tag>{{ image.filename }}</el-tag>
              <span>{{ image.ocr_text }}</span>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Chunks" name="chunks">
          <div class="chunk-list">
            <el-card v-for="chunk in document.chunks" :key="chunk.id" shadow="never" class="chunk-card">
              <div class="chunk-head">
                <strong>#{{ chunk.chunk_index }} {{ chunk.title_path }}</strong>
                <el-tag type="info">{{ chunk.keywords || 'no keywords' }}</el-tag>
              </div>
              <p>{{ chunk.content }}</p>
            </el-card>
            <el-empty v-if="!document.chunks.length" description="No chunks" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="Test Case Drafts" name="cases">
          <div class="case-list">
            <el-card v-for="item in cases" :key="item.id" shadow="never" class="case-card">
              <el-form label-width="88px" label-position="left">
                <div class="case-title-line">
                  <el-input v-model="item.title" />
                  <el-select v-model="item.priority" class="priority-select">
                    <el-option label="P0" value="P0" />
                    <el-option label="P1" value="P1" />
                    <el-option label="P2" value="P2" />
                    <el-option label="P3" value="P3" />
                  </el-select>
                  <el-select v-model="item.status" class="status-select">
                    <el-option label="Draft" value="draft" />
                    <el-option label="Confirmed" value="confirmed" />
                  </el-select>
                </div>
                <el-row :gutter="12">
                  <el-col :span="6"><el-input v-model="item.project" placeholder="project" /></el-col>
                  <el-col :span="6"><el-input v-model="item.module" placeholder="module" /></el-col>
                  <el-col :span="8"><el-input v-model="item.api_path" placeholder="api path" /></el-col>
                  <el-col :span="4">
                    <el-select v-model="item.method" clearable placeholder="method">
                      <el-option label="GET" value="GET" />
                      <el-option label="POST" value="POST" />
                      <el-option label="PUT" value="PUT" />
                      <el-option label="PATCH" value="PATCH" />
                      <el-option label="DELETE" value="DELETE" />
                    </el-select>
                  </el-col>
                </el-row>
                <el-form-item label="Precondition"><el-input v-model="item.precondition" type="textarea" :rows="2" /></el-form-item>
                <el-form-item label="Steps"><el-input v-model="item.steps" type="textarea" :rows="4" /></el-form-item>
                <el-form-item label="Expected"><el-input v-model="item.expected_result" type="textarea" :rows="3" /></el-form-item>
                <div class="case-footer">
                  <el-tag type="info">{{ item.source }}</el-tag>
                  <el-button :icon="Check" type="success" @click="emit('save-case', item)">Save</el-button>
                </div>
              </el-form>
            </el-card>
            <el-empty v-if="!cases.length" description="No test case drafts" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="AI Chat" name="chat">
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
</script>
