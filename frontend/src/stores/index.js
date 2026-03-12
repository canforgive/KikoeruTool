import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { taskApi, configApi, watcherApi } from '../api'

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
    async fetchTasks(status = null, showLoading = true) {
      try {
        if (showLoading) {
          this.loading = true
        }
        this.tasks = await taskApi.list(status)
      } catch (error) {
        console.error('获取任务失败:', error)
        throw error
      } finally {
        if (showLoading) {
          this.loading = false
        }
      }
    },

    async createTask(sourcePath, taskType = 'auto_process', autoClassify = true) {
      try {
        return await taskApi.create(sourcePath, taskType, autoClassify)
      } catch (error) {
        console.error('创建任务失败:', error)
        throw error
      }
    },

    async pauseTask(taskId) {
      try {
        await taskApi.pause(taskId)
        ElMessage.success('任务已暂停')
        setTimeout(() => this.fetchTasks(), 500)
      } catch (error) {
        console.error('暂停任务失败:', error)
        ElMessage.error('暂停任务失败: ' + (error.response?.data?.detail || error.message))
        throw error
      }
    },

    async resumeTask(taskId) {
      try {
        await taskApi.resume(taskId)
        ElMessage.success('任务已恢复')
        setTimeout(() => this.fetchTasks(), 500)
      } catch (error) {
        console.error('恢复任务失败:', error)
        ElMessage.error('恢复任务失败: ' + (error.response?.data?.detail || error.message))
        throw error
      }
    },

    async cancelTask(taskId) {
      try {
        await taskApi.cancel(taskId)
        ElMessage.success('任务已取消')
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
        this.config = await configApi.get()
      } catch (error) {
        console.error('获取配置失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    async saveConfig(configData) {
      try {
        this.loading = true
        const result = await configApi.save(configData)
        this.config = result.config || configData
        return result
      } catch (error) {
        console.error('保存配置失败:', error)
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
        this.status = await watcherApi.status()
      } catch (error) {
        console.error('获取监视器状态失败:', error)
      }
    },

    async start() {
      try {
        await watcherApi.start()
        await this.fetchStatus()
      } catch (error) {
        console.error('启动监视器失败:', error)
        throw error
      }
    },

    async stop() {
      try {
        await watcherApi.stop()
        await this.fetchStatus()
      } catch (error) {
        console.error('停止监视器失败:', error)
        throw error
      }
    }
  }
})