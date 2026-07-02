<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <div class="filters">
        <el-input
          v-model="search"
          placeholder="搜索名称 / CVE / 应用 / 路径"
          clearable
          style="width: 280px"
          :prefix-icon="Search"
          @keyup.enter="reload"
          @clear="reload"
        />
        <el-select v-model="tag" placeholder="漏洞/应用类型标签" clearable style="width: 200px" @change="reload">
          <el-option v-for="t in meta.tags" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select v-model="app" placeholder="应用" clearable filterable style="width: 200px" @change="reload">
          <el-option v-for="a in meta.apps" :key="a" :label="a" :value="a" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="reload">查询</el-button>
        <el-button
          v-if="auth.isAdmin"
          :icon="Refresh"
          :loading="reloading"
          @click="reloadCatalog"
        >
          刷新目录
        </el-button>
        <span class="count">共 {{ items.length }} 个靶场</span>
      </div>
    </el-card>

    <el-table :data="pageItems" v-loading="loading" stripe border style="margin-top: 12px">
      <el-table-column prop="name" label="名称" min-width="260" show-overflow-tooltip />
      <el-table-column prop="app" label="应用" width="150" show-overflow-tooltip />
      <el-table-column label="CVE" width="170">
        <template #default="{ row }">
          <span>{{ row.cve.join(', ') || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="标签" min-width="200">
        <template #default="{ row }">
          <el-tag v-for="t in row.tags" :key="t" size="small" style="margin: 2px">{{ t }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="goDetail(row)">详情</el-button>
          <el-button size="small" type="success" :loading="starting === row.path" @click="start(row)">
            启动
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 12px; justify-content: flex-end"
      layout="total, sizes, prev, pager, next"
      :total="items.length"
      :page-sizes="[10, 20, 50, 100]"
      v-model:current-page="page"
      v-model:page-size="pageSize"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { envApi, instanceApi } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const reloading = ref(false)
const starting = ref('')
const items = ref([])
const meta = reactive({ tags: [], apps: [] })
const search = ref('')
const tag = ref('')
const app = ref('')
const page = ref(1)
const pageSize = ref(20)

const pageItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return items.value.slice(start, start + pageSize.value)
})

async function reload() {
  loading.value = true
  page.value = 1
  try {
    const { data } = await envApi.list({
      search: search.value || undefined,
      tag: tag.value || undefined,
      app: app.value || undefined,
    })
    items.value = data
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  const { data } = await envApi.meta()
  meta.tags = data.tags
  meta.apps = data.apps
}

async function reloadCatalog() {
  reloading.value = true
  try {
    const { data } = await envApi.reload()
    await loadMeta()
    await reload()
    ElMessage.success(`目录已刷新，共 ${data.count} 个靶场`)
  } catch (e) {
    /* handled by interceptor */
  } finally {
    reloading.value = false
  }
}

function goDetail(row) {
  router.push({ name: 'environment-detail', params: { path: row.path } })
}

async function start(row) {
  starting.value = row.path
  try {
    const { data } = await instanceApi.start(row.path)
    const urls = data.ports.map((p) => p.url).filter(Boolean)
    ElMessageBox.alert(
      `靶场已启动。访问地址：<br/>${urls.map((u) => `<a href="${u}" target="_blank">${u}</a>`).join('<br/>') || '无公开端口'}`,
      '启动成功',
      { dangerouslyUseHTMLString: true }
    )
  } catch (e) {
    /* handled by interceptor */
  } finally {
    starting.value = ''
  }
}

onMounted(async () => {
  await loadMeta()
  await reload()
})
</script>

<style scoped>
.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.count {
  color: #909399;
  margin-left: auto;
}
</style>
