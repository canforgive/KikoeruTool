<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon :size="32"><Box /></el-icon>
        <span class="logo-text">Prekikoeru</span>
      </div>
      
      <el-menu
        :default-active="$route.path"
        router
        class="sidebar-menu"
        background-color="#1e293b"
        text-color="#94a3b8"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>概览</span>
        </el-menu-item>
        
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span>任务队列</span>
        </el-menu-item>
        
        <el-menu-item index="/conflicts">
          <el-icon><WarningFilled /></el-icon>
          <span>问题作品</span>
          <el-badge v-if="conflictCount > 0" :value="conflictCount" class="conflict-badge" />
        </el-menu-item>
        
        <el-menu-item index="/library">
          <el-icon><Box /></el-icon>
          <span>库存管理</span>
        </el-menu-item>
        
        <el-menu-item index="/passwords">
          <el-icon><Lock /></el-icon>
          <span>密码库</span>
        </el-menu-item>
        
        <el-menu-item index="/existing-folders">
          <el-icon><Folder /></el-icon>
          <span>已有文件夹</span>
        </el-menu-item>
        
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>设置</span>
        </el-menu-item>
        
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>日志</span>
        </el-menu-item>
      </el-menu>
      
      <div class="sidebar-footer">
        <div class="watcher-status">
          <el-tag :type="watcherStatus.is_running ? 'success' : 'info'" size="small">
            {{ watcherStatus.is_running ? '监视中' : '已停止' }}
          </el-tag>
          <el-button 
            :type="watcherStatus.is_running ? 'danger' : 'primary'"
            size="small"
            @click="toggleWatcher"
          >
            {{ watcherStatus.is_running ? '停止' : '启动' }}
          </el-button>
        </div>
        <div class="version-info">
          <span class="version-text">版本: v{{ appVersion }}</span>
        </div>
      </div>
    </el-aside>
    
    <!-- 主内容区 -->
    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Box, HomeFilled, List, WarningFilled, Setting, Document, Lock, Folder } from '@element-plus/icons-vue'
import { useWatcherStore } from './stores'

// 直接定义版本号（确保每次构建都会更新）
const appVersion = '1.0.1'

const watcherStore = useWatcherStore()
const conflictCount = ref(0)
const watcherStatus = ref({ is_running: false, watch_path: '', pending_files: [] })

let intervalId

onMounted(async () => {
  await refreshStatus()
  intervalId = setInterval(refreshStatus, 3000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})

async function refreshStatus() {
  await watcherStore.fetchStatus()
  watcherStatus.value = watcherStore.status
}

async function toggleWatcher() {
  if (watcherStatus.value.is_running) {
    await watcherStore.stop()
  } else {
    await watcherStore.start()
  }
  await refreshStatus()
}
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.sidebar {
  background-color: #1e293b;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
  border-bottom: 1px solid #334155;
  color: #ffffff;
}

.logo-text {
  margin-left: 12px;
  font-size: 20px;
  font-weight: 600;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid #334155;
}

.watcher-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conflict-badge {
  margin-left: auto;
}

.version-info {
  margin-top: 8px;
  text-align: center;
  padding-top: 8px;
  border-top: 1px solid #334155;
}

.version-text {
  font-size: 12px;
  color: #94a3b8;
  background-color: #0f172a;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
}

.main-content {
  background-color: #f1f5f9;
  padding: 20px;
  overflow-y: auto;
  min-width: 0; /* 防止 flex 子元素溢出 */
}

/* 响应式布局 */
@media screen and (max-width: 768px) {
  .app-container {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100% !important;
    height: auto;
    max-height: 60px;
    overflow: hidden;
  }
  
  .sidebar.expanded {
    max-height: none;
  }
  
  .main-content {
    padding: 10px;
  }
}

/* 确保表格容器可以横向滚动 */
:deep(.el-card) {
  overflow: visible;
}

:deep(.el-card__body) {
  overflow-x: auto;
}
</style>
