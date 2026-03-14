import axios from 'axios'

const API_BASE = '/api'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json; charset=utf-8'
  }
})

apiClient.interceptors.response.use(
  response => response,
  error => {
    const detail = error.response?.data?.detail || error.message || '未知错误'
    console.error('[API Error]', error.config?.url, detail)
    return Promise.reject(error)
  }
)

export const taskApi = {
  list: async (status = null) => {
    const params = status ? { status } : {}
    const response = await apiClient.get('/tasks', { params })
    return response.data
  },

  get: async (taskId) => {
    const response = await apiClient.get(`/tasks/${taskId}`)
    return response.data
  },

  create: async (sourcePath, taskType = 'auto_process', autoClassify = true) => {
    const response = await apiClient.post('/tasks', {
      source_path: sourcePath,
      task_type: taskType,
      auto_classify: autoClassify
    })
    return response.data
  },

  pause: async (taskId) => {
    const response = await apiClient.post(`/tasks/${taskId}/pause`)
    return response.data
  },

  resume: async (taskId) => {
    const response = await apiClient.post(`/tasks/${taskId}/resume`)
    return response.data
  },

  cancel: async (taskId) => {
    const response = await apiClient.post(`/tasks/${taskId}/cancel`)
    return response.data
  }
}

export const configApi = {
  get: async () => {
    const response = await apiClient.get('/config')
    return response.data
  },

  save: async (configData) => {
    const response = await apiClient.post('/config', configData)
    return response.data
  }
}

export const watcherApi = {
  status: async () => {
    const response = await apiClient.get('/watcher/status')
    return response.data
  },

  start: async () => {
    const response = await apiClient.post('/watcher/start')
    return response.data
  },

  stop: async () => {
    const response = await apiClient.post('/watcher/stop')
    return response.data
  }
}

export const scanApi = {
  scan: async () => {
    const response = await apiClient.post('/scan')
    return response.data
  }
}

export const passwordApi = {
  list: async (params = {}) => {
    const response = await apiClient.get('/passwords', { params })
    return response.data
  },

  create: async (data) => {
    const response = await apiClient.post('/passwords', {
      rjcode: data.rjcode || null,
      filename: data.filename || null,
      password: data.password,
      description: data.description || null,
      source: data.source || 'manual'
    })
    return response.data
  },

  update: async (id, data) => {
    const response = await apiClient.put(`/passwords/${id}`, data)
    return response.data
  },

  delete: async (id) => {
    const response = await apiClient.delete(`/passwords/${id}`)
    return response.data
  },

  batchCreate: async (entries) => {
    const response = await apiClient.post('/passwords/batch', entries)
    return response.data
  },

  importFromText: async (text) => {
    const response = await apiClient.post('/passwords/import-from-text', { text })
    return response.data
  },

  findForArchive: async (archivePath) => {
    const response = await apiClient.get('/passwords/find-for-archive', {
      params: { archive_path: archivePath }
    })
    return response.data
  }
}

export const logApi = {
  get: async (lines = 100) => {
    const response = await apiClient.get('/logs', { params: { lines } })
    return response.data
  }
}

export const conflictApi = {
  list: async () => {
    const response = await apiClient.get('/conflicts')
    return response.data
  },

  resolve: async (conflictId, action) => {
    const response = await apiClient.post(`/conflicts/${conflictId}/resolve`, { action })
    return response.data
  },

  enhancedCheck: async (rjcode, options = {}) => {
    const response = await apiClient.post('/conflicts/enhanced-check', {
      rjcode,
      check_linked_works: options.checkLinkedWorks ?? true,
      cue_languages: options.cueLanguages ?? ['CHI_HANS', 'CHI_HANT', 'ENG']
    })
    return response.data
  }
}

export const processedArchiveApi = {
  list: async (params = {}) => {
    const response = await apiClient.get('/processed-archives', { params })
    return response.data
  },

  scan: async () => {
    const response = await apiClient.post('/processed-archives/scan')
    return response.data
  },

  reprocess: async (archiveId) => {
    const response = await apiClient.post(`/processed-archives/${archiveId}/reprocess`)
    return response.data
  }
}

