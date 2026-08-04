<template>
  <main class="app-shell">
    <section class="topbar">
      <div>
        <h1>KnowledgeBase</h1>
        <p>R&D testing knowledge, trusted search, and source-grounded AI answers.</p>
      </div>
      <div class="top-actions">
        <el-tag v-if="currentUser" type="success">{{ currentUser.username }} · {{ currentUser.role }}</el-tag>
        <el-button :icon="UserIcon" @click="loginVisible = true">Login</el-button>
        <el-button :icon="Setting" @click="configVisible = true">AI Config</el-button>
      </div>
    </section>

    <el-tabs v-model="activeView" class="main-tabs">
      <el-tab-pane label="Workbench" name="workbench">
        <KnowledgeWorkbench @select-document="openDocument" />
      </el-tab-pane>

      <el-tab-pane label="Documents" name="documents">
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
            :cases="cases"
            :loading="detailLoading"
            @generate="handleGenerate"
            @save-case="handleSaveCase"
            @select-document="openDocument"
            @reindex="handleReindex"
          />
        </section>
      </el-tab-pane>

      <el-tab-pane label="AI Chat" name="chat">
        <section class="full-panel">
          <KnowledgeChat
            v-if="activeDocument"
            :document="activeDocument"
            @select-document="openDocument"
          />
          <el-empty v-else description="Select a document first, or search from the workbench." />
        </section>
      </el-tab-pane>

      <el-tab-pane label="Governance" name="admin">
        <AdminCenter @select-document="openDocument" />
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="detailVisible" size="72%" title="Knowledge Detail">
      <DocumentDetail
        :document="activeDocument"
        :cases="cases"
        :loading="detailLoading"
        @generate="handleGenerate"
        @save-case="handleSaveCase"
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
import { generateCases, getDocument, listCases, listDocuments, reindexDocument, updateCase } from './api/knowledge'
import type { KnowledgeDocument, KnowledgeDocumentListItem, TestCaseDraft, User } from './api/types'

const activeView = ref('workbench')
const documents = ref<KnowledgeDocumentListItem[]>([])
const activeDocument = ref<KnowledgeDocument | null>(null)
const cases = ref<TestCaseDraft[]>([])
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
    cases.value = await listCases(id)
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

async function handleGenerate(maxCases: number) {
  if (!activeDocument.value) return
  detailLoading.value = true
  try {
    cases.value = await generateCases(activeDocument.value.id, maxCases)
    await loadDocuments()
    ElMessage.success('Test case drafts generated')
  } finally {
    detailLoading.value = false
  }
}

async function handleSaveCase(item: TestCaseDraft) {
  const saved = await updateCase(item)
  const index = cases.value.findIndex((entry) => entry.id === saved.id)
  if (index >= 0) cases.value[index] = saved
  ElMessage.success('Case saved')
}

async function handleReindex(documentId: number) {
  detailLoading.value = true
  try {
    activeDocument.value = await reindexDocument(documentId)
    await loadDocuments()
    ElMessage.success('Index rebuilt')
  } finally {
    detailLoading.value = false
  }
}

function handleLoggedIn(user: User) {
  currentUser.value = user
}

onMounted(loadDocuments)
</script>
