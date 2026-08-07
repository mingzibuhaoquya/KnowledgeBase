<template>
  <el-dialog v-model="visible" title="模型配置" width="760px" class="model-config-dialog">
    <el-tabs v-model="activeKind">
      <el-tab-pane v-for="item in forms" :key="item.kind" :label="item.label" :name="item.kind">
        <section class="config-summary">
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.description }}</p>
          </div>
          <el-switch v-model="item.enabled" />
        </section>

        <el-form label-width="110px" label-position="left">
          <el-form-item label="Provider">
            <el-select v-model="item.provider">
              <el-option label="OpenAI Compatible" value="openai_compatible" />
              <el-option label="Mock / Disabled" value="mock" />
            </el-select>
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="item.base_url" :placeholder="item.basePlaceholder" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="item.api_key" :placeholder="item.api_key_masked || '保存后脱敏展示'" show-password />
          </el-form-item>
          <el-form-item label="Model">
            <el-input v-model="item.model" :placeholder="item.modelPlaceholder" />
          </el-form-item>
          <el-form-item v-if="item.kind === 'embedding'" label="Dimension">
            <el-input-number v-model="item.dimension" :min="1" :max="8192" controls-position="right" />
          </el-form-item>
          <el-form-item label="连接测试">
            <div class="test-row">
              <el-input v-model="item.testText" />
              <el-button :loading="testing === item.kind" @click="test(item)">测试</el-button>
            </div>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveActive">保存当前配置</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listModelConfigs, saveModelConfig, testModelConfig } from '../api/knowledge'
import type { ModelConfig } from '../api/types'

type ModelKind = ModelConfig['kind']

interface ModelForm {
  kind: ModelKind
  label: string
  title: string
  description: string
  provider: string
  base_url: string
  api_key: string
  api_key_masked: string
  model: string
  dimension: number | null
  enabled: boolean
  basePlaceholder: string
  modelPlaceholder: string
  testText: string
}

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const activeKind = ref<ModelKind>('chat')
const saving = ref(false)
const testing = ref<ModelKind | ''>('')

const forms = reactive<ModelForm[]>([
  {
    kind: 'chat',
    label: 'Chat',
    title: '对话模型',
    description: '用于 RAG 问答、摘要、知识归纳和测试关注点建议。',
    provider: 'openai_compatible',
    base_url: 'https://api.deepseek.com/v1',
    api_key: '',
    api_key_masked: '',
    model: 'deepseek-chat',
    dimension: null,
    enabled: false,
    basePlaceholder: 'https://api.deepseek.com/v1',
    modelPlaceholder: 'deepseek-chat',
    testText: '请用一句话说明知识库问答模型连接成功。'
  },
  {
    kind: 'embedding',
    label: 'Embedding',
    title: '嵌入模型',
    description: '把文档切片和问题转换成向量，写入 Qdrant 做语义检索。',
    provider: 'openai_compatible',
    base_url: '',
    api_key: '',
    api_key_masked: '',
    model: '',
    dimension: 1024,
    enabled: false,
    basePlaceholder: '供应商 OpenAI-compatible base URL',
    modelPlaceholder: '例如 BAAI/bge-m3',
    testText: '账号锁定规则是什么？'
  },
  {
    kind: 'rerank',
    label: 'Rerank',
    title: '重排模型',
    description: '对关键词和语义检索候选重新排序，提高最终引用质量；可选。',
    provider: 'openai_compatible',
    base_url: '',
    api_key: '',
    api_key_masked: '',
    model: '',
    dimension: null,
    enabled: false,
    basePlaceholder: '供应商 rerank endpoint base URL',
    modelPlaceholder: '例如 BAAI/bge-reranker-v2-m3',
    testText: '找出最相关的知识库说明。'
  }
])

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    const configs = await listModelConfigs()
    for (const config of configs) {
      const form = forms.find((item) => item.kind === config.kind)
      if (!form) continue
      form.provider = config.provider
      form.base_url = config.base_url
      form.model = config.model
      form.dimension = config.dimension
      form.enabled = config.enabled
      form.api_key = ''
      form.api_key_masked = config.api_key_masked
    }
  }
)

async function saveActive() {
  const form = forms.find((item) => item.kind === activeKind.value)
  if (!form) return
  saving.value = true
  try {
    const saved = await saveModelConfig(form.kind, {
      provider: form.provider,
      base_url: form.base_url,
      api_key: form.api_key,
      model: form.model,
      dimension: form.dimension,
      enabled: form.enabled
    })
    form.api_key = ''
    form.api_key_masked = saved.api_key_masked
    ElMessage.success('模型配置已保存')
  } finally {
    saving.value = false
  }
}

async function test(form: ModelForm) {
  testing.value = form.kind
  try {
    await saveModelConfig(form.kind, {
      provider: form.provider,
      base_url: form.base_url,
      api_key: form.api_key,
      model: form.model,
      dimension: form.dimension,
      enabled: form.enabled
    })
    const result = await testModelConfig(form.kind, form.testText)
    if (result.ok) {
      ElMessageBox.alert(result.detail || result.message, result.message, { type: 'success' })
    } else {
      ElMessageBox.alert(result.detail || result.message, '连接失败', { type: 'error' })
    }
  } finally {
    testing.value = ''
  }
}
</script>

<style scoped>
.config-summary {
  align-items: center;
  background: #f7fafb;
  border: 1px solid #dfe8ef;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  margin-bottom: 18px;
  padding: 14px 16px;
}

.config-summary p {
  color: #607086;
  line-height: 1.6;
  margin: 4px 0 0;
}

.test-row {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr auto;
  width: 100%;
}
</style>
