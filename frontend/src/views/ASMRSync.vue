<template>
  <div class="asmr-sync-page">
    <el-card class="page-header">
      <template #header>
        <div class="header-content">
          <span class="title">ASMR 同步下载</span>
          <el-tag type="info">根据字幕文件自动下载并匹配</el-tag>
        </div>
      </template>

      <div class="scan-section">
        <el-form :inline="true">
          <el-form-item label="字幕文件夹">
            <el-input
              v-model="subtitleFolder"
              placeholder="选择包含字幕文件的文件夹"
              style="width: 400px"
              clearable
            >
              <template #append>
                <el-button @click="selectFolder">选择</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="scanFolder" :loading="scanning">
              <el-icon><Search /></el-icon>
              扫描
            </el-button>
            <el-button
              type="success"
              @click="startSync"
              :loading="syncing"
              :disabled="selectedItems.length === 0"
            >
              <el-icon><Download /></el-icon>
              开始同步下载
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>

    <!-- 扫描结果 -->
    <el-card v-if="scanResults.length > 0" class="results-card">
      <template #header>
        <div class="results-header">
          <span>扫描结果 ({{ scanResults.length }} 个作品)</span>
          <el-checkbox v-model="selectAll" @change="handleSelectAll">全选</el-checkbox>
        </div>
      </template>

      <el-table :data="scanResults" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="rjcode" label="RJ号" width="120" />
        <el-table-column prop="folder_name" label="文件夹名称" min-width="250">
          <template #default="{ row }">
            <div class="folder-name">
              <el-icon><Folder /></el-icon>
              <span>{{ row.folder_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="subtitle_count" label="字幕数" width="80" align="center" />
        <el-table-column label="预览" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="previewDownload(row)" :loading="row.previewing">预览</el-button>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'pending'" type="info">待下载</el-tag>
            <el-tag v-else-if="row.status === 'downloading'" type="warning">下载中</el-tag>
            <el-tag v-else-if="row.status === 'completed'" type="success">已完成</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger">失败</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewDialogVisible" title="下载预览" width="900px">
      <div v-if="previewLoading" class="preview-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在获取作品信息...</span>
      </div>
      <div v-else-if="previewData" class="preview-content">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="请求RJ号">{{ previewData.rjcode }}</el-descriptions-item>
          <el-descriptions-item label="实际下载">
            <el-tag :type="previewData.actual_rjcode !== previewData.rjcode ? 'warning' : 'success'">
              {{ previewData.actual_rjcode || '未找到' }}
            </el-tag>
            <span v-if="previewData.lang" style="margin-left: 8px;">({{ previewData.lang }})</span>
          </el-descriptions-item>
          <el-descriptions-item label="标题">{{ previewData.title }}</el-descriptions-item>
          <el-descriptions-item label="总文件数">{{ previewData.total_files }}</el-descriptions-item>
          <el-descriptions-item label="筛选后">
            <el-tag type="success">{{ previewData.filtered_files }} 个</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="预计大小">
            <span style="font-weight: bold; color: #409EFF;">{{ formatSize(previewData.total_size) }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 可用版本列表 -->
        <div v-if="previewData.available_versions && previewData.available_versions.length > 0" class="version-list">
          <h4>可用版本</h4>
          <el-table :data="previewData.available_versions" size="small">
            <el-table-column prop="rjcode" label="RJ号" width="120" />
            <el-table-column prop="lang" label="语言" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.priority <= 1 ? 'success' : row.priority <= 2 ? 'warning' : 'info'">
                  {{ getLangName(row.lang) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="file_count" label="文件数" width="80" />
            <el-table-column label="可用" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.available ? 'success' : 'danger'">{{ row.available ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>

        <!-- 文件列表 -->
        <div class="file-list">
          <h4>下载文件列表 ({{ previewData.filtered_files }} 个)</h4>
          <el-table :data="previewData.files" max-height="400" size="small">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column label="文件路径" min-width="300">
              <template #default="{ row }">
                <div class="file-path">
                  <el-icon><Document /></el-icon>
                  <span :title="row.path || row.title">{{ row.title }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.type || '文件' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <div v-else class="preview-error">
        <el-empty description="无法获取预览信息" />
      </div>
    </el-dialog>

    <!-- 任务详情 -->
    <el-card v-if="tasks.length > 0" class="tasks-card">
      <template #header>
        <div class="results-header">
          <span>下载任务</span>
          <div class="header-actions">
            <el-button size="small" @click="refreshStatus" :loading="refreshing">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 等待重试的任务 -->
      <div v-if="waitingRetryTasks.length > 0" class="waiting-section">
        <div class="section-title">
          <el-icon><Clock /></el-icon>
          <span>等待重试 ({{ waitingRetryTasks.length }} 个)</span>
          <span v-if="nextRetryTime" class="next-retry-time">
            下次自动重试: {{ formatNextRetryTime(nextRetryTime) }}
          </span>
        </div>
        <div class="waiting-list">
          <el-card v-for="task in waitingRetryTasks" :key="task.id" class="waiting-item">
            <div class="waiting-header">
              <span class="task-rjcode">{{ task.rjcode }}</span>
              <span class="task-title">{{ task.work_title || task.task_metadata?.work_title }}</span>
            </div>
            <div class="waiting-info">
              <span class="retry-reason">{{ task.task_metadata?.retry_reason || task.current_step || '未找到版本' }}</span>
              <span class="retry-count">已重试 {{ task.task_metadata?.retry_count || 0 }} 次</span>
            </div>
            <div class="waiting-actions">
              <el-button type="primary" size="small" @click="retryWaitingTask(task.id)">立即重试</el-button>
              <el-button size="small" @click="cancelWaitingTask(task.id)">取消</el-button>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 正在处理/已完成/失败的任务 -->
      <div v-if="activeTasks.length > 0" class="task-list">
        <el-card v-for="task in activeTasks" :key="task.id" class="task-item" :class="task.status">
          <div class="task-header">
            <div class="task-info">
              <span class="task-rjcode">{{ task.actual_rjcode || task.rjcode }}</span>
              <span v-if="task.actual_rjcode && task.actual_rjcode !== task.rjcode" class="task-original-rj">
                (原: {{ task.rjcode }})
              </span>
              <span class="task-title">{{ task.work_title }}</span>
            </div>
            <div class="task-actions">
              <el-tag :type="task.status === 'completed' ? 'success' : task.status === 'failed' ? 'danger' : task.status === 'paused' ? 'info' : task.status === 'waiting_retry' ? 'warning' : 'warning'" size="small">
                {{ getStatusText(task.status) }}
              </el-tag>
              <!-- 暂停/继续按钮 -->
              <el-button-group v-if="task.status === 'processing'" size="small">
                <el-button @click="pauseTask(task.id)" :loading="task.pausing">暂停</el-button>
              </el-button-group>
              <el-button-group v-if="task.status === 'paused'" size="small">
                <el-button type="primary" @click="resumeTask(task.id)" :loading="task.resuming">继续</el-button>
              </el-button-group>
              <!-- 等待重试任务的手动重试按钮 -->
              <el-button v-if="task.status === 'waiting_retry'" size="small" type="primary" @click="retryWaitingTask(task.id)" :loading="task.retrying">
                立即重试
              </el-button>
              <!-- 重试失败文件按钮 -->
              <el-button v-if="task.failed_files && task.failed_files.length > 0" size="small" type="warning" @click="retryFailed(task.id)" :loading="task.retrying">
                重试失败文件 ({{ task.failed_files.length }})
              </el-button>
            </div>
          </div>
          <el-progress
            :percentage="task.progress"
            :status="task.status === 'completed' ? 'success' : task.status === 'failed' ? 'exception' : ''"
            :stroke-width="10"
            style="margin: 12px 0;"
          />
          <div class="task-step">
            <el-icon v-if="task.status === 'processing'"><Loading /></el-icon>
            <span>{{ task.current_step }}</span>
          </div>
          <div v-if="task.error_message" class="task-error">
            <el-icon><WarningFilled /></el-icon>
            {{ task.error_message }}
          </div>

          <!-- 字幕同步结果 -->
          <div v-if="task.sync_result && task.sync_result.renamed_files && task.sync_result.renamed_files.length > 0" class="sync-result">
            <el-collapse>
              <el-collapse-item>
                <template #title>
                  <span class="sync-list-title">
                    <el-icon><Document /></el-icon>
                    字幕同步映射 ({{ task.sync_result.renamed_files.length }} 对)
                  </span>
                </template>
                <div class="sync-items">
                  <div v-for="(item, idx) in task.sync_result.renamed_files" :key="idx" class="sync-item">
                    <div class="sync-row">
                      <span class="sync-label">原始音频:</span>
                      <span class="sync-original">{{ item.original }}</span>
                    </div>
                    <div class="sync-arrow-down">↓</div>
                    <div class="sync-row">
                      <span class="sync-label">重命名为:</span>
                      <span class="sync-new">{{ item.new }}</span>
                    </div>
                    <div class="sync-row">
                      <span class="sync-label">匹配字幕:</span>
                      <span class="sync-subtitle">{{ item.subtitle }}</span>
                    </div>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 失败文件列表 -->
          <div v-if="task.failed_files && task.failed_files.length > 0" class="failed-files">
            <el-collapse>
              <el-collapse-item>
                <template #title>
                  <span class="failed-list-title">
                    <el-icon><WarningFilled /></el-icon>
                    失败文件 ({{ task.failed_files.length }} 个)
                  </span>
                </template>
                <div class="failed-items">
                  <div v-for="(file, idx) in task.failed_files" :key="idx" class="failed-item">
                    <span class="failed-name">{{ file.title || file.path }}</span>
                    <span class="failed-reason">{{ file.reason }}</span>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 文件下载列表 -->
          <div v-if="task.download_files && task.download_files.length > 0" class="file-download-list">
            <el-collapse>
              <el-collapse-item>
                <template #title>
                  <span class="file-list-title">
                    <el-icon><Folder /></el-icon>
                    文件下载进度 ({{ task.download_files.length }} 个文件)
                  </span>
                </template>
                <div class="file-items">
                  <div v-for="file in task.download_files" :key="file.name" class="file-item">
                    <div class="file-name">{{ file.name }}</div>
                    <el-progress
                      :percentage="file.progress"
                      :stroke-width="6"
                      :show-text="false"
                      style="width: 100px; margin: 0 8px;"
                    />
                    <span class="file-size">{{ formatSize(file.downloaded) }} / {{ formatSize(file.total) }}</span>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Download, Folder, Loading, Refresh, Document, WarningFilled, Clock } from '@element-plus/icons-vue'
import { asmrSyncApi, configApi } from '../api'

const subtitleFolder = ref('')
const scanning = ref(false)
const syncing = ref(false)
const refreshing = ref(false)
const scanResults = ref([])
const selectedItems = ref([])
const selectAll = ref(false)
const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewData = ref(null)
const tasks = ref([])
const nextRetryTime = ref('')
let statusInterval = null

// 计算属性：分离等待重试的任务和活动任务
const waitingRetryTasks = computed(() => {
  return tasks.value.filter(t => t.status === 'waiting_retry')
})

const activeTasks = computed(() => {
  return tasks.value.filter(t => t.status !== 'waiting_retry')
})

// 格式化下次重试时间
const formatNextRetryTime = (isoString) => {
  if (!isoString) return '未知'
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = date - now
  if (diffMs <= 0) return '即将重试'

  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    return `${diffDays}天${diffHours % 24}小时后`
  } else if (diffHours > 0) {
    return `${diffHours}小时${diffMins % 60}分钟后`
  } else {
    return `${diffMins}分钟后`
  }
}

const getLangName = (lang) => {
  const map = { 'CHI_HANS': '简中', 'CHI_SIMP': '简中', 'CHI_HANT': '繁中', 'CHI_TRAD': '繁中', 'JPN': '日文', 'JAP': '日文', 'ENG': '英文' }
  return map[lang] || lang
}

const getStatusText = (status) => {
  const map = { 'pending': '等待中', 'processing': '处理中', 'completed': '已完成', 'failed': '失败', 'paused': '已暂停', 'waiting_retry': '等待重试' }
  return map[status] || status
}

const pauseTask = async (taskId) => {
  try {
    await asmrSyncApi.pause(taskId)
    ElMessage.success('任务已暂停')
    await refreshStatus()
  } catch (error) {
    ElMessage.error('暂停失败')
  }
}

const resumeTask = async (taskId) => {
  try {
    await asmrSyncApi.resume(taskId)
    ElMessage.success('任务已恢复')
    await refreshStatus()
  } catch (error) {
    ElMessage.error('恢复失败')
  }
}

const retryFailed = async (taskId) => {
  try {
    const result = await asmrSyncApi.retry(taskId)
    ElMessage.success(result.message)
    await refreshStatus()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

const retryWaitingTask = async (taskId) => {
  try {
    const result = await asmrSyncApi.retryWaiting(taskId)
    ElMessage.success(result.message)
    await refreshStatus()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

const cancelWaitingTask = async (taskId) => {
  try {
    // 从数据库和内存中删除等待重试的任务
    await asmrSyncApi.deleteWaitingRetry(taskId)
    ElMessage.success('任务已取消')
    // 从本地列表中移除
    const index = tasks.value.findIndex(t => t.id === taskId)
    if (index > -1) {
      tasks.value.splice(index, 1)
    }
  } catch (error) {
    ElMessage.error('取消失败')
  }
}

const loadSavedFolder = async () => {
  try {
    const config = await configApi.get()
    if (config.storage?.asmr_subtitle_path) {
      subtitleFolder.value = config.storage.asmr_subtitle_path
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  }
}

// 加载等待重试任务
const loadWaitingRetryTasks = async () => {
  try {
    const result = await asmrSyncApi.getWaitingRetry()
    nextRetryTime.value = result.next_retry_time || ''

    // 将等待重试任务添加到任务列表
    if (result.tasks && result.tasks.length > 0) {
      const waitingTasks = result.tasks.map(t => ({
        id: t.id,
        rjcode: t.rjcode,
        work_title: t.work_title,
        status: 'waiting_retry',
        progress: 0,
        current_step: `等待重试: ${t.retry_reason || '未找到版本'}`,
        task_metadata: {
          retry_reason: t.retry_reason,
          retry_count: t.retry_count,
          retry_after: t.retry_after,
          subtitle_folder: t.subtitle_folder
        }
      }))

      // 合并到任务列表（避免重复）
      const existingIds = new Set(tasks.value.map(t => t.id))
      for (const task of waitingTasks) {
        if (!existingIds.has(task.id)) {
          tasks.value.push(task)
        }
      }
    }
  } catch (error) {
    console.error('加载等待重试任务失败:', error)
  }
}

const selectFolder = () => ElMessage.info('请手动输入文件夹路径')

const scanFolder = async () => {
  if (!subtitleFolder.value) return ElMessage.warning('请先选择字幕文件夹')
  scanning.value = true
  scanResults.value = []
  try {
    const result = await asmrSyncApi.scan(subtitleFolder.value)
    if (result.success) {
      scanResults.value = result.items.map(item => ({ ...item, status: 'pending', previewing: false }))
      ElMessage.success(`发现 ${result.total_found} 个作品`)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '扫描失败')
  } finally {
    scanning.value = false
  }
}

const previewDownload = async (row) => {
  previewLoading.value = true
  previewDialogVisible.value = true
  previewData.value = null
  row.previewing = true
  try {
    const result = await asmrSyncApi.preview(row.rjcode)
    previewData.value = result
    if (!result.success) ElMessage.warning(result.error || '未找到可用版本')
  } catch (error) {
    ElMessage.error('获取预览信息失败')
  } finally {
    previewLoading.value = false
    row.previewing = false
  }
}

const startSync = async () => {
  if (selectedItems.value.length === 0) return ElMessage.warning('请先选择要下载的作品')
  syncing.value = true
  try {
    const items = selectedItems.value.map(item => ({ rjcode: item.rjcode, subtitle_folder: item.folder_path, work_title: item.folder_name }))
    const result = await asmrSyncApi.start(items)
    if (result.success) {
      ElMessage.success(result.message)
      await refreshStatus()
      result.tasks.forEach(task => {
        const item = scanResults.value.find(i => i.rjcode === task.rjcode)
        if (item) { item.status = 'downloading'; item.taskId = task.task_id }
      })
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '启动下载失败')
  } finally {
    syncing.value = false
  }
}

const handleSelectAll = (val) => {
  selectedItems.value = val ? scanResults.value.filter(item => item.status === 'pending') : []
}

const handleSelectionChange = (selection) => {
  selectedItems.value = selection
  selectAll.value = selection.length === scanResults.value.filter(i => i.status === 'pending').length
}

const refreshStatus = async () => {
  refreshing.value = true
  try {
    const result = await asmrSyncApi.status()
    tasks.value = result.tasks
    result.tasks.forEach(task => {
      const item = scanResults.value.find(i => i.rjcode === task.rjcode)
      if (item) item.status = task.status === 'processing' ? 'downloading' : task.status
    })
  } catch (error) {
    console.error('获取状态失败:', error)
  } finally {
    refreshing.value = false
  }
}

const formatSize = (bytes) => {
  if (!bytes) return '未知'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0, size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return `${size.toFixed(2)} ${units[i]}`
}

onMounted(async () => {
  await loadSavedFolder()
  await loadWaitingRetryTasks()
  refreshStatus()
  statusInterval = setInterval(refreshStatus, 3000)
  // 自动扫描字幕文件夹
  if (subtitleFolder.value) {
    scanFolder()
  }
})

onUnmounted(() => {
  if (statusInterval) clearInterval(statusInterval)
})
</script>

<style scoped>
.asm-sync-page { padding: 20px; }
.page-header { margin-bottom: 20px; }
.header-content { display: flex; align-items: center; gap: 12px; }
.header-content .title { font-size: 18px; font-weight: 600; }
.scan-section { margin-top: 16px; }
.results-card { margin-bottom: 20px; }
.results-header { display: flex; justify-content: space-between; align-items: center; }
.folder-name { display: flex; align-items: center; gap: 8px; }
.preview-loading { display: flex; flex-direction: column; align-items: center; padding: 40px; gap: 12px; }
.preview-content { padding: 16px 0; }
.version-list, .file-list { margin-top: 20px; }
.version-list h4, .file-list h4 { margin-bottom: 12px; color: #606266; font-size: 14px; }
.file-path { display: flex; align-items: center; gap: 6px; }
.file-path span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-error { padding: 40px; }
.tasks-card { margin-top: 20px; }
.task-list { display: flex; flex-direction: column; gap: 12px; }
.task-item { border-left: 4px solid #409EFF; }
.task-item.completed { border-left-color: #67C23A; }
.task-item.failed { border-left-color: #F56C6C; }
.task-item.paused { border-left-color: #909399; }
.task-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.task-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.task-rjcode { font-weight: bold; color: #409EFF; }
.task-original-rj { color: #909399; font-size: 12px; }
.task-title { color: #606266; font-size: 13px; }
.task-actions { display: flex; align-items: center; gap: 8px; }
.task-step { display: flex; align-items: center; gap: 6px; color: #909399; font-size: 12px; }
.task-error { display: flex; align-items: center; gap: 6px; color: #F56C6C; font-size: 12px; margin-top: 8px; padding: 8px; background: #fef0f0; border-radius: 4px; }
.file-download-list { margin-top: 12px; }
.file-list-title { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.file-items { display: flex; flex-direction: column; gap: 8px; }
.file-item { display: flex; align-items: center; padding: 8px; background: #f5f7fa; border-radius: 4px; }
.file-name { flex: 1; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { font-size: 11px; color: #909399; min-width: 120px; text-align: right; }
.failed-files { margin-top: 12px; }
.failed-list-title { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #F56C6C; }
.failed-items { display: flex; flex-direction: column; gap: 4px; }
.failed-item { display: flex; justify-content: space-between; padding: 6px 8px; background: #fef0f0; border-radius: 4px; font-size: 12px; }
.failed-name { color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.failed-reason { color: #F56C6C; margin-left: 8px; }
.sync-result { margin-top: 12px; }
.sync-list-title { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #67C23A; }
.sync-items { display: flex; flex-direction: column; gap: 8px; }
.sync-item { display: flex; flex-direction: column; padding: 10px; background: #f0f9eb; border-radius: 4px; gap: 4px; }
.sync-row { display: flex; align-items: center; gap: 8px; }
.sync-label { color: #909399; font-size: 11px; white-space: nowrap; min-width: 70px; }
.sync-original { font-size: 12px; color: #E6A23C; font-weight: 500; }
.sync-new { font-size: 12px; color: #409EFF; font-weight: 500; }
.sync-subtitle { font-size: 12px; color: #67C23A; font-weight: 500; }
.sync-arrow-down { color: #67C23A; font-weight: bold; font-size: 14px; text-align: center; }
.waiting-section { margin-bottom: 16px; padding: 12px; background: #fdf6ec; border-radius: 8px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #E6A23C; margin-bottom: 12px; }
.next-retry-time { margin-left: auto; font-size: 12px; font-weight: normal; color: #909399; }
.waiting-list { display: flex; flex-direction: column; gap: 8px; }
.waiting-item { padding: 12px; }
.waiting-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.waiting-info { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 12px; }
.retry-reason { color: #E6A23C; }
.retry-count { color: #909399; }
.retry-after { color: #409EFF; margin-left: 8px; }
.waiting-actions { display: flex; gap: 8px; }
.header-actions { display: flex; gap: 8px; }
</style>