export const libraryApi = {
  listFiles: async () => {
    const response = await apiClient.get('/library/files')
    return response.data
  },

  rename: async (path, newName) => {
    const response = await apiClient.post('/library/rename', { path, new_name: newName })
    return response.data
  },

  apiRename: async (path) => {
    const response = await apiClient.post('/library/api-rename', { path })
    return response.data
  },

  delete: async (path, confirmed = false) => {
    const response = await apiClient.post('/library/delete', { path, confirmed })
    return response.data
  },

  openFolder: async (path, forceLocal = false) => {
    const response = await apiClient.post('/library/open-folder', { path, force_local: forceLocal })
    return response.data
  }
}

export const existingFolderApi = {
  list: async () => {
    const response = await apiClient.get('/existing-folders')
    return response.data
  },

  scan: async (checkDuplicates = true, forceRefresh = false) => {
    const response = await apiClient.post('/existing-folders/scan', null, {
      params: { check_duplicates: checkDuplicates, force_refresh: forceRefresh }
    })
    return response
  },

  checkDuplicates: async (folders, options = {}) => {
    const response = await apiClient.post('/existing-folders/check-duplicates', {
      folders,
      check_linked_works: options.checkLinkedWorks ?? true,
      cue_languages: options.cueLanguages ?? ['CHI_HANS', 'CHI_HANT', 'ENG']
    })
    return response.data
  },

  process: async (folders, autoClassify = true) => {
    const response = await apiClient.post('/existing-folders/process', {
      folders,
      auto_classify: autoClassify
    })
    return response.data
  },

  delete: async (path) => {
    const response = await apiClient.post('/existing-folders/delete', { path })
    return response.data
  },

  processWithResolution: async (folderPath, resolution, autoClassify = true) => {
    const response = await apiClient.post('/existing-folders/process-with-resolution', {
      folder_path: folderPath,
      resolution,
      auto_classify: autoClassify
    })
    return response.data
  },

  refreshCache: async () => {
    const response = await apiClient.post('/existing-folders/refresh-cache')
    return response.data
  },

  clearCache: async () => {
    const response = await apiClient.post('/existing-folders/clear-cache')
    return response.data
  }
}

export const cleanupApi = {
  password: {
    status: async () => {
      const response = await apiClient.get('/password-cleanup/status')
      return response.data
    },

    preview: async () => {
      const response = await apiClient.get('/password-cleanup/preview')
      return response.data
    },

    run: async () => {
      const response = await apiClient.post('/password-cleanup/run')
      return response.data
    },

    history: async (limit = 50) => {
      const response = await apiClient.get('/password-cleanup/history', { params: { limit } })
      return response.data
    },

    restart: async () => {
      const response = await apiClient.post('/password-cleanup/restart')
      return response.data
    }
  },

  archive: {
    status: async () => {
      const response = await apiClient.get('/processed-archive-cleanup/status')
      return response.data
    },

    preview: async () => {
      const response = await apiClient.get('/processed-archive-cleanup/preview')
      return response.data
    },

    run: async () => {
      const response = await apiClient.post('/processed-archive-cleanup/run')
      return response.data
    },

    history: async (limit = 50) => {
      const response = await apiClient.get('/processed-archive-cleanup/history', { params: { limit } })
      return response.data
    },

    restart: async () => {
      const response = await apiClient.post('/processed-archive-cleanup/restart')
      return response.data
    }
  }
}

export const pathMappingApi = {
  config: async () => {
    const response = await apiClient.get('/path-mapping/config')
    return response.data
  },

  save: async (data) => {
    const response = await apiClient.post('/path-mapping/config', data)
    return response.data
  },

  test: async (path) => {
    const response = await apiClient.post('/path-mapping/test', { path })
    return response.data
  }
}

