<template>
  <div v-loading="loading">
    <el-card>
      <template #header>
        <span class="card-title">实例超时配置</span>
      </template>
      <el-form :model="form" label-width="180px" style="max-width: 560px">
        <el-form-item label="默认超时时间">
          <el-input-number v-model="form.instance_default_ttl_minutes" :min="1" :step="15" />
          <span class="hint">分钟（启动新实例时自动应用）</span>
        </el-form-item>
        <el-form-item label="用户最大续期时长">
          <el-input-number v-model="form.instance_max_ttl_minutes" :min="1" :step="15" />
          <span class="hint">分钟（普通用户单次续期上限，管理员不受此限）</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          <el-button @click="reload">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="tip">
        提示：实例到达超时时间后会自动停止并清理容器，用户可在“我的实例”页面手动续期。
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { settingsApi } from '../api'

const loading = ref(false)
const saving = ref(false)
const form = reactive({
  instance_default_ttl_minutes: 60,
  instance_max_ttl_minutes: 1440,
})

async function reload() {
  loading.value = true
  try {
    const { data } = await settingsApi.get()
    form.instance_default_ttl_minutes = data.instance_default_ttl_minutes
    form.instance_max_ttl_minutes = data.instance_max_ttl_minutes
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const { data } = await settingsApi.update({
      instance_default_ttl_minutes: form.instance_default_ttl_minutes,
      instance_max_ttl_minutes: form.instance_max_ttl_minutes,
    })
    form.instance_default_ttl_minutes = data.instance_default_ttl_minutes
    form.instance_max_ttl_minutes = data.instance_max_ttl_minutes
    ElMessage.success('配置已保存')
  } catch (e) {
    /* handled by interceptor */
  } finally {
    saving.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.card-title {
  font-weight: bold;
}
.hint {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}
.tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
