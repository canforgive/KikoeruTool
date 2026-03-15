# Prekikoeru 查重功能改进总结

## 概述

参考 VoiceLinks 的查重功能，对 Prekikoeru 的查重系统进行了全面改进，支持通过 RJ 号查询关联作品（不同语言版本），并提供更详细的冲突分析和解决选项。

## 核心改进

### 1. DLsite API 服务 (`dlsite_service.py`)

实现了与 VoiceLinks 类似的 DLsite API 集成，支持：

- **翻译信息获取**: 检测作品是否为原作品、翻译父级或翻译子级
- **关联作品链查询**: 
  - 获取原作品的所有语言版本
  - 获取翻译版本的所有子作品
  - 支持完整关联链递归查询
- **作品详细信息**: 获取标题、社团、发售日期等元数据

**关键数据结构:**
```python
TranslationInfo:
  - is_original: bool      # 是否为原作品
  - is_parent: bool        # 是否为翻译父级
  - is_child: bool         # 是否为翻译子级
  - parent_workno: str     # 父作品 RJ 号
  - original_workno: str   # 原作品 RJ 号
  - lang: str              # 语言代码

LinkedWork:
  - workno: str            # RJ 号
  - work_type: str         # original, parent, child
  - lang: str              # 语言代码
  - title: str             # 作品标题
```

### 2. 增强查重服务 (`duplicate_service.py`)

提供了改进的查重检测逻辑：

**主要功能:**
- **直接重复检测**: 检查相同 RJ 号是否已存在
- **关联作品检测**: 检查同一作品的不同语言版本
- **冲突类型识别**:
  - `DUPLICATE`: 直接重复（相同 RJ）
  - `LINKED_WORK_ORIGINAL`: 当前是原作品，库中有翻译版本
  - `LINKED_WORK_TRANSLATION`: 当前是翻译版本，库中有原作品或其他翻译
  - `LINKED_WORK_CHILD`: 当前是子作品

**冲突分析信息:**
```python
analysis_info = {
    "current_work": {
        "rjcode": "RJxxx",
        "work_type": "original|parent|child",
        "lang": "JPN"
    },
    "has_original": bool,
    "has_parent": bool,
    "has_child": bool,
    "has_translation": bool,
    "lang_stats": {"JPN": 1, "CHI_HANS": 2, ...},
    "library_summary": [...]  # 库中已存在的作品
}
```

**推荐解决选项:**
- 原作品冲突: 建议"保留两者"
- 翻译版本冲突: 建议"保留两者"或"保留新版"
- 直接重复: 建议"保留新版"

### 3. 数据库模型扩展

**ConflictWork 表新增字段:**
```python
linked_works_info = Column(JSON)    # 发现的关联作品列表
analysis_info = Column(JSON)        # 详细分析报告
related_rjcodes = Column(JSON)      # 所有关联的 RJ 号
```

**新增 WorkLinkage 表:**
用于缓存作品关联信息，避免频繁调用 API

**新增 KikoeruSearchConfig 表:**
存储 Kikoeru 仓库搜索配置

### 4. API 端点

#### 关联作品查询

**GET `/api/linked-works/{rjcode}`**
获取作品的关联作品链

参数:
- `include_full_linkage`: 是否包含完整关联链
- `cue_languages`: 需要查询的语言列表（逗号分隔）

返回:
```json
{
  "rjcode": "RJxxx",
  "translation_info": {...},
  "linked_works": {
    "RJxxx": {"workno": "RJxxx", "work_type": "original", ...},
    "RJyyy": {"workno": "RJyyy", "work_type": "parent", ...}
  },
  "total_count": 5
}
```

**GET `/api/linked-works/{rjcode}/check-library`**
检查关联作品是否在库中

返回:
```json
{
  "rjcode": "RJxxx",
  "is_in_library": true,
  "library_works": [...],
  "total_linked": 5,
  "found_in_library": 2
}
```

#### 改进的查重检查

**POST `/api/conflicts/enhanced-check`**
改进的查重检查端点

