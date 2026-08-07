<template>
  <main class="app-shell">
    <section class="topbar">
      <div class="brand-block">
        <h1>研发测试知识库</h1>
        <p>需求沉淀、接口检索、AI 问答和来源引用。</p>
      </div>
      <div class="top-actions">
        <el-tag v-if="currentUser" type="success" effect="light">{{ currentUser.username }} / {{ currentUser.role }}</el-tag>
        <el-button :icon="UserIcon" @click="loginVisible = true">登录</el-button>
        <el-button type="primary" plain :icon="Setting" @click="configVisible = true">模型配置</el-button>
      </div>
    </section>

    <el-tabs v-model="activeView" class="main-tabs">
      <el-tab-pane label="知识工作台" name="workbench">
        <KnowledgeWorkbench @select-document="openDocument" />
      </el-tab-pane>

      <el-tab-pane label="文档库" name="documents">
        <section class="workspace">
          <DocumentPanel
            :documents="documents"
            :projects="projects"
            :active-project="activeProject"
            :active-id="activeDocument?.id"
            :loading="documentLoading"
            @project-change="handleProjectChange"
            @search="loadDocuments"
            @uploaded="handleUploaded"
            @select="openDocument"
          />
          <DocumentDetail
            :document="activeDocument"
            :similar-results="similarResults"
            :loading="detailLoading"
            @select-document="openDocument"
            @reindex="handleReindex"
          />
        </section>
      </el-tab-pane>

      <el-tab-pane label="AI 问答" name="chat">
        <section class="full-panel">
          <KnowledgeChat v-if="activeDocument" :document="activeDocument" @select-document="openDocument" />
          <el-empty v-else description="请先选择一个文档，或在知识工作台中检索。" />
        </section>
      </el-tab-pane>

      <el-tab-pane label="治理中心" name="admin">
        <AdminCenter @select-document="openDocument" />
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="detailVisible" size="72%" title="知识详情">
      <DocumentDetail
        :document="activeDocument"
        :similar-results="similarResults"
        :loading="detailLoading"
        @select-document="openDocument"
        @reindex="handleReindex"
      />
    </el-drawer>

    <AIConfigDialog v-model="configVisible" />
    <LoginDialog v-model="loginVisible" @logged-in="handleLoggedIn" />
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, User as UserIcon } from '@element-plus/icons-vue'
import AdminCenter from './components/AdminCenter.vue'
import AIConfigDialog from './components/AIConfigDialog.vue'
import DocumentDetail from './components/DocumentDetail.vue'
import DocumentPanel from './components/DocumentPanel.vue'
import KnowledgeChat from './components/KnowledgeChat.vue'
import KnowledgeWorkbench from './components/KnowledgeWorkbench.vue'
import LoginDialog from './components/LoginDialog.vue'
import { findSimilarKnowledge, getDocument, listDocuments, listProjects, reindexDocument } from './api/knowledge'
import type { KnowledgeDocument, KnowledgeDocumentListItem, ProjectSummary, SearchResult, User } from './api/types'

const activeView = ref('workbench')
const documents = ref<KnowledgeDocumentListItem[]>([])
const projects = ref<ProjectSummary[]>([])
const activeProject = ref<string>('')
const activeDocument = ref<KnowledgeDocument | null>(null)
const similarResults = ref<SearchResult[]>([])
const documentCache = new Map<number, KnowledgeDocument>()
const documentLoading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const configVisible = ref(false)
const loginVisible = ref(false)
const currentUser = ref<User | null>(JSON.parse(localStorage.getItem('kb_user') || 'null'))

async function loadDocuments(keyword = '') {
  documentLoading.value = true
  try {
    documents.value = await listDocuments({ keyword, project: activeProject.value || undefined })
  } finally {
    documentLoading.value = false
  }
}

async function openDocument(id: number) {
  detailLoading.value = true
  try {
    const cached = documentCache.get(id)
    activeDocument.value = cached || await getDocument(id)
    if (!cached && activeDocument.value) {
      documentCache.set(id, activeDocument.value)
    }
    similarResults.value = activeDocument.value
      ? await findSimilarKnowledge({ document_id: activeDocument.value.id, project: activeDocument.value.project || undefined, limit: 6 })
      : []
    detailVisible.value = activeView.value !== 'documents'
  } finally {
    detailLoading.value = false
  }
}

async function handleUploaded(documentId: number) {
  documentCache.delete(documentId)
  await loadProjects()
  await loadDocuments()
  await openDocument(documentId)
  activeView.value = 'documents'
}

async function handleProjectChange(project: string) {
  activeProject.value = project
  activeDocument.value = null
  similarResults.value = []
  await loadDocuments()
}

async function handleReindex(documentId: number) {
  detailLoading.value = true
  try {
    const document = await reindexDocument(documentId)
    activeDocument.value = document
    documentCache.set(documentId, document)
    similarResults.value = await findSimilarKnowledge({ document_id: document.id, project: document.project || undefined, limit: 6 })
    await loadDocuments()
    ElMessage.success('索引已重建')
  } finally {
    detailLoading.value = false
  }
}

async function loadProjects() {
  projects.value = await listProjects()
}

function handleLoggedIn(user: User) {
  currentUser.value = user
}

onMounted(async () => {
  await loadProjects()
  await loadDocuments()
})
</script>
