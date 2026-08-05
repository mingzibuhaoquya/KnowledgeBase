<template>
  <main class="app-shell">
    <section class="topbar">
      <div>
        <h1>研发测试知识库</h1>
        <p>需求沉淀、接口检索、AI 问答和来源引用。</p>
      </div>
      <div class="top-actions">
        <el-tag v-if="currentUser" type="success">{{ currentUser.username }} / {{ currentUser.role }}</el-tag>
        <el-button :icon="UserIcon" @click="loginVisible = true">登录</el-button>
        <el-button :icon="Setting" @click="configVisible = true">模型配置</el-button>
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
            :active-id="activeDocument?.id"
            :loading="documentLoading"
            @search="loadDocuments"
            @uploaded="handleUploaded"
            @select="openDocument"
          />
          <DocumentDetail
            :document="activeDocument"
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
import { getDocument, listDocuments, reindexDocument } from './api/knowledge'
import type { KnowledgeDocument, KnowledgeDocumentListItem, User } from './api/types'

const activeView = ref('workbench')
const documents = ref<KnowledgeDocumentListItem[]>([])
const activeDocument = ref<KnowledgeDocument | null>(null)
const documentLoading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const configVisible = ref(false)
const loginVisible = ref(false)
const currentUser = ref<User | null>(JSON.parse(localStorage.getItem('kb_user') || 'null'))

async function loadDocuments(keyword = '') {
  documentLoading.value = true
  try {
    documents.value = await listDocuments({ keyword })
  } finally {
    documentLoading.value = false
  }
}

async function openDocument(id: number) {
  detailLoading.value = true
  try {
    activeDocument.value = await getDocument(id)
    detailVisible.value = activeView.value !== 'documents'
  } finally {
    detailLoading.value = false
  }
}

async function handleUploaded(documentId: number) {
  await loadDocuments()
  await openDocument(documentId)
  activeView.value = 'documents'
}

async function handleReindex(documentId: number) {
  detailLoading.value = true
  try {
    activeDocument.value = await reindexDocument(documentId)
    await loadDocuments()
    ElMessage.success('索引已重建')
  } finally {
    detailLoading.value = false
  }
}

function handleLoggedIn(user: User) {
  currentUser.value = user
}

onMounted(loadDocuments)
</script>
