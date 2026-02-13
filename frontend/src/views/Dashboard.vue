<template>
  <div class="dashboard">
    <h1 class="page-title">概览</h1>
    
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background-color: #3b82f6;">
            <el-icon :size="24"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background-color: #f59e0b;">
            <el-icon :size="24"><Loading /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.processing }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card clickable" @click="$router.push('/library')">
          <div class="stat-icon" style="background-color: #10b981;">
            <el-icon :size="24"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.completed }}</div>
            <div class="stat-label">已完成（点击查看库文件）</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background-color: #ef4444;">
            <el-icon :size="24"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.conflicts }}</div>
            <div class="stat-label">问题作品</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 快捷操作栏 -->
    <el-card class="action-card">
      <template #header>
        <div class="card-header">
          <span>快捷操作</span>
        </div>
      </template>
      <div class="action-buttons">
        <el-button 
          type="primary" 
          size="large" 
          @click="handleManualScan"
          :loading="scanning"
        >
          <el-icon><Search /></el-icon>
          扫描并处理文件夹
        </el-button>
        <el-button 
          type="success" 
          size="large" 
          @click="handleWatcherToggle"
        >
          <el-icon><VideoPlay v-if="!watcherRunning" /><VideoPause v-else /></el-icon>
          {{ watcherRunning ? '停止监视器' : '启动监视器' }}
        </el-button>
        <el-button 
          type="info" 
          size="large" 
          @click="$router.push('/conflicts')"
        >
          <el-icon><Warning /></el-icon>
          问题作品 ({{ stats.conflicts }})
        </el-button>
      </div>
      <el-divider />
      <FileUploader @upload-success="handleUploadSuccess" />
    </el-card>
    
    <!-- 当前任务 -->
    <el-card class="tasks-card">
      <template #header>
        <div class="card-header">
          <span>当前任务</span>
          <el-button link @click="$router.push('/tasks')">查看全部</el-button>
        </div>
      </template>
      
      <el-table :data="recentTasks" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80">
          <template #default="{ row }">
            <span class="task-id">{{ row.id.slice(0, 8) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="source_path" label="源文件" show-overflow-tooltip />
        
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getTaskTypeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="progress" label="进度" width="200">
          <template #default="{ row }">
            <div class="progress-wrapper">
              <el-progress 
                :percentage="row.progress" 
                :status="getProgressStatus(row.status)"
                :stroke-width="16"
              />
              <span class="progress-text">{{ row.current_step }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button-group v-if="row.status === 'processing'">
              <el-button size="small" @click="pauseTask(row.id)">暂停</el-button>
              <el-button size="small" type="danger" @click="cancelTask(row.id)">取消</el-button>
            </el-button-group>
            <el-button 
              v-else-if="row.status === 'paused'" 
              size="small" 
              type="primary"
              @click="resumeTask(row.id)"
            >
              恢复
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 已处理压缩包 -->
    <el-card class="archives-card">
      <template #header>
        <div class="card-header">
          <span>已处理压缩包</span>
          <div class="archives-header-actions">
            <!-- 搜索框 -->
            <el-input
              v-model="archiveSearchQuery"
              placeholder="搜索RJ号或文件名"
              style="width: 200px; margin-right: 12px;"
              clearable
              @input="handleArchiveSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            
            <!-- 排序选择器 -->
            <el-select v-model="archiveSortBy" style="width: 140px; margin-right: 8px;" @change="handleArchiveSortChange">
              <el-option label="处理时间" value="processed_at" />
              <el-option label="RJ号" value="rjcode" />
              <el-option label="文件大小" value="file_size" />
              <el-option label="处理次数" value="process_count" />
              <el-option label="状态" value="status" />
            </el-select>
            
            <!-- 排序方向 -->
            <el-button 
              link 
              @click="toggleArchiveSortOrder"
              :title="archiveSortOrder === 'desc' ? '降序' : '升序'"
            >
              <el-icon>
                <SortDown v-if="archiveSortOrder === 'desc'" />
                <SortUp v-else />
              </el-icon>
            </el-button>
            
            <el-button link @click="fetchProcessedArchives" :loading="archivesLoading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button link @click="showAllArchives = !showAllArchives">
              {{ showAllArchives ? '收起' : '查看全部' }}
            </el-button>
          </div>
        </div>
      </template>
      
      <el-table 
        :data="displayedArchives" 
        v-loading="archivesLoading" 
        style="width: 100%"
        empty-text="暂无已处理压缩包"
        row-key="id"
      >
        <el-table-column type="expand" width="40" v-if="displayedArchives.some(a => a.isVolumeGroup)">
          <template #default="{ row }">
            <div v-if="row.isVolumeGroup && row.volumes" class="volume-list">
              <div class="volume-list-title">分卷文件列表：</div>
              <div v-for="(vol, idx) in row.volumes" :key="idx" class="volume-item">
                <span class="volume-name">{{ vol.filename }}</span>
                <span class="volume-size">{{ formatFileSize(vol.file_size) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="rjcode" label="RJ号" width="120">
          <template #default="{ row }">
            <el-tag type="primary" size="small" v-if="row.rjcode">{{ row.rjcode }}</el-tag>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="filename" label="文件名" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.filename }}
            <el-tag v-if="row.isVolumeGroup" type="warning" size="small" class="volume-tag">
              {{ row.volumes.length }}个分卷
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        
        <el-table-column prop="process_count" label="处理次数" width="100">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.process_count || 1 }} 次</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="processed_at" label="处理时间" width="160">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.processed_at) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag 
              :type="row.status === 'completed' ? 'success' : (row.status === 'reprocessing' ? 'warning' : 'info')" 
              size="small"
            >
              {{ row.status === 'completed' ? '已完成' : (row.status === 'reprocessing' ? '重新处理中' : '处理中') }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button 
              size="small" 
              type="primary"
              @click="reprocessArchive(row.id)"
              :loading="reprocessingId === row.id"
            >
              重新解压
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Document, Loading, CircleCheck, Warning, Search, VideoPlay, VideoPause, Refresh, SortDown, SortUp } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useTaskStore } from '../stores'
import FileUploader from '../components/FileUploader.vue'

