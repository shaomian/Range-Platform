<template>
  <div v-loading="loading">
    <el-page-header @back="$router.push({ name: 'environments' })" :content="detail?.name || '靶场详情'" />

    <el-card v-if="detail" shadow="never" style="margin-top: 12px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="应用">{{ detail.app }}</el-descriptions-item>
        <el-descriptions-item label="路径">{{ detail.path }}</el-descriptions-item>
        <el-descriptions-item label="CVE">{{ detail.cve.join(', ') || '-' }}</el-descriptions-item>
        <el-descriptions-item label="镜像">{{ detail.images.join(', ') || '-' }}</el-descriptions-item>
        <el-descriptions-item label="标签" :span="2">
          <el-tag v-for="t in detail.tags" :key="t" size="small" style="margin: 2px">{{ t }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="声明端口" :span="2">
          <span v-for="p in detail.declared_ports" :key="p.service + p.host_port" style="margin-right: 12px">
            {{ p.service }}: {{ p.host_port }}→{{ p.container_port }}
          </span>
          <span v-if="!detail.declared_ports.length">-</span>
        </el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 12px">
        <el-button type="success" :icon="VideoPlay" :loading="starting" @click="start">启动靶场</el-button>
      </div>
    </el-card>

    <el-tabs v-if="detail" v-model="tab" style="margin-top: 12px">
      <el-tab-pane label="说明文档 (README)" name="readme">
        <div class="readme-body" v-html="renderedReadme"></div>
      </el-tab-pane>
      <el-tab-pane label="docker-compose.yml" name="compose">
        <pre class="readme-body">{{ detail.compose || '无' }}</pre>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Marked } from 'marked'
import { ElMessageBox } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import { envApi, instanceApi } from '../api'

const route = useRoute()
const loading = ref(false)
const starting = ref(false)
const detail = ref(null)
const tab = ref('readme')

const md = new Marked({
  renderer: {
    image({ href, title, text }) {
      let src = href || ''
      if (src && !/^(https?:)?\/\//i.test(src) && !src.startsWith('data:')) {
        const base = `/api/environments/${route.params.path}/raw/`
        src = base + src.replace(/^\.?\//, '')
        const token = localStorage.getItem('token')
        if (token) {
          src += (src.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token)
        }
      }
      let out = `<img src="${src}" alt="${text || ''}"`
      if (title) out += ` title="${title}"`
      out += '>'
      return out
    },
  },
})

const renderedReadme = computed(() =>
  detail.value?.readme ? md.parse(detail.value.readme) : '<p>暂无说明文档</p>'
)

async function load() {
  loading.value = true
  try {
    const { data } = await envApi.detail(route.params.path)
    detail.value = data
  } finally {
    loading.value = false
  }
}

async function start() {
  starting.value = true
  try {
    const { data } = await instanceApi.start(detail.value.path)
    const urls = data.ports.map((p) => p.url).filter(Boolean)
    ElMessageBox.alert(
      `靶场已启动。访问地址：<br/>${urls.map((u) => `<a href="${u}" target="_blank">${u}</a>`).join('<br/>') || '无公开端口'}`,
      '启动成功',
      { dangerouslyUseHTMLString: true }
    )
  } catch (e) {
    /* handled by interceptor */
  } finally {
    starting.value = false
  }
}

onMounted(load)
</script>