请求体:
```json
{
  "rjcode": "RJxxx",
  "check_linked_works": true,
  "cue_languages": ["CHI_HANS", "CHI_HANT", "ENG"]
}
```

返回:
```json
{
  "is_duplicate": true,
  "conflict_type": "LINKED_WORK_TRANSLATION",
  "direct_duplicate": null,
  "linked_works_found": [...],
  "related_rjcodes": ["RJxxx", "RJyyy", ...],
  "analysis_info": {...},
  "resolution_options": [...]
}
```

#### Kikoeru 搜索配置管理

- **GET `/api/kikoeru-configs`**: 获取所有配置
- **POST `/api/kikoeru-configs`**: 创建配置
- **PUT `/api/kikoeru-configs/{id}`**: 更新配置
- **DELETE `/api/kikoeru-configs/{id}`**: 删除配置

配置格式:
```json
{
  "name": "我的Kikoeru",
  "search_url_template": "http://192.168.1.100:8080/api/search?keyword=%s",
  "show_url_template": "http://192.168.1.100:8080/works?keyword=%s",
  "enabled": true,
  "custom_headers": {}
}
```

## 与 VoiceLinks 的功能对比

| 功能 | VoiceLinks | Prekikoeru (改进后) |
|------|------------|---------------------|
| 关联作品检测 | ✅ | ✅ |
| 翻译版本识别 | ✅ | ✅ |
| 完整关联链查询 | ✅ | ✅ |
| Kikoeru 仓库搜索 | ✅ | ✅ (通过配置) |
| 多语言支持 | ✅ | ✅ |
| 冲突分析 | ✅ | ✅ |
| 缓存机制 | ✅ | ✅ |
| 库中作品检测 | ❌ (浏览器脚本) | ✅ (本地数据库) |
| 自动分类移动 | ❌ | ✅ |
| 冲突解决选项 | 显示状态 | 提供解决操作 |

## 使用场景示例

### 场景 1: 原作品已存在，添加翻译版本

**VoiceLinks 显示:**
- 原作 ✔ | 翻译(简中)

**Prekikoeru 处理:**
1. 检测冲突类型: `LINKED_WORK_ORIGINAL`
2. 推荐选项: "保留两者"
3. 自动将翻译版本移动到库中（不与原作冲突）

### 场景 2: 翻译版本已存在，添加原作

**VoiceLinks 显示:**
- ✘本作 | ✔ 翻译(简中)

**Prekikoeru 处理:**
1. 检测冲突类型: `LINKED_WORK_TRANSLATION`
2. 推荐选项: "保留两者"
3. 用户可以选择保留原作品（作为补充）

### 场景 3: 同一作品的重复 RJ 号

**VoiceLinks 显示:**
- 本作 ✔

**Prekikoeru 处理:**
1. 检测冲突类型: `DUPLICATE`
2. 提供选项: 保留新版/保留旧版/合并/跳过

## 后续建议

### 前端改进
1. **冲突页面增强**:
   - 显示关联作品树状图
   - 显示语言版本对比
   - 提供一键"保留两者"操作

2. **作品详情页**:
   - 显示关联作品列表
   - 提供跳转到关联作品的链接

3. **搜索功能**:
   - 支持搜索关联作品
   - 显示库存中已有的语言版本

### 配置扩展
1. 支持自动处理关联作品:
   - 自动保留不同语言版本
   - 自动跳过已存在的翻译版本

2. 自定义冲突解决策略:
   - 设置默认处理规则
   - 根据语言自动选择操作

## 技术说明

### 缓存策略
- API 响应缓存: 24 小时
- 关联作品链缓存: 24 小时
- 库中作品快照: 实时更新

### 支持的 RJ 号格式
- RJ + 6位数字 (旧格式)
- RJ + 8位数字 (新格式)
- RE + 数字 (其他类型)
- VJ/BJ + 数字 (视频/漫画)

### 支持的语言代码
- JPN: 日语（原作品）
- CHI_HANS: 简体中文
- CHI_HANT: 繁体中文
- ENG: 英语
- KO_KR: 韩语
- 其他 DLsite 支持的语言
