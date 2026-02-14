<template>
  <div class="existing-folders">
    <h1 class="page-title">已存在文件夹处理</h1>
    <p class="page-description">
      处理已经存在于文件夹中的作品（非软件解压的压缩包），这些文件夹通常以 <code>{RJCode} {work_name}</code> 格式命名。
      <br>
      <el-tag type="info" size="small" style="margin-top: 8px;">处理流程：查重检查 → 获取元数据 → 重命名 → 过滤 → 扁平化 → 分类移动</el-tag>
    </p>
    
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>文件夹列表</span>
            <el-tag type="info" v-if="folders.length > 0" style="margin-left: 10px;">
              {{ selectedFolders.length }}/{{ folders.length }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button @click="refreshFolders" :loading="loading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <el-button type="primary" @click="handleProcess" :disabled="selectedFolders.length === 0" :loading="processing">
              <el-icon><VideoPlay /></el-icon>
              处理选中文件夹 ({{ selectedFolders.length }})
            </el-button>
          </div>
        </div>
      </template>
      
      <div class="toolbar">
        <el-input
          v-model="searchQuery"
          placeholder="搜索文件夹名或RJ号"
          style="width: 300px;"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-checkbox v-model="autoClassify" style="margin-left: 20px;">
          自动分类移动到库
        </el-checkbox>
        <el-checkbox v-model="checkDuplicates" style="margin-left: 20px;">
          扫描时检查重复
        </el-checkbox>
        <el-button 
          @click="checkSelectedDuplicates" 
          :disabled="selectedFolders.length === 0"
          :loading="checkingDuplicates"
          style="margin-left: 20px;"
        >
          <el-icon><Search /></el-icon>
          检查选中项重复
        </el-button>
        <el-button 
          @click="refreshWithCache" 
          :loading="loading"
          style="margin-left: 20px;"
          type="info"
        >
          <el-icon><Refresh /></el-icon>
          刷新信息（使用缓存）
        </el-button>
        <el-button 
          @click="refreshForce" 
          :loading="loading"
          style="margin-left: 10px;"
          type="warning"
        >
          <el-icon><RefreshRight /></el-icon>
          重新抓取
        </el-button>
      </div>

      <!-- 冲突警告 -->
      <el-alert
        v-if="conflictCount > 0"
        :title="`发现 ${conflictCount} 个可能有冲突的文件夹`"
        type="warning"
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <template #default>
          <p>这些文件夹对应的RJ号在库中已存在或有相关联的作品。</p>
          <p>请仔细查看冲突详情后再决定是否处理。</p>
        </template>
      </el-alert>
      
      <el-alert
        v-if="folders.length === 0 && !loading"
        title="暂无文件夹"
        type="info"
          description="请将文件夹放入配置中设置的「已存在文件夹目录」中，然后点击刷新"
        show-icon
        :closable="false"
        style="margin: 20px 0;"
      />
      
      <!-- 扫描进度提示 -->
      <el-alert
        v-if="loading && folders.length > 0"
        :title="`正在扫描... 已找到 ${folders.length} 个文件夹`"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 10px;"
      />
      
      <el-table
        v-else-if="folders.length > 0 || !loading"
        :data="filteredFolders"
        style="width: 100%"
        empty-text="暂无文件夹"
        row-key="path"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" label="文件夹名" show-overflow-tooltip>
          <template #default="{ row }">
            <el-icon class="folder-icon"><Folder /></el-icon>
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="rjcode" label="RJ号" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.rjcode" type="primary" size="small">{{ row.rjcode }}</el-tag>
            <span v-else class="no-rjcode">未识别</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.size) }}
          </template>
        </el-table-column>
        
         <el-table-column prop="modified_time" label="修改时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.modified_time) }}
          </template>
        </el-table-column>
        
        <el-table-column label="查重状态" width="150">
          <template #default="{ row }">
            <el-tag 
              v-if="row.duplicate_info && row.duplicate_info.is_duplicate" 
              type="danger" 
              size="small"
              @click="showDuplicateDetail(row)"
              style="cursor: pointer;"
            >
              <el-icon><Warning /></el-icon>
              {{ getConflictTypeLabel(row.duplicate_info.conflict_type) }}
            </el-tag>
            <el-tag v-else-if="row.duplicate_info === null" type="info" size="small">
              检查中...
            </el-tag>
            <el-tag v-else type="success" size="small">
              <el-icon><Check /></el-icon>
              无冲突
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button 
              v-if="row.duplicate_info && row.duplicate_info.is_duplicate"
              type="warning" 
              size="small"
              @click="showDuplicateDetail(row)"
            >
              查看冲突
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 处理结果对话框 -->
    <el-dialog
      v-model="resultDialogVisible"
      title="处理结果"
      width="500px"
    >
      <el-result
        :icon="resultData.success ? 'success' : 'warning'"
        :title="resultData.success ? '任务创建成功' : '部分任务创建失败'"
        :sub-title="resultData.message"
      >
        <template #extra>
          <div class="result-details" v-if="resultData.tasks && resultData.tasks.length > 0">
            <p>已创建 {{ resultData.tasks.length }} 个处理任务：</p>
            <el-scrollbar max-height="200px">
              <ul class="task-list">
                <li v-for="task in resultData.tasks" :key="task.task_id">
                  <el-tag type="success" size="small">{{ task.task_id.substring(0, 8) }}...</el-tag>
                  <span class="task-path">{{ getFolderName(task.folder_path) }}</span>
                </li>
              </ul>
            </el-scrollbar>
          </div>
          <el-button type="primary" @click="resultDialogVisible = false">确定</el-button>
          <el-button @click="goToTasks">查看任务队列</el-button>
        </template>
      </el-result>
    </el-dialog>
    
    <!-- 查重详情对话框 -->
    <el-dialog
      v-model="duplicateDetailVisible"
      title="冲突详情"
      width="700px"
    >
      <div v-if="duplicateDetailData" class="duplicate-detail">
        <!-- 冲突类型 -->
        <el-alert
          :title="getConflictTypeLabel(duplicateDetailData.conflict_type)"
          :type="duplicateDetailData.conflict_type === 'DUPLICATE' ? 'error' : 'warning'"
          :description="duplicateDetailData.analysis_info?.current_work ? 
            `当前作品类型: ${duplicateDetailData.analysis_info.current_work.work_type} (${duplicateDetailData.analysis_info.current_work.lang})` : ''"
          show-icon
          style="margin-bottom: 20px;"
        />
        
        <!-- 直接重复 -->
        <div v-if="duplicateDetailData.direct_duplicate" class="detail-section">
          <h4>已存在的相同RJ号作品</h4>
          <el-descriptions border :column="1">
            <el-descriptions-item label="RJ号">{{ duplicateDetailData.direct_duplicate.rjcode }}</el-descriptions-item>
            <el-descriptions-item label="路径">{{ duplicateDetailData.direct_duplicate.path }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatFileSize(duplicateDetailData.direct_duplicate.size) }}</el-descriptions-item>
          </el-descriptions>
        </div>
        
        <!-- 关联作品 -->
        <div v-if="duplicateDetailData.linked_works_found && duplicateDetailData.linked_works_found.length > 0" class="detail-section">
          <h4>库中已存在的关联作品</h4>
          <el-table :data="duplicateDetailData.linked_works_found" border size="small">
            <el-table-column prop="rjcode" label="RJ号" width="120" />
            <el-table-column prop="work_name" label="作品名称" show-overflow-tooltip />
            <el-table-column prop="work_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.work_type === 'original' ? 'success' : 'info'" size="small">
                  {{ row.work_type === 'original' ? '原作' : row.work_type === 'parent' ? '翻译父级' : '翻译子级' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="lang" label="语言" width="80" />
            <el-table-column prop="size" label="大小" width="100">
              <template #default="{ row }">
                {{ formatFileSize(row.size) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
        
        <!-- 分析报告 -->
        <div v-if="duplicateDetailData.analysis_info" class="detail-section">
          <h4>分析报告</h4>
          <el-descriptions border :column="2">
            <el-descriptions-item label="有原作品">{{ duplicateDetailData.analysis_info.has_original ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="有翻译版本">{{ duplicateDetailData.analysis_info.has_translation ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="有父级作品">{{ duplicateDetailData.analysis_info.has_parent ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="有子级作品">{{ duplicateDetailData.analysis_info.has_child ? '是' : '否' }}</el-descriptions-item>
          </el-descriptions>
          
          <!-- 语言统计 -->
          <div v-if="duplicateDetailData.analysis_info.lang_stats" class="lang-stats">
            <h5>语言版本统计</h5>
            <el-tag 
              v-for="(count, lang) in duplicateDetailData.analysis_info.lang_stats" 
              :key="lang"
              size="small"
              style="margin-right: 8px; margin-bottom: 8px;"
            >
              {{ lang }}: {{ count }}
            </el-tag>
          </div>
        </div>
        
        <!-- 建议操作 -->
        <div v-if="duplicateDetailData.resolution_options && duplicateDetailData.resolution_options.length > 0" class="detail-section">
          <h4>
            建议操作
            <el-tooltip content="优先级：简体中文 > 繁体中文 > 日文 > 其他语言" placement="top">
              <el-icon><Info-Filled /></el-icon>
            </el-tooltip>
          </h4>
          <el-alert
            v-if="getRecommendedOption()"
            :title="getRecommendedOption().description"
            type="success"
            :closable="false"
            style="margin-bottom: 15px;"
          />
          <el-radio-group v-model="selectedResolution" style="display: flex; flex-direction: column; gap: 10px;">
            <el-radio 
              v-for="option in duplicateDetailData.resolution_options" 
              :key="option.action"
              :label="option.action"
              style="height: auto; align-items: flex-start; padding: 12px; border: 2px solid #e4e7ed; border-radius: 8px; transition: all 0.3s;"
              :style="option.recommend ? 'border-color: #67c23a; background-color: #f0f9eb;' : 'border-color: #dcdfe6;'"
            >
              <div style="display: flex; flex-direction: column; gap: 5px; width: 100%;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <strong style="font-size: 14px;">{{ option.label }}</strong>
                  <el-tag v-if="option.recommend" type="success" size="small" effect="dark">
                    <el-icon><Check /></el-icon> 智能推荐
                  </el-tag>
                  <el-tag v-if="option.action === 'SKIP'" type="danger" size="small">删除</el-tag>
                  <el-tag v-else-if="option.action === 'KEEP_NEW'" type="primary" size="small">保留新版</el-tag>
                  <el-tag v-else-if="option.action === 'KEEP_OLD'" type="warning" size="small">保留旧版</el-tag>
                  <el-tag v-else-if="option.action === 'KEEP_BOTH'" type="info" size="small">保留两者</el-tag>
                </div>
                <span style="color: #606266; font-size: 13px; line-height: 1.5;">{{ option.description }}</span>
              </div>
            </el-radio>
          </el-radio-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="duplicateDetailVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleProcessWithResolution">确认处理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, RefreshRight, Search, Folder, VideoPlay, Warning, Check, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const loading = ref(false)
const processing = ref(false)
const checkingDuplicates = ref(false)
const folders = ref([])
const selectedFolders = ref([])
const searchQuery = ref('')
const autoClassify = ref(true)
const checkDuplicates = ref(true)
const conflictCount = ref(0)

// 结果对话框
const resultDialogVisible = ref(false)
const resultData = ref({
  success: true,
  message: '',
  tasks: []
})

// 查重详情对话框
const duplicateDetailVisible = ref(false)
const duplicateDetailData = ref(null)
const selectedResolution = ref('')
const currentConflictFolder = ref(null)

// 过滤后的文件夹列表
const filteredFolders = computed(() => {
  let result = folders.value
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(folder => 
      folder.name.toLowerCase().includes(query) || 
      (folder.rjcode && folder.rjcode.toLowerCase().includes(query))
    )
  }
  
  return result
})

onMounted(() => {
  refreshWithCache() // 默认使用缓存刷新
})

async function refreshFolders() {
  loading.value = true
  folders.value = [] // 清空列表
  conflictCount.value = 0
  
  try {
    const response = await fetch(`/api/existing-folders/scan?check_duplicates=${checkDuplicates.value}`, {
      method: 'POST',
      headers: {
        'Accept': 'application/x-ndjson'
      }
    })
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整的最后一行
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const data = JSON.parse(line)
            
            if (data.type === 'start') {
              ElMessage.info(data.message)
            } else if (data.type === 'folder') {
              // 实时添加文件夹到列表（使用展开运算符确保Vue检测到变化）
              folders.value = [...folders.value, data.folder]
              if (data.folder.duplicate_info) {
                conflictCount.value++
              }
            } else if (data.type === 'complete') {
              let msg = data.message
              ElMessage.success(msg)
            } else if (data.type === 'error') {
              ElMessage.error(data.error)
            }
          } catch (e) {
            console.error('解析数据失败:', e, line)
          }
        }
      }
    }
  } catch (error) {
    console.error('获取文件夹列表失败:', error)
    ElMessage.error('获取失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 使用缓存刷新
async function refreshWithCache() {
  // 使用缓存，不传 force_refresh 参数
  await refreshFoldersWithOptions(false)
}

// 强制刷新（重新抓取API）
async function refreshForce() {
  try {
    await ElMessageBox.confirm(
      '确定要重新抓取所有信息吗？这将清除缓存并重新调用API查询，可能需要较长时间。',
      '确认重新抓取',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 先刷新缓存标记
    await axios.post('/api/existing-folders/refresh-cache')
    ElMessage.success('已标记缓存需要刷新')
    
    // 强制刷新
    await refreshFoldersWithOptions(true)
  } catch (error) {
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
    console.error('刷新缓存失败:', error)
    ElMessage.error('刷新失败: ' + (error.message || '未知错误'))
  }
}

// 带参数的刷新方法
async function refreshFoldersWithOptions(forceRefresh = false) {
  loading.value = true
  folders.value = [] // 清空列表
  conflictCount.value = 0
  
  try {
    const url = `/api/existing-folders/scan?check_duplicates=${checkDuplicates.value}&force_refresh=${forceRefresh}`
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Accept': 'application/x-ndjson'
      }
    })
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let cachedCount = 0
    let apiCount = 0
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整的最后一行
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const data = JSON.parse(line)
            
            if (data.type === 'start') {
              ElMessage.info(data.message)
            } else if (data.type === 'folder') {
              // 实时添加文件夹到列表（使用展开运算符确保Vue检测到变化）
              folders.value = [...folders.value, data.folder]
              if (data.folder.duplicate_info) {
                conflictCount.value++
              }
              // 统计缓存/API
              if (data.from_cache) {
                cachedCount++
              } else {
                apiCount++
              }
            } else if (data.type === 'complete') {
              let msg = data.message
              if (cachedCount > 0 || apiCount > 0) {
                msg += `（缓存: ${cachedCount}, API: ${apiCount}）`
              }
              ElMessage.success(msg)
            } else if (data.type === 'error') {
              ElMessage.error(data.error)
            }
          } catch (e) {
            console.error('解析数据失败:', e, line)
          }
        }
      }
    }
  } catch (error) {
    console.error('获取文件夹列表失败:', error)
    ElMessage.error('获取失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(selection) {
  selectedFolders.value = selection
}

async function handleProcess() {
  if (selectedFolders.value.length === 0) {
    ElMessage.warning('请先选择要处理的文件夹')
    return
  }
  
  processing.value = true
  try {
    const response = await axios.post('/api/existing-folders/process', {
      folders: selectedFolders.value.map(f => f.path),
      auto_classify: autoClassify.value
    })
    
    resultData.value = {
      success: true,
      message: response.data.message,
      tasks: response.data.tasks || []
    }
    resultDialogVisible.value = true
    
    // 清空选择
    selectedFolders.value = []
    
  } catch (error) {
    console.error('处理文件夹失败:', error)
    resultData.value = {
      success: false,
      message: error.response?.data?.detail || error.message,
      tasks: []
    }
    resultDialogVisible.value = true
  } finally {
    processing.value = false
  }
}

function getFolderName(path) {
  if (!path) return ''
  const parts = path.split(/[\\/]/)
  return parts[parts.length - 1]
}

function goToTasks() {
  resultDialogVisible.value = false
  router.push('/tasks')
}

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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

function getConflictTypeLabel(conflictType) {
  const labels = {
    'DUPLICATE': '直接重复',
    'LINKED_WORK_ORIGINAL': '原作已存在',
    'LINKED_WORK_TRANSLATION': '翻译版已存在',
    'LINKED_WORK_CHILD': '子版本已存在',
    'LINKED_WORK': '关联作品',
    'LANGUAGE_VARIANT': '语言变体',
    'MULTIPLE_VERSIONS': '多版本'
  }
  return labels[conflictType] || '冲突'
}

async function checkSelectedDuplicates() {
  if (selectedFolders.value.length === 0) {
    ElMessage.warning('请先选择要检查的文件夹')
    return
  }
  
  checkingDuplicates.value = true
  try {
    const response = await axios.post('/api/existing-folders/check-duplicates', {
      folders: selectedFolders.value.map(f => f.path),
      check_linked_works: true
    })
    
    // 更新文件夹的查重信息
    response.data.results.forEach(result => {
      const folder = folders.value.find(f => f.path === result.folder_path)
      if (folder) {
        if (result.error) {
          folder.duplicate_info = { error: result.error }
        } else {
          folder.duplicate_info = {
            is_duplicate: result.is_duplicate,
            conflict_type: result.conflict_type,
            direct_duplicate: result.direct_duplicate,
            linked_works_found: result.linked_works_found,
            related_rjcodes: result.related_rjcodes,
            analysis_info: result.analysis_info,
            resolution_options: result.resolution_options
          }
        }
      }
    })
    
    // 更新冲突计数
    conflictCount.value = folders.value.filter(f => 
      f.duplicate_info && f.duplicate_info.is_duplicate
    ).length
    
    if (response.data.duplicate_count > 0) {
      ElMessage.warning(`发现 ${response.data.duplicate_count} 个冲突`)
    } else {
      ElMessage.success('未发现冲突')
    }
    
  } catch (error) {
    console.error('查重检查失败:', error)
    ElMessage.error('查重检查失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    checkingDuplicates.value = false
  }
}

function showDuplicateDetail(row) {
  currentConflictFolder.value = row
  duplicateDetailData.value = row.duplicate_info
  // 设置默认选择推荐的选项
  if (row.duplicate_info.resolution_options) {
    const recommendOption = row.duplicate_info.resolution_options.find(o => o.recommend)
    selectedResolution.value = recommendOption ? recommendOption.action : row.duplicate_info.resolution_options[0]?.action
  }
  duplicateDetailVisible.value = true
}

function getRecommendedOption() {
  if (!duplicateDetailData.value || !duplicateDetailData.value.resolution_options) return null
  return duplicateDetailData.value.resolution_options.find(o => o.recommend)
}

async function handleProcessWithResolution() {
  if (!selectedResolution.value) {
    ElMessage.warning('请先选择一个处理方案')
    return
  }
  
  const selectedOption = duplicateDetailData.value?.resolution_options?.find(o => o.action === selectedResolution.value)
  
  // 如果是抛弃新版，直接删除文件夹
  if (selectedResolution.value === 'SKIP') {
    try {
      await ElMessageBox.confirm(
        `确定要抛弃新版吗？这将删除文件夹：${currentConflictFolder.value?.name}`,
        '确认删除',
        {
          confirmButtonText: '确认删除',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
      
      // 调用后端删除接口
      await axios.post('/api/existing-folders/delete', {
        path: currentConflictFolder.value?.path
      })
      
      ElMessage.success('已删除新版文件夹')
      duplicateDetailVisible.value = false
      
      // 刷新列表
      await refreshFolders()
    } catch (error) {
      if (error !== 'cancel') {
        console.error('删除失败:', error)
        ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message))
      }
    }
    return
  }
  
  // 其他操作：保留新版/保留旧版/保留两者/合并
  try {
    await ElMessageBox.confirm(
      `确定要执行"${selectedOption?.label}"操作吗？`,
      '确认操作',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    // 调用处理接口，传入解决方案
    const response = await axios.post('/api/existing-folders/process-with-resolution', {
      folder_path: currentConflictFolder.value?.path,
      resolution: selectedResolution.value,
      auto_classify: autoClassify.value
    })
    
    ElMessage.success(response.data.message || '操作成功')
    duplicateDetailVisible.value = false
    
    // 刷新列表
    await refreshFolders()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('处理失败:', error)
      ElMessage.error('处理失败: ' + (error.response?.data?.detail || error.message))
    }
  }
}
</script>

<style scoped>
.existing-folders {
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px;
}

.page-description {
  color: #64748b;
  margin-bottom: 24px;
  line-height: 1.6;
}

.page-description code {
  background-color: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.folder-icon {
  margin-right: 8px;
  color: #409eff;
}

.no-rjcode {
  color: #909399;
  font-size: 12px;
}

.result-details {
  text-align: left;
  margin: 20px 0;
}

.task-list {
  list-style: none;
  padding: 0;
  margin: 10px 0;
}

.task-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 8px;
}

.task-path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.duplicate-detail {
  max-height: 600px;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #303133;
  border-left: 4px solid #409eff;
  padding-left: 8px;
}

.detail-section h5 {
  margin: 12px 0 8px 0;
  font-size: 14px;
  color: #606266;
}

.lang-stats {
  margin-top: 12px;
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
}
</style>