export const kikoeruApi = {
  config: async () => {
    const response = await apiClient.get('/kikoeru-server/config')
    return response.data
  },

  saveConfig: async (config) => {
    const response = await apiClient.post('/kikoeru-server/config', config)
    return response.data
  },

  testConnection: async () => {
    const response = await apiClient.post('/kikoeru-server/test')
    return response.data
  },

  check: async (rjcode, checkLinkages = true, cueLanguages = 'CHI_HANS CHI_HANT ENG JPN') => {
    const response = await apiClient.post('/kikoeru-server/check', null, {
      params: { rjcode, check_linkages: checkLinkages, cue_languages: cueLanguages }
    })
    return response.data
  },

  clearCache: async () => {
    const response = await apiClient.post('/kikoeru-server/clear-cache')
    return response.data
  },

  linkedWorks: async (rjcode, options = {}) => {
    const response = await apiClient.get(`/linked-works/${rjcode}`, {
      params: {
        include_full_linkage: options.includeFullLinkage ?? true,
        cue_languages: options.cueLanguages ?? 'CHI_HANS,CHI_HANT,ENG'
      }
    })
    return response.data
  },

  checkLibrary: async (rjcode, cueLanguages = 'CHI_HANS,CHI_HANT,ENG') => {
    const response = await apiClient.get(`/linked-works/${rjcode}/check-library`, {
      params: { cue_languages: cueLanguages }
    })
    return response.data
  },

  searchConfigs: async () => {
    const response = await apiClient.get('/kikoeru-configs')
    return response.data
  },

  createSearchConfig: async (data) => {
    const response = await apiClient.post('/kikoeru-configs', data)
    return response.data
  },

  updateSearchConfig: async (configId, data) => {
    const response = await apiClient.put(`/kikoeru-configs/${configId}`, data)
    return response.data
  },

  deleteSearchConfig: async (configId) => {
    const response = await apiClient.delete(`/kikoeru-configs/${configId}`)
    return response.data
  }
}

export const healthApi = {
  check: async () => {
    const response = await apiClient.get('/health')
    return response.data
  }
}

export const asmrSyncApi = {
  scan: async (folderPath) => {
    const response = await apiClient.post('/asmr-sync/scan', { folder_path: folderPath })
    return response.data
  },

  preview: async (rjcode) => {
    const response = await apiClient.post('/asmr-sync/preview', { rjcode })
    return response.data
  },

  start: async (items, autoClassify = true) => {
    const response = await apiClient.post('/asmr-sync/start', {
      items,
      auto_classify: autoClassify
    })
    return response.data
  },

  status: async () => {
    const response = await apiClient.get('/asmr-sync/status')
    return response.data
  },

  getWaitingRetry: async () => {
    const response = await apiClient.get('/asmr-sync/waiting-retry')
    return response.data
  },

  pause: async (taskId) => {
    const response = await apiClient.post(`/asmr-sync/task/${taskId}/pause`)
    return response.data
  },

  resume: async (taskId) => {
    const response = await apiClient.post(`/asmr-sync/task/${taskId}/resume`)
    return response.data
  },

  retry: async (taskId) => {
    const response = await apiClient.post(`/asmr-sync/task/${taskId}/retry`)
    return response.data
  },

  retryWaiting: async (taskId) => {
    const response = await apiClient.post(`/asmr-sync/task/${taskId}/retry-waiting`)
    return response.data
  },

  deleteWaitingRetry: async (taskId) => {
    const response = await apiClient.delete(`/asmr-sync/task/${taskId}/waiting-retry`)
    return response.data
  }
}

export default {
  task: taskApi,
  config: configApi,
  watcher: watcherApi,
  scan: scanApi,
  password: passwordApi,
  log: logApi,
  conflict: conflictApi,
  processedArchive: processedArchiveApi,
  library: libraryApi,
  existingFolder: existingFolderApi,
  cleanup: cleanupApi,
  pathMapping: pathMappingApi,
  kikoeru: kikoeruApi,
  health: healthApi,
  asmrSync: asmrSyncApi
}