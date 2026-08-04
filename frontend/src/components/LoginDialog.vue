<template>
  <el-dialog v-model="visible" title="登录" width="420px">
    <el-form label-position="top">
      <el-form-item label="用户名">
        <el-input v-model="username" placeholder="admin" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="password" placeholder="admin123" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit">登录</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { login } from '../api/knowledge'
import type { User } from '../api/types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'logged-in': [user: User]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const username = ref('admin')
const password = ref('admin123')

async function submit() {
  const response = await login(username.value, password.value)
  localStorage.setItem('kb_access_token', response.access_token)
  localStorage.setItem('kb_user', JSON.stringify(response.user))
  emit('logged-in', response.user)
  ElMessage.success('登录成功')
  visible.value = false
}
</script>

