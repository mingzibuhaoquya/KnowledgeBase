<template>
  <section class="workbench" v-loading="loading">
    <div class="command-center">
      <div>
        <h2>知识工作台</h2>
        <p>检索需求规则、接口字段、异常处理和测试关注点。</p>
      </div>
      <div class="command-search">
        <el-input
          v-model="query"
          :prefix-icon="Search"
          clearable
          placeholder="输入需求、接口、错误码或自然语言问题"
          @keyup.enter="runSearch"
        />
        <el-button type="primary" :icon="Search" @click="runSearch">检索</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <section><strong>{{ overview?.document_count || 0 }}</strong><span>文档数</span></section>
      <section><strong>{{ overview?.indexed_count || 0 }}</strong><span>已索引</span></section>
      <section><strong>{{ overview?.chunk_count || 0 }}</strong><span>知识切片</span></section>
      <section><strong>{{ overview?.chat_count || 0 }}</strong><span>问答次数</span></section>
      <section><strong>{{ overview?.feedback_count || 0 }}</strong><span>反馈数</span></section>
      <section><strong>{{ overview?.failed_count || 0 }}</strong><span>失败文档</span></section>
    </div>

    <div v-if="searchResults.length" class="wide-panel">
      <div class="section-head">
        <h3>检索结果</h3>
        <span>{{ searchResults.length }} 条命中</span>
      </div>
      <div class="result-list">
        <button v-for="item in searchResults" :key="`${item.document_id}-${item.chunk_id}`" @click="emit('select-document', item.document_id)">
          <strong>{{ item.title }}</strong>
          <span>{{ item.match_reason || item.source }} / 分数 {{ item.score.toFixed(1) }}</span>
          <p>{{ item.snippet || item.original_filename }}</p>
        </button>
      </div>
    </div>

    <div class="workbench-grid">
      <section class="wide-panel">
        <div class="section-head">
          <h3>最近知识</h3>
          <span>{{ overview?.recent_documents.length || 0 }} 条</span>
        </div>
        <div class="compact-list">
          <button v-for="doc in overview?.recent_documents || []" :key="doc.id" @click="emit('select-document', doc.id)">
            <strong>{{ doc.title }}</strong>
            <span>{{ doc.project || '未设置项目' }} / {{ doc.module || '未设置模块' }} / {{ statusText(doc.status) }}</span>
          </button>
          <el-empty v-if="!overview?.recent_documents.length" description="暂无文档" />
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>知识空间</h3>
          <span>项目 / 模块</span>
        </div>
        <div class="compact-list">
          <button v-for="space in overview?.spaces || []" :key="`${space.project}-${space.module}`">
            <strong>{{ space.project }}{{ space.module ? ` / ${space.module}` : '' }}</strong>
            <span>{{ space.document_count }} 个文档 / {{ space.chunk_count }} 个切片</span>
          </button>
          <el-empty v-if="!overview?.spaces.length" description="暂无空间" />
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>热门问题</h3>
          <span>最近提问</span>
        </div>
        <div class="compact-list">
          <button v-for="message in overview?.popular_questions || []" :key="message.id">
            <strong>{{ message.content }}</strong>
            <span>{{ new Date(message.created_at).toLocaleString() }}</span>
          </button>
          <el-empty v-if="!overview?.popular_questions.length" description="暂无问答记录" />
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>知识标签</h3>
          <span>高频标签</span>
        </div>
        <div class="tag-cloud">
          <el-tag v-for="tag in overview?.tags || []" :key="tag.tag" type="info">
            {{ tag.tag }} / {{ tag.document_count }}
          </el-tag>
          <el-empty v-if="!overview?.tags.length" description="暂无标签" />
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getDashboardOverview, searchKnowledge } from '../api/knowledge'
import type { DashboardOverview, SearchResult } from '../api/types'

const emit = defineEmits<{ 'select-document': [documentId: number] }>()

const loading = ref(false)
const query = ref('')
const overview = ref<DashboardOverview | null>(null)
const searchResults = ref<SearchResult[]>([])

async function load() {
  loading.value = true
  try {
    overview.value = await getDashboardOverview()
  } finally {
    loading.value = false
  }
}

async function runSearch() {
  if (!query.value.trim()) {
    searchResults.value = []
    return
  }
  searchResults.value = await searchKnowledge(query.value.trim(), 8)
  if (!searchResults.value.length) ElMessage.info('没有检索到匹配知识')
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

onMounted(load)
</script>
