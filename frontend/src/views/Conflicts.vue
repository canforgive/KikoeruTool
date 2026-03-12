<template>
  <div class="conflicts">
    <div class="page-header">
      <div>
        <h1 class="page-title">问题作品</h1>
        <p class="page-desc">检测到重复或冲突的作品，请手动选择处理方式</p>
      </div>
      <div class="batch-actions" v-if="selectedConflicts.length > 0">
        <span class="selected-count">已选择 {{ selectedConflicts.length }} 项</span>
        <el-button-group>
          <el-button size="small" type="primary" @click="handleBatchAction('KEEP_NEW')">
            批量保留新版
          </el-button>
          <el-button size="small" @click="handleBatchAction('KEEP_OLD')">
            批量保留旧版
          </el-button>
          <el-button size="small" type="info" @click="handleBatchAction('SKIP')">
            批量跳过
          </el-button>
        </el-button-group>
      </div>
    </div>
    
    <el-card v-loading="loading" :element-loading-text="loadingText">
      <el-table 
        ref="conflictsTable"
        :data="conflicts" 
        style="width: 100%"
        :header-cell-style="{ 'white-space': 'nowrap' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <div class="conflict-detail">
              <el-row :gutter="20">
                <el-col :xs="24" :sm="24" :md="12">
                  <h4>库存中已存在</h4>
                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="路径">
                      <div class="path-text">{{ row.existing_path }}</div>
                    </el-descriptions-item>
                  </el-descriptions>
                </el-col>
                <el-col :xs="24" :sm="24" :md="12">
                  <h4>新检测到</h4>
                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="路径">
                      <div class="path-text">{{ row.new_path }}</div>
                    </el-descriptions-item>
                    <template v-if="row.new_metadata">
                      <el-descriptions-item label="作品名">{{ row.new_metadata.work_name }}</el-descriptions-item>
                      <el-descriptions-item label="社团">{{ row.new_metadata.maker_name }}</el-descriptions-item>
                      <el-descriptions-item label="声优">{{ row.new_metadata.cvs?.join(', ') }}</el-descriptions-item>
                    </template>
                  </el-descriptions>
                </el-col>
              </el-row>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="RJ号" width="130">
          <template #default="{ row }">
            <div class="rjcode-cell">
              <span class="rjcode-text">{{ row.rjcode }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="conflict_type" label="冲突类型" width="110">
          <template #default="{ row }">
            <el-tag :type="getConflictTypeType(row.conflict_type)" size="small" class="conflict-type-tag">
              {{ getConflictTypeLabel(row.conflict_type) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="existing_path" label="已存在路径" min-width="200">
          <template #default="{ row }">
            <div class="path-cell" :title="row.existing_path">{{ row.existing_path }}</div>
          </template>
        </el-table-column>
        
        <el-table-column prop="new_path" label="新文件路径" min-width="200">
          <template #default="{ row }">
            <div class="path-cell" :title="row.new_path">{{ row.new_path }}</div>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="检测时间" min-width="150">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" min-width="280" fixed="right">
          <template #default="{ row }">
            <el-button-group class="action-buttons">
              <el-button size="small" type="primary" @click="handleAction(row, 'KEEP_NEW')" :loading="processingIds.has(row.id)">
                保留新版
              </el-button>
              <el-button size="small" @click="handleAction(row, 'KEEP_OLD')" :loading="processingIds.has(row.id)">
                保留旧版
              </el-button>
              <el-button size="small" type="warning" @click="handleAction(row, 'MERGE')" :loading="processingIds.has(row.id)">
                合并
              </el-button>
              <el-button size="small" type="info" @click="handleAction(row, 'SKIP')" :loading="processingIds.has(row.id)">
                跳过
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty v-if="conflicts.length === 0" description="没有问题作品" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { conflictApi } from '../api'

const conflicts = ref([])
const loading = ref(false)
const loadingText = ref('加载中...')
const selectedConflicts = ref([])
const conflictsTable = ref(null)
const processingIds = ref(new Set())
let intervalId = null

onMounted(async () => {
  await fetchConflicts()
  intervalId = setInterval(fetchConflicts, 5000)
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
  }
})

async function fetchConflicts() {
  try {
    const data = await conflictApi.list()
    conflicts.value = data.conflicts || []
  } catch (error) {
    console.error('获取问题作品失败:', error)
  }
}

function getConflictTypeLabel(type) {
  const labels = {
    'DUPLICATE': '完全重复',
    'LANGUAGE_VARIANT': '多语言版本',
    'MULTIPLE_VERSIONS': '多版本'
  }
  return labels[type] || type
}

function getConflictTypeType(type) {
  const types = {
    'DUPLICATE': 'danger',
    'LANGUAGE_VARIANT': 'warning',
    'MULTIPLE_VERSIONS': 'info'
  }
  return types[type] || ''
}

function formatDate(date) {
  if (!date) return ''
  // 尝试处理不同格式的日期字符串
  let dateObj
  if (typeof date === 'string') {
    if (date.includes('T')) {
      // 如果是ISO 8601格式 (如 '2026-03-01T14:05:00' )，这是UTC时间，需转为本地时间
      dateObj = new Date(date + 'Z') // 添加'Z'标识UTC
    } else {
      dateObj = new Date(date)
    }
  } else {
    dateObj = new Date(date)
  }
  // 格式化为中文本地格式
  return dateObj.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

async function handleAction(conflict, action) {
  const actionLabels = {
    'KEEP_NEW': '保留新版',
    'KEEP_OLD': '保留旧版',
    'MERGE': '合并',
    'SKIP': '跳过'
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要${actionLabels[action]}吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    processingIds.value.add(conflict.id)
    loadingText.value = '处理中...'
    loading.value = true
    
    await conflictApi.resolve(conflict.id, action)
    
    ElMessage.success('操作成功')
    conflicts.value = conflicts.value.filter(c => c.id !== conflict.id)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作失败:', error)
      ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    processingIds.value.delete(conflict.id)
    loading.value = false
    loadingText.value = '加载中...'
  }
}

function handleSelectionChange(selection) {
  selectedConflicts.value = selection
}

async function handleBatchAction(action) {
  const actionLabels = {
    'KEEP_NEW': '保留新版',
    'KEEP_OLD': '保留旧版',
    'SKIP': '跳过'
  }
  
  if (selectedConflicts.value.length === 0) {
    ElMessage.warning('请先选择要处理的问题作品')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要对选中的 ${selectedConflicts.value.length} 个问题作品执行"${actionLabels[action]}"操作吗？`,
      '批量操作确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    loadingText.value = `正在批量处理 ${selectedConflicts.value.length} 个问题作品...`
    loading.value = true
    
    let successCount = 0
    let failCount = 0
    
    for (const conflict of selectedConflicts.value) {
      try {
        processingIds.value.add(conflict.id)
        await conflictApi.resolve(conflict.id, action)
        successCount++
        conflicts.value = conflicts.value.filter(c => c.id !== conflict.id)
      } catch (error) {
        failCount++
        console.error(`处理 ${conflict.rjcode} 失败:`, error)
      } finally {
        processingIds.value.delete(conflict.id)
      }
    }
    
    if (successCount > 0) {
      ElMessage.success(`成功处理 ${successCount} 个问题作品`)
    }
    if (failCount > 0) {
      ElMessage.warning(`${failCount} 个问题作品处理失败`)
    }
    
    selectedConflicts.value = []
    if (conflictsTable.value) {
      conflictsTable.value.clearSelection()
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量操作失败:', error)
      ElMessage.error('批量操作失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    loading.value = false
    loadingText.value = '加载中...'
  }
}
</script>

<style scoped>
.conflicts {
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  padding: 0 20px;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px;
}

.page-desc {
  color: #64748b;
  margin: 0;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.selected-count {
  color: #409eff;
  font-weight: 500;
}

.rjcode-cell {
  display: flex;
  align-items: center;
}

.rjcode-text {
  display: inline-block;
  padding: 2px 8px;
  background-color: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  font-family: monospace;
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  box-sizing: border-box;
  line-height: 1.4;
  vertical-align: middle;
}

.path-cell {
  word-break: break-all;
  white-space: normal;
  line-height: 1.4;
  max-height: 60px;
  overflow-y: auto;
  font-size: 13px;
  color: #606266;
}

.path-text {
  word-break: break-all;
  white-space: pre-wrap;
  line-height: 1.5;
  font-family: monospace;
  font-size: 12px;
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  max-height: 120px;
  overflow-y: auto;
}

.conflict-type-tag {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.action-buttons .el-button {
  flex: 1;
  min-width: 60px;
}

.conflict-detail {
  padding: 20px;
  background-color: #f8fafc;
  border-radius: 8px;
}

.conflict-detail h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #64748b;
}

@media screen and (max-width: 1200px) {
  .conflicts {
    padding: 0 10px;
  }
  
  .page-title {
    font-size: 24px;
  }
  
  .page-header {
    flex-direction: column;
    gap: 16px;
  }
  
  .batch-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}

@media screen and (max-width: 768px) {
  .action-buttons {
    flex-direction: column;
  }
  
  .action-buttons .el-button {
    width: 100%;
  }
}

:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table__header) {
  font-weight: 600;
}

:deep(.el-table__cell) {
  padding: 8px 0;
}

:deep(.el-table .cell) {
  white-space: normal;
  word-break: break-word;
  line-height: 1.4;
}

:deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

:deep(.el-table__fixed-right) {
  height: 100% !important;
}

:deep(.el-table__fixed-right-patch) {
  background-color: #f5f7fa;
}
</style>