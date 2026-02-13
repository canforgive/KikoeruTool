# 改进的查重功能 - 快速开始指南

## 概述

本指南介绍如何使用改进后的查重功能，该功能支持检测关联作品（不同语言版本）。

## 新功能

### 1. 查询关联作品

**API 端点:** `GET /api/linked-works/{rjcode}`

**示例:**
```bash
curl "http://localhost:8000/api/linked-works/RJ01234567?include_full_linkage=true&cue_languages=CHI_HANS,CHI_HANT,ENG"
```

**返回示例:**
```json
{
  "rjcode": "RJ01234567",
  "translation_info": {
    "is_original": true,
    "is_parent": false,
    "is_child": false,
    "lang": "JPN"
  },
  "linked_works": {
    "RJ01234567": {
      "workno": "RJ01234567",
      "work_type": "original",
      "lang": "JPN",
      "title": "原作品标题"
    },
    "RJ01234568": {
      "workno": "RJ01234568",
      "work_type": "parent",
      "lang": "CHI_HANS",
      "title": "中文版标题"
    }
  },
  "total_count": 2
}
```

### 2. 检查库中关联作品

**API 端点:** `GET /api/linked-works/{rjcode}/check-library`

**示例:**
```bash
curl "http://localhost:8000/api/linked-works/RJ01234567/check-library"
```

**返回示例:**
```json
{
  "rjcode": "RJ01234567",
  "is_in_library": true,
  "library_works": [
    {
      "rjcode": "RJ01234568",
      "work_type": "parent",
      "lang": "CHI_HANS",
      "work_name": "中文版标题",
      "path": "E:/Library/RJ012xxxx/RJ01234568 中文版标题",
      "size": 123456789,
      "file_count": 15
    }
  ],
  "total_linked": 2,
  "found_in_library": 1
}
```

### 3. 改进的查重检查

**API 端点:** `POST /api/conflicts/enhanced-check`

**示例:**
```bash
curl -X POST "http://localhost:8000/api/conflicts/enhanced-check" \
  -H "Content-Type: application/json" \
  -d '{
    "rjcode": "RJ01234567",
    "check_linked_works": true,
    "cue_languages": ["CHI_HANS", "CHI_HANT", "ENG"]
  }'
```

**返回示例 (发现关联作品):**
```json
{
  "is_duplicate": true,
  "conflict_type": "LINKED_WORK_TRANSLATION",
  "direct_duplicate": null,
  "linked_works_found": [
    {
      "rjcode": "RJ01234568",
      "work_type": "parent",
      "lang": "CHI_HANS",
      "path": "E:/Library/...",
      "size": 123456789,
      "work_name": "中文版标题"
    }
  ],
  "related_rjcodes": ["RJ01234567", "RJ01234568"],
  "analysis_info": {
    "current_work": {
      "rjcode": "RJ01234567",
      "work_type": "original",
      "lang": "JPN"
    },
    "has_original": true,
    "has_translation": true,
    "library_summary": [...]
  },
  "resolution_options": [
    {
      "action": "KEEP_BOTH",
      "label": "保留两者",
      "description": "原作品和翻译版本是不同作品，建议保留",
      "recommend": true
    },
    {
      "action": "KEEP_NEW",
      "label": "保留新版（原作品）",
      "description": "用新版原作品替换翻译版本（不推荐）"
    }
  ]
}
```

## Kikoeru 搜索配置

### 创建配置

**API 端点:** `POST /api/kikoeru-configs`

**示例:**
```bash
curl -X POST "http://localhost:8000/api/kikoeru-configs" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "家庭Kikoeru",
    "search_url_template": "http://192.168.1.100:8080/api/search?keyword=%s",
    "show_url_template": "http://192.168.1.100:8080/works?keyword=%s",
    "enabled": true
  }'
```

### 获取配置列表

**API 端点:** `GET /api/kikoeru-configs`

### 更新配置

**API 端点:** `PUT /api/kikoeru-configs/{config_id}`

### 删除配置

**API 端点:** `DELETE /api/kikoeru-configs/{config_id}`

## 前端集成建议

### 1. 冲突页面增强

在 `Conflicts.vue` 中添加关联作品显示：

