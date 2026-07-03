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
      <el-table-column label="剩余时长" width="140">
        <template #default="{ row }">
          <span v-if="row.status === 'running' && row.expires_at" :style="{ color: countdownColor(row) }">
            {{ countdown(row) }}
          </span>
          <span v-else style="color: #909399">-</span>
        </template>
      </el-table-column>
      <el-table-column v-if="auth.isAdmin && showAll" prop="owner_username" label="所属用户" width="120" />
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="430" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="refreshStatus(row)">状态</el-button>
          <el-button size="small" @click="viewLogs(row)">日志</el-button>
          <el-button
            size="small"
            type="success"
            :disabled="row.status !== 'running'"
            @click="openTerminal(row)"
          >
            终端
          </el-button>
          <el-button
            size="small"
            type="primary"
            :disabled="row.status !== 'running'"
            @click="renew(row)"
          >
            续期
          </el-button>
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

    <el-dialog v-model="renewVisible" title="续期实例" width="380px">
      <el-form :model="renewForm" label-width="100px">
        <el-form-item label="续期时长">
          <el-input-number v-model="renewForm.minutes" :min="1" :max="renewMax" :step="15" />
          <span style="margin-left: 8px; color: #909399">分钟</span>
        </el-form-item>
        <div style="color: #909399; font-size: 12px">
          续期后将自当前时刻起 {{ renewForm.minutes }} 分钟后自动停止。
          <span v-if="renewForm.maxHint">{{ renewForm.maxHint }}</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="renewVisible = false">取消</el-button>
        <el-button type="primary" :loading="renewing" @click="doRenew">确认续期</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logsVisible" title="容器日志" width="70%">
      <pre class="logs">{{ logs }}</pre>
    </el-dialog>

    <el-dialog
      v-model="termVisible"
      :title="`容器终端 - ${termRow ? termRow.env_name : ''}`"
      width="80%"
      @open="onTermOpen"
      @opened="onTermOpened"
      @closed="onTermClosed"
    >
      <div ref="termHost" class="term-host"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { instanceApi, settingsApi } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const showAll = ref(false)
const logsVisible = ref(false)
const logs = ref('')

const termVisible = ref(false)
const termRow = ref(null)
const termHost = ref(null)
let term = null
let fitAddon = null
let ws = null

// Live countdown needs a per-second re-render. We don't poll the server every
// second; we just bump a reactive "now" tick so the computed countdown reads
// fresh values. A slower 30s server refresh catches auto-stops and removals.
const nowTick = ref(Date.now())
let countdownTimer = null
let pollTimer = null

// TTL configuration loaded from the admin settings endpoint.
const ttlConfig = reactive({
  defaultMinutes: 60,
  maxMinutes: 1440,
})

// Renew dialog state.
const renewVisible = ref(false)
const renewing = ref(false)
const renewForm = reactive({ minutes: 60, maxHint: '', targetId: null })
const renewMax = ref(1440)

function formatTime(t) {
  return t ? new Date(t).toLocaleString() : '-'
}

function _remainingMs(row) {
  if (!row.expires_at) return null
  const end = new Date(row.expires_at).getTime()
  return end - nowTick.value
}

function countdown(row) {
  const ms = _remainingMs(row)
  if (ms === null) return '-'
  if (ms <= 0) return '即将停止'
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

function countdownColor(row) {
  const ms = _remainingMs(row)
  if (ms === null) return '#909399'
  if (ms <= 60 * 1000) return '#f56c6c' // <1m -> red
  if (ms <= 5 * 60 * 1000) return '#e6a23c' // <5m -> orange
  return '#67c23a'
}

async function loadSettings() {
  try {
    const { data } = await settingsApi.get()
    ttlConfig.defaultMinutes = data.instance_default_ttl_minutes
    ttlConfig.maxMinutes = data.instance_max_ttl_minutes
  } catch (e) {
    /* keep defaults; non-fatal */
  }
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

function openTerminal(row) {
  termRow.value = row
  termVisible.value = true
}

async function onTermOpen() {
  await nextTick()
  if (!termHost.value) return
  term = new Terminal({ fontSize: 13, cursorBlink: true, scrollback: 5000 })
  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(termHost.value)
  try {
    fitAddon.fit()
  } catch (e) {
    /* layout not ready yet */
  }

  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = localStorage.getItem('token') || ''
  const cols = term.cols
  const rows = term.rows
  const url =
    `${proto}://${location.host}/api/instances/${termRow.value.id}/terminal` +
    `?token=${encodeURIComponent(token)}&cols=${cols}&rows=${rows}`
  ws = new WebSocket(url)
  ws.binaryType = 'arraybuffer'

  ws.onmessage = (ev) => {
    if (!term) return
    if (ev.data instanceof ArrayBuffer) {
      term.write(new Uint8Array(ev.data))
    } else if (typeof ev.data === 'string') {
      term.write(ev.data)
    }
  }
  ws.onerror = () => {
    if (term) term.write('\r\n*** 连接错误 ***\r\n')
  }
  ws.onclose = () => {
    if (term) term.write('\r\n*** 连接已关闭 ***\r\n')
  }

  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(data)
  })
  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', cols, rows }))
    }
  })
}

function onTermOpened() {
  try {
    if (fitAddon) fitAddon.fit()
  } catch (e) {
    /* ignore */
  }
  if (term) term.focus()
}

function onTermClosed() {
  if (ws) {
    try {
      ws.close()
    } catch (e) {
      /* ignore */
    }
    ws = null
  }
  if (term) {
    term.dispose()
    term = null
  }
  fitAddon = null
  termRow.value = null
}

async function stop(row) {
  await ElMessageBox.confirm(`确认停止「${row.env_name}」?`, '提示', { type: 'warning' })
  await instanceApi.stop(row.id)
  ElMessage.success('已停止')
  load()
}

function renew(row) {
  renewForm.targetId = row.id
  renewForm.minutes = ttlConfig.defaultMinutes
  const isOwner = auth.user?.id === row.owner_id
  if (auth.isAdmin) {
    renewMax.value = 43200 // 30 days upper bound for the picker (admin otherwise unrestricted)
    renewForm.maxHint = '管理员不受上限约束。'
  } else {
    renewMax.value = ttlConfig.maxMinutes
    renewForm.maxHint = isOwner
      ? `普通用户单次最长 ${ttlConfig.maxMinutes} 分钟。`
      : ''
  }
  renewVisible.value = true
}

async function doRenew() {
  renewing.value = true
  try {
    const { data } = await instanceApi.renew(renewForm.targetId, renewForm.minutes)
    const row = items.value.find((i) => i.id === renewForm.targetId)
    if (row) Object.assign(row, data)
    ElMessage.success(`已续期至 ${renewForm.minutes} 分钟后自动停止`)
    renewVisible.value = false
  } catch (e) {
    /* handled by interceptor */
  } finally {
    renewing.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除「${row.env_name}」的实例记录? 若在运行将先停止。`, '提示', {
    type: 'warning',
  })
  await instanceApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  await loadSettings()
  await load()
  countdownTimer = setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
  pollTimer = setInterval(load, 30000)
})

onBeforeUnmount(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (pollTimer) clearInterval(pollTimer)
})
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
.term-host {
  height: 60vh;
  background: #1e1e1e;
  padding: 8px;
  border-radius: 6px;
}
</style>
