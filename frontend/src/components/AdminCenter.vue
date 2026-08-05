<template>
  <section class="admin-center" v-loading="loading">
    <div class="section-head">
      <h2>治理中心</h2>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="workbench-grid">
      <section class="wide-panel">
        <div class="section-head">
          <h3>解析 / 索引任务</h3>
          <span>最近 {{ jobs.length }} 条</span>
        </div>
        <div class="job-list">
          <div v-for="job in jobs" :key="job.id" class="job-row">
            <el-tag :type="job.status === 'success' ? 'success' : job.status === 'running' ? 'warning' : 'danger'">
              {{ job.stage }} / {{ job.status }}
            </el-tag>
            <span>{{ job.message || '暂无消息' }}</span>
            <el-button size="small" @click="retry(job.id)">重试</el-button>
          </div>
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>知识质量问题</h3>
          <span>{{ issues.length }} 条问题</span>
        </div>
        <div class="issue-list">
          <button v-for="issue in issues" :key="`${issue.type}-${issue.document_id}-${issue.created_at}`" @click="issue.document_id && emit('select-document', issue.document_id)">
            <strong>{{ issue.title }}</strong>
            <span>{{ issue.severity }} / {{ issue.type }}</span>
            <p>{{ issue.detail }}</p>
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { listAdminJobs, listQualityIssues, retryAdminJob } from '../api/knowledge'
import type { ParseJob, QualityIssue } from '../api/types'

const emit = defineEmits<{ 'select-document': [documentId: number] }>()

const loading = ref(false)
const jobs = ref<ParseJob[]>([])
const issues = ref<QualityIssue[]>([])

async function load() {
  loading.value = true
  try {
    jobs.value = await listAdminJobs()
    issues.value = await listQualityIssues()
  } finally {
    loading.value = false
  }
}

async function retry(jobId: number) {
  await retryAdminJob(jobId)
  ElMessage.success('任务已重试')
  await load()
}

onMounted(load)
</script>
