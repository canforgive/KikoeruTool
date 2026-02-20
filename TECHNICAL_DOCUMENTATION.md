# KikoeruTool 技术文档

> **版本**: v1.0.0  
> **更新日期**: 2024年  
> **用途**: DLsite 音声作品自动整理工具完整技术参考

---

## 📑 目录

1. [项目概述](#一项目概述)
2. [后端API文档](#二后端api文档)
3. [前端组件文档](#三前端组件文档)
4. [核心服务类](#四核心服务类)
5. [查重系统详解](#五查重系统详解)
   - 5.1 [查重系统架构](#51-查重系统架构)
   - 5.2 [查重流程](#52-查重流程)
   - 5.3 [冲突类型体系](#53-冲突类型体系)
   - 5.4 [语言优先级系统](#54-语言优先级系统)
   - 5.5 [智能解决方案推荐](#55-智能解决方案推荐)
   - 5.6 [分析报告生成](#56-分析报告生成)
   - 5.7 [前端查重交互](#57-前端查重交互)
   - 5.8 [查重缓存机制](#58-查重缓存机制)
6. [业务流程详解](#六业务流程详解)
7. [索引速查表](#七索引速查表)

---

## 一、项目概述

### 1.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │Dashboard│ │  Tasks  │ │Library  │ │Settings │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端 (FastAPI)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  API Routes  │  │ Task Engine  │  │   Services   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据层                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ SQLite   │  │ 文件系统 │  │ DLsite   │  │ 配置文件 │       │
│  │ Database │  │ (作品库) │  │   API    │  │ (config) │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Element Plus | 现代化SPA，响应式UI |
| 后端 | FastAPI + SQLAlchemy | 高性能API，ORM数据库操作 |
| 数据 | SQLite | 轻量级本地数据库 |
| 部署 | Docker + GHCR | 容器化部署，GitHub镜像仓库 |

### 1.3 项目目录结构

```
prekikoeru/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # API路由定义
│   │   ├── core/
│   │   │   ├── task_engine.py     # 任务引擎
│   │   │   ├── extract_service.py # 解压服务
│   │   │   ├── metadata_service.py# 元数据服务
│   │   │   ├── rename_service.py  # 重命名服务
│   │   │   ├── filter_service.py  # 过滤服务
│   │   │   ├── classifier.py      # 分类器
│   │   │   ├── duplicate_service.py# 查重服务
│   │   │   ├── dlsite_service.py  # DLsite API
│   │   │   ├── watcher.py         # 文件监视器
│   │   │   └── password_cleanup.py# 密码清理
│   │   ├── models/
│   │   │   └── database.py        # 数据库模型
│   │   └── config/
│   │       └── settings.py        # 配置管理
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── views/                 # 页面组件
│       │   ├── Dashboard.vue
│       │   ├── Tasks.vue
│       │   ├── Library.vue
│       │   ├── ExistingFolders.vue
│       │   └── Settings.vue
│       ├── stores/
│       │   └── index.js           # Pinia状态管理
│       └── router/
│           └── index.js           # 路由配置
└── Dockerfile
```

---

## 二、后端API文档

### 2.1 API概览

**基础URL**: `/api`  
**响应格式**: JSON  
**错误处理**: HTTP状态码 + 错误详情

### 2.2 任务管理API

#### 2.2.1 创建任务

```http
POST /api/tasks
Content-Type: application/json
```

**请求体**:
```json
{
  "source_path": "/input/RJ123456.zip",
  "task_type": "auto_process",
  "auto_classify": true
}
```

**响应**:
```json
{
  "id": "task-uuid",
  "type": "auto_process",
  "status": "pending",
  "source_path": "/input/RJ123456.zip",
  "progress": 0,
  "current_step": "等待处理"
}
```

**任务类型**:
| 类型 | 说明 |
|------|------|
| `auto_process` | 自动处理（解压→元数据→重命名→过滤→分类） |
| `extract` | 仅解压 |
| `metadata` | 仅获取元数据 |
| `rename` | 仅重命名 |
| `filter` | 仅过滤 |
| `process_existing_folder` | 处理已有文件夹 |

#### 2.2.2 获取任务列表

```http
GET /api/tasks?status=processing
```

**查询参数**:
- `status`: `pending` | `processing` | `completed` | `failed`

**响应**: TaskResponse 数组

#### 2.2.3 任务控制

```http
POST /api/tasks/{task_id}/pause     # 暂停任务
POST /api/tasks/{task_id}/resume    # 恢复任务
POST /api/tasks/{task_id}/cancel    # 取消任务
GET  /api/tasks/{task_id}           # 获取任务详情
```

### 2.3 配置管理API

#### 2.3.1 获取配置

```http
GET /api/config
```

**响应**:
```json
{
  "storage": {
    "input_path": "/input",
    "temp_path": "/temp",
    "library_path": "/library",
    "processed_archives_path": "/processed",
    "existing_folders_path": "/existing"
  },
  "processing": {
    "max_workers": 2,
    "auto_repair_extension": true,
    "verify_after_extract": true,
    "extract_nested_archives": true,
    "max_nested_depth": 3,
    "password_list": []
  },
  "watcher": {
    "enabled": true,
    "scan_interval": 30,
    "auto_start": false,
    "auto_classify": true,
    "delete_after_process": false
  },
  "filter": {
    "enabled": true,
    "filter_dir": true,
    "rules": []
  },
  "metadata": {
    "locale": "zh-cn",
    "cache_enabled": true,
    "fetch_cover": true,
    "make_folder_icon": false,
    "http_proxy": ""
  },
  "rename": {
    "template": "{rjcode} {work_name}",
    "date_format": "%Y-%m-%d",
    "exclude_square_brackets": true,
    "illegal_char_to_full_width": true,
    "flatten_single_subfolder": true,
    "flatten_depth": 1,
    "remove_empty_folders": true
  },
  "classification": [],
  "password_cleanup": {
    "enabled": true,
    "cron_expression": "0 0 * * 0",
    "max_use_count": 10,
    "preserve_days": 365,
    "exclude_sources": ["manual"]
  },
  "processed_archive_cleanup": {
    "enabled": true,
    "strategy": "age",
    "preserve_days": 180,
    "max_count": 1000,
    "max_size_gb": 100,
    "exclude_reprocessing": true
  },
  "path_mapping": {
    "enabled": false,
    "open_mode": "direct",
    "rules": []
  }
}
```

#### 2.3.2 更新配置

```http
POST /api/config
Content-Type: application/json

[Config Object]
```

### 2.4 文件夹监视器API

```http
POST /api/watcher/start     # 启动监视器
POST /api/watcher/stop      # 停止监视器
GET  /api/watcher/status    # 获取状态
POST /api/scan              # 手动扫描输入目录
```

### 2.5 问题作品API

```http
GET  /api/conflicts                    # 获取问题作品列表
POST /api/conflicts/{id}/resolve       # 解决冲突
POST /api/conflicts/enhanced-check     # 增强查重检查
```

**冲突解决请求体**:
```json
{
  "action": "KEEP_NEW"
}
```

**动作类型**:
- `KEEP_NEW`: 保留新版，删除旧版
- `KEEP_OLD`: 保留旧版，删除新版
- `MERGE`: 合并两个版本
- `SKIP`: 跳过处理

### 2.6 库存管理API

```http
GET  /api/library/files           # 获取库文件列表
POST /api/library/rename          # 重命名
POST /api/library/api-rename      # API重命名（重新获取元数据）
POST /api/library/delete          # 删除
POST /api/library/open-folder     # 打开文件夹
```

### 2.7 已有文件夹处理API

```http
GET  /api/existing-folders                           # 获取列表
POST /api/existing-folders/scan                      # 扫描（支持NDJSON流）
POST /api/existing-folders/refresh-cache             # 刷新缓存
POST /api/existing-folders/clear-cache               # 清除缓存
POST /api/existing-folders/check-duplicates          # 查重检查
POST /api/existing-folders/process                   # 批量处理
POST /api/existing-folders/delete                    # 删除文件夹
POST /api/existing-folders/process-with-resolution   # 带解决方案处理
```

**NDJSON流式扫描示例**:
```javascript
const response = await fetch('/api/existing-folders/scan?check_duplicates=true', {
  method: 'POST'
});
const reader = response.body.getReader();
// 逐行读取NDJSON数据
```

### 2.8 密码库API

```http
GET    /api/passwords                    # 获取密码列表
POST   /api/passwords                    # 创建密码
PUT    /api/passwords/{id}               # 更新密码
DELETE /api/passwords/{id}               # 删除密码
POST   /api/passwords/batch              # 批量导入
POST   /api/passwords/import-from-text   # 从文本导入
GET    /api/passwords/find-for-archive   # 查找压缩包密码
```

### 2.9 日志API

```http
GET /api/logs?lines=200    # 获取最近N行日志
```

---

## 三、前端组件文档

### 3.1 组件概览

| 组件 | 路径 | 功能 | 关键特性 |
|------|------|------|----------|
| Dashboard | `views/Dashboard.vue` | 仪表盘首页 | 统计、快捷操作、归档管理 |
| Tasks | `views/Tasks.vue` | 任务队列 | 状态筛选、任务控制 |
| Conflicts | `views/Conflicts.vue` | 问题作品 | 冲突解决、批量操作 |
| ExistingFolders | `views/ExistingFolders.vue` | 已有文件夹 | 查重、处理、缓存 |
| Library | `views/Library.vue` | 库存管理 | 重命名、API重命名、删除 |
| Settings | `views/Settings.vue` | 系统设置 | 全配置管理 |
| PasswordVault | `views/PasswordVault.vue` | 密码库 | 密码管理、智能清理 |
| Logs | `views/Logs.vue` | 日志查看 | 实时刷新、智能滚动 |

### 3.2 Dashboard.vue

**核心数据**:
```javascript
const stats = ref({
  pending: 0,      // 待处理
  processing: 0,   // 处理中
  completed: 0,    // 已完成
  failed: 0,       // 失败
  conflicts: 0     // 问题作品
});

const recentTasks = ref([]);    // 最近5条任务
const archives = ref([]);       // 已处理压缩包
```

**关键方法**:
- `refreshData()` - 每3秒轮询刷新
- `fetchProcessedArchives()` - 获取归档列表（支持搜索排序）
- `groupedArchives` (computed) - 智能合并分卷压缩包
- `reprocessArchive()` - 重新处理归档

### 3.3 Tasks.vue

**筛选逻辑**:
```javascript
const currentStatus = ref('');  // '' | 'pending' | 'processing' | 'completed'
```

**任务状态标签**:
| 状态 | 标签类型 | 中文 |
|------|----------|------|
| pending | info | 待处理 |
| processing | primary | 处理中 |
| paused | warning | 已暂停 |
| completed | success | 已完成 |
| failed | danger | 失败 |
| cancelled | info | 已取消 |

### 3.4 ExistingFolders.vue

**核心状态**:
```javascript
const folders = ref([]);           // 文件夹列表
const selectedFolders = ref([]);   // 选中项
const autoClassify = ref(true);    // 自动分类
const checkDuplicates = ref(true); // 检查重复
```

**两阶段扫描**:
1. **阶段1**: 快速列出所有文件夹（立即可见）
2. **阶段2**: 后台逐个查重（SSE流式更新）

**状态显示逻辑**:
```javascript
// 优先级从高到低
if (is_duplicate) return '冲突类型标签';
if (status === 'pending') return '等待检查...';
if (status === 'checking') return '检查中...';
return '无冲突';  // 包括缓存和已检查
```

**操作方法**:
- `handleProcessSingle(row)` - 处理单个文件夹
- `handleDeleteFolder(row)` - 删除文件夹
- `handleRefreshFolder(row)` - 强制刷新查重
- `handleProcessWithResolution()` - 带解决方案处理

### 3.5 Library.vue

**搜索和分页**:
```javascript
const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = ref(20);

const filteredFiles = computed(() => {
  // 按名称或RJ号搜索
});

const paginatedFiles = computed(() => {
  // 分页计算
});
```

**路径映射支持**:
```javascript
// 模式1: direct - 后端直接打开
// 模式2: mapped - 返回映射路径，前端处理

const mappedPathInfo = ref(null);

// 支持Tampermonkey直接打开
const tampermonkeyLoaded = ref(false);
window.addEventListener('kikoeru-tampermonkey-loaded', () => {
  tampermonkeyLoaded.value = true;
});
```

### 3.6 Settings.vue

**配置结构**:
```javascript
const config = ref({
  storage: {...},      // 存储路径
  processing: {...},   // 处理配置
  watcher: {...},      // 监视器
  filter: {...},       // 过滤规则
  metadata: {...},     // 元数据
  rename: {...},       // 重命名
  classification: [],  // 分类规则
  password_cleanup: {...},        // 密码清理
  processed_archive_cleanup: {...}, // 压缩包清理
  path_mapping: {...}  // 路径映射
});
```

**分类规则类型**:
- `none` - 无子目录
- `maker` - 按社团名
- `series` - 按系列名
- `rjcode` - 按RJ号范围
- `date` - 按发布日期

---

## 四、核心服务类

### 4.1 TaskEngine - 任务引擎

**位置**: `backend/app/core/task_engine.py`

**类结构**:
```python
class TaskEngine:
    def __init__(self, max_workers=2):
        self.max_workers = max_workers
        self.tasks = {}           # 任务字典
        self.executor = None      # 线程池
        self._processing_rjcodes = set()  # 正在处理的RJ号
    
    def submit(self, task: Task) -> Task:
        """提交任务到队列"""
    
    def start(self):
        """启动任务引擎"""
    
    def stop(self):
        """停止任务引擎"""
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
    
    def is_rjcode_processing(self, rjcode: str) -> bool:
        """检查RJ号是否正在处理（防并发）"""
```

**Task类**:
```python
class Task:
    id: str              # 任务ID
    type: TaskType       # 任务类型
    status: TaskStatus   # 任务状态
    source_path: str     # 源路径
    output_path: str     # 输出路径
    progress: int        # 进度(0-100)
    current_step: str    # 当前步骤
    error_message: str   # 错误信息
    metadata: dict       # 元数据
    created_at: datetime # 创建时间
    updated_at: datetime # 更新时间
```

### 4.2 ExtractService - 解压服务

**位置**: `backend/app/core/extract_service.py`

**核心方法**:
```python
class ExtractService:
    def extract(self, task: Task) -> Optional[str]:
        """
        解压压缩包
        返回: 解压后的目录路径
        """
    
    def _wait_file_stable(self, file_path: str, max_wait: int = 300):
        """等待文件写入完成（检测文件大小稳定）"""
    
    def _detect_volume_set(self, file_path: str) -> Optional[VolumeSet]:
        """检测分卷压缩包"""
    
    def _extract_nested_archives(self, directory: str, max_depth: int = 3):
        """递归解压嵌套压缩包"""
    
    def _get_passwords_for_archive(self, archive_path: str) -> List[str]:
        """从密码库获取可能的密码列表"""
```

**支持的格式**:
- ZIP, RAR, 7Z, TAR
- GZ, BZ2, XZ
- 自解压EXE

### 4.3 MetadataService - 元数据服务

**位置**: `backend/app/core/metadata_service.py`

**核心方法**:
```python
class MetadataService:
    def fetch(self, path: str, task: Task) -> dict:
        """
        获取作品元数据
        流程: 提取RJ号 → 查缓存 → 调API → 缓存结果
        """
    
    def _extract_rjcode(self, path: str) -> Optional[str]:
        """从路径提取RJ号（支持RJ/VJ/BJ格式）"""
    
    def _get_cached_metadata(self, rjcode: str) -> Optional[WorkMetadata]:
        """从数据库缓存获取元数据（30天过期）"""
    
    def _fetch_from_dlsite(self, rjcode: str) -> WorkMetadata:
        """从DLsite API获取元数据"""
    
    def _fetch_translated_title(self, rjcode: str, lang: str) -> Optional[str]:
        """获取翻译标题（优先中文）"""
```

**缓存策略**:
- TTL: 30天
- 缓存字段: 作品名、社团、CV、标签、封面URL等

### 4.4 RenameService - 重命名服务

**位置**: `backend/app/core/rename_service.py`

**核心方法**:
```python
class RenameService:
    def rename(self, path: str, task: Task) -> str:
        """
        重命名文件夹
        返回: 新路径
        """
    
    def _compile_name(self, metadata: WorkMetadata) -> str:
        """根据模板编译新名称"""
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理非法字符（支持转全角）"""
    
    def _flatten_single_subfolder(self, path: str) -> str:
        """扁平化单一层级子文件夹"""
    
    def remove_empty_folders(self, path: str, remove_root: bool = False):
        """递归移除空文件夹"""
```

**模板变量**:
| 变量 | 说明 | 示例 |
|------|------|------|
| `{rjcode}` | RJ号 | RJ123456 |
| `{work_name}` | 作品名 | 作品标题 |
| `{maker_id}` | 社团ID | RJ123 |
| `{maker_name}` | 社团名 | 社团名称 |
| `{release_date}` | 发布日期 | 2024-01-01 |
| `{cvs}` | CV列表 | (CV: 声优A, 声优B) |
| `{tags}` | 标签 | [标签1][标签2] |

### 4.5 FilterService - 过滤服务

**位置**: `backend/app/core/filter_service.py`

**核心方法**:
```python
class FilterService:
    def filter(self, path: str, task: Task):
        """应用过滤规则删除不需要的文件"""
    
    def _should_filter_file(self, file_path: str, rules: List[FilterRule]) -> bool:
        """判断是否应该过滤文件"""
    
    def _should_filter_dir(self, dir_path: str, rules: List[FilterRule]) -> bool:
        """判断是否应该过滤文件夹"""
    
    def _detect_audio_formats(self, path: str) -> dict:
        """检测音频格式分布（用于MP3特殊处理）"""
```

**MP3特殊逻辑**:
```python
# 如果文件夹中只有MP3格式，临时禁用MP3过滤规则
if only_mp3:
    disable_mp3_filter_rules()
```

### 4.6 SmartClassifier - 智能分类器

**位置**: `backend/app/core/classifier.py`

**核心方法**:
```python
class SmartClassifier:
    def check_duplicate_before_extract(self, rjcode: str, task: Task, engine: TaskEngine) -> bool:
        """
        解压前预检
        返回: True=可以继续, False=存在冲突
        """
    
    def classify_and_move(self, source_path: str, metadata: dict, task: Task) -> str:
        """
        智能分类并移动到库
        返回: 最终路径
        """
    
    def _check_existing(self, rjcode: str) -> Optional[dict]:
        """检查作品是否已存在于库"""
    
    def _apply_classification_rules(self, metadata: dict) -> str:
        """应用分类规则生成目标路径"""
    
    def _move_with_rename(self, source: str, target_dir: str) -> str:
        """移动文件/文件夹，处理重名"""
```

### 4.7 KikoeruDuplicateService - Kikoeru服务器查重服务

**位置**: `backend/app/core/kikoeru_duplicate_service.py`

**功能说明**: 通过 API 和 Token 访问本地部署的 Kikoeru 服务器进行查重，实现本地库和远程 Kikoeru 库的双重查重。

**核心方法**:
```python
class KikoeruDuplicateService:
    async def check_duplicate(
        self, 
        rjcode: str,
        use_cache: bool = True
    ) -> KikoeruCheckResult:
        """
        检查作品是否在 Kikoeru 服务器中
        调用 /api/search 接口进行查询
        """
    
    async def check_duplicates_batch(
        self, 
        rjcodes: List[str],
        use_cache: bool = True
    ) -> Dict[str, KikoeruCheckResult]:
        """批量检查多个 RJ 号"""
    
    async def test_connection(self) -> Dict[str, any]:
        """测试与 Kikoeru 服务器的连接"""
    
    def clear_cache(self):
        """清除查重缓存"""
```

**配置项**:
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | false | 是否启用 Kikoeru 查重 |
| `server_url` | string | "" | Kikoeru 服务器地址 |
| `api_token` | string | "" | API 访问令牌 |
| `timeout` | int | 10 | 请求超时(秒) |
| `cache_ttl` | int | 300 | 缓存时间(秒) |

**API 端点**:
```
GET    /api/kikoeru-server/config    # 获取配置
POST   /api/kikoeru-server/config    # 更新配置
POST   /api/kikoeru-server/test      # 测试连接
POST   /api/kikoeru-server/check     # 查重检查
POST   /api/kikoeru-server/clear-cache  # 清除缓存
```

**KikoeruCheckResult**:
```python
@dataclass
class KikoeruCheckResult:
    is_found: bool           # 是否找到
    rjcode: str             # RJ号
    work_id: int            # Kikoeru 作品ID
    title: str              # 作品标题
    circle_name: str        # 社团名
    tags: List[str]         # 标签列表
    total_count: int        # 搜索结果总数
    source: str            # 结果来源
    checked_at: datetime   # 检查时间
```

### 4.8 DuplicateService - 增强查重服务

**位置**: `backend/app/core/duplicate_service.py`

**功能说明**: 综合查重服务，集成本地查重、关联作品检测和 Kikoeru 服务器查重。

**核心方法**:
```python
class EnhancedDuplicateService:
    def __init__(self):
        self.dlsite_service = get_dlsite_service()
        self.kikoeru_service = get_kikoeru_service()  # 新增
    
    async def check_duplicate_enhanced(
        self, 
        rjcode: str, 
        check_linked_works: bool = True,
        cue_languages: List[str] = ["CHI_HANS", "CHI_HANT", "ENG"]
    ) -> DuplicateCheckResult:
        """
        综合查重检查流程:
        1. 本地直接重复检查
        2. 关联作品检查
        3. Kikoeru 服务器检查（如启用）
        """
    
    def _check_direct_duplicate(self, rjcode: str) -> Optional[dict]:
        """检查直接重复（相同RJ号）"""
    
    def _check_linked_works_in_library(
        self, 
        linked_works: Dict[str, LinkedWork],
        exclude_rjcode: str
    ) -> List[LinkedWorkInLibrary]:
        """检查关联作品是否在库中"""
    
    def _analyze_linked_works(...) -> dict:
        """分析关联作品关系，生成详细报告"""
    
    def get_conflict_resolution_options(self, check_result: DuplicateCheckResult) -> List[dict]:
        """获取推荐的冲突解决选项"""
```

**DuplicateCheckResult 扩展**:
```python
@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    direct_duplicate: Optional[Dict]
    linked_works_found: List[Dict]
    conflict_type: str                    # DUPLICATE, LINKED_WORK, etc.
    related_rjcodes: List[str]
    analysis_info: Dict
    kikoeru_result: Optional[KikoeruCheckResult]  # 新增: Kikoeru查重结果
```

**冲突类型**:
| 类型 | 说明 |
|------|------|
| `NONE` | 无冲突 |
| `DUPLICATE` | 直接重复（相同RJ号） |
| `LINKED_WORK_ORIGINAL` | 原作已存在 |
| `LINKED_WORK_TRANSLATION` | 翻译版已存在 |
| `LINKED_WORK_CHILD` | 子版本已存在 |
| `LINKED_WORK` | 其他关联作品 |
| `LANGUAGE_VARIANT` | 多语言版本 |
| `MULTIPLE_VERSIONS` | 多版本 |

### 4.8 DLsiteService - DLsite API服务

**位置**: `backend/app/core/dlsite_service.py`

**核心方法**:
```python
class DLsiteApiService:
    def get_translation_info(self, rjcode: str) -> TranslationInfo:
        """获取作品的翻译信息"""
    
    def get_linked_works(self, rjcode: str) -> Dict[str, LinkedWork]:
        """获取作品的关联作品"""
    
    def get_full_linkage(
        self, 
        rjcode: str,
        cue_languages: List[str] = ["CHI_HANS", "CHI_HANT", "ENG"]
    ) -> Dict[str, LinkedWork]:
        """获取完整关联链（递归）"""
    
    def get_work_info(self, rjcode: str) -> Optional[dict]:
        """获取作品详细信息"""
```

**TranslationInfo**:
```python
@dataclass
class TranslationInfo:
    is_original: bool      # 是否为原作品
    is_parent: bool        # 是否为翻译父级
    is_child: bool         # 是否为翻译子级
    parent_workno: str     # 父作品RJ号
    original_workno: str   # 原作品RJ号
    lang: str              # 语言代码
```

### 4.9 FolderWatcher - 文件监视器

**位置**: `backend/app/core/watcher.py`

**核心方法**:
```python
class FolderWatcher:
    def start(self):
        """启动监视器"""
    
    def stop(self):
        """停止监视器"""
    
    def _on_archive_detected(self, file_path: str):
        """检测到压缩包回调"""
    
    def _process_file(self, file_path: str):
        """处理文件（异步）"""
    
    def _is_archive(self, path: str) -> bool:
        """检查是否是压缩包（通过后缀和魔数）"""
    
    def _detect_archive_by_magic(self, path: str) -> bool:
        """通过魔数检测压缩文件"""
```

**魔数检测**:
```python
# ZIP: PK\x03\x04 或 PK\x05\x06
# RAR: Rar!\x1a\x07
# 7Z: 7z\xbc\xaf\x27\x1c
```

---

## 五、查重系统详解

Kikoeru 的查重系统是其核心功能之一，支持多层次、多维度的重复检测，特别针对 DLsite 音声作品的翻译版本和关联作品进行了优化。

### 5.1 查重系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    查重系统架构                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │  直接重复检测    │    │  关联作品检测    │                │
│  │  (相同RJ号)     │    │  (DLsite API)   │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                         │
│           └──────────┬───────────┘                         │
│                      ▼                                      │
│           ┌─────────────────┐                              │
│           │   冲突类型判定   │                              │
│           │  (7种冲突类型)  │                              │
│           └────────┬────────┘                              │
│                    ▼                                        │
│           ┌─────────────────┐                              │
│           │  智能解决方案推荐 │                              │
│           │  (语言优先级)   │                              │
│           └─────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 查重流程

#### 5.2.1 主查重流程

```python
async def check_duplicate_enhanced(
    self, 
    rjcode: str, 
    check_linked_works: bool = True,
    cue_languages: List[str] = ['CHI_HANS', 'CHI_HANT', 'ENG']
) -> DuplicateCheckResult:
```

**流程步骤**:

1. **直接重复检查**（相同 RJ 号）
   - 查询数据库 `LibrarySnapshot` 表
   - 扫描库存目录作为后备
   - 返回：`DUPLICATE` 冲突类型

2. **关联作品检查**（如启用）
   - 调用 `DLsiteService.get_full_linkage()` 获取完整关联链
   - 包含原作、翻译版本、子版本等
   - 检查这些关联作品是否在库中

3. **冲突类型判定**
   - 根据发现的作品类型确定具体冲突类型
   - 生成详细分析报告

4. **解决方案生成**
   - 基于语言优先级智能推荐
   - 返回多个选项供用户选择

#### 5.2.2 直接重复检测

```python
async def _check_direct_duplicate(self, rjcode: str) -> Optional[Dict]:
```

**检测逻辑**:
- **优先级1**: 查询 `LibrarySnapshot` 数据库表
- **优先级2**: 扫描库存目录（`library_path`）
- 匹配方式：RJ 号出现在文件夹名称中
- 返回信息：RJ号、路径、大小、文件数量

**过期清理**:
```python
if not os.path.exists(folder_path):
    # 路径不存在，清理过期记录
    db.delete(snapshot)
```

#### 5.2.3 关联作品检测

```python
async def _check_linked_works_in_library(
    self, 
    linked_works: Dict[str, LinkedWork], 
    exclude_rjcode: str
) -> List[LinkedWorkInLibrary]:
```

**检测范围**:
- 翻译父级（parent）
- 翻译子级（child）
- 原作品（original）
- 系列作品（series）

**作品类型定义**:
```python
@dataclass
class LinkedWork:
    workno: str           # RJ号
    work_type: str        # original/parent/child/series
    lang: str            # 语言代码
    parent_workno: str   # 父作品RJ号
    original_workno: str # 原作品RJ号
```

### 5.3 冲突类型体系

| 冲突类型 | 代码 | 说明 | 触发条件 |
|---------|------|------|----------|
| **无冲突** | `NONE` | 未发现重复 | 全新作品 |
| **直接重复** | `DUPLICATE` | 相同 RJ 号 | 库中已存在相同RJ号 |
| **原作已存在** | `LINKED_WORK_ORIGINAL` | 原作品在库中 | 当前是翻译版，原作已存在 |
| **翻译版已存在** | `LINKED_WORK_TRANSLATION` | 翻译版在库中 | 当前是原作，翻译版已存在 |
| **子版本已存在** | `LINKED_WORK_CHILD` | 子版本在库中 | 当前是父版本，子版本已存在 |
| **关联作品** | `LINKED_WORK` | 其他关联作品 | 存在系列或衍生作品 |
| **多语言版本** | `LANGUAGE_VARIANT` | 多语言版本冲突 | 同一作品多种语言 |
| **多版本** | `MULTIPLE_VERSIONS` | 多个版本存在 | 存在多个不同版本 |

### 5.4 语言优先级系统

#### 5.4.1 优先级定义

```python
def _get_lang_priority(self, lang: str) -> int:
    """数字越小优先级越高"""
    priorities = {
        'CHI_HANS': 1,   # 简体中文 - 最高
        'CHI_HANT': 2,   # 繁体中文
        'JPN': 3,        # 日文
        'ENG': 4,        # 英文
        'KO_KR': 5,      # 韩语
        'SPA': 6,        # 西班牙语
        'FRE': 7,        # 法语
        'GER': 8,        # 德语
        'RUS': 9,        # 俄语
        'THA': 10,       # 泰语
        'VIE': 11,       # 越南语
        'ITA': 12,       # 意大利语
        'POR': 13,       # 葡萄牙语
    }
    return priorities.get(lang, 99)  # 未知语言最低
```

#### 5.4.2 语言名称映射

```python
def _get_lang_name(self, lang: str) -> str:
    names = {
        'CHI_HANS': '简体中文',
        'CHI_HANT': '繁体中文',
        'JPN': '日文',
        'ENG': '英文',
        # ... 其他语言
    }
```

### 5.5 智能解决方案推荐

#### 5.5.1 直接重复场景

```python
if conflict_type == "DUPLICATE":
    options = [
        {
            'action': 'KEEP_NEW',
            'label': '保留新版',
            'description': '删除旧版本，保留新版本',
            'recommend': True  # 默认推荐
        },
        {
            'action': 'KEEP_OLD',
            'label': '保留旧版',
            'description': '删除新版本，保留现有版本'
        },
        {
            'action': 'MERGE',
            'label': '合并保留',
            'description': '保留两个版本，新版本添加编号后缀'
        },
        {
            'action': 'SKIP',
            'label': '抛弃新版',
            'description': '删除新版本，不做任何更改'
        }
    ]
```

#### 5.5.2 关联作品场景

**推荐算法**:
```python
# 获取当前作品和已存在作品的语言优先级
current_priority = self._get_lang_priority(current_lang)
existing_priority = self._get_lang_priority(best_existing_lang)

if current_priority < existing_priority:
    # 新版优先级更高（数字更小）
    recommend_action = 'KEEP_NEW'
elif current_priority > existing_priority:
    # 旧版优先级更高
    recommend_action = 'SKIP'
else:
    # 优先级相同
    recommend_action = 'KEEP_BOTH'
```

**可用选项**:
- **KEEP_NEW**: 保留新版，删除旧版（或已存在的低优先级版本）
- **SKIP**: 抛弃新版，保留现有版本
- **KEEP_BOTH**: 保留两个版本（新版本加语言标识或编号）
- **MERGE_LANG**: 合并语言版本（仅同一语言时可用）

#### 5.5.3 解决方案示例

**场景1**: 库中有日文版，新下载了简体中文版
```
推荐: KEEP_NEW（简体中文优先级 > 日文）
选项:
  1. 保留新版（简体中文）⭐ 推荐
     删除日文版，保留简体中文版
  
  2. 抛弃新版（保留日文）
     保留日文版，删除简体中文版
  
  3. 保留两者
     同时保留日文和简体中文版
```

**场景2**: 库中有简体中文版，新下载了繁体中文版
```
推荐: SKIP（简体中文优先级 > 繁体中文）
选项:
  1. 抛弃新版（保留简体中文）⭐ 推荐
     保留简体中文版，删除繁体中文版
  
  2. 保留新版（繁体中文）
     用繁体中文版替换简体中文版
  
  3. 保留两者
     同时保留两个中文版本
```

### 5.6 分析报告生成

#### 5.6.1 分析信息结构

```python
def _analyze_linked_works(...) -> Dict:
    return {
        'current_work': {
            'rjcode': current_rjcode,
            'work_type': 'translation',
            'lang': 'CHI_HANS'
        },
        'has_original': True,      # 是否有原作品
        'has_parent': False,       # 是否有翻译父级
        'has_child': True,         # 是否有翻译子级
        'has_translation': True,   # 是否有翻译版本
        'lang_stats': {
            'CHI_HANS': 2,         # 各语言版本数量
            'JPN': 1,
            'ENG': 1
        },
        'library_summary': [       # 库中已存在的作品
            {
                'rjcode': 'RJ654321',
                'work_type': 'original',
                'lang': 'JPN',
                'work_name': '原作品名称',
                'path': '/library/RJ654321'
            }
        ]
    }
```

### 5.7 前端查重交互

#### 5.7.1 查重状态显示

在 `ExistingFolders.vue` 中的状态显示逻辑：

```vue
<!-- 有冲突 -->
<el-tag v-if="row.duplicate_info && row.duplicate_info.is_duplicate" type="danger">
  {{ getConflictTypeLabel(row.duplicate_info.conflict_type) }}
</el-tag>

<!-- 无冲突 -->
<el-tag v-else type="success">
  无冲突
</el-tag>
```

#### 5.7.2 冲突详情对话框

显示内容：
- 当前作品信息（RJ号、名称、语言）
- 库中已存在的作品列表
- 详细的分析报告
- 推荐的解决方案选项
- 操作按钮组

#### 5.7.3 API调用

```javascript
// 查重检查
POST /api/existing-folders/check-duplicates
{
  "folders": ["/path/to/folder"],
  "check_linked_works": true,
  "cue_languages": ["CHI_HANS", "CHI_HANT", "ENG"]
}

// 带解决方案处理
POST /api/existing-folders/process-with-resolution
{
  "folder_path": "/path/to/folder",
  "resolution": "KEEP_NEW",
  "auto_classify": true
}
```

### 5.8 查重缓存机制

#### 5.8.1 缓存表结构

```sql
CREATE TABLE existing_folder_cache (
    id INTEGER PRIMARY KEY,
    folder_path TEXT UNIQUE NOT NULL,
    rjcode TEXT,
    folder_size INTEGER,
    file_count INTEGER,
    duplicate_info TEXT,  -- JSON格式存储查重结果
    last_checked_at TIMESTAMP,
    needs_refresh BOOLEAN DEFAULT 0
);
```

#### 5.8.2 缓存策略

- **首次扫描**: 执行完整查重，保存结果
- **后续扫描**: 
  - 检查 `needs_refresh` 标记
  - 如为 `false` 且缓存存在，直接返回缓存
  - 如为 `true` 或强制刷新，重新查重
- **刷新时机**:
  - 用户点击"强制刷新"
  - 手动触发 `refresh-cache` API
  - 定时任务（可配置）

### 5.9 使用示例

#### 5.9.1 基本查重检查

```python
from backend.app.core.duplicate_service import get_duplicate_service

service = get_duplicate_service()
result = await service.check_duplicate_enhanced(
    rjcode="RJ123456",
    check_linked_works=True,
    cue_languages=["CHI_HANS", "CHI_HANT"]
)

if result.is_duplicate:
    print(f"发现冲突: {result.conflict_type}")
    print(f"关联作品: {result.related_rjcodes}")
    
    # 获取解决方案
    options = await service.get_conflict_resolution_options(result)
    for opt in options:
        print(f"{opt['label']}: {opt['description']}")
        if opt.get('recommend'):
            print("  ⭐ 推荐")
```

#### 5.9.2 在任务处理中使用

```python
# 在 Classifier 中调用
classifier = SmartClassifier()
if classifier.check_duplicate_before_extract(rjcode, task, engine):
    # 发现冲突，添加到问题作品队列
    pass
else:
    # 无冲突，继续处理
    pass
```

---

## 六、业务流程详解

### 5.1 自动处理流程 (AUTO_PROCESS)

```
┌──────────────────────────────────────────────────────────────┐
│ 1. 文件检测 (Watcher/手动扫描)                                │
│    └─> 检测到压缩包文件                                      │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. 解压前预检 (Classifier.check_duplicate_before_extract)   │
│    ├─> 等待文件写入完成 (ExtractService._wait_file_stable)  │
│    ├─> 检测分卷组 (ExtractService._detect_volume_set)        │
│    └─> 检查RJ号是否已存在/正在处理                           │
│       └─> 如存在冲突，添加到问题作品队列                     │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼ (无冲突)
┌──────────────────────────────────────────────────────────────┐
│ 3. 解压 (ExtractService.extract)                             │
│    ├─> 从密码库获取密码列表                                  │
│    ├─> 尝试解压（带密码）                                    │
│    ├─> 递归解压嵌套压缩包                                    │
│    └─> 验证解压完整性                                        │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. 获取元数据 (MetadataService.fetch)                        │
│    ├─> 从文件夹名提取RJ号                                    │
│    ├─> 查本地缓存                                            │
│    ├─> 调DLsite API                                          │
│    └─> 缓存到数据库                                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. 重命名 (RenameService.rename)                             │
│    ├─> 根据模板编译新名称                                    │
│    ├─> 清理非法字符                                          │
│    ├─> 扁平化单层文件夹                                      │
│    └─> 移除空文件夹                                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. 过滤文件 (FilterService.filter)                           │
│    ├─> 检测音频格式分布                                      │
│    ├─> 应用过滤规则                                          │
│    └─> 删除匹配的文件/文件夹                                 │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. 智能分类移动 (SmartClassifier.classify_and_move)          │
│    ├─> 再次检查重复（增强查重）                              │
│    ├─> 应用分类规则                                          │
│    ├─> 移动并处理重名                                        │
│    └─> 更新库存快照                                          │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. 归档压缩包                                                │
│    └─> 移动到 processed_archives_path                        │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 9. 清理临时文件                                              │
│    └─> 删除解压临时目录                                      │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 增强查重流程

```
输入: RJ号
    │
    ▼
┌──────────────────┐
│ 1. 直接重复检查   │
│ (相同RJ号)       │
└────────┬─────────┘
         │ 未发现
         ▼
┌──────────────────┐
│ 2. 获取关联作品链 │
│ (DLsite API)     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. 检查关联作品   │
│ 是否在库中        │
└────────┬─────────┘
         │ 发现
         ▼
┌──────────────────┐
│ 4. 分析关系      │
│ - 原作vs翻译版   │
│ - 父级vs子级     │
│ - 语言优先级     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. 生成解决方案   │
│ - KEEP_NEW       │
│ - KEEP_OLD       │
│ - KEEP_BOTH      │
│ - MERGE          │
└────────┬─────────┘
         │
         ▼
输出: DuplicateCheckResult
```

### 5.3 已有文件夹处理流程

```
用户请求: 处理已有文件夹
    │
    ▼
┌──────────────────────┐
│ 1. 扫描文件夹         │
│ - 快速列出所有文件夹  │
│ - 提取RJ号            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 后台查重 (可选)    │
│ - 检查缓存            │
│ - 调用API查重         │
│ - SSE流式更新状态     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. 用户选择操作       │
├─ 无冲突              │
│  └─ 直接处理          │
├─ 有冲突              │
│  └─ 选择解决方案      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. 执行处理           │
│ - 创建处理任务        │
│ - 跳过后续的解压步骤  │
│ - 执行重命名→过滤→分类│
└──────────────────────┘
```

### 5.4 密码学习流程

```
解压尝试
    │
    ├─ 密码成功 ───┐
    │              ▼
    │    ┌────────────────┐
    │    │ 1. 记录密码    │
    │    │ - RJ号         │
    │    │ - 文件名       │
    │    │ - 密码         │
    │    │ - 使用次数+1   │
    │    └────────┬───────┘
    │             │
    │             ▼
    │    ┌────────────────┐
    │    │ 2. 下次解压    │
    │    │ - 匹配RJ号优先 │
    │    │ - 匹配文件名   │
    │    │ - 返回密码列表 │
    │    └────────────────┘
    │
    └─ 密码失败 ───> 尝试下一个密码
```

### 5.5 缓存机制

#### 5.5.1 元数据缓存

```
获取元数据请求
    │
    ▼
检查数据库缓存
    │
    ├─ 缓存存在且未过期(30天)
    │      │
    │      └─> 返回缓存数据
    │
    └─ 缓存不存在或已过期
           │
           ▼
    调用DLsite API
           │
           ▼
    保存到数据库
           │
           ▼
    返回新数据
```

#### 5.5.2 已有文件夹查重缓存

```
扫描文件夹
    │
    ▼
检查ExistingFolderCache表
    │
    ├─ 缓存存在且不需要刷新
    │      │
    │      └─> 使用缓存数据
    │         (status='cached')
    │
    └─ 需要刷新
           │
           ▼
    调用DuplicateService查重
           │
           ▼
    保存到缓存表
           │
           ▼
    返回新数据
           (status='checked')
```

---

## 七、索引速查表

### 6.1 API端点索引

| 功能模块 | HTTP方法 | URL | 说明 |
|----------|----------|-----|------|
| **健康检查** ||||
|| GET | `/api/health` | 服务健康状态 |
|| GET | `/health` | 简单健康检查 |
| **任务管理** ||||
|| GET | `/api/tasks` | 获取任务列表 |
|| POST | `/api/tasks` | 创建任务 |
|| GET | `/api/tasks/{id}` | 获取任务详情 |
|| POST | `/api/tasks/{id}/pause` | 暂停任务 |
|| POST | `/api/tasks/{id}/resume` | 恢复任务 |
|| POST | `/api/tasks/{id}/cancel` | 取消任务 |
| **配置管理** ||||
|| GET | `/api/config` | 获取配置 |
|| POST | `/api/config` | 更新配置 |
| **文件夹监视器** ||||
|| POST | `/api/watcher/start` | 启动监视器 |
|| POST | `/api/watcher/stop` | 停止监视器 |
|| GET | `/api/watcher/status` | 获取状态 |
|| POST | `/api/scan` | 手动扫描 |
| **密码库** ||||
|| GET | `/api/passwords` | 获取密码列表 |
|| POST | `/api/passwords` | 创建密码 |
|| PUT | `/api/passwords/{id}` | 更新密码 |
|| DELETE | `/api/passwords/{id}` | 删除密码 |
|| POST | `/api/passwords/batch` | 批量导入 |
|| GET | `/api/passwords/find-for-archive` | 查找压缩包密码 |
| **问题作品** ||||
|| GET | `/api/conflicts` | 获取问题作品列表 |
|| POST | `/api/conflicts/{id}/resolve` | 解决冲突 |
|| POST | `/api/conflicts/enhanced-check` | 增强查重检查 |
| **查重系统** ||||
|| POST | `/api/existing-folders/check-duplicates` | 查重检查 |
|| POST | `/api/existing-folders/process-with-resolution` | 带解决方案处理 |
|| GET | `/api/linked-works/{rjcode}` | 获取关联作品链 |
|| GET | `/api/linked-works/{rjcode}/check-library` | 检查库中关联作品 |
| **Kikoeru 服务器查重** ||||
|| GET | `/api/kikoeru-server/config` | 获取配置 |
|| POST | `/api/kikoeru-server/config` | 更新配置 |
|| POST | `/api/kikoeru-server/test` | 测试连接 |
|| POST | `/api/kikoeru-server/check` | 查重检查 |
|| POST | `/api/kikoeru-server/clear-cache` | 清除缓存 |
| **库存管理** ||||
|| GET | `/api/library/files` | 获取库文件列表 |
|| POST | `/api/library/rename` | 重命名 |
|| POST | `/api/library/api-rename` | API重命名 |
|| POST | `/api/library/delete` | 删除 |
|| POST | `/api/library/open-folder` | 打开文件夹 |
| **已有文件夹** ||||
|| GET | `/api/existing-folders` | 获取列表 |
|| POST | `/api/existing-folders/scan` | 扫描(NDJSON流) |
|| POST | `/api/existing-folders/process` | 批量处理 |
|| POST | `/api/existing-folders/check-duplicates` | 查重 |
|| POST | `/api/existing-folders/process-with-resolution` | 带解决方案处理 |
| **日志** ||||
|| GET | `/api/logs?lines={n}` | 获取日志 |

### 6.2 服务类索引

| 服务类 | 文件路径 | 核心功能 | 主要方法 |
|--------|----------|----------|----------|
| TaskEngine | `core/task_engine.py` | 任务调度管理 | `submit()`, `start()`, `pause_task()`, `cancel_task()` |
| ExtractService | `core/extract_service.py` | 压缩包解压 | `extract()`, `_detect_volume_set()`, `_extract_nested_archives()` |
| MetadataService | `core/metadata_service.py` | 元数据获取 | `fetch()`, `_extract_rjcode()`, `_fetch_from_dlsite()` |
| RenameService | `core/rename_service.py` | 重命名 | `rename()`, `_compile_name()`, `_flatten_single_subfolder()` |
| FilterService | `core/filter_service.py` | 文件过滤 | `filter()`, `_should_filter_file()` |
| SmartClassifier | `core/classifier.py` | 智能分类 | `classify_and_move()`, `_apply_classification_rules()` |
| KikoeruDuplicateService | `core/kikoeru_duplicate_service.py` | Kikoeru服务器查重 | `check_duplicate()` - 查询Kikoeru服务器<br>`check_duplicates_batch()` - 批量查询<br>`test_connection()` - 连接测试<br>`clear_cache()` - 清除缓存 |
| DuplicateService | `core/duplicate_service.py` | 增强查重服务 | `check_duplicate_enhanced()` - 主查重方法（集成本地+Kikoeru）<br>`_check_direct_duplicate()` - 直接重复检查<br>`_check_linked_works_in_library()` - 关联作品检查<br>`_analyze_linked_works()` - 关联作品分析<br>`get_conflict_resolution_options()` - 解决方案推荐<br>`_get_lang_priority()` - 语言优先级<br>`_get_lang_name()` - 语言名称映射 |
| DLsiteService | `core/dlsite_service.py` | DLsite API | `get_translation_info()`, `get_linked_works()`, `get_work_info()` |
| FolderWatcher | `core/watcher.py` | 文件监视 | `start()`, `stop()`, `_on_archive_detected()` |

### 6.3 前端组件索引

| 组件 | 文件路径 | 核心功能 | 主要方法/Computed |
|------|----------|----------|-------------------|
| Dashboard | `views/Dashboard.vue` | 仪表盘首页 | `refreshData()`, `groupedArchives` |
| Tasks | `views/Tasks.vue` | 任务队列 | `handleStatusChange()`, `retryTask()` |
| Conflicts | `views/Conflicts.vue` | 问题作品 | `fetchConflicts()`, `handleAction()` |
| ExistingFolders | `views/ExistingFolders.vue` | 已有文件夹 | `refreshFolders()`, `handleProcessSingle()`, `handleRefreshFolder()` |
| Library | `views/Library.vue` | 库存管理 | `filteredFiles`, `paginatedFiles`, `openFolder()` |
| Settings | `views/Settings.vue` | 系统设置 | `loadConfig()`, `saveConfig()` |
| PasswordVault | `views/PasswordVault.vue` | 密码库 | `loadPasswords()`, `previewCleanup()` |
| Logs | `views/Logs.vue` | 日志查看 | `refreshLogs()`, `togglePause()` |

### 6.4 数据模型索引

| 模型 | 表名 | 核心字段 | 用途 |
|------|------|----------|------|
| TaskModel | tasks | id, type, status, source_path, progress | 任务存储 |
| PasswordEntry | password_entries | id, rjcode, filename, password, use_count | 密码库 |
| ConflictWork | conflict_works | id, rjcode, conflict_type, existing_path, new_path | 问题作品 |
| ProcessedArchive | processed_archives | id, rjcode, filename, file_path, file_size | 已处理压缩包 |
| ExistingFolderCache | existing_folder_cache | id, folder_path, rjcode, duplicate_info | 已有文件夹缓存 |
| WorkMetadata | work_metadata | rjcode, work_name, maker_name, cover_url | 作品元数据缓存 |
| KikoeruSearchConfig | kikoeru_search_configs | id, name, search_url_template | Kikoeru搜索配置 |

### 6.5 冲突类型索引

| 冲突类型代码 | 中文名称 | 优先级 | 说明 | 典型场景 |
|-------------|---------|--------|------|----------|
| `NONE` | 无冲突 | 0 | 未发现任何重复 | 全新作品入库 |
| `DUPLICATE` | 直接重复 | 1 | 相同 RJ 号已存在 | 重复下载同一作品 |
| `LINKED_WORK_ORIGINAL` | 原作已存在 | 2 | 原作品已在库中 | 已有日文版，下载翻译版 |
| `LINKED_WORK_TRANSLATION` | 翻译版已存在 | 3 | 翻译版本已在库中 | 已有中文版，下载日文原版 |
| `LINKED_WORK_CHILD` | 子版本已存在 | 4 | 子版本已在库中 | 已有后续版本，下载前作 |
| `LINKED_WORK` | 关联作品 | 5 | 其他关联作品存在 | 同一系列其他作品 |
| `LANGUAGE_VARIANT` | 多语言版本 | 6 | 多语言版本冲突 | 同一作品多种语言 |
| `MULTIPLE_VERSIONS` | 多版本 | 7 | 存在多个版本 | 多个不同版本 |

### 6.6 语言优先级索引

| 语言代码 | 中文名称 | 优先级 | 说明 |
|---------|---------|--------|------|
| `CHI_HANS` | 简体中文 | 1 | 最高优先级 |
| `CHI_HANT` | 繁体中文 | 2 | 次高优先级 |
| `JPN` | 日文 | 3 | 原版语言 |
| `ENG` | 英文 | 4 | 英语版本 |
| `KO_KR` | 韩语 | 5 | 韩语版本 |
| `SPA` | 西班牙语 | 6 | 西班牙语版本 |
| `FRE` | 法语 | 7 | 法语版本 |
| `GER` | 德语 | 8 | 德语版本 |
| `RUS` | 俄语 | 9 | 俄语版本 |
| `THA` | 泰语 | 10 | 泰语版本 |
| `VIE` | 越南语 | 11 | 越南语版本 |
| `ITA` | 意大利语 | 12 | 意大利语版本 |
| `POR` | 葡萄牙语 | 13 | 葡萄牙语版本 |
| 其他 | 未知语言 | 99 | 最低优先级 |

### 6.7 解决方案动作索引

| 动作代码 | 中文名称 | 适用场景 | 操作说明 |
|---------|---------|---------|----------|
| `KEEP_NEW` | 保留新版 | 新版优先级更高 | 删除旧版，保留新版 |
| `KEEP_OLD` | 保留旧版 | 旧版优先级更高 | 删除新版，保留旧版 |
| `KEEP_BOTH` | 保留两者 | 优先级相同或需备份 | 两个版本都保留 |
| `MERGE` | 合并 | 直接重复 | 合并两个版本，新版加后缀 |
| `MERGE_LANG` | 合并语言 | 同一语言多版本 | 合并到同一文件夹 |
| `SKIP` | 抛弃新版 | 抛弃当前版本 | 删除新版，不做更改 |

### 6.8 配置项索引

| 配置项 | 路径 | 类型 | 默认值 | 说明 |
|--------|------|------|--------|------|
| **存储路径** ||||
| input_path | `storage.input_path` | string | `/input` | 输入目录 |
| temp_path | `storage.temp_path` | string | `/temp` | 临时目录 |
| library_path | `storage.library_path` | string | `/library` | 作品库目录 |
| processed_archives_path | `storage.processed_archives_path` | string | `/processed` | 已处理压缩包目录 |
| existing_folders_path | `storage.existing_folders_path` | string | `/existing` | 已有文件夹目录 |
| **处理配置** ||||
| max_workers | `processing.max_workers` | int | 2 | 最大并发任务数 |
| auto_repair_extension | `processing.auto_repair_extension` | bool | true | 自动修复文件后缀 |
| verify_after_extract | `processing.verify_after_extract` | bool | true | 解压后验证 |
| extract_nested_archives | `processing.extract_nested_archives` | bool | true | 解压嵌套压缩包 |
| max_nested_depth | `processing.max_nested_depth` | int | 3 | 最大嵌套深度 |
| **重命名配置** ||||
| template | `rename.template` | string | `{rjcode} {work_name}` | 重命名模板 |
| flatten_single_subfolder | `rename.flatten_single_subfolder` | bool | true | 扁平化单层文件夹 |
| remove_empty_folders | `rename.remove_empty_folders` | bool | true | 移除空文件夹 |
| **Kikoeru 服务器配置** ||||
| enabled | `kikoeru_server.enabled` | bool | false | 启用 Kikoeru 服务器查重 |
| server_url | `kikoeru_server.server_url` | string | "" | Kikoeru 服务器地址 |
| api_token | `kikoeru_server.api_token` | string | "" | API 访问令牌 |
| timeout | `kikoeru_server.timeout` | int | 10 | 请求超时(秒) |
| cache_ttl | `kikoeru_server.cache_ttl` | int | 300 | 缓存时间(秒) |

---

## 附录：常用操作速查

### A. 添加新的API端点

1. 在 `backend/app/api/routes.py` 中添加路由函数
2. 使用 `@app.get/post/put/delete` 装饰器
3. 定义 Pydantic 模型用于请求/响应验证
4. 添加适当的错误处理

### B. 添加新的前端页面

1. 在 `frontend/src/views/` 创建 Vue 组件
2. 在 `frontend/src/router/index.js` 添加路由
3. 在 `App.vue` 添加导航链接

### C. 修改处理流程

1. 找到对应的服务类（如 `ExtractService`）
2. 修改或添加处理方法
3. 在 `TaskEngine` 中调用新方法
4. 更新前端对应的状态显示

### D. 数据库迁移

```python
# 在 backend/app/models/database.py 修改模型
# 重启服务时会自动创建新表
```

### E. 查重系统使用指南

#### E.1 手动触发查重

```python
from backend.app.core.duplicate_service import get_duplicate_service

async def check_duplicate_example():
    service = get_duplicate_service()
    
    # 查重检查
    result = await service.check_duplicate_enhanced(
        rjcode="RJ123456",
        check_linked_works=True,  # 检查关联作品
        cue_languages=["CHI_HANS", "CHI_HANT", "ENG"]  # 关注这些语言
    )
    
    if result.is_duplicate:
        print(f"❌ 发现冲突: {result.conflict_type}")
        print(f"📚 关联作品: {result.related_rjcodes}")
        
        # 获取解决方案
        options = await service.get_conflict_resolution_options(result)
        for opt in options:
            mark = "⭐" if opt.get('recommend') else "  "
            print(f"{mark} {opt['label']}: {opt['description']}")
    else:
        print("✅ 无冲突，可以入库")
```

#### E.2 在已有文件夹中使用

```javascript
// 前端调用示例
// 1. 查重检查
const response = await axios.post('/api/existing-folders/check-duplicates', {
  folders: ['/existing/RJ123456'],
  check_linked_works: true,
  cue_languages: ['CHI_HANS', 'CHI_HANT', 'ENG']
});

// 2. 根据结果选择操作
const result = response.data.results[0];
if (result.is_duplicate) {
  // 显示冲突详情对话框
  showConflictDialog(result);
} else {
  // 直接处理
  await handleProcessSingle(folder);
}

// 3. 带解决方案处理
await axios.post('/api/existing-folders/process-with-resolution', {
  folder_path: '/existing/RJ123456',
  resolution: 'KEEP_NEW',  // 或 'SKIP', 'KEEP_BOTH', 'MERGE'
  auto_classify: true
});
```

#### E.3 Kikoeru 服务器查重使用

**后端调用**:
```python
from backend.app.core.kikoeru_duplicate_service import get_kikoeru_service

async def check_kikoeru_example():
    service = get_kikoeru_service()
    
    # 单个查询
    result = await service.check_duplicate("RJ123456")
    if result.is_found:
        print(f"✓ 在 Kikoeru 找到: {result.title}")
        print(f"  社团: {result.circle_name}")
        print(f"  标签: {', '.join(result.tags)}")
    else:
        print("✗ Kikoeru 中未找到")
    
    # 批量查询
    results = await service.check_duplicates_batch(
        ["RJ123456", "RJ789012", "RJ345678"]
    )
    for rj, res in results.items():
        print(f"{rj}: {'✓' if res.is_found else '✗'}")
    
    # 测试连接
    test_result = await service.test_connection()
    print(f"连接状态: {test_result['message']}")
    print(f"延迟: {test_result['latency']:.0f}ms")
```

**前端调用**:
```javascript
// 1. 配置 Kikoeru 服务器
await axios.post('/api/kikoeru-server/config', {
  enabled: true,
  server_url: 'http://192.168.1.100:8088',
  api_token: 'your-api-token',
  timeout: 10,
  cache_ttl: 300
});

// 2. 测试连接
const testResult = await axios.post('/api/kikoeru-server/test');
console.log(testResult.data.success ? '连接成功' : '连接失败');

// 3. 查重检查
const checkResult = await axios.post('/api/kikoeru-server/check?rjcode=RJ123456');
console.log('Kikoeru中是否存在:', checkResult.data.is_found);

// 4. 清除缓存
await axios.post('/api/kikoeru-server/clear-cache');
```

**在综合查重中自动使用**:
```python
# 当 kikoeru_server.enabled = true 时
# check_duplicate_enhanced 会自动查询 Kikoeru 服务器

result = await duplicate_service.check_duplicate_enhanced("RJ123456")
if result.kikoeru_result:
    print(f"Kikoeru查询结果: {result.kikoeru_result.is_found}")
```

#### E.4 修改语言优先级

```python
# 在 duplicate_service.py 中修改 _get_lang_priority 方法

def _get_lang_priority(self, lang: str) -> int:
    """自定义语言优先级"""
    priorities = {
        'CHI_HANS': 1,   # 简体中文优先
        'CHI_HANT': 2,
        'JPN': 3,
        'ENG': 4,
        # 添加新语言...
        'CUSTOM': 5,     # 自定义语言
    }
    return priorities.get(lang, 99)
```

#### E.5 添加新的冲突类型

```python
# 1. 在 DuplicateCheckResult 中添加新类型
class DuplicateCheckResult:
    conflict_type: str = "NONE"  # 添加新类型: "NEW_TYPE"

# 2. 在 check_duplicate_enhanced 中添加检测逻辑
if some_condition:
    result.conflict_type = "NEW_TYPE"
    
# 3. 在 get_conflict_resolution_options 中添加处理选项
elif check_result.conflict_type == "NEW_TYPE":
    options = [
        {
            'action': 'CUSTOM_ACTION',
            'label': '自定义操作',
            'description': '操作说明',
            'recommend': True
        }
    ]
```

#### E.5 查重缓存管理

```javascript
// 刷新缓存
await axios.post('/api/existing-folders/refresh-cache');

// 清除缓存
await axios.post('/api/existing-folders/clear-cache');

// 强制重新扫描（不使用缓存）
await axios.post('/api/existing-folders/scan?force_refresh=true');
```

---

**文档版本**: v1.0  
**最后更新**: 2024年  
**作者**: AI Assistant

如有疑问或需要补充，请参考源代码或提交Issue。