```vue
<template>
  <div v-if="conflict.linked_works_info && conflict.linked_works_info.length > 0">
    <h4>发现关联作品:</h4>
    <div v-for="work in conflict.linked_works_info" :key="work.rjcode" class="linked-work">
      <span class="work-type">{{ work.work_type }}</span>
      <span class="work-lang">{{ work.lang }}</span>
      <span class="work-name">{{ work.work_name }}</span>
      <span class="work-path">{{ work.path }}</span>
    </div>
  </div>
</template>
```

### 2. 关联作品树形图

为复杂的关联关系创建可视化：

```vue
<template>
  <div class="linkage-tree">
    <div class="original-work">
      原作品: {{ originalWork.rjcode }}
    </div>
    <div class="translations">
      <div v-for="trans in translations" :key="trans.rjcode" class="translation">
        {{ trans.lang }}: {{ trans.rjcode }}
      </div>
    </div>
  </div>
</template>
```

### 3. 添加"检查关联作品"按钮

在入库流程中添加手动检查按钮：

```vue
<template>
  <div class="duplicate-check-actions">
    <button @click="checkDirectDuplicate">检查直接重复</button>
    <button @click="checkLinkedWorks">检查关联作品</button>
  </div>
</template>

<script>
async function checkLinkedWorks() {
  const response = await fetch(`/api/linked-works/${this.rjcode}/check-library`);
  const data = await response.json();
  
  if (data.is_in_library) {
    this.showLinkedWorksDialog(data.library_works);
  }
}
</script>
```

## 常见使用场景

### 场景 1: 处理翻译版本

**问题:** 已有原作品 RJ01234567，现在要添加中文版 RJ01234568

**解决:**
1. 系统检测到这是关联作品
2. 显示冲突类型: `LINKED_WORK_ORIGINAL`
3. 推荐操作: "保留两者"
4. 两个版本都保留在库中

### 场景 2: 发现重复 RJ 号

**问题:** 库中已有 RJ01234567，又添加了同 RJ 号的新版本

**解决:**
1. 系统检测到直接重复
2. 显示冲突类型: `DUPLICATE`
3. 提供选项:
   - 保留新版（删除旧版）
   - 保留旧版（删除新版）
   - 合并（保留两个，新版加编号）
   - 跳过（删除新版）

### 场景 3: 批量检查

**问题:** 想检查一批作品是否已有关联版本在库中

**解决:**
```javascript
async function batchCheckLinkedWorks(rjcodes) {
  const results = await Promise.all(
    rjcodes.map(rjcode => 
      fetch(`/api/linked-works/${rjcode}/check-library`).then(r => r.json())
    )
  );
  
  return results.filter(r => r.is_in_library);
}
```

## 注意事项

1. **API 缓存**: DLsite API 响应缓存 24 小时，如需刷新请重启服务
2. **网络依赖**: 关联作品查询需要访问 DLsite API，确保网络通畅
3. **性能考虑**: 完整关联链查询可能较慢，建议在后台执行
4. **语言代码**: 使用标准语言代码（CHI_HANS, CHI_HANT, ENG 等）

## 故障排除

### 问题: API 返回 500 错误

**可能原因:**
- DLsite API 不可访问
- RJ 号格式错误

**解决:**
- 检查网络连接
- 确认 RJ 号格式正确（RJ + 6-8位数字）

### 问题: 关联作品查询为空

**可能原因:**
- 该作品没有翻译版本
- API 响应被缓存

**解决:**
- 确认 DLsite 上该作品确实有翻译版本
- 等待 24 小时缓存过期或重启服务

### 问题: 库中作品检测不准确

**可能原因:**
- LibrarySnapshot 表未同步

**解决:**
- 执行库扫描以更新快照表

## 配置文件示例

```yaml
# config.yaml 中的 Kikoeru 配置（可选）
kikoeru_search:
  enabled: true
  configs:
    - name: "家庭Kikoeru"
      search_url: "http://192.168.1.100:8080/api/search?keyword=%s"
      show_url: "http://192.168.1.100:8080/works?keyword=%s"
      enabled: true
```

## 更新日志

### v1.1.0 - 改进查重功能
- ✅ 关联作品检测
- ✅ 翻译版本识别
- ✅ 详细冲突分析
- ✅ Kikoeru 搜索配置
- ✅ 改进的 API 端点

## 技术支持

如有问题，请查看:
1. 后端日志: `data/app.log`
2. API 文档: `http://localhost:8000/docs`
3. 数据库: `data/cache.db`
