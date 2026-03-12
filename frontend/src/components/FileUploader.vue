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
      style="display: none"
      @change="handleFileSelect"
    />

    <div class="upload-content">
      <el-icon :size="64" class="upload-icon"><Upload /></el-icon>
      <h3 class="upload-title">拖拽文件到此处或点击上传</h3>
      <p class="upload-desc">支持多种文件格式</p>

      <div v-if="displayFiles.length > 0" class="selected-files">
        <!-- 显示分组后的文件 -->
        <div v-for="(group, index) in displayFiles" :key="group._uid" class="file-item">
          <el-icon><Document /></el-icon>
          <span class="file-name">
            {{ group.displayName }}
            <el-tag v-if="group.isVolumeGroup" type="warning" size="small" class="volume-tag">
              {{ group.fileCount }} 个分卷
            </el-tag>
          </span>
          <span class="file-size">{{ formatFileSize(group.totalSize) }}</span>
        </div>

        <el-button
          type="primary"
          size="large"
          :loading="uploading"
          @click.stop="startUpload"
          class="upload-btn"
        >
          开始处理 ({{ displayFiles.length }} 个任务)
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Upload, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['upload-success'])

const fileInput = ref(null)
const isDragOver = ref(false)
const selectedFiles = ref([])
const uploading = ref(false)

// 生成分卷组显示名称
function getVolumeBaseName(filename) {
  // 匹配 .z01, .z02 等 ZIP 分卷
  const zipMatch = filename.match(/^(.+)\.z\d{2}$/i)
  if (zipMatch) return zipMatch[1]

  // 匹配 .part1.rar, .part2.rar 等 RAR 分卷
  const rarMatch = filename.match(/^(.+)\.part\d+\.(rar|7z|zip|exe)$/i)
  if (rarMatch) return rarMatch[1]

  // 匹配 .7z.001, .7z.002 等 7z 分卷
  const sevenZMatch = filename.match(/^(.+\.(7z|zip|rar))\.\d{3}$/i)
  if (sevenZMatch) return sevenZMatch[1]

  return null
}

// 检测是否是分卷文件（包括 .zip 主文件）
function getVolumeGroupInfo(filename, allFiles) {
  // 首先检查是否是标准分卷格式
  const baseName = getVolumeBaseName(filename)
  if (baseName) {
    return { baseName, isVolume: true }
  }

  // 检查是否是 ZIP 分卷的主文件 (.zip)
  // 如果存在对应的 .z01 文件，则这个 .zip 也是分卷的一部分
  if (filename.toLowerCase().endsWith('.zip')) {
    const nameWithoutExt = filename.slice(0, -4) // 去掉 .zip
    // 检查是否有对应的 .z01 文件
    const hasVolumeFiles = allFiles.some(f =>
      f.name.toLowerCase() === `${nameWithoutExt.toLowerCase()}.z01` ||
      f.name.toLowerCase().match(new RegExp(`^${nameWithoutExt.toLowerCase()}\\.z\\d{2}$`))
    )
    if (hasVolumeFiles) {
      return { baseName: nameWithoutExt, isVolume: true }
    }
  }

  return { baseName: null, isVolume: false }
}

// 检测是否是分卷文件（简单版本，用于判断是否显示分卷标签）
function isVolumeFile(filename) {
  return getVolumeBaseName(filename) !== null
}

// 计算分组后的显示文件
const displayFiles = computed(() => {
  const groups = new Map()
  const singles = []
  const allFiles = selectedFiles.value

  // 第一遍：收集所有分卷基础名称
  const volumeBaseNames = new Set()
  allFiles.forEach(file => {
    const baseName = getVolumeBaseName(file.name)
    if (baseName) {
      volumeBaseNames.add(baseName.toLowerCase())
    }
  })

  // 检查 .zip 文件是否有对应的分卷文件
  allFiles.forEach(file => {
    if (file.name.toLowerCase().endsWith('.zip')) {
      const nameWithoutExt = file.name.slice(0, -4)
      if (volumeBaseNames.has(nameWithoutExt.toLowerCase())) {
        // 这个 .zip 是分卷的一部分
        volumeBaseNames.add(file.name.toLowerCase()) // 添加完整名称用于匹配
      }
    }
  })

  allFiles.forEach(file => {
    const nameLower = file.name.toLowerCase()

    // 检查是否是分卷文件 (.z01, .part1.rar 等)
    let baseName = getVolumeBaseName(file.name)

    // 如果是 .zip 文件，检查是否有对应的分卷
    if (!baseName && nameLower.endsWith('.zip')) {
      const nameWithoutExt = file.name.slice(0, -4)
      if (volumeBaseNames.has(nameWithoutExt.toLowerCase())) {
        baseName = nameWithoutExt
      }
    }

    if (baseName) {
      // 是分卷文件
      const groupKey = baseName.toLowerCase()
      if (!groups.has(groupKey)) {
        groups.set(groupKey, {
          _uid: `group_${baseName}_${Date.now()}`,
          displayName: baseName,
          isVolumeGroup: true,
          fileCount: 0,
          totalSize: 0,
          files: []
        })
      }
      const group = groups.get(groupKey)
      group.files.push(file)
      group.totalSize += file.size
      group.fileCount = group.files.length
    } else {
      // 非分卷文件
      singles.push({
        _uid: file._uid,
        displayName: file.name,
        isVolumeGroup: false,
        fileCount: 1,
        totalSize: file.size,
        files: [file]
      })
    }
  })

  // 合并组和非分卷文件
  return [...groups.values(), ...singles]
})

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
  e.stopPropagation() // 阻止事件冒泡
  isDragOver.value = false
  const files = Array.from(e.dataTransfer.files)
  addFiles(files)
}

function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  addFiles(files)
}

// 生成唯一ID的计数器
let uidCounter = 0

function addFiles(files) {
  // 接受所有文件，不进行扩展名验证
  const validFiles = files

  if (validFiles.length === 0) {
    ElMessage.warning('没有可添加的文件')
    return
  }

  // 为每个文件添加唯一ID，同时保留原始 File 对象的引用
  const filesWithUid = validFiles.map(file => ({
    _file: file,  // 保留原始 File 对象
    name: file.name,
    size: file.size,
    lastModified: file.lastModified,
    _uid: `file_${Date.now()}_${uidCounter++}`
  }))

  // 过滤掉已经在列表中的文件（基于名称和大小）
  const newFiles = filesWithUid.filter(newFile =>
    !selectedFiles.value.some(existingFile =>
      existingFile.name === newFile.name && existingFile.size === newFile.size
    )
  )

  if (newFiles.length > 0) {
    selectedFiles.value = [...selectedFiles.value, ...newFiles]
    ElMessage.success(`添加了 ${newFiles.length} 个文件`)
  } else {
    ElMessage.info('所有文件都已在列表中')
  }
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
    // 始终通过上传文件内容处理，因为浏览器环境中的 file.path 可能不可靠
    // 即使在 Electron 等桌面环境中，也通过上传确保文件内容完整传输
    const formData = new FormData()

    for (const file of selectedFiles.value) {
      formData.append('files', file._file)
    }

    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error(`上传失败: ${response.statusText}`)
    }

    const result = await response.json()
    ElMessage.success(result.message)

    selectedFiles.value = []
    emit('upload-success')
  } catch (error) {
    ElMessage.error('处理失败: ' + error.message)
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

.volume-tag {
  margin-left: 8px;
  vertical-align: middle;
}
</style>
