import { defineStore } from 'pinia'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const API_BASE = '/api'

export const useTaskStore = defineStore('tasks', {
  state: () => ({
    tasks: [],
    currentTask: null,
    loading: false
  }),
  
  getters: {
    pendingTasks: (state) => state.tasks.filter(t => t.status === 'pending'),
    processingTasks: (state) => state.tasks.filter(t => t.status === 'processing'),
    completedTasks: (state) => state.tasks.filter(t => t.status === 'completed' || t.status === 'failed')
  },
  
  actions: {
    async fetchTasks(status = null) {
      try {
        this.loading = true
        const params = status ? { status } : {}
        const response = await axios.get(`${API_BASE}/tasks`, { params })
        this.tasks = response.data
      } catch (error) {
        console.error('获取任务失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },
    
    async createTask(sourcePath, taskType = 'auto_process', autoClassify = true) {
      try {
        const response = await axios.post(`${API_BASE}/tasks`, {
          source_path: sourcePath,
          task_type: taskType,
          auto_classify: autoClassify
        }, {
          headers: {
            'Content-Type': 'application/json; charset=utf-8'
          }
        })
        return response.data
      } catch (error) {
        console.error('创建任务失败:', error)
        throw error
      }
    },
    
    async pauseTask(taskId) {
      try {
        await axios.post(`${API_BASE}/tasks/${taskId}/pause`)
        ElMessage.success('任务已暂停')
        // 延迟刷新以确保状态已更新
        setTimeout(() => this.fetchTasks(), 500)
      } catch (error) {
        console.error('暂停任务失败:', error)
        ElMessage.error('暂停任务失败: ' + (error.response?.data?.detail || error.message))
        throw error
      }
    },
    
    async resumeTask(taskId) {
      try {
        await axios.post(`${API_BASE}/tasks/${taskId}/resume`)
        ElMessage.success('任务已恢复')
        // 延迟刷新以确保状态已更新
        setTimeout(() => this.fetchTasks(), 500)
      } catch (error) {
        console.error('恢复任务失败:', error)
        ElMessage.error('恢复任务失败: ' + (error.response?.data?.detail || error.message))
        throw error
      }
    },
    
    async cancelTask(taskId) {
      try {
        await axios.post(`${API_BASE}/tasks/${taskId}/cancel`)
        ElMessage.success('任务已取消')
        // 延迟刷新以确保状态已更新
        setTimeout(() => this.fetchTasks(), 500)
      } catch (error) {
        console.error('取消任务失败:', error)
        ElMessage.error('取消任务失败: ' + (error.response?.data?.detail || error.message))
        throw error
      }
    }
  }
})

export const useConfigStore = defineStore('config', {
  state: () => ({
    config: null,
    loading: false
  }),
  
  actions: {
    async fetchConfig() {
      try {
        this.loading = true
        const response = await axios.get(`${API_BASE}/config`)
        this.config = response.data
      } catch (error) {
        console.error('获取配置失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    }
  }
})

export const useWatcherStore = defineStore('watcher', {
  state: () => ({
    status: {
      is_running: false,
      watch_path: '',
      pending_files: []
    }
  }),
  
  actions: {
    async fetchStatus() {
      try {
        const response = await axios.get(`${API_BASE}/watcher/status`)
        this.status = response.data
      } catch (error) {
        console.error('获取监视器状态失败:', error)
      }
    },
    
    async start() {
      try {
        await axios.post(`${API_BASE}/watcher/start`)
        await this.fetchStatus()
      } catch (error) {
        console.error('启动监视器失败:', error)
        throw error
      }
    },
    
    async stop() {
      try {
        await axios.post(`${API_BASE}/watcher/stop`)
        await this.fetchStatus()
      } catch (error) {
        console.error('停止监视器失败:', error)
        throw error
      }
    }
  }
})