const taskStore = useTaskStore()
const loading = ref(false)
const scanning = ref(false)
const watcherRunning = ref(false)
const recentTasks = ref([])
const stats = ref({
  pending: 0,
  processing: 0,
  completed: 0,
  conflicts: 0
})

// 已处理压缩包相关
const archives = ref([])
const archivesLoading = ref(false)
const reprocessingId = ref(null)
const showAllArchives = ref(false)
const archiveSearchQuery = ref('')
const archiveSortBy = ref('processed_at')
const archiveSortOrder = ref('desc')
let archiveSearchTimeout = null

// 合并分卷压缩包组
const groupedArchives = computed(() => {
  const groups = new Map()
  const singles = []
  
  archives.value.forEach(archive => {
    const filename = archive.filename
    // 检查是否是分卷压缩包（支持 .part1.rar, .part2.rar, .part1.exe 等）
    const volumeMatch = filename.match(/^(.*)\.part(\d+)\.(rar|zip|7z|exe)$/i)
    
    if (volumeMatch) {
      // 提取基础组名（如：RJ01207739，不包含 .part 和扩展名）
      const baseName = volumeMatch[1]
      const groupKey = baseName + '_volume_group'
      
      if (!groups.has(groupKey)) {
        groups.set(groupKey, {
          id: archive.id,
          rjcode: archive.rjcode,
          filename: baseName + '（分卷组）',
          originalFilename: filename,
          file_size: 0,
          process_count: archive.process_count || 1,
          processed_at: archive.processed_at || new Date(0).toISOString(),
          status: archive.status,
          isVolumeGroup: true,
          groupKey: groupKey,
          volumes: []
        })
      }
      
      const group = groups.get(groupKey)
      group.volumes.push(archive)
      group.file_size += (archive.file_size || 0)
      
      // 使用最新的处理时间和状态（使用 Date 对象比较，避免字符串比较问题）
      const archiveTime = archive.processed_at ? new Date(archive.processed_at).getTime() : 0
      const groupTime = group.processed_at ? new Date(group.processed_at).getTime() : 0
      if (archiveTime > groupTime) {
        group.processed_at = archive.processed_at
        // 同时更新状态为最新的状态
        group.status = archive.status
        group.process_count = archive.process_count || 1
      }
      // 优先使用 part1 作为组的ID
      if (filename.toLowerCase().includes('.part1.')) {
        group.id = archive.id
      }
      // 如果没有 part1，使用第一个作为ID
      if (!group.id) {
        group.id = archive.id
      }
    } else {
      // 非分卷文件，直接添加
      singles.push({
        ...archive,
        isVolumeGroup: false
      })
    }
  })
  
  // 合并组和非分卷文件
  const result = [...groups.values(), ...singles]
  
  // 按处理时间排序（降序，最新的在前）
  result.sort((a, b) => {
    const timeA = a.processed_at ? new Date(a.processed_at).getTime() : 0
    const timeB = b.processed_at ? new Date(b.processed_at).getTime() : 0
    return timeB - timeA
  })
  
  return result
})

