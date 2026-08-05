<template>
  <div class="knowledge-chat">
    <section class="search-strip">
      <el-input
        v-model="searchText"
        :prefix-icon="Search"
        clearable
        placeholder="提问前可先检索知识库"
        @keyup.enter="runSearch"
      />
      <el-button :icon="Search" @click="runSearch">检索</el-button>
    </section>

    <div v-if="searchResults.length" class="search-results">
      <button v-for="item in searchResults" :key="`${item.document_id}-${item.chunk_id}`" class="search-result" @click="emit('select-document', item.document_id)">
        <strong>{{ item.title }}</strong>
        <span>{{ item.match_reason || item.source }} / 分数 {{ item.score.toFixed(1) }}</span>
        <span>{{ item.snippet || item.original_filename }}</span>
      </button>
    </div>

    <section class="chat-toolbar">
      <el-radio-group v-model="scope" size="small">
        <el-radio-button label="document">当前文档</el-radio-button>
        <el-radio-button label="all">全库</el-radio-button>
      </el-radio-group>
      <el-tag type="info">{{ scope === 'document' ? document.title : '全部文档' }}</el-tag>
    </section>

    <el-scrollbar class="chat-history">
      <div v-for="message in messages" :key="message.id" class="chat-message" :class="message.role">
        <div class="message-role">{{ message.role === 'user' ? '我' : '知识助手' }}</div>
        <div class="message-content" v-html="renderMessage(message.content)" />
        <div v-if="message.sources?.length" class="source-list">
          <button v-for="source in message.sources" :key="`${message.id}-${source.document_id}-${source.chunk_id}`" @click="emit('select-document', source.document_id)">
            {{ source.title }}{{ source.chunk_id ? ` #${source.chunk_id}` : '' }}
          </button>
        </div>
        <div v-if="message.role === 'assistant'" class="feedback-actions">
          <el-button size="small" @click="feedback(message.id, 'useful')">有用</el-button>
          <el-button size="small" @click="feedback(message.id, 'not_useful')">无用</el-button>
          <el-button size="small" @click="feedback(message.id, 'wrong')">错误</el-button>
        </div>
      </div>
      <el-empty v-if="!messages.length" description="可以询问需求规则、异常处理、接口字段、测试关注点。" />
    </el-scrollbar>

    <section class="chat-input">
      <el-input
        v-model="question"
        type="textarea"
        :rows="3"
        resize="none"
        placeholder="向知识库提问，Ctrl+Enter 发送"
        @keydown.ctrl.enter.prevent="ask"
      />
      <el-button type="primary" :icon="Promotion" :loading="asking" @click="ask">提问</el-button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Search } from '@element-plus/icons-vue'
import { askKnowledge, saveChatFeedback, searchKnowledge } from '../api/knowledge'
import type { ChatMessage, KnowledgeDocument, SearchResult } from '../api/types'

const props = defineProps<{ document: KnowledgeDocument }>()
const emit = defineEmits<{ 'select-document': [documentId: number] }>()

const scope = ref<'document' | 'all'>('all')
const searchText = ref('')
const question = ref('')
const asking = ref(false)
const sessionId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const searchResults = ref<SearchResult[]>([])

watch(
  () => props.document.id,
  () => {
    sessionId.value = null
    messages.value = []
    searchResults.value = []
    scope.value = 'all'
  }
)

async function runSearch() {
  if (!searchText.value.trim()) {
    searchResults.value = []
    return
  }
  searchResults.value = await searchKnowledge(searchText.value.trim(), 8)
}

async function ask() {
  const text = question.value.trim()
  if (!text) {
    ElMessage.warning('请输入问题')
    return
  }
  asking.value = true
  try {
    const response = await askKnowledge({
      question: text,
      session_id: sessionId.value,
      document_id: scope.value === 'document' ? props.document.id : null,
      scope: scope.value,
      top_k: 5
    })
    sessionId.value = response.session.id
    messages.value.push(response.question, response.answer)
    question.value = ''
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '提问失败，请检查后端服务或模型配置')
  } finally {
    asking.value = false
  }
}

async function feedback(messageId: number, rating: string) {
  await saveChatFeedback(messageId, { rating })
  ElMessage.success('反馈已记录')
}

function renderMessage(content: string) {
  return renderMarkdownLite(content || '')
}

function renderMarkdownLite(content: string) {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const blocks: string[] = []
  let index = 0

  while (index < lines.length) {
    if (isTableStart(lines, index)) {
      const tableLines = [lines[index], lines[index + 1]]
      index += 2
      while (index < lines.length && isTableRow(lines[index])) {
        tableLines.push(lines[index])
        index += 1
      }
      blocks.push(renderTable(tableLines))
      continue
    }

    const line = lines[index]
    if (!line.trim()) {
      blocks.push('<br />')
    } else if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(`<li>${inlineFormat(lines[index].replace(/^\s*[-*]\s+/, ''))}</li>`)
        index += 1
      }
      blocks.push(`<ul>${items.join('')}</ul>`)
      continue
    } else if (/^\s*\d+\.\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(`<li>${inlineFormat(lines[index].replace(/^\s*\d+\.\s+/, ''))}</li>`)
        index += 1
      }
      blocks.push(`<ol>${items.join('')}</ol>`)
      continue
    } else {
      blocks.push(`<p>${inlineFormat(line)}</p>`)
    }
    index += 1
  }

  return blocks.join('')
}

function isTableStart(lines: string[], index: number) {
  return isTableRow(lines[index]) && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
}

function isTableRow(line: string) {
  return line.includes('|') && line.split('|').filter((cell) => cell.trim()).length >= 2
}

function renderTable(lines: string[]) {
  const headers = splitTableRow(lines[0])
  const bodyRows = lines.slice(2).map(splitTableRow)
  const head = `<thead><tr>${headers.map((cell) => `<th>${inlineFormat(cell)}</th>`).join('')}</tr></thead>`
  const body = `<tbody>${bodyRows.map((row) => `<tr>${row.map((cell) => `<td>${inlineFormat(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`
  return `<div class="message-table-wrap"><table>${head}${body}</table></div>`
}

function splitTableRow(line: string) {
  return line.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map((cell) => cell.trim())
}

function inlineFormat(text: string) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
</script>
