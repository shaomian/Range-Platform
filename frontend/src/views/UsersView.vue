<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" :icon="Plus" @click="openCreate">新建用户</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe border style="margin-top: 12px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" min-width="160" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新建用户'" width="420px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="editing" />
        </el-form-item>
        <el-form-item :label="editing ? '重置密码' : '密码'">
          <el-input v-model="form.password" type="password" show-password
            :placeholder="editing ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editing" label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { userApi } from '../api'

const loading = ref(false)
const saving = ref(false)
const items = ref([])
const dialogVisible = ref(false)
const editing = ref(false)
const editId = ref(null)
const form = reactive({ username: '', password: '', role: 'user', is_active: true })

async function load() {
  loading.value = true
  try {
    const { data } = await userApi.list()
    items.value = data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  editId.value = null
  Object.assign(form, { username: '', password: '', role: 'user', is_active: true })
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  editId.value = row.id
  Object.assign(form, { username: row.username, password: '', role: row.role, is_active: row.is_active })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      const payload = { role: form.role, is_active: form.is_active }
      if (form.password) payload.password = form.password
      await userApi.update(editId.value, payload)
    } else {
      await userApi.create({ username: form.username, password: form.password, role: form.role })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) {
    /* handled by interceptor */
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除用户「${row.username}」?`, '提示', { type: 'warning' })
  await userApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
}
</style>
