<template>
  <div>
    <div class="toolbar">
      <el-button :icon="Refresh" @click="load">刷新</el-button>
      <el-checkbox v-if="auth.isAdmin" v-model="showAll" @change="load" style="margin-left: 12px">
        查看所有用户的实例
      </el-checkbox>
    </div>

    <el-table :data="items" v-loading="loading" stripe border style="margin-top: 12px">
      <el-table-column prop="env_name" label="靶场" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'running' ? 'success' : 'info'">
            {{ row.status === 'running' ? '运行中' : '已停止' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="访问地址" min-width="220">
        <template #default="{ row }">
          <div v-for="p in row.ports" :key="p.host_port">
            <a :href="p.url" target="_blank">{{ p.url }}</a>
            <span style="color: #909399"> ({{ p.container_port }})</span>
          </div>
          <span v-if="!row.ports.length">-</span>
        </template>
      </el-table-column>
      <el-table-column v-if="auth.isAdmin && showAll" prop="owner_username" label="所属用户" width="120" />
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="refreshStatus(row)">状态</el-button>
          <el-button size="small" @click="viewLogs(row)">日志</el-button>
          <el-button
            size="small"
            type="warning"
            :disabled="row.status !== 'running'"
            @click="stop(row)"
          >
            停止
          </el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="logsVisible" title="容器日志" width="70%">
      <pre class="logs">{{ logs }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { instanceApi } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const showAll = ref(false)
const logsVisible = ref(false)
const logs = ref('')

function formatTime(t) {
  return t ? new Date(t).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    const { data } = await instanceApi.list(showAll.value)
    items.value = data
  } finally {
    loading.value = false
  }
}

async function refreshStatus(row) {
  const { data } = await instanceApi.status(row.id)
  Object.assign(row, data)
  ElMessage.success('状态已刷新')
}

async function viewLogs(row) {
  logs.value = '加载中...'
  logsVisible.value = true
  const { data } = await instanceApi.logs(row.id)
  logs.value = data.logs || '(无日志)'
}

async function stop(row) {
  await ElMessageBox.confirm(`确认停止「${row.env_name}」?`, '提示', { type: 'warning' })
  await instanceApi.stop(row.id)
  ElMessage.success('已停止')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除「${row.env_name}」的实例记录? 若在运行将先停止。`, '提示', {
    type: 'warning',
  })
  await instanceApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
}
.logs {
  max-height: 60vh;
  overflow: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
