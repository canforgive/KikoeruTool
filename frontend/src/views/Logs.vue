<template>
  <div class="logs">
    <h1 class="page-title">日志</h1>
    
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统日志</span>
          <div class="header-actions">
            <el-button 
              :type="isPaused ? 'success' : 'warning'"
              @click="togglePause"
            >
              <el-icon><component :is="isPaused ? 'VideoPlay' : 'VideoPause'" /></el-icon>
              {{ isPaused ? '恢复自动刷新' : '暂停自动刷新' }}
            </el-button>
            <el-button @click="refreshLogs">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <el-button type="danger" @click="clearLogs">
              <el-icon><Delete /></el-icon> 清空
            </el-button>
          </div>
        </div>
      </template>
      
      <div 
        class="log-container" 
        ref="logContainer"
        @scroll="handleScroll"
        :class="{ 'paused': isPaused }"
      >
        <div v-if="isPaused" class="log-status-indicator paused">
          已暂停自动刷新
        </div>
        <div v-else-if="isUserScrolling" class="log-status-indicator">
          查看历史日志中...
        </div>
        <div 
          v-for="(log, index) in logs" 
          :key="index"
          class="log-line"
          :class="`log-${log.level.toLowerCase()}`"
        >
          <span class="log-time">{{ log.time }}</span>
          <span class="log-level">[{{ log.level }}]</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
      
      <el-empty v-if="logs.length === 0" description="暂无日志" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Refresh, Delete, VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const logs = ref([])
const logContainer = ref(null)
let intervalId = null
const isPaused = ref(false)
const isUserScrolling = ref(false)
let scrollTimeout = null

onMounted(() => {
  refreshLogs()
  // 每3秒自动刷新
  intervalId = setInterval(() => {
    if (!isPaused.value) {
      refreshLogs()
    }
  }, 3000)
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
  }
  if (scrollTimeout) {
    clearTimeout(scrollTimeout)
  }
})

function handleScroll() {
  if (!logContainer.value) return
  
  // 检测用户是否正在查看历史日志（不在底部）
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50
  
  isUserScrolling.value = !isAtBottom
  
  // 清除之前的定时器
  if (scrollTimeout) {
    clearTimeout(scrollTimeout)
  }
  
  // 如果用户停止滚动5秒后，且在最底部，恢复自动滚动
  scrollTimeout = setTimeout(() => {
    if (isAtBottom) {
      isUserScrolling.value = false
    }
  }, 5000)
}

function togglePause() {
  isPaused.value = !isPaused.value
  if (isPaused.value) {
    ElMessage.info('已暂停自动刷新，可以查看历史日志')
  } else {
    ElMessage.success('已恢复自动刷新')
    refreshLogs()
  }
}

async function refreshLogs() {
  try {
    const response = await axios.get('/api/logs?lines=200')
    const logLines = response.data.logs || []
    
    // 解析日志行
    logs.value = logLines.map(line => {
      // 尝试解析新格式: 2024-01-01 12:00:00 [LEVEL] name - message
      let match = line.match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+\S+\s+-\s+(.+)$/)
      if (match) {
        return {
          time: match[1],
          level: match[2].toUpperCase(),
          message: match[3],
          raw: line
        }
      }
      
      // 尝试解析旧格式: 2024-01-01 12:00:00 - name - level - message
      match = line.match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-\s+\S+\s+-\s+(\w+)\s+-\s+(.+)$/)
      if (match) {
        return {
          time: match[1],
          level: match[2].toUpperCase(),
          message: match[3],
          raw: line
        }
      }
      
      // 如果解析失败，显示原始行
      return {
        time: '',
        level: 'INFO',
        message: line,
        raw: line
      }
    })
    
    // 只有当用户没有在查看历史日志时才滚动到底部
    nextTick(() => {
      if (logContainer.value && !isUserScrolling.value && !isPaused.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    })
  } catch (error) {
    console.error('获取日志失败:', error)
  }
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm('确定要清空所有日志吗？', '确认', {
      type: 'warning'
    })
    logs.value = []
    ElMessage.success('日志已清空')
  } catch (error) {
    // 取消操作
  }
}
</script>

<style scoped>
.logs {
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.log-container {
  height: 600px;
  overflow-y: auto;
  background-color: #1e293b;
  border-radius: 8px;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  position: relative;
}

.log-container.paused {
  border: 2px solid #f59e0b;
}

.log-status-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.log-status-indicator.paused {
  background-color: #f59e0b;
  color: white;
}

.log-status-indicator:not(.paused) {
  background-color: #3b82f6;
  color: white;
}

.log-line {
  display: flex;
  gap: 12px;
  padding: 2px 0;
  color: #e2e8f0;
}

.log-time {
  color: #64748b;
  white-space: nowrap;
}

.log-level {
  font-weight: bold;
  white-space: nowrap;
}

.log-debug .log-level { color: #94a3b8; }
.log-info .log-level { color: #3b82f6; }
.log-warning .log-level { color: #f59e0b; }
.log-error .log-level { color: #ef4444; }
</style>
