<template>
  <div 
    class="file-uploader"
    :class="{ 'drag-over': isDragOver }"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
    @click="triggerFileInput"
  >
    <input
      ref="fileInput"
      type="file"
      multiple
      accept=".zip,.rar,.7z,.tar,.gz,.bz2,.xz"
      style="display: none"
      @change="handleFileSelect"
    />
    
    <div class="upload-content">
      <el-icon :size="64" class="upload-icon"><Upload /></el-icon>
      <h3 class="upload-title">拖拽文件到此处或点击上传</h3>
      <p class="upload-desc">支持 ZIP, RAR, 7Z 等压缩格式</p>
      
      <div v-if="selectedFiles.length > 0" class="selected-files">
        <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
          <el-icon><Document /></el-icon>
          <span class="file-name">{{ file.name }}</span>
          <span class="file-size">{{ formatFileSize(file.size) }}</span>
        </div>
        
        <el-button 
          type="primary" 
          size="large" 
          :loading="uploading"
          @click.stop="startUpload"
          class="upload-btn"
        >
          开始处理 ({{ selectedFiles.length }} 个文件)
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Upload, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '../stores'

const emit = defineEmits(['upload-success'])

const taskStore = useTaskStore()
const fileInput = ref(null)
const isDragOver = ref(false)
const selectedFiles = ref([])
const uploading = ref(false)

function triggerFileInput() {
  fileInput.value?.click()
}

function handleDragOver() {
  isDragOver.value = true
}

function handleDragLeave() {
  isDragOver.value = false
}

function handleDrop(e) {
  isDragOver.value = false
  const files = Array.from(e.dataTransfer.files)
  addFiles(files)
}

function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  addFiles(files)
}

function addFiles(files) {
  const validFiles = files.filter(file => {
    const ext = file.name.toLowerCase()
    return ext.endsWith('.zip') || ext.endsWith('.rar') || 
           ext.endsWith('.7z') || ext.endsWith('.tar') ||
           ext.endsWith('.gz') || ext.endsWith('.bz2') ||
           ext.endsWith('.xz')
  })
  
  if (validFiles.length === 0) {
    ElMessage.warning('请选择有效的压缩文件')
    return
  }
  
  selectedFiles.value = [...selectedFiles.value, ...validFiles]
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

async function startUpload() {
  if (selectedFiles.value.length === 0) return
  
  uploading.value = true
  
  try {
    for (const file of selectedFiles.value) {
      // 在真实环境中，这里需要将文件上传到服务器
      // 由于后端API使用文件路径，这里仅演示流程
      const filePath = file.path || file.name
      await taskStore.createTask(filePath, 'auto_process', true)
    }
    
    ElMessage.success(`成功添加 ${selectedFiles.value.length} 个任务`)
    selectedFiles.value = []
    emit('upload-success')
  } catch (error) {
    ElMessage.error('添加任务失败: ' + error.message)
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.file-uploader {
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background-color: #f8fafc;
}

.file-uploader:hover,
.file-uploader.drag-over {
  border-color: #3b82f6;
  background-color: #eff6ff;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-icon {
  color: #94a3b8;
  margin-bottom: 16px;
}

.upload-title {
  font-size: 18px;
  font-weight: 500;
  color: #334155;
  margin: 0 0 8px;
}

.upload-desc {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.selected-files {
  margin-top: 24px;
  width: 100%;
  max-width: 600px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: white;
  border-radius: 6px;
  margin-bottom: 8px;
  border: 1px solid #e2e8f0;
}

.file-name {
  flex: 1;
  font-size: 14px;
  color: #334155;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #64748b;
}

.upload-btn {
  margin-top: 16px;
}
</style>
