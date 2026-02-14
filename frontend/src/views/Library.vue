<template>
  <div class="library">
    <h1 class="page-title">库存文件管理</h1>
    
    <el-card>
      <template #header>
        <div class="card-header">
          <span>库内文件列表</span>
          <div class="header-actions">
            <el-button @click="refreshLibrary" :loading="loading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <el-input
              v-model="searchQuery"
              placeholder="搜索文件名或RJ号"
              style="width: 250px; margin-left: 10px;"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>
      </template>
      
      <el-table
        :data="paginatedFiles"
        v-loading="loading"
        style="width: 100%"
        empty-text="暂无文件"
        row-key="id"
      >
        <el-table-column prop="name" label="文件名" show-overflow-tooltip>
          <template #default="{ row }">
            <el-icon class="file-icon"><Folder /></el-icon>
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="rjcode" label="RJ号" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.rjcode" type="primary" size="small">{{ row.rjcode }}</el-tag>
            <span v-else>-</span>
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
        
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button 
              size="small" 
              type="primary"
              @click="openFolder(row)"
            >
              打开位置
            </el-button>
            <el-button 
              size="small" 
              type="success"
              @click="openFolderDirect(row)"
              title="直接打开文件夹（需安装Tampermonkey脚本）"
            >
              直接打开
            </el-button>
            <el-button 
              size="small" 
              type="warning"
              @click="renameItem(row)"
              :loading="renamingId === row.id"
            >
              重命名
            </el-button>
            <el-button 
              size="small" 
              type="success"
              @click="apiRenameItem(row)"
              :loading="apiRenamingId === row.id"
              title="重新获取DLsite元数据并重命名"
            >
              API重命名
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalFiles"
          layout="total, sizes, prev, pager, next"
        />
      </div>
    </el-card>
    
    <!-- 重命名对话框 -->
    <el-dialog
      v-model="renameDialogVisible"
      title="重命名"
      width="500px"
    >
      <el-form :model="renameForm" label-width="80px">
        <el-form-item label="当前名称">
          <el-input v-model="renameForm.currentName" disabled />
        </el-form-item>
        <el-form-item label="新名称">
          <el-input v-model="renameForm.newName" placeholder="输入新名称" />
        </el-form-item>
        <el-form-item label="预览">
          <div class="name-preview">{{ renameForm.newName || renameForm.currentName }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename" :loading="isRenaming">
          确认重命名
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 路径映射对话框 -->
    <el-dialog
      v-model="mappedPathDialogVisible"
      title="跨设备访问 - 路径映射"
      width="600px"
    >
      <el-alert
        title="检测到跨设备部署环境"
        type="info"
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <template #default>
          由于应用部署在远程服务器/Docker中，无法直接打开本地文件夹。请使用下方映射后的路径手动打开。
        </template>
      </el-alert>
      
      <el-descriptions :column="1" border>
        <el-descriptions-item label="远程路径">
          <code>{{ mappedPathInfo.originalPath }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="本地映射路径">
          <div class="mapped-path-container">
            <code class="mapped-path">{{ mappedPathInfo.mappedPath }}</code>
            <el-button 
              type="primary" 
              size="small" 
              @click="copyMappedPath"
              style="margin-left: 10px;"
            >
              复制路径
            </el-button>
            <el-button 
              type="success" 
              size="small" 
              @click="openWithBrowser"
              style="margin-left: 5px;"
              title="尝试用浏览器打开（可能被安全设置阻止）"
            >
              尝试打开
            </el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="映射状态">
          <el-tag :type="mappedPathInfo.isMapped ? 'success' : 'warning'">
            {{ mappedPathInfo.isMapped ? '已配置映射' : '未配置映射（使用原路径）' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <div class="path-mapping-help" style="margin-top: 20px; padding: 15px; background-color: #f5f7fa; border-radius: 4px;">
        <h4 style="margin-top: 0;">如何使用：</h4>
        <ol style="margin-bottom: 0; padding-left: 20px;">
          <li>点击"复制路径"按钮复制映射后的本地路径</li>
          <li>打开Windows文件资源管理器</li>
          <li>在地址栏粘贴路径并按回车</li>
        </ol>
        <p style="margin-top: 10px; margin-bottom: 0; color: #909399; font-size: 12px;">
          提示：如果路径无法访问，请检查网络驱动器映射是否正确配置。
        </p>
      </div>
      
      <template #footer>
        <el-button @click="mappedPathDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyMappedPath">复制路径</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, Search, Folder } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const files = ref([])
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const renamingId = ref(null)
const apiRenamingId = ref(null)

// 重命名对话框
const renameDialogVisible = ref(false)
const renameForm = ref({
  id: '',
  currentName: '',
  newName: '',
  path: ''
})
const isRenaming = ref(false)

// 路径映射对话框
const mappedPathDialogVisible = ref(false)
const mappedPathInfo = ref({
  originalPath: '',
  mappedPath: '',
  isMapped: false
})

// Tampermonkey 脚本检测
const tampermonkeyLoaded = ref(false)

// 过滤后的文件列表
const filteredFiles = computed(() => {
  let result = files.value
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(file => 
      file.name.toLowerCase().includes(query) || 
      (file.rjcode && file.rjcode.toLowerCase().includes(query))
    )
  }
  
  return result
})

// 总文件数
const totalFiles = computed(() => filteredFiles.value.length)

// 分页后的文件列表
const paginatedFiles = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  const result = filteredFiles.value.slice(start, end)
  console.log(`[Library Pagination] Page ${currentPage.value}, Size ${pageSize.value}, Start ${start}, End ${end}, Total ${filteredFiles.value.length}, Result ${result.length}`)
  return result
})

