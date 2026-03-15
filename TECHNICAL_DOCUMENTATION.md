# KikoeruTool 技术文档

> **版本**: v1.6.4
> **更新日期**: 2026-03
> **用途**: DLsite 音声作品自动整理工具完整技术参考

---

## 目录

1. [项目概述](#一项目概述)
2. [后端 API 文档](#二后端-api-文档)
3. [核心服务类](#三核心服务类)
4. [数据模型](#四数据模型)
5. [配置系统](#五配置系统)
6. [查重系统详解](#六查重系统详解)
7. [业务流程详解](#七业务流程详解)
8. [前端组件文档](#八前端组件文档)
9. [索引速查表](#九索引速查表)

---

## 一、项目概述

### 1.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │Dashboard│ │  Tasks  │ │Library  │ │Settings │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │Conflicts│ │ASMRSync │ │Logs     │ │Password │          │
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
│  │ Database │  │ (作品库) │  │   API    │  │ (YAML)  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Element Plus + Vite | 现代化 SPA，响应式 UI |
| 后端 | FastAPI + SQLAlchemy + Pydantic | 高性能 API，ORM 数据库操作 |
| 数据 | SQLite | 轻量级本地数据库 |
| 部署 | Docker + GHCR | 容器化部署，GitHub 镜像仓库 |

### 1.3 项目目录结构

```
KikoeruTool/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py              # API 路由定义
│   │   ├── core/
│   │   │   ├── task_engine.py         # 任务引擎
│   │   │   ├── extract_service.py     # 解压服务
│   │   │   ├── metadata_service.py    # 元数据服务
│   │   │   ├── rename_service.py      # 重命名服务
│   │   │   ├── filter_service.py      # 过滤服务
│   │   │   ├── classifier.py          # 分类器
│   │   │   ├── duplicate_service.py   # 查重服务
│   │   │   ├── dlsite_service.py      # DLsite API 服务
│   │   │   ├── kikoeru_duplicate_service.py  # Kikoeru 服务器查重
│   │   │   ├── file_processor.py      # 文件处理器
│   │   │   ├── watcher.py             # 文件监视器
│   │   │   ├── password_cleanup.py    # 密码清理
│   │   │   ├── processed_archive_cleanup.py  # 压缩包清理
│   │   │   ├── asmr_download_service.py      # ASMR 下载服务
│   │   │   └── subtitle_sync_service.py      # 字幕同步服务
│   │   ├── models/
│   │   │   └── database.py            # 数据库模型
│   │   ├── config/
│   │   │   └── settings.py            # 配置管理
│   │   └── main.py                    # 应用入口
│   ├── build.py                       # 构建脚本
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── views/                     # 页面组件
│       │   ├── Dashboard.vue          # 仪表板
│       │   ├── Tasks.vue              # 任务管理
│       │   ├── Library.vue            # 作品库
│       │   ├── Settings.vue           # 设置页面
│       │   ├── Conflicts.vue          # 冲突管理
│       │   ├── ExistingFolders.vue    # 已有文件夹
│       │   ├── ASMRSync.vue           # ASMR 同步
│       │   ├── Logs.vue               # 日志查看
│       │   └── PasswordVault.vue      # 密码库
│       ├── components/
│       │   └── FileUploader.vue       # 文件上传组件
│       ├── stores/
│       │   └── index.js               # Pinia 状态管理
│       └── router/
│           └── index.js               # 路由配置
└── docs/
    ├── INTRODUCTION.md                # 功能介绍
    ├── DOCKER.md                      # Docker 部署
    └── DEVELOPMENT.md                 # 开发指南
```

---

## 二、后端 API 文档

### 2.1 API 概览

**基础 URL**: `/api`
**响应格式**: JSON
**错误处理**: HTTP 状态码 + 错误详情

### 2.2 任务管理 API

#### 创建任务

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
| `asmr_sync_download` | ASMR 同步下载 |

#### 任务控制

```http
GET  /api/tasks                    # 获取任务列表
GET  /api/tasks/{task_id}          # 获取任务详情
POST /api/tasks/{task_id}/pause    # 暂停任务
POST /api/tasks/{task_id}/resume   # 恢复任务
POST /api/tasks/{task_id}/cancel   # 取消任务
```

### 2.3 配置管理 API

```http
GET  /api/config                   # 获取配置
POST /api/config                   # 更新配置
```

### 2.4 监视器 API

```http
POST /api/watcher/start            # 启动监视器
POST /api/watcher/stop             # 停止监视器
GET  /api/watcher/status           # 获取监视器状态
POST /api/scan                     # 扫描输入目录
```

### 2.5 密码库 API

```http
GET    /api/passwords              # 获取密码列表
POST   /api/passwords              # 创建密码
POST   /api/passwords/batch        # 批量创建密码
PUT    /api/passwords/{id}         # 更新密码
DELETE /api/passwords/{id}         # 删除密码
GET    /api/passwords/find-for-archive  # 查找密码
POST   /api/passwords/import-from-text  # 从文本导入
```

### 2.6 冲突管理 API

```http
GET  /api/conflicts                # 获取冲突列表
POST /api/conflicts/{id}/resolve   # 解决冲突
```

### 2.7 已处理压缩包 API

```http
POST /api/processed-archives/scan   # 扫描已处理压缩包
GET  /api/processed-archives        # 获取压缩包列表
POST /api/processed-archives/{id}/reprocess  # 重新处理
```

### 2.8 作品库 API

```http
GET  /api/library/files            # 获取作品库文件
POST /api/library/rename           # 重命名文件
POST /api/library/api-rename       # API 重命名
POST /api/library/delete           # 删除文件
POST /api/library/open-folder      # 打开文件夹
```

### 2.9 路径映射 API

```http
GET  /api/path-mapping/config      # 获取路径映射配置
POST /api/path-mapping/config      # 更新路径映射配置
POST /api/path-mapping/test        # 测试路径映射
```

### 2.10 清理服务 API

```http
# 密码清理
GET  /api/password-cleanup/status    # 获取清理状态
GET  /api/password-cleanup/preview   # 预览清理
POST /api/password-cleanup/run       # 执行清理
GET  /api/password-cleanup/history   # 清理历史

# 压缩包清理
GET  /api/processed-archive-cleanup/status
GET  /api/processed-archive-cleanup/preview
POST /api/processed-archive-cleanup/run
GET  /api/processed-archive-cleanup/history
```

### 2.11 已有文件夹 API

```http
GET  /api/existing-folders         # 获取已有文件夹列表
POST /api/existing-folders/scan    # 扫描已有文件夹
```

### 2.12 日志 API

```http
GET  /api/logs?lines=100           # 获取日志
```

---

## 三、核心服务类

### 3.1 ExtractService (extract_service.py)

解压服务，负责压缩包解压、编码检测、密码爆破。

**关键属性**:
```python
class ArchiveInfo:
    path: str              # 压缩包路径
    file_list: List[Dict]  # 文件列表
    password: str          # 密码
    is_volume: bool        # 是否为分卷
    volume_set: List[str]  # 分卷集合
```

**关键方法**:

| 方法 | 说明 |
|------|------|
| `extract(task)` | 解压压缩包，返回解压后目录 |
| `_find_7z_executable()` | 查找 7z 可执行文件 |
| `_check_7z_available()` | 检查 7z 是否可用 |
| `_detect_best_encoding(raw_bytes)` | **自动检测最佳编码** (v1.6.3+) |
| `_score_decoded_text(text)` | 评估解码文本质量分数 |
| `_list_archive_contents(archive_path, password)` | 列出压缩包内容 |
| `_try_passwords(archive_path)` | 尝试密码列表 |
| `_extract_archive(archive_path, output_dir, password)` | 执行解压 |
| `_detect_volume_set(archive_path)` | 检测分卷压缩包 |
| `_merge_volume_set(volume_set, output_dir)` | 合并分卷 |

**编码自动检测算法** (v1.6.3):
```python
def _detect_best_encoding(self, raw_bytes: bytes) -> str:
    """自动检测压缩包文件名的最佳编码"""
    encodings = ['gbk', 'shift_jis', 'utf-8', 'big5', 'euc_kr']
    best_encoding = 'gbk'
    best_score = -1

    for encoding in encodings:
        decoded = raw_bytes.decode(encoding, errors='replace')
        score = self._score_decoded_text(decoded)
        if score > best_score:
            best_score = score
            best_encoding = encoding

    return best_encoding

def _score_decoded_text(self, text: str) -> int:
    """评估解码后文本的质量分数"""
    score = 0
    # 惩罚替换字符（乱码标志）
    score -= text.count('\ufffd') * 10
    # 奖励日文假名
    for c in text:
        if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff':
            score += 2
        elif '\u4e00' <= c <= '\u9fff':
            score += 1
        elif c.isalnum() or c in '._-+/\\':
            score += 1
    return score
```

---

### 3.2 MetadataService (metadata_service.py)

元数据服务，负责从 DLsite 获取作品信息。

**关键方法**:

| 方法 | 说明 |
|------|------|
| `fetch_metadata(rjcode)` | 获取作品元数据 |
| `fetch_japanese_metadata(rjcode)` | **获取日语元数据** (v1.6.4+) |
| `_parse_work_data(data)` | 解析 DLsite API 响应 |
| `_get_cached_metadata(rjcode)` | 获取缓存的元数据 |
| `_cache_metadata(rjcode, data)` | 缓存元数据 |

**日语元数据获取** (v1.6.4):
```python
async def fetch_japanese_metadata(self, rjcode: str) -> Optional[dict]:
    """获取日语版本的元数据"""
    url = f"https://www.dlsite.com/maniax/api/=/product.json?workno={rjcode}&locale=ja-JP"
    response = self.session.get(url, timeout=(...))
    data = response.json()[0]
    return {
        'maker_name': data.get('maker_name'),
        'cvs': self._parse_cvs(data),
        'tags': self._parse_tags(data),
        # ...
    }
```

---

### 3.3 RenameService (rename_service.py)

重命名服务，负责文件夹命名和模板渲染。

**关键方法**:

| 方法 | 说明 |
|------|------|
| `rename(path, task)` | 执行重命名 |
| `_compile_name(metadata, japanese_metadata)` | 根据模板编译名称 |
| `_flatten_single_subfolder(path)` | 扁平化单一子文件夹 |
| `_sanitize_filename(name)` | 清理文件名非法字符 |

**日语元数据支持** (v1.6.4):
```python
def _compile_name(self, metadata: dict, japanese_metadata: Optional[dict] = None) -> str:
    """根据模板编译名称"""
    use_japanese = self.config.rename.use_japanese_metadata and japanese_metadata

    # rjcode 和 work_name 始终使用当前语言
    rjcode = metadata.get('rjcode', '')
    work_name = metadata.get('work_name', '')

    # 其他字段可使用日语
    if use_japanese:
        maker_name = japanese_metadata.get('maker_name', metadata.get('maker_name', ''))
        cvs = japanese_metadata.get('cvs', metadata.get('cvs', []))
        tags = japanese_metadata.get('tags', metadata.get('tags', []))
    else:
        maker_name = metadata.get('maker_name', '')
        cvs = metadata.get('cvs', [])
        tags = metadata.get('tags', [])

    # 渲染模板...
```

---

### 3.4 FilterService (filter_service.py)

过滤服务，负责文件过滤和清理。

**关键方法**:

| 方法 | 说明 |
|------|------|
| `filter(path, task)` | 执行过滤 |
| `_create_filter_rule(...)` | 创建过滤规则 |
| `_should_filter_file(file_path, rules)` | 判断是否过滤文件 |
| `_should_filter_dir(dir_path, rules)` | 判断是否过滤目录 |
| `_delete_file(file_path)` | 删除文件 |
| `_delete_dir(dir_path)` | 删除目录 |
| `_detect_audio_formats(path)` | 检测音频格式 |

**默认过滤规则**:
```python
FilterRule(name="过滤无SE的WAV文件", pattern=r"(?:SE|音|音效)(?:[な無]し|CUT).*\.WAV$", target="file", action="exclude")
FilterRule(name="过滤MP3文件", pattern=r"\.mp3$", target="file", action="exclude", enabled=False)
```

---

### 3.5 SmartClassifier (classifier.py)

智能分类器，负责作品分类和重复检测。

**关键方法**:

| 方法 | 说明 |
|------|------|
| `check_duplicate_before_extract(rjcode, task, engine)` | 解压前查重 |
| `classify_and_move(source_path, metadata, task)` | 分类并移动 |
| `_check_existing(rjcode)` | 检查是否已存在 |
| `_determine_conflict_type(existing, new_metadata)` | 确定冲突类型 |
| `_apply_classification_rules(metadata)` | 应用分类规则 |
| `_apply_single_rule(rule, metadata)` | 应用单条分类规则 |
| `_sanitize_path(path)` | 清理路径 |
| `_move_with_rename(source, target_dir)` | 移动并处理重名 |

**冲突类型**:
| 类型 | 说明 |
|------|------|
| `DUPLICATE` | 直接重复（相同 RJ） |
| `LINKED_WORK_ORIGINAL` | 原作已存在 |
| `LINKED_WORK_TRANSLATION` | 翻译版已存在 |
| `LINKED_WORK_CHILD` | 子版本已存在 |
| `LANGUAGE_VARIANT` | 语言变体 |
| `MULTIPLE_VERSIONS` | 多版本 |

---

### 3.6 DLsiteApiService (dlsite_service.py)

DLsite API 服务，负责获取作品关联信息。

**数据结构**:
```python
class TranslationInfo:
    is_original: bool      # 是否为原作品
    is_parent: bool        # 是否为翻译父级
    is_child: bool         # 是否为翻译子级
    parent_workno: str     # 父作品 RJ 号
    original_workno: str   # 原作品 RJ 号
    lang: str              # 语言代码

class LinkedWork:
    workno: str            # RJ 号
    work_type: str         # original, parent, child
    lang: str              # 语言代码
    title: str             # 作品标题
```

**关键方法**:

| 方法 | 说明 |
|------|------|
| `get_translation_info(rjcode)` | 获取翻译信息 |
| `get_linked_works(rjcode)` | 获取关联作品 |
| `get_full_linkage(rjcode, cue_languages)` | 获取完整关联链 |
| `get_work_info(rjcode)` | 获取作品信息 |
| `get_rj_chain(rjcode, trans)` | 获取 RJ 链 |

---

### 3.7 KikoeruDuplicateService (kikoeru_duplicate_service.py)

Kikoeru 服务器查重服务。

**数据结构**:
```python
@dataclass
class KikoeruCheckResult:
    is_duplicate: bool           # 是否重复
    work_id: int                 # 作品 ID
    title: str                   # 标题
    language: str                # 语言
    similarity: float            # 相似度
    work_url: str                # 作品 URL
```

**关键方法**:

| 方法 | 说明 |
|------|------|
| `check_duplicate(rjcode)` | 检查单个作品 |
| `check_duplicates_batch(rjcodes)` | 批量检查 |
| `check_duplicate_with_linkages(rjcode)` | 带关联检查 |
| `test_connection()` | 测试连接 |
| `_login()` | 登录获取 Token |
| `_ensure_valid_token()` | 确保有效 Token |

---

### 3.8 TaskEngine (task_engine.py)

任务引擎，管理任务队列和执行。

**任务状态**:
```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAUSED = "paused"
    WAITING_MANUAL = "waiting_manual"
    WAITING_RETRY = "waiting_retry"
    COMPLETED = "completed"
    FAILED = "failed"
```

**任务类型**:
```python
class TaskType(str, Enum):
    EXTRACT = "extract"
    FILTER = "filter"
    METADATA = "metadata"
    RENAME = "rename"
    AUTO_PROCESS = "auto_process"
    PROCESS_EXISTING_FOLDER = "process_existing_folder"
    ASMR_SYNC_DOWNLOAD = "asmr_sync_download"
```

**关键方法**:

| 方法 | 说明 |
|------|------|
| `add_task(task)` | 添加任务 |
| `start()` | 启动引擎 |
| `stop()` | 停止引擎 |
| `_process_task(task)` | 处理单个任务 |
| `_run_auto_process(task)` | 运行自动处理流程 |

---

### 3.9 ASMRDownloadService (asmr_download_service.py)

ASMR 同步下载服务。

**关键方法**:

| 方法 | 说明 |
|------|------|
| `download_work(rjcode, output_dir)` | 下载作品 |
| `get_available_versions(rjcode)` | 获取可用版本 |
| `sync_subtitle(subtitle_folder, work_dir)` | 同步字幕 |

---

### 3.10 Watcher (watcher.py)

文件监视器，监视输入目录。

**关键方法**:

| 方法 | 说明 |
|------|------|
| `start()` | 启动监视 |
| `stop()` | 停止监视 |
| `_scan_directory()` | 扫描目录 |
| `_on_file_created(event)` | 文件创建事件 |

---

## 四、数据模型

### 4.1 数据库表结构

#### Task 表
```python
class Task(Base):
    __tablename__ = 'tasks'

    id = Column(String(36), primary_key=True)
    type = Column(String(20))           # 任务类型
    status = Column(String(20))         # 状态
    source_path = Column(Text)          # 源路径
    output_path = Column(Text)          # 输出路径
    progress = Column(Integer)          # 进度
    current_step = Column(String(100))  # 当前步骤
    error_message = Column(Text)        # 错误信息
    created_at = Column(DateTime)       # 创建时间
    started_at = Column(DateTime)       # 开始时间
    completed_at = Column(DateTime)     # 完成时间
    task_metadata = Column(JSON)        # 元数据
```

#### WorkMetadata 表
```python
class WorkMetadata(Base):
    __tablename__ = 'work_metadata'

    rjcode = Column(String(20), primary_key=True)
    work_name = Column(Text)
    maker_id = Column(String(20))
    maker_name = Column(Text)
    release_date = Column(String(20))
    series_name = Column(Text)
    series_id = Column(String(20))
    age_category = Column(String(10))
    tags = Column(JSON)                 # 标签列表
    cvs = Column(JSON)                  # CV 列表
    cover_url = Column(Text)
    cached_at = Column(DateTime)
    expires_at = Column(DateTime)
```

#### ConflictWork 表
```python
class ConflictWork(Base):
    __tablename__ = 'conflict_works'

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36))
    rjcode = Column(String(20))
    conflict_type = Column(String(30))  # 冲突类型
    existing_path = Column(Text)        # 已存在路径
    new_path = Column(Text)             # 新路径
    new_metadata = Column(JSON)         # 新元数据
    status = Column(String(20))         # 解决状态
    linked_works_info = Column(JSON)    # 关联作品信息
    analysis_info = Column(JSON)        # 分析报告
    related_rjcodes = Column(JSON)      # 关联 RJ 号
```

#### PasswordEntry 表
```python
class PasswordEntry(Base):
    __tablename__ = 'password_entries'

    id = Column(String(36), primary_key=True)
    rjcode = Column(String(20))         # RJ 号
    filename = Column(String(255))      # 文件名
    password = Column(String(255))      # 密码
    description = Column(Text)          # 描述
    source = Column(String(50))         # 来源: manual, batch, auto
    use_count = Column(Integer)         # 使用次数
    last_used_at = Column(DateTime)     # 最后使用时间
```

#### ProcessedArchive 表
```python
class ProcessedArchive(Base):
    __tablename__ = 'processed_archives'

    id = Column(String(36), primary_key=True)
    original_path = Column(Text)        # 原始路径
    current_path = Column(Text)         # 当前路径
    filename = Column(Text)             # 文件名
    rjcode = Column(String(20))         # RJ 号
    file_size = Column(BigInteger)      # 文件大小
    processed_at = Column(DateTime)     # 处理时间
    process_count = Column(Integer)     # 处理次数
    status = Column(String(20))         # 状态
```

#### LibrarySnapshot 表
```python
class LibrarySnapshot(Base):
    __tablename__ = 'library_snapshot'

    id = Column(Integer, primary_key=True)
    rjcode = Column(String(20), unique=True)
    folder_path = Column(Text)
    folder_size = Column(BigInteger)
    file_count = Column(Integer)
    scanned_at = Column(DateTime)
```

#### WorkLinkage 表
```python
class WorkLinkage(Base):
    __tablename__ = 'work_linkages'

    id = Column(Integer, primary_key=True)
    original_rjcode = Column(String(20))   # 原 RJ
    linked_rjcode = Column(String(20))     # 关联 RJ
    work_type = Column(String(20))         # 类型
    lang = Column(String(20))              # 语言
    cached_at = Column(DateTime)
    expires_at = Column(DateTime)
```

#### WaitingRetryTask 表
```python
class WaitingRetryTask(Base):
    __tablename__ = 'waiting_retry_tasks'

    id = Column(String(36), primary_key=True)
    rjcode = Column(String(20))
    subtitle_folder = Column(Text)
    work_title = Column(Text)
    retry_reason = Column(Text)
    retry_count = Column(Integer)
    max_retry_count = Column(Integer)
    retry_after = Column(DateTime)
```

---

## 五、配置系统

### 5.1 配置模型 (settings.py)

#### StorageConfig
```python
class StorageConfig(BaseModel):
    input_path: str = "/input"              # 输入目录
    temp_path: str = "/temp"                # 临时目录
    library_path: str = "/library"          # 作品库目录
    processed_archives_path: str = "/processed"  # 已处理目录
    existing_folders_path: str = "/existing"     # 已有文件夹目录
    asmr_subtitle_path: str = ""            # ASMR 字幕目录
```

#### ExtractConfig
```python
class ExtractConfig(BaseModel):
    seven_zip_path: str = "7z"              # 7z 路径
    auto_repair_extension: bool = True      # 自动修复扩展名
    verify_after_extract: bool = True       # 解压后验证
    password_list: list = []                # 密码列表
    extract_nested_archives: bool = True    # 解压嵌套压缩包
    max_nested_depth: int = 5               # 最大嵌套深度
```

#### RenameConfig
```python
class RenameConfig(BaseModel):
    template: str = "{rjcode} {work_name}"  # 重命名模板
    date_format: str = "%y%m%d"             # 日期格式
    delimiter: str = " "                    # 分隔符
    cv_list_left: str = "(CV "              # CV 左括号
    cv_list_right: str = ")"                # CV 右括号
    exclude_square_brackets: bool = False   # 排除方括号
    illegal_char_to_full_width: bool = False
    tags_max_number: int = 5                # 最大标签数
    tags_ordered_list: list = []            # 标签顺序
    flatten_single_subfolder: bool = True   # 扁平化单子文件夹
    flatten_depth: int = 3                  # 扁平化深度
    remove_empty_folders: bool = True       # 删除空文件夹
    api_rename_follow_template: bool = False
    use_japanese_metadata: bool = False     # 使用日语元数据 (v1.6.4+)
```

#### MetadataConfig
```python
class MetadataConfig(BaseModel):
    locale: str = "zh_cn"                   # 语言区域
    connect_timeout: int = 10               # 连接超时
    read_timeout: int = 10                  # 读取超时
    sleep_interval: int = 3                 # 请求间隔
    http_proxy: Optional[str] = None        # HTTP 代理
    cache_enabled: bool = True              # 启用缓存
    fetch_cover: bool = True                # 获取封面
    make_folder_icon: bool = True           # 创建文件夹图标
    remove_jpg_file: bool = True            # 删除 JPG 文件
```

#### FilterConfig
```python
class FilterConfig(BaseModel):
    enabled: bool = True                    # 启用过滤
    filter_dir: bool = True                 # 过滤目录
    rules: list[FilterRule] = []            # 过滤规则
```

#### ClassificationRule
```python
class ClassificationRule(BaseModel):
    type: str                               # none, maker, series, rjcode
    enabled: bool = True
    path_template: str = ""                 # 路径模板
    custom_name: Optional[str] = None       # 自定义名称
    fallback: Optional[str] = None          # 回退规则
    max_tags: Optional[int] = None          # 最大标签数
    rjcode_range: Optional[str] = None      # RJ 号范围
```

#### WatcherConfig
```python
class WatcherConfig(BaseModel):
    enabled: bool = True                    # 启用监视器
    scan_interval: int = 30                 # 扫描间隔(秒)
    auto_start: bool = True                 # 自动启动
    auto_classify: bool = True              # 自动分类
    delete_after_process: bool = False      # 处理后删除
```

#### ASMRSyncConfig
```python
class ASMRSyncConfig(BaseModel):
    enabled: bool = True
    api_base_url: str = "https://api.asmr-200.com/api"
    max_concurrent_downloads: int = 3
    http_proxy: Optional[str] = None
    retry_interval_hours: float = 1.0
    max_retry_count: int = 10
    lrc_clean_enabled: bool = True          # LRC 广告清理
    simplify_chinese_enabled: bool = True   # 繁简转换
```

#### AutoProcessConfig
```python
class AutoProcessConfig(BaseModel):
    check_duplicate: bool = True            # 查重
    extract: bool = True                    # 解压
    fetch_metadata: bool = True             # 获取元数据
    rename: bool = True                     # 重命名
    filter: bool = True                     # 过滤
    classify: bool = True                   # 分类
    archive: bool = True                    # 归档
```

---

## 六、查重系统详解

### 6.1 查重系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      查重系统                                │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ 本地数据库查重    │  │ Kikoeru服务器查重 │                │
│  │ (duplicate_svc)  │  │ (kikoeru_svc)    │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                     │                          │
│           └──────────┬──────────┘                          │
│                      ▼                                      │
│           ┌──────────────────┐                              │
│           │   DLsite API     │                              │
│           │ (dlsite_service) │                              │
│           └──────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 冲突类型体系

| 类型 | 说明 | 推荐操作 |
|------|------|---------|
| `DUPLICATE` | 直接重复（相同RJ号） | 保留新版/保留旧版 |
| `LINKED_WORK_ORIGINAL` | 原作已存在，当前是翻译版 | 保留两者 |
| `LINKED_WORK_TRANSLATION` | 翻译版已存在，当前是原作 | 保留两者 |
| `LINKED_WORK_CHILD` | 子版本已存在 | 保留两者 |
| `LANGUAGE_VARIANT` | 语言变体 | 保留两者 |
| `MULTIPLE_VERSIONS` | 多版本 | 根据大小判断 |

### 6.3 关联作品查询

**API 端点**:
```http
GET /api/linked-works/{rjcode}?include_full_linkage=true&cue_languages=CHI_HANS,CHI_HANT
```

**返回结构**:
```json
{
  "rjcode": "RJ123456",
  "translation_info": {
    "is_original": true,
    "is_parent": false,
    "is_child": false,
    "lang": "JPN"
  },
  "linked_works": {
    "RJ123456": {"workno": "RJ123456", "work_type": "original", "lang": "JPN"},
    "RJ789012": {"workno": "RJ789012", "work_type": "child", "lang": "CHI_HANS"}
  },
  "total_count": 2
}
```

### 6.4 查重缓存机制

- **API 响应缓存**: 24 小时
- **关联作品链缓存**: 24 小时
- **库中作品快照**: 实时更新
- **Kikoeru 服务器缓存**: 5 分钟

---

## 七、业务流程详解

### 7.1 自动处理流程 (auto_process)

```
输入压缩包
    │
    ▼
┌─────────────────┐
│  查重检测       │ ← check_duplicate
│  (可选)         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  解压           │ ← extract
│  (ExtractService)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  获取元数据     │ ← fetch_metadata
│  (MetadataService)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  重命名         │ ← rename
│  (RenameService)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  过滤           │ ← filter
│  (FilterService)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  智能分类       │ ← classify
│  (Classifier)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  归档压缩包     │ ← archive
└─────────────────┘
```

### 7.2 已有文件夹处理流程 (process_existing_folder)

```
已有文件夹
    │
    ▼
┌─────────────────┐
│  查重检测       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  获取元数据     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  重命名         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  过滤           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LRC 导入       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  智能分类       │
└─────────────────┘
```

### 7.3 ASMR 同步下载流程

```
字幕文件夹扫描
    │
    ▼
┌─────────────────┐
│  获取 RJ 号     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  查询可用版本   │
│  (ASMR API)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │ 找到版本 │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│  下载文件       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  同步字幕       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  重命名/分类    │
└─────────────────┘
```

---

## 八、前端组件文档

### 8.1 页面组件列表

| 组件 | 文件 | 功能 |
|------|------|------|
| Dashboard | `Dashboard.vue` | 仪表板，显示统计信息 |
| Tasks | `Tasks.vue` | 任务管理页面 |
| Library | `Library.vue` | 作品库管理 |
| Settings | `Settings.vue` | 设置页面 |
| Conflicts | `Conflicts.vue` | 冲突管理 |
| ExistingFolders | `ExistingFolders.vue` | 已有文件夹处理 |
| ASMRSync | `ASMRSync.vue` | ASMR 同步下载 |
| Logs | `Logs.vue` | 日志查看 |
| PasswordVault | `PasswordVault.vue` | 密码库管理 |

### 8.2 状态管理 (Pinia)

```javascript
// stores/index.js
const useStore = defineStore('main', {
  state: () => ({
    tasks: [],
    config: {},
    watcherStatus: {},
    conflicts: [],
    // ...
  }),
  actions: {
    async fetchTasks() { ... },
    async fetchConfig() { ... },
    // ...
  }
})
```

---

## 九、索引速查表

### 9.1 关键文件位置

| 功能 | 文件路径 |
|------|----------|
| API 路由 | `backend/app/api/routes.py` |
| 任务引擎 | `backend/app/core/task_engine.py` |
| 解压服务 | `backend/app/core/extract_service.py` |
| 元数据服务 | `backend/app/core/metadata_service.py` |
| 重命名服务 | `backend/app/core/rename_service.py` |
| 过滤服务 | `backend/app/core/filter_service.py` |
| 分类服务 | `backend/app/core/classifier.py` |
| DLsite API | `backend/app/core/dlsite_service.py` |
| 数据库模型 | `backend/app/models/database.py` |
| 配置模型 | `backend/app/config/settings.py` |

### 9.2 关键方法位置

| 方法 | 文件 | 行号范围 |
|------|------|----------|
| `_detect_best_encoding` | `extract_service.py` | ~1249 |
| `_score_decoded_text` | `extract_service.py` | ~1275 |
| `fetch_japanese_metadata` | `metadata_service.py` | ~371 |
| `_compile_name` | `rename_service.py` | 查找"def _compile_name" |
| `check_duplicate_before_extract` | `classifier.py` | ~20 |
| `classify_and_move` | `classifier.py` | ~72 |

### 9.3 配置项速查

| 配置项 | 模型 | 默认值 |
|--------|------|--------|
| 输入目录 | `storage.input_path` | `/input` |
| 作品库目录 | `storage.library_path` | `/library` |
| 重命名模板 | `rename.template` | `{rjcode} {work_name}` |
| 使用日语元数据 | `rename.use_japanese_metadata` | `false` |
| 监视器间隔 | `watcher.scan_interval` | `30` |
| 最大并发 | `processing.max_workers` | `4` |

---

## 更新日志

### v1.6.4 (2026-03)
- 新增 `use_japanese_metadata` 配置，支持重命名模板使用日语元数据
- 新增 `fetch_japanese_metadata()` 方法获取日语版本元数据

### v1.6.3 (2026-03)
- 新增 `_detect_best_encoding()` 自动检测压缩包编码
- 新增 `_score_decoded_text()` 编码质量评估
- 解决日区压缩包乱码问题

### v1.6.0 及之前
- ASMR 同步下载功能
- Kikoeru 服务器查重集成
- 密码库和已处理压缩包管理
- 智能清理服务
- 路径映射功能