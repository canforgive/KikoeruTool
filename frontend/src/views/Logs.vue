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
      
      <div class="filter-section">
        <div class="filter-group">
          <span class="filter-label">日志级别：</span>
          <el-checkbox-group v-model="selectedLevels" size="small">
            <el-checkbox-button v-for="level in allLevels" :key="level" :value="level">
              <span :class="`level-badge level-${level.toLowerCase()}`">{{ level }}</span>
            </el-checkbox-button>
          </el-checkbox-group>
        </div>
        <div class="filter-group">
          <span class="filter-label">模块筛选：</span>
          <el-select v-model="selectedModules" multiple collapse-tags collapse-tags-tooltip placeholder="全部模块" clearable size="small" style="width: 200px">
            <el-option v-for="mod in availableModules" :key="mod" :label="mod" :value="mod" />
          </el-select>
        </div>
        <div class="filter-group">
          <span class="filter-label">搜索：</span>
          <el-input v-model="searchKeyword" placeholder="搜索日志内容" clearable size="small" style="width: 200px">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="filter-group">
          <span class="filter-label">显示条数：</span>
          <el-select v-model="logLimit" size="small" style="width: 100px" @change="refreshLogs">
            <el-option :value="200" label="200条" />
            <el-option :value="500" label="500条" />
            <el-option :value="1000" label="1000条" />
            <el-option :value="2000" label="2000条" />
            <el-option :value="5000" label="5000条" />
          </el-select>
        </div>
        <div class="filter-stats">
          共 {{ filteredLogs.length }} 条 / {{ logs.length }} 条
        </div>
      </div>
      
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
          v-for="(log, index) in filteredLogs" 
          :key="index"
          class="log-line"
          :class="`log-${log.level.toLowerCase()}`"
        >
          <span class="log-time">{{ log.time }}</span>
          <span class="log-level" :class="`level-${log.level.toLowerCase()}`">{{ log.level }}</span>
          <span v-if="log.module" class="log-module" :style="{ backgroundColor: getModuleColor(log.module) }">{{ log.module }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
      
      <el-empty v-if="filteredLogs.length === 0 && logs.length > 0" description="没有匹配的日志" />
      <el-empty v-if="logs.length === 0" description="暂无日志" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Refresh, Delete, VideoPlay, VideoPause, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logApi } from '../api'

const logs = ref([])
const logContainer = ref(null)
let intervalId = null
const isPaused = ref(false)
const isUserScrolling = ref(false)
let scrollTimeout = null
const logLimit = ref(1000)

const allLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
const selectedLevels = ref(['INFO', 'WARNING', 'ERROR'])
const selectedModules = ref([])
const searchKeyword = ref('')

const availableModules = computed(() => {
  const modules = new Set()
  logs.value.forEach(log => {
    if (log.module) modules.add(log.module)
  })
  return Array.from(modules).sort()
})

const filteredLogs = computed(() => {
  return logs.value.filter(log => {
    if (!selectedLevels.value.includes(log.level)) return false
    if (selectedModules.value.length > 0 && !selectedModules.value.includes(log.module)) return false
    if (searchKeyword.value) {
      const keyword = searchKeyword.value.toLowerCase()
      return log.message.toLowerCase().includes(keyword) || 
             log.module?.toLowerCase().includes(keyword)
    }
    return true
  })
})

const moduleColors = {
  'Kikoeru': '#8b5cf6',
  'Kikoeru关联查询': '#a855f7',
  'Kikoeru查重': '#7c3aed',
  'CONFIG': '#06b6d4',
  'CONFIG SAVE': '#0891b2',
  'RENAME': '#10b981',
  'API RENAME': '#059669',
  '解压': '#f59e0b',
  '分类': '#3b82f6',
  '元数据': '#ec4899',
  '密码': '#6366f1',
  '清理': '#14b8a6',
  '扫描': '#f97316',
}

function getModuleColor(moduleName) {
  return moduleColors[moduleName] || '#6b7280'
}

function parseModule(message, rawLine) {
  const bracketMatch = rawLine.match(/\[(\w+(?:\s*\w+)*)\]/)
  if (bracketMatch) {
    const tag = bracketMatch[1]
    if (tag.includes('Kikoeru') || tag.includes('CONFIG') || tag.includes('RENAME')) {
      return tag
    }
  }
  if (message.includes('扫描') || message.includes('库存') || message.includes('已处理压缩包')) return '扫描'
  if (message.includes('解压') || message.includes('压缩')) return '解压'
  if (message.includes('分类') || message.includes('规则')) return '分类'
  if (message.includes('元数据') || message.includes('RJ')) return '元数据'
  if (message.includes('密码')) return '密码'
  if (message.includes('清理') || message.includes('删除')) return '清理'
  return null
}

onMounted(() => {
  refreshLogs()
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
  
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50
  
  isUserScrolling.value = !isAtBottom
  
  if (scrollTimeout) {
    clearTimeout(scrollTimeout)
  }
  
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
    const data = await logApi.get(logLimit.value)
    const logLines = data.logs || []
    
    logs.value = logLines.map(line => {
      let match = line.match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+\S+\s+-\s+(.+)$/)
      if (match) {
        const message = match[3]
        return {
          time: match[1],
          level: match[2].toUpperCase(),
          module: parseModule(message, line),
          message: message,
          raw: line
        }
      }
      
      match = line.match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-\s+\S+\s+-\s+(\w+)\s+-\s+(.+)$/)
      if (match) {
        const message = match[3]
        return {
          time: match[1],
          level: match[2].toUpperCase(),
          module: parseModule(message, line),
          message: message,
          raw: line
        }
      }
      
      return {
        time: '',
        level: 'INFO',
        module: parseModule(line, line),
        message: line,
        raw: line
      }
    })
    
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
  gap: 8px;
}

.filter-section {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background-color: #f8fafc;
  border-radius: 8px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: #64748b;
  white-space: nowrap;
}

.filter-stats {
  margin-left: auto;
  font-size: 13px;
  color: #94a3b8;
}

.level-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.level-debug { background-color: #e2e8f0; color: #475569; }
.level-info { background-color: #dbeafe; color: #1d4ed8; }
.level-warning { background-color: #fef3c7; color: #b45309; }
.level-error { background-color: #fee2e2; color: #b91c1c; }

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
  gap: 8px;
  padding: 2px 0;
  color: #e2e8f0;
  align-items: flex-start;
}

.log-time {
  color: #64748b;
  white-space: nowrap;
  flex-shrink: 0;
}

.log-level {
  font-weight: bold;
  white-space: nowrap;
  flex-shrink: 0;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 11px;
  min-width: 50px;
  text-align: center;
}

.log-debug .log-level { background-color: #374151; color: #9ca3af; }
.log-info .log-level { background-color: #1e3a5f; color: #60a5fa; }
.log-warning .log-level { background-color: #78350f; color: #fbbf24; }
.log-error .log-level { background-color: #7f1d1d; color: #f87171; }

.log-module {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
  color: white;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  word-break: break-word;
}

.log-debug { opacity: 0.7; }
.log-error { background-color: rgba(239, 68, 68, 0.1); }
.log-warning { background-color: rgba(245, 158, 11, 0.1); }
</style>
