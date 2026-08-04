<template>
  <el-dialog v-model="visible" title="AI 配置" width="560px">
    <el-form label-width="96px" label-position="left">
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item label="Provider">
        <el-select v-model="form.provider">
          <el-option label="Mock" value="mock" />
          <el-option label="OpenAI Compatible" value="openai_compatible" />
        </el-select>
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="form.base_url" placeholder="https://api.example.com/v1" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="form.api_key" :placeholder="maskedKey || '保存后脱敏展示'" show-password />
      </el-form-item>
      <el-form-item label="Model">
        <el-input v-model="form.model" placeholder="model name" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getAIConfig, saveAIConfig } from '../api/knowledge'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const maskedKey = ref('')
const form = reactive({
  provider: 'mock',
  base_url: '',
  api_key: '',
  model: '',
  enabled: false
})

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    const config = await getAIConfig()
    if (!config) return
    form.provider = config.provider
    form.base_url = config.base_url
    form.model = config.model
    form.enabled = config.enabled
    form.api_key = ''
    maskedKey.value = config.api_key_masked
  }
)

async function save() {
  const saved = await saveAIConfig(form)
  maskedKey.value = saved.api_key_masked
  form.api_key = ''
  ElMessage.success('AI 配置已保存')
  visible.value = false
}
</script>