// 显示的归档列表（根据showAllArchives控制数量）
const displayedArchives = computed(() => {
  if (showAllArchives.value) {
    return groupedArchives.value
  }
  return groupedArchives.value.slice(0, 5)
})

let intervalId

onMounted(async () => {
  await refreshData()
  await fetchWatcherStatus()
  await fetchProcessedArchives()
  intervalId = setInterval(refreshData, 3000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})

let previousCompletedCount = 0
let lastRefreshTime = 0

async function refreshData() {
  await taskStore.fetchTasks()
  recentTasks.value = taskStore.tasks.slice(0, 5)
  
  // 获取当前完成的任务数
  const currentCompletedCount = recentTasks.value.filter(task => 
    task.status === 'completed' || task.status === 'COMPLETED'
  ).length
  
  // 如果完成的任务数增加了，或者距离上次刷新已处理压缩包已超过30秒，则刷新
  const now = Date.now()
  const shouldRefreshArchives = 
    currentCompletedCount > previousCompletedCount || 
    (now - lastRefreshTime > 30000 && recentTasks.value.length > 0)
  
  if (shouldRefreshArchives) {
    console.log('检测到任务状态变化，刷新已处理压缩包列表')
    await fetchProcessedArchives()
    lastRefreshTime = now
  }
  
  previousCompletedCount = currentCompletedCount
  
  // 获取问题作品数量
  let conflictCount = 0
  try {
    const response = await axios.get('/api/conflicts')
    conflictCount = response.data.conflicts?.length || 0
  } catch (error) {
    console.error('获取问题作品数量失败:', error)
  }
  
  stats.value = {
    pending: taskStore.pendingTasks.length,
    processing: taskStore.processingTasks.length,
    completed: taskStore.completedTasks.length,
    conflicts: conflictCount
  }
}

function getTaskTypeLabel(type) {
  const labels = {
    'auto_process': '自动处理',
    'extract': '解压',
    'filter': '过滤',
    'metadata': '元数据',
    'rename': '重命名'
  }
  return labels[type] || type
}

function getStatusLabel(status) {
  const labels = {
    'pending': '等待中',
    'processing': '处理中',
    'paused': '已暂停',
    'waiting_manual': '等待手动处理',
    'completed': '已完成',
    'failed': '失败'
  }
  return labels[status] || status
}

function getStatusType(status) {
  const types = {
    'pending': 'info',
    'processing': 'warning',
    'paused': '',
    'waiting_manual': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return types[status] || ''
}

function getProgressStatus(status) {
  if (status === 'failed') return 'exception'
  if (status === 'completed') return 'success'
  return ''
}

async function pauseTask(taskId) {
  await taskStore.pauseTask(taskId)
}

async function resumeTask(taskId) {
  await taskStore.resumeTask(taskId)
}

async function cancelTask(taskId) {
  await taskStore.cancelTask(taskId)
}

function handleUploadSuccess() {
  refreshData()
}

async function handleManualScan() {
  scanning.value = true
  try {
    ElMessage.info('正在扫描文件夹...')
    
    // 调用后端API扫描文件夹
    const response = await axios.post('/api/scan')
    
    ElMessage.success(response.data.message)
    await refreshData()
  } catch (error) {
    console.error('扫描失败:', error)
    ElMessage.error('扫描失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    scanning.value = false
  }
}

async function handleWatcherToggle() {
  try {
    if (watcherRunning.value) {
      // 停止监视器
      await axios.post('/api/watcher/stop')
      ElMessage.success('监视器已停止')
      watcherRunning.value = false
    } else {
      // 启动监视器
      await axios.post('/api/watcher/start')
      ElMessage.success('监视器已启动')
      watcherRunning.value = true
    }
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function fetchWatcherStatus() {
  try {
    const response = await axios.get('/api/watcher/status')
    watcherRunning.value = response.data.is_running
  } catch (error) {
    console.error('获取监视器状态失败:', error)
  }
}

// 获取已处理压缩包列表
async function fetchProcessedArchives() {
  archivesLoading.value = true
  try {
    // 先触发目录扫描
    await axios.post('/api/processed-archives/scan')
    // 然后获取最新列表，带上排序和搜索参数
    // 添加时间戳防止缓存
    const params = {
      sort_by: archiveSortBy.value,
      sort_order: archiveSortOrder.value,
      _t: Date.now()  // 添加时间戳防止浏览器缓存
    }
    if (archiveSearchQuery.value) {
      params.search = archiveSearchQuery.value
    }
    const response = await axios.get('/api/processed-archives', { 
      params,
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      }
    })
    archives.value = response.data.archives || []
    console.log('获取到已处理压缩包:', archives.value.length, '条记录')
    // 打印第一条记录的时间，用于调试
    if (archives.value.length > 0) {
      console.log('第一条记录:', archives.value[0].filename, '时间:', archives.value[0].processed_at)
    }
    ElMessage.success('刷新成功')
  } catch (error) {
    console.error('获取已处理压缩包列表失败:', error)
    ElMessage.error('获取已处理压缩包列表失败')
  } finally {
    archivesLoading.value = false
  }
}

// 处理搜索输入（防抖）
function handleArchiveSearch() {
  if (archiveSearchTimeout) {
    clearTimeout(archiveSearchTimeout)
  }
  archiveSearchTimeout = setTimeout(() => {
    fetchProcessedArchives()
  }, 500)
}

// 处理排序字段变化
function handleArchiveSortChange() {
  fetchProcessedArchives()
}

// 切换排序方向
function toggleArchiveSortOrder() {
  archiveSortOrder.value = archiveSortOrder.value === 'desc' ? 'asc' : 'desc'
  fetchProcessedArchives()
}

// 重新处理压缩包
async function reprocessArchive(archiveId) {
  reprocessingId.value = archiveId
  try {
    const response = await axios.post(`/api/processed-archives/${archiveId}/reprocess`)
    ElMessage.success(response.data.message)
    // 刷新任务列表
    await refreshData()
    // 刷新归档列表
    await fetchProcessedArchives()
  } catch (error) {
    console.error('重新处理失败:', error)
    ElMessage.error('重新处理失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    reprocessingId.value = null
  }
}

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes === 0 || !bytes) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化日期
function formatDate(dateString) {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  margin-bottom: 24px;
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-right: 16px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #64748b;
  margin-top: 4px;
}

.upload-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-id {
  font-family: monospace;
  color: #64748b;
}

.progress-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-text {
  font-size: 12px;
  color: #64748b;
}

.action-card {
  margin-bottom: 24px;
}

.action-buttons {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.action-buttons .el-button {
  min-width: 160px;
}

.action-buttons .el-icon {
  margin-right: 8px;
}

.archives-card {
  margin-top: 24px;
}

.archives-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.archives-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.archives-card .el-button-group {
  margin-left: 8px;
}

.text-gray {
  color: #94a3b8;
}

.stat-card.clickable {
  cursor: pointer;
  transition: all 0.3s ease;
}

.stat-card.clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-card.clickable:active {
  transform: translateY(0);
}

.volume-tag {
  margin-left: 8px;
}

.volume-list {
  padding: 12px 24px;
  background-color: #f8f9fa;
  border-radius: 4px;
  margin: 8px 0;
}

.volume-list-title {
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
  font-size: 13px;
}

.time-text {
  font-size: 12px;
  color: #909399;
  font-family: 'Consolas', 'Monaco', monospace;
}

.volume-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 12px;
  margin: 4px 0;
  background-color: white;
  border-radius: 4px;
  font-size: 13px;
}

.volume-name {
  color: #303133;
  font-family: 'Consolas', 'Monaco', monospace;
}

.volume-size {
  color: #909399;
  font-size: 12px;
}

:deep(.el-table__expand-icon) {
  color: #409eff;
}
</style>
