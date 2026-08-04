<template>
  <section class="workbench" v-loading="loading">
    <div class="command-center">
      <div>
        <h2>Knowledge Workbench</h2>
        <p>Search requirements, ask questions, and inspect trusted sources.</p>
      </div>
      <div class="command-search">
        <el-input
          v-model="query"
          :prefix-icon="Search"
          clearable
          placeholder="Search or ask about a requirement, rule, API, or error code"
          @keyup.enter="runSearch"
        />
        <el-button type="primary" :icon="Search" @click="runSearch">Search</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <section><strong>{{ overview?.document_count || 0 }}</strong><span>Documents</span></section>
      <section><strong>{{ overview?.indexed_count || 0 }}</strong><span>Indexed</span></section>
      <section><strong>{{ overview?.chunk_count || 0 }}</strong><span>Knowledge chunks</span></section>
      <section><strong>{{ overview?.chat_count || 0 }}</strong><span>Questions</span></section>
      <section><strong>{{ overview?.feedback_count || 0 }}</strong><span>Feedback</span></section>
      <section><strong>{{ overview?.failed_count || 0 }}</strong><span>Failed docs</span></section>
    </div>

    <div v-if="searchResults.length" class="wide-panel">
      <div class="section-head">
        <h3>Search Results</h3>
        <span>{{ searchResults.length }} matches</span>
      </div>
      <div class="result-list">
        <button v-for="item in searchResults" :key="`${item.document_id}-${item.chunk_id}`" @click="emit('select-document', item.document_id)">
          <strong>{{ item.title }}</strong>
          <span>{{ item.match_reason || item.source }} · score {{ item.score.toFixed(1) }}</span>
          <p>{{ item.snippet || item.original_filename }}</p>
        </button>
      </div>
    </div>

    <div class="workbench-grid">
      <section class="wide-panel">
        <div class="section-head">
          <h3>Recent Knowledge</h3>
          <span>{{ overview?.recent_documents.length || 0 }} items</span>
        </div>
        <div class="compact-list">
          <button v-for="doc in overview?.recent_documents || []" :key="doc.id" @click="emit('select-document', doc.id)">
            <strong>{{ doc.title }}</strong>
            <span>{{ doc.project || 'No project' }} / {{ doc.module || 'No module' }} · {{ doc.status }}</span>
          </button>
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>Knowledge Spaces</h3>
          <span>Project / module</span>
        </div>
        <div class="compact-list">
          <button v-for="space in overview?.spaces || []" :key="`${space.project}-${space.module}`">
            <strong>{{ space.project }}{{ space.module ? ` / ${space.module}` : '' }}</strong>
            <span>{{ space.document_count }} docs · {{ space.chunk_count }} chunks</span>
          </button>
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>Popular Questions</h3>
          <span>Recent user asks</span>
        </div>
        <div class="compact-list">
          <button v-for="message in overview?.popular_questions || []" :key="message.id">
            <strong>{{ message.content }}</strong>
            <span>{{ new Date(message.created_at).toLocaleString() }}</span>
          </button>
        </div>
      </section>

      <section class="wide-panel">
        <div class="section-head">
          <h3>Knowledge Tags</h3>
          <span>Top labels</span>
        </div>
        <div class="tag-cloud">
          <el-tag v-for="tag in overview?.tags || []" :key="tag.tag" type="info">
            {{ tag.tag }} · {{ tag.document_count }}
          </el-tag>
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
  if (!searchResults.value.length) ElMessage.info('No matching knowledge found')
}

onMounted(load)
</script>

