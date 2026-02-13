<template>
  <div class="password-vault">
    <h1 class="page-title">密码库</h1>
    
    <el-card class="main-card">
      <!-- 操作栏 -->
      <!-- 统计信息栏 -->
      <div class="stats-bar" v-if="cleanupStatus">
        <el-alert
          :title="cleanupStatus.enabled ? '智能清理已启用' : '智能清理已禁用'"
          :type="cleanupStatus.enabled ? 'success' : 'info'"
          :closable="false"
          show-icon
        >
          <template #default>
            <span v-if="cleanupStatus.enabled">
              下次清理时间: {{ formatNextCleanupTime(cleanupStatus.next_cleanup_time) }} |
              清理规则: 使用次数 ≤ {{ cleanupStatus.max_use_count }}, 保留 {{ cleanupStatus.preserve_days }} 天
            </span>
            <span v-else>
              前往设置页面启用密码库智能清理功能
            </span>
          </template>
        </el-alert>
      </div>

      <div class="toolbar">
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          添加密码
        </el-button>
        <el-button @click="showImportDialog = true">
          <el-icon><Document /></el-icon>
          批量导入
        </el-button>
        <el-button type="danger" plain @click="handleBatchDelete" :disabled="selectedRows.length === 0">
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>
        <el-button @click="showCleanupDialog = true">
          <el-icon><Timer /></el-icon>
          智能清理
        </el-button>
        
        <!-- 排序选择器 -->
        <el-select v-model="passwordSortBy" style="width: 140px; margin-left: 12px;" @change="handlePasswordSortChange">
          <el-option label="添加时间" value="created_at" />
          <el-option label="更新时间" value="updated_at" />
          <el-option label="RJ号" value="rjcode" />
          <el-option label="文件名" value="filename" />
          <el-option label="使用次数" value="use_count" />
        </el-select>
        
        <!-- 排序方向 -->
        <el-button 
          link 
          @click="togglePasswordSortOrder"
          :title="passwordSortOrder === 'desc' ? '降序' : '升序'"
        >
          <el-icon>
            <SortDown v-if="passwordSortOrder === 'desc'" />
            <SortUp v-else />
          </el-icon>
        </el-button>
        
        <el-input
          v-model="searchQuery"
          placeholder="搜索RJ号、文件名或密码"
          style="width: 280px; margin-left: auto;"
          clearable
          @input="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      
      <!-- 数据表格 -->
      <el-table
        :data="passwords"
        style="width: 100%"
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="rjcode" label="RJ号" width="120" sortable>
          <template #default="{ row }">
            <el-tag v-if="row.rjcode" type="info" size="small">{{ row.rjcode }}</el-tag>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <span v-if="row.filename">{{ row.filename }}</span>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="password" label="密码" width="200">
          <template #default="{ row }">
            <div class="password-cell">
              <span class="password-text">{{ row.password }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="备注" min-width="150">
          <template #default="{ row }">
            <span v-if="row.description">{{ row.description }}</span>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="use_count" label="使用次数" width="100" sortable>
          <template #default="{ row }">
            <el-tag :type="row.use_count > 0 ? 'success' : 'info'" size="small">
              {{ row.use_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_used_at" label="最后使用" width="150">
          <template #default="{ row }">
            <span v-if="row.last_used_at">{{ formatDate(row.last_used_at) }}</span>
            <span v-else class="text-gray">未使用</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="150">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 空状态 -->
      <el-empty v-if="!loading && passwords.length === 0" description="暂无密码记录">
        <el-button type="primary" @click="showAddDialog = true">添加第一个密码</el-button>
      </el-empty>
    </el-card>
    
    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="showAddDialog"
      :title="isEditing ? '编辑密码' : '添加密码'"
      width="500px"
    >
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" placeholder="输入解压密码" show-password />
          <div class="form-tip">必填：解压密码</div>
        </el-form-item>
        <el-form-item label="RJ号">
          <el-input v-model="form.rjcode" placeholder="例如: RJ123456（可选）" />
          <div class="form-tip">可选：如果密码与特定作品关联，请填写RJ号</div>
        </el-form-item>
        <el-form-item label="文件名">
          <el-input v-model="form.filename" placeholder="例如: RJ123456.zip（可选）" />
          <div class="form-tip">可选：如果密码与特定文件关联，请填写文件名</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选：添加描述信息，如" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ isEditing ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 智能清理对话框 -->
    <el-dialog
      v-model="showCleanupDialog"
      title="密码库智能清理"
      width="800px"
    >
      <div v-loading="cleanupLoading">
        <!-- 状态卡片 -->
        <el-row :gutter="20" style="margin-bottom: 20px;">
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>
                <span>清理状态</span>
              </template>
              <div style="text-align: center;">
                <el-tag :type="cleanupStatus?.enabled ? 'success' : 'info'" size="large">
                  {{ cleanupStatus?.enabled ? '已启用' : '已禁用' }}
                </el-tag>
                <div style="margin-top: 10px; font-size: 12px; color: #909399;">
                  {{ cleanupStatus?.is_running ? '服务运行中' : '服务未运行' }}
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>
                <span>下次清理</span>
              </template>
              <div style="text-align: center;">
                <div style="font-size: 18px; font-weight: 600; color: #409eff;">
                  {{ formatNextCleanupTime(cleanupStatus?.next_cleanup_time) }}
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: #909399;">
                  Cron: {{ cleanupStatus?.cron_expression }}
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>
                <span>清理规则</span>
              </template>
              <div style="text-align: center; font-size: 14px;">
                <div>使用次数 ≤ {{ cleanupStatus?.max_use_count }}</div>
                <div style="margin-top: 5px; color: #909399;">
                  保留 {{ cleanupStatus?.preserve_days }} 天
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 操作按钮 -->
        <div style="margin-bottom: 20px; display: flex; gap: 10px;">
          <el-button type="primary" @click="previewCleanup" :disabled="!cleanupStatus?.enabled">
            <el-icon><View /></el-icon>
            预览清理
          </el-button>
          <el-button type="danger" @click="runCleanup" :disabled="!cleanupStatus?.enabled">
            <el-icon><Delete /></el-icon>
            立即清理
          </el-button>
          <el-button @click="loadCleanupHistory">
            <el-icon><Refresh /></el-icon>
            刷新历史
          </el-button>
          <el-button style="margin-left: auto;" @click="$router.push('/settings')">
            <el-icon><Setting /></el-icon>
            前往设置
          </el-button>
        </div>

        <!-- 清理历史 -->
        <el-divider>清理历史</el-divider>
        <el-table :data="cleanupHistory" style="width: 100%" max-height="300">
          <el-table-column prop="created_at" label="清理时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="deleted_count" label="删除数量" width="100">
            <template #default="{ row }">
              <el-tag type="danger">{{ row.deleted_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="config_snapshot" label="配置快照">
            <template #default="{ row }">
              <div style="font-size: 12px; color: #606266;">
                使用次数≤{{ row.config_snapshot?.max_use_count }},
                保留{{ row.config_snapshot?.preserve_days }}天
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="deleted_passwords_summary" label="删除详情" min-width="200">
            <template #default="{ row }">
              <div v-if="row.deleted_passwords_summary && row.deleted_passwords_summary.length > 0"
                   style="font-size: 12px;">
                <div v-for="(pwd, idx) in row.deleted_passwords_summary.slice(0, 3)" :key="idx">
                  {{ pwd.rjcode || pwd.filename || '通用密码' }} ({{ pwd.use_count }}次)
                </div>
                <div v-if="row.deleted_passwords_summary.length > 3" style="color: #909399;">
                  等 {{ row.deleted_passwords_summary.length }} 个密码...
                </div>
              </div>
              <span v-else style="color: #909399;">-</span>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="cleanupHistory.length === 0" description="暂无清理记录" />
      </div>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog
      v-model="showImportDialog"
      title="批量导入密码"
      width="600px"
    >
      <el-alert
        title="导入格式说明"
        type="info"
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <div style="font-size: 12px; line-height: 1.8;">
          <p>每行一个密码，系统会尝试解压时使用这些密码</p>
          <p>系统会自动匹配RJ号，无需在导入时指定</p>
        </div>
      </el-alert>
      
      <el-input
        v-model="importText"
        type="textarea"
        :rows="10"
        placeholder="在此粘贴密码列表（每行一个）...&#10;例如：&#10;password123&#10;password456&#10;password789"
      />
      
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="handleImport" :loading="importing">
          导入 {{ importText.trim() ? importText.trim().split('\n').filter(l => l.trim()).length : 0 }} 个密码
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { Plus, Delete, Document, Search, View, Hide, Timer, Refresh, Setting, SortDown, SortUp } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const passwords = ref([])
const selectedRows = ref([])
const searchQuery = ref('')
const passwordSortBy = ref('created_at')
const passwordSortOrder = ref('desc')
const showAddDialog = ref(false)
const showImportDialog = ref(false)
const showCleanupDialog = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const importing = ref(false)
const cleanupLoading = ref(false)
const showPassword = ref({})
const importText = ref('')
const formRef = ref(null)
const cleanupStatus = ref(null)
const cleanupHistory = ref([])

const form = ref({
  id: null,
  rjcode: '',
  filename: '',
  password: '',
  description: ''
})

const rules = {
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, max: 255, message: '密码长度应在1-255个字符之间', trigger: 'blur' }
  ]
}

onMounted(() => {
  loadPasswords()
  loadCleanupStatus()
})

async function loadPasswords() {
  loading.value = true
  try {
    const params = {
      sort_by: passwordSortBy.value,
      sort_order: passwordSortOrder.value
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    const response = await axios.get('/api/passwords', { params })
    passwords.value = response.data
  } catch (error) {
    console.error('加载密码列表失败:', error)
    ElMessage.error('加载密码列表失败')
  } finally {
    loading.value = false
  }
}

// 处理排序字段变化
function handlePasswordSortChange() {
  loadPasswords()
}

// 切换排序方向
function togglePasswordSortOrder() {
  passwordSortOrder.value = passwordSortOrder.value === 'desc' ? 'asc' : 'desc'
  loadPasswords()
}

function handleSearch() {
  loadPasswords()
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

function togglePassword(id) {
  showPassword.value[id] = !showPassword.value[id]
}

function handleEdit(row) {
  isEditing.value = true
  form.value = {
    id: row.id,
    rjcode: row.rjcode || '',
    filename: row.filename || '',
    password: row.password,
    description: row.description || ''
  }
  showAddDialog.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEditing.value) {
      await axios.put(`/api/passwords/${form.value.id}`, {
        rjcode: form.value.rjcode || null,
        filename: form.value.filename || null,
        password: form.value.password,
        description: form.value.description || null
      })
      ElMessage.success('密码已更新')
    } else {
      await axios.post('/api/passwords', {
        rjcode: form.value.rjcode || null,
        filename: form.value.filename || null,
        password: form.value.password,
        description: form.value.description || null,
        source: 'manual'
      })
      ElMessage.success('密码已添加')
    }
    showAddDialog.value = false
    resetForm()
    loadPasswords()
  } catch (error) {
    console.error('保存密码失败:', error)
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除这个密码吗？${row.rjcode ? `（RJ号: ${row.rjcode}）` : ''}`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await axios.delete(`/api/passwords/${row.id}`)
    ElMessage.success('密码已删除')
    loadPasswords()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除密码失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个密码吗？`,
      '确认批量删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    for (const row of selectedRows.value) {
      await axios.delete(`/api/passwords/${row.id}`)
    }
    
    ElMessage.success(`已删除 ${selectedRows.value.length} 个密码`)
    selectedRows.value = []
    loadPasswords()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

async function handleImport() {
  const trimmedText = importText.value.trim()
  if (!trimmedText) {
    ElMessage.warning('请输入要导入的密码')
    return
  }

  // 统计有效密码数量
  const passwords = trimmedText.split('\n').filter(line => line.trim()).length
  if (passwords === 0) {
    ElMessage.warning('请输入有效的密码')
    return
  }

  importing.value = true
  try {
    const response = await axios.post('/api/passwords/import-from-text', {
      text: trimmedText
    })
    
    const { message, imported, skipped } = response.data
    if (skipped > 0) {
      ElMessage.success(`${message}`)
    } else {
      ElMessage.success(`成功导入 ${imported} 个密码`)
    }
    
    showImportDialog.value = false
    importText.value = ''
    loadPasswords()
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error('导入失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    importing.value = false
  }
}

function resetForm() {
  form.value = {
    id: null,
    rjcode: '',
    filename: '',
    password: '',
    description: ''
  }
  isEditing.value = false
  formRef.value?.resetFields()
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadCleanupStatus() {
  try {
    const response = await axios.get('/api/password-cleanup/status')
    cleanupStatus.value = response.data
  } catch (error) {
    console.error('加载清理状态失败:', error)
  }
}

async function loadCleanupHistory() {
  cleanupLoading.value = true
  try {
    const response = await axios.get('/api/password-cleanup/history', {
      params: { limit: 50 }
    })
    cleanupHistory.value = response.data.history || []
  } catch (error) {
    console.error('加载清理历史失败:', error)
    ElMessage.error('加载清理历史失败')
  } finally {
    cleanupLoading.value = false
  }
}

async function previewCleanup() {
  cleanupLoading.value = true
  try {
    const response = await axios.get('/api/password-cleanup/preview')
    const data = response.data

    if (data.deleted_count === 0) {
      ElMessage.info('没有需要清理的密码')
      return
    }

    // 显示预览对话框
    const passwordList = data.deleted_passwords.map(p =>
      `• ${p.rjcode || p.filename || '通用密码'} (${p.use_count}次使用, ${p.source})`
    ).join('\n')

    await ElMessageBox.confirm(
      `将清理 ${data.deleted_count} 个密码：\n\n${passwordList}\n\n确定要立即清理吗？`,
      '清理预览',
      {
        confirmButtonText: '立即清理',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: false
      }
    )

    // 用户确认后执行清理
    await runCleanup()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('预览清理失败:', error)
      ElMessage.error('预览清理失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    cleanupLoading.value = false
  }
}

async function runCleanup() {
  cleanupLoading.value = true
  try {
    const response = await axios.post('/api/password-cleanup/run')
    const data = response.data

    if (data.deleted_count === 0) {
      ElMessage.info('没有需要清理的密码')
    } else {
      ElMessage.success(`成功清理 ${data.deleted_count} 个密码`)
      // 刷新密码列表和历史记录
      loadPasswords()
      loadCleanupHistory()
    }
  } catch (error) {
    console.error('执行清理失败:', error)
    ElMessage.error('执行清理失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    cleanupLoading.value = false
  }
}

function formatNextCleanupTime(timeStr) {
  if (!timeStr) return '未设置'
  const date = new Date(timeStr)
  const now = new Date()
  const diff = date - now

  if (diff < 0) return '即将执行'

  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

  if (days > 0) return `${days}天${hours}小时后`
  if (hours > 0) return `${hours}小时${minutes}分钟后`
  return `${minutes}分钟后`
}

// 监听对话框打开事件
watch(showCleanupDialog, (newVal) => {
  if (newVal) {
    loadCleanupStatus()
    loadCleanupHistory()
  }
})
</script>

<style scoped>
.password-vault {
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 24px;
}

.main-card {
  min-height: 600px;
}

.toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  gap: 12px;
}

.password-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.text-gray {
  color: #909399;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

:deep(.el-table) {
  margin-top: 10px;
}

.stats-bar {
  margin-bottom: 16px;
}
</style>