onMounted(() => {
  refreshLibrary()
  
  // 检查 Tampermonkey 脚本是否已加载（脚本可能已经在页面加载前完成）
  if (window.kikoeruHelperLoaded) {
    console.log('[Kikoeru] Tampermonkey 助手已预先加载')
    tampermonkeyLoaded.value = true
  }
  
  // 监听 Tampermonkey 脚本就绪事件（脚本可能在页面加载后才加载）
  window.addEventListener('kikoeru-helper-ready', (event) => {
    console.log('[Kikoeru] Tampermonkey 助手已加载', event.detail)
    tampermonkeyLoaded.value = true
  })
  
  // 5秒后再次检查（兜底机制）
  setTimeout(() => {
    if (!tampermonkeyLoaded.value && window.kikoeruHelperLoaded) {
      console.log('[Kikoeru] 延迟检测到 Tampermonkey')
      tampermonkeyLoaded.value = true
    }
  }, 5000)
})

async function refreshLibrary() {
  loading.value = true
  try {
    const response = await axios.get('/api/library/files')
    files.value = response.data.files || []
    ElMessage.success(`已加载 ${files.value.length} 个文件`)
  } catch (error) {
    console.error('获取库文件失败:', error)
    ElMessage.error('获取库文件失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
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

async function openFolder(row) {
  try {
    const response = await axios.post('/api/library/open-folder', { path: row.path })
    const data = response.data
    
    // 如果是映射模式，显示路径映射对话框
    if (data.mode === 'mapped') {
      mappedPathInfo.value = {
        originalPath: data.original_path,
        mappedPath: data.mapped_path,
        isMapped: data.is_mapped
      }
      mappedPathDialogVisible.value = true
      return
    }
    
    // 直接模式，后端已成功打开
    ElMessage.success('已打开文件夹')
  } catch (error) {
    console.error('打开文件夹失败:', error)
    ElMessage.error(error.response?.data?.detail || '打开文件夹失败')
  }
}

// 直接打开文件夹（跳过弹窗）
async function openFolderDirect(row) {
  try {
    // 先获取映射路径
    const response = await axios.post('/api/library/open-folder', { path: row.path })
    const data = response.data
    
    let targetPath
    if (data.mode === 'mapped') {
      targetPath = data.mapped_path
    } else {
      // 如果是直接模式，说明后端已打开
      ElMessage.success('已打开文件夹')
      return
    }
    
    // 检查 Tampermonkey 是否可用
    const hasTampermonkey = window.kikoeruHelperLoaded || tampermonkeyLoaded.value
    
    // 无论是否检测到，都尝试发送事件（Tampermonkey 可能已加载但未触发事件）
    console.log('[Kikoeru] 尝试直接打开:', targetPath, 'Tampermonkey状态:', hasTampermonkey)
    
    try {
      window.dispatchEvent(new CustomEvent('kikoeru-open-folder', {
        detail: { path: targetPath }
      }))
      
      // 如果检测到了，显示成功消息
      if (hasTampermonkey) {
        ElMessage.success('正在打开文件夹...')
      } else {
        // 未检测到，等待2秒看是否有反应
        ElMessage.info('正在尝试打开文件夹...')
        
        // 延迟检查是否成功
        setTimeout(() => {
          if (!window.kikoeruHelperLoaded && !tampermonkeyLoaded.value) {
            // 仍然没有检测到，说明可能没有安装
            showTampermonkeyDialog(targetPath)
          }
        }, 2000)
      }
      return
    } catch (err) {
      console.error('[Kikoeru] 发送打开事件失败:', err)
    }
    
    // 如果走到这里，说明发送事件失败
    showTampermonkeyDialog(targetPath)
  } catch (error) {
    console.error('直接打开失败:', error)
    ElMessage.error(error.response?.data?.detail || '打开文件夹失败')
  }
}

// 显示 Tampermonkey 安装提示对话框
async function showTampermonkeyDialog(targetPath) {
  ElMessage.warning('Tampermonkey 脚本未安装或加载失败，无法直接打开')
  
  // 复制路径并显示安装提示
  try {
    await navigator.clipboard.writeText(targetPath)
    ElMessage.success('路径已复制到剪贴板')
  } catch (err) {
    console.error('复制失败:', err)
  }
  
  ElMessageBox.confirm(
    `直接打开需要安装 Tampermonkey 脚本。<br><br>
    <strong>已复制路径：</strong><code>${targetPath}</code><br><br>
    是否查看安装教程？`,
    '需要 Tampermonkey',
    {
      confirmButtonText: '查看安装教程',
      cancelButtonText: '手动打开',
      type: 'warning',
      dangerouslyUseHTMLString: true
    }
  ).then(() => {
    window.open('https://github.com/canforgive/KikoeruTool/blob/main/tampermonkey/kikoeru-folder-opener.js', '_blank')
  })
}

// 复制映射路径到剪贴板
async function copyMappedPath() {
  try {
    await navigator.clipboard.writeText(mappedPathInfo.value.mappedPath)
    ElMessage.success('路径已复制到剪贴板')
  } catch (err) {
    console.error('复制失败:', err)
    ElMessage.error('复制失败，请手动复制')
  }
}

// 尝试用浏览器打开文件夹
function openWithBrowser() {
  const localPath = mappedPathInfo.value.mappedPath
  
  // 方法1: 尝试使用 Tampermonkey（如果已安装）
  if (window.kikoeruHelperLoaded || tampermonkeyLoaded.value) {
    console.log('[Kikoeru] 使用 Tampermonkey 打开:', localPath)
    window.dispatchEvent(new CustomEvent('kikoeru-open-folder', {
      detail: { path: localPath }
    }))
    ElMessage.success('已发送打开请求给 Tampermonkey')
    return
  }
  
  // 方法2: 普通浏览器方式（大概率失败）
  // 将 Windows 路径转换为 file 协议格式
  let fileUrl = localPath.replace(/\\/g, '/')
  
  // 如果是 Windows 驱动器路径（如 V:\...），添加 file:///
  if (/^[a-zA-Z]:/.test(fileUrl)) {
    fileUrl = 'file:///' + fileUrl
  } else {
    fileUrl = 'file://' + fileUrl
  }
  
  console.log('尝试打开路径:', fileUrl)
  
  // 尝试 window.open
  let opened = false
  try {
    const win = window.open(fileUrl, '_blank')
    if (win) {
      opened = true
      console.log('window.open 成功')
    }
  } catch (err) {
    console.log('window.open 失败:', err)
  }
  
  // 尝试 iframe
  if (!opened) {
    try {
      const iframe = document.createElement('iframe')
      iframe.style.display = 'none'
      iframe.src = fileUrl
      document.body.appendChild(iframe)
      setTimeout(() => document.body.removeChild(iframe), 1000)
      opened = true
    } catch (err) {
      console.log('iframe 方式失败:', err)
    }
  }
  
  if (opened) {
    ElMessage.success('已尝试打开文件夹')
  } else {
    // 所有方法都失败，提示安装 Tampermonkey
    ElMessage.warning('浏览器阻止了直接打开操作')
    
    ElMessageBox.confirm(
      `浏览器安全策略阻止了直接打开本地文件夹。<br><br>
      <strong>推荐方案：</strong>安装 Tampermonkey 脚本<br>
      安装后点击"尝试打开"即可直接打开文件夹<br><br>
      <strong>临时方案：</strong>路径已复制，请手动打开`,
      '无法直接打开',
      {
        confirmButtonText: '查看 Tampermonkey 脚本',
        cancelButtonText: '手动打开',
        type: 'warning',
        dangerouslyUseHTMLString: true
      }
    ).then(() => {
      // 打开 GitHub 上的脚本页面
      window.open('https://github.com/canforgive/KikoeruTool/blob/main/tampermonkey/kikoeru-folder-opener.js', '_blank')
    }).catch(() => {
      // 用户选择手动打开，复制路径
      copyMappedPath()
    })
  }
}

function renameItem(row) {
  renameForm.value = {
    id: row.id,
    currentName: row.name,
    newName: row.name,
    path: row.path
  }
  renameDialogVisible.value = true
}

async function confirmRename() {
  if (!renameForm.value.newName || renameForm.value.newName === renameForm.value.currentName) {
    ElMessage.warning('请输入不同的新名称')
    return
  }
  
  isRenaming.value = true
  try {
    await axios.post('/api/library/rename', {
      path: renameForm.value.path,
      new_name: renameForm.value.newName
    })
    
    ElMessage.success('重命名成功')
    renameDialogVisible.value = false
    
    // 刷新列表
    await refreshLibrary()
  } catch (error) {
    console.error('重命名失败:', error)
    ElMessage.error('重命名失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isRenaming.value = false
  }
}

async function apiRenameItem(row) {
  // 确认对话框
  try {
    await ElMessageBox.confirm(
      `确定要重新获取DLsite元数据并重命名吗？\n\n当前: ${row.name}`,
      'API重新命名确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
  } catch {
    return // 用户取消
  }
  
  apiRenamingId.value = row.id
  try {
    const response = await axios.post('/api/library/api-rename', {
      path: row.path
    })
    
    ElMessage.success(response.data.message)
    
    // 如果有新名称，显示详细信息
    if (response.data.new_name) {
      ElMessage.info(`新名称: ${response.data.new_name}`)
    }
    
    // 刷新列表
    await refreshLibrary()
  } catch (error) {
    console.error('API重命名失败:', error)
    ElMessage.error('API重命名失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    apiRenamingId.value = null
  }
}
</script>

<style scoped>
.library {
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

.file-icon {
  margin-right: 8px;
  color: #409eff;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.name-preview {
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  word-break: break-all;
}

.mapped-path-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.mapped-path {
  flex: 1;
  min-width: 0;
  word-break: break-all;
  background-color: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
}
</style>
