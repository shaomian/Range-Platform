<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" class="aside">
      <div class="logo">🎯 Vulhub 靶场平台</div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item index="/environments">
          <el-icon><Grid /></el-icon><span>靶场列表</span>
        </el-menu-item>
        <el-menu-item index="/instances">
          <el-icon><Monitor /></el-icon><span>我的实例</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/users">
          <el-icon><User /></el-icon><span>用户管理</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/settings">
          <el-icon><Setting /></el-icon><span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span />
        <el-dropdown @command="onCommand">
          <span class="user-info">
            <el-icon><Avatar /></el-icon>
            {{ auth.user?.username }}
            <el-tag size="small" :type="auth.isAdmin ? 'danger' : 'info'">
              {{ auth.isAdmin ? '管理员' : '普通用户' }}
            </el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => {
  if (route.path.startsWith('/environments')) return '/environments'
  return route.path
})

onMounted(async () => {
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch (e) {
      /* handled by interceptor */
    }
  }
})

function onCommand(cmd) {
  if (cmd === 'logout') {
    auth.logout()
    router.push({ name: 'login' })
  }
}
</script>

<style scoped>
.aside {
  background: #001529;
  color: #fff;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-weight: bold;
  color: #fff;
  font-size: 15px;
}
.menu {
  background: #001529;
  border-right: none;
}
.menu :deep(.el-menu-item) {
  color: #cfd3dc;
}
.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #1890ff;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #eaeaea;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
</style>
