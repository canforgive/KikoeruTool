<template>
  <div class="conflicts">
    <h1 class="page-title">问题作品</h1>
    <p class="page-desc">检测到重复或冲突的作品，请手动选择处理方式</p>
    
    <el-card v-loading="loading">
      <el-table 
        :data="conflicts" 
        style="width: 100%"
        :header-cell-style="{ 'white-space': 'nowrap' }"
      >
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
              <el-button size="small" type="primary" @click="handleAction(row, 'KEEP_NEW')">
                保留新版
              </el-button>
              <el-button size="small" @click="handleAction(row, 'KEEP_OLD')">
                保留旧版
              </el-button>
              <el-button size="small" type="warning" @click="handleAction(row, 'MERGE')">
                合并
              </el-button>
              <el-button size="small" type="info" @click="handleAction(row, 'SKIP')">
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
import axios from 'axios'

const conflicts = ref([])
const loading = ref(false)
let intervalId = null

onMounted(async () => {
  await fetchConflicts()
  // 每5秒自动刷新
  intervalId = setInterval(fetchConflicts, 5000)
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
  }
})

async function fetchConflicts() {
  try {
    const response = await axios.get('/api/conflicts')
    conflicts.value = response.data.conflicts || []
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
  return new Date(date).toLocaleString('zh-CN')
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
    
    loading.value = true
    await axios.post(`/api/conflicts/${conflict.id}/resolve`, { action })
    
    ElMessage.success('操作成功')
    await fetchConflicts()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作失败:', error)
      ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    loading.value = false
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

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px;
}

.page-desc {
  color: #64748b;
  margin-bottom: 24px;
}

/* RJ号单元格样式 */
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

/* 路径单元格样式 - 支持多行显示 */
.path-cell {
  word-break: break-all;
  white-space: normal;
  line-height: 1.4;
  max-height: 60px;
  overflow-y: auto;
  font-size: 13px;
  color: #606266;
}

/* 详细视图中的路径文本 */
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

/* 冲突类型标签样式 */
.conflict-type-tag {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* 操作按钮组样式 */
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

/* 响应式调整 */
@media screen and (max-width: 1200px) {
  .conflicts {
    padding: 0 10px;
  }
  
  .page-title {
    font-size: 24px;
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

/* 表格样式优化 */
:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table__header) {
  font-weight: 600;
}

:deep(.el-table__cell) {
  padding: 8px 0;
}

/* 确保表格内容不被压缩 */
:deep(.el-table .cell) {
  white-space: normal;
  word-break: break-word;
  line-height: 1.4;
}

/* 表格滚动条样式 */
:deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

:deep(.el-table__fixed-right) {
  height: 100% !important;
}

/* 修复固定列与表格内容重叠 */
:deep(.el-table__fixed-right-patch) {
  background-color: #f5f7fa;
}
</style>
