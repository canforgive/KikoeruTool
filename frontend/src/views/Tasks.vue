<template>
  <div class="tasks">
    <div class="page-header">
      <h1 class="page-title">任务队列</h1>
      <el-radio-group v-model="currentStatus" @change="handleStatusChange">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="pending">待处理</el-radio-button>
        <el-radio-button label="processing">处理中</el-radio-button>
        <el-radio-button label="completed">已完成</el-radio-button>
      </el-radio-group>
    </div>
    
    <el-card v-loading="initialLoading" element-loading-text="加载中...">
      <el-table 
        :data="taskStore.tasks"
        style="width: 100%"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="task-detail">
              <p><strong>完整ID:</strong> {{ row.id }}</p>
              <p><strong>源路径:</strong> {{ row.source_path }}</p>
              <p v-if="row.output_path"><strong>输出路径:</strong> {{ row.output_path }}</p>
              <p v-if="row.error_message"><strong>错误信息:</strong> <span class="error-text">{{ row.error_message }}</span></p>
              <div v-if="row.metadata" class="metadata-section">
                <h4>元数据</h4>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="RJ号">{{ row.metadata.rjcode }}</el-descriptions-item>
                  <el-descriptions-item label="作品名">{{ row.metadata.work_name }}</el-descriptions-item>
                  <el-descriptions-item label="社团">{{ row.metadata.maker_name }}</el-descriptions-item>
                  <el-descriptions-item label="发售日期">{{ row.metadata.release_date }}</el-descriptions-item>
                  <el-descriptions-item label="声优">{{ row.metadata.cvs?.join(', ') }}</el-descriptions-item>
                  <el-descriptions-item label="标签">{{ row.metadata.tags?.join(', ') }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="id" label="ID" width="100">
          <template #default="{ row }">
            <span class="task-id">{{ row.id.slice(0, 8) }}...</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="source_path" label="源文件" show-overflow-tooltip min-width="250">
          <template #default="{ row }">
            {{ getFileName(row.source_path) }}
          </template>
        </el-table-column>
        
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">
              {{ getTaskTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="progress" label="进度" width="250">
          <template #default="{ row }">
            <div class="progress-wrapper">
              <el-progress 
                :percentage="row.progress" 
                :status="getProgressStatus(row.status)"
                :stroke-width="12"
              />
              <span class="step-text">{{ row.current_step }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button-group v-if="row.status === 'processing'">
              <el-button size="small" @click="taskStore.pauseTask(row.id)">
                <el-icon><VideoPause /></el-icon>
              </el-button>
              <el-button size="small" type="danger" @click="taskStore.cancelTask(row.id)">
                <el-icon><CircleClose /></el-icon>
              </el-button>
            </el-button-group>
            
            <el-button 
              v-else-if="row.status === 'paused'" 
              size="small" 
              type="primary"
              @click="taskStore.resumeTask(row.id)"
            >
              <el-icon><VideoPlay /></el-icon> 恢复
            </el-button>
            
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              type="warning"
              @click="retryTask(row)"
            >
              <el-icon><Refresh /></el-icon> 重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty v-if="taskStore.tasks.length === 0" description="暂无任务" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { VideoPause, VideoPlay, CircleClose, Refresh } from '@element-plus/icons-vue'
import { useTaskStore } from '../stores'

const taskStore = useTaskStore()
const currentStatus = ref('')
const initialLoading = ref(true)

let intervalId

onMounted(async () => {
  try {
    await taskStore.fetchTasks()
  } finally {
    initialLoading.value = false
  }
  // 轮询时不显示全局 loading
  intervalId = setInterval(async () => {
    try {
      await taskStore.fetchTasks(currentStatus.value, false) // false = 不显示 loading
    } catch (e) {
      console.error('轮询任务失败:', e)
    }
  }, 3000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})

async function handleStatusChange() {
  initialLoading.value = true
  try {
    await taskStore.fetchTasks(currentStatus.value)
  } finally {
    initialLoading.value = false
  }
}

function getFileName(path) {
  if (!path) return ''
  return path.split(/[\\/]/).pop()
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
    'failed': '失败',
    'cancelled': '已取消'
  }
  return labels[status] || status
}

function getStatusType(status) {
  const types = {
    'pending': 'info',
    'processing': 'warning',
    'paused': 'info',
    'waiting_manual': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'cancelled': 'danger'
  }
  return types[status] || ''
}

function getProgressStatus(status) {
  if (status === 'failed') return 'exception'
  if (status === 'completed') return 'success'
  return ''
}

async function retryTask(task) {
  await taskStore.createTask(task.source_path, task.type, true)
}
</script>

<style scoped>
.tasks {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.task-id {
  font-family: monospace;
  font-size: 12px;
  color: #64748b;
}

.progress-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-text {
  font-size: 12px;
  color: #64748b;
}

.task-detail {
  padding: 20px;
  background-color: #f8fafc;
  border-radius: 8px;
}

.task-detail p {
  margin: 8px 0;
  font-size: 14px;
}

.error-text {
  color: #ef4444;
}

.metadata-section {
  margin-top: 16px;
}

.metadata-section h4 {
  margin: 0 0 12px;
  font-size: 16px;
  color: #334155;
}
</style>
