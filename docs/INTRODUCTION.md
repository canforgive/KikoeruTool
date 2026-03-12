# Prekikoeru - DLsite 音声作品智能整理工具

## 软件简介

Prekikoeru 是一款专为 DLsite 音声作品设计的智能整理工具。它能够自动处理压缩包、获取元数据、整理文件结构，大大简化了音声作品的管理流程。

## 核心功能

### 1. 智能解压处理

- **自动识别压缩格式**: 支持 ZIP、RAR、7z、tar、gz 等多种压缩格式
- **分卷压缩包支持**: 自动识别并合并分卷文件（如 .part1.rar、.7z.001 等）
- **密码破解**: 内置密码库，支持自动尝试常用密码
- **嵌套解压**: 自动解压多层嵌套的压缩包
- **后缀名修复**: 自动检测并修复错误的文件后缀名

### 2. 元数据获取

- **DLsite 信息获取**: 自动从 DLsite 获取作品标题、作者、社团、标签等信息
- **关联作品查询**: 自动查询同一作品的不同语言版本
- **ASMR.one 数据同步**: 支持从 asmr.one 获取资源下载信息
- **智能缓存**: 元数据本地缓存，减少重复请求

### 3. 文件过滤系统

- **正则表达式过滤**: 支持使用正则表达式自定义过滤规则
- **文件类型过滤**: 按扩展名过滤（如只保留音频文件）
- **文件夹过滤**: 过滤特定名称的文件夹
- **大小过滤**: 过滤过小的文件（如缩略图）

### 4. 智能分类整理

- **按社团分类**: 自动按社团名称创建目录结构
- **按系列分类**: 支持按系列作品整理
- **重复检测**: 检测并标记重复作品
- **多语言版本管理**: 自动识别同一作品的不同语言版本

### 5. ASMR 同步下载

- **字幕扫描**: 扫描字幕文件夹，自动识别 RJ 号
- **版本搜索**: 自动搜索 asmr.one 上的可用版本
- **优先级下载**: 按语言优先级选择最佳版本
- **断点续传**: 支持下载中断后继续下载
- **自动重试**: 失败任务自动进入重试队列，支持 Cron 调度

### 6. 字幕处理

- **LRC 广告清理**: 使用正则表达式清理字幕中的广告信息
- **繁简转换**: 自动将繁体中文字幕转换为简体中文
- **字幕同步**: 将字幕文件与下载的音频文件同步

### 7. 监视器功能

- **文件夹监视**: 自动监视指定文件夹，新文件自动处理
- **实时处理**: 文件复制完成后立即开始处理
- **队列管理**: 支持暂停、恢复、取消任务

### 8. 密码管理

- **密码库**: 存储常用解压密码
- **智能匹配**: 根据作品信息自动匹配可能的密码
- **密码分享**: 支持从社区密码库同步密码

## 界面介绍

### 仪表盘

显示系统概览信息：
- 处理任务统计
- 库存作品数量
- 磁盘使用情况
- 最近处理记录

### 任务列表

- 实时显示所有任务状态
- 支持暂停、恢复、取消操作
- 显示详细进度和错误信息
- 任务失败时显示失败文件列表

### 库存管理

- 浏览已处理的作品
- 搜索和筛选功能
- 查看作品详细信息
- 支持重新处理

### 问题作品

- 显示处理失败的作品
- 查看错误详情
- 支持手动修复后重新处理

### ASMR 同步下载

- 扫描字幕文件夹
- 预览下载内容
- 批量选择下载
- 等待重试任务管理

### 设置

#### 存储路径设置
- 输入目录：待处理的压缩包位置
- 输出目录：处理完成后的存放位置
- 临时目录：解压临时文件存放位置
- 已处理压缩包目录：归档的压缩包位置
- ASMR 字幕文件夹：字幕文件位置

#### 解压设置
- 自动修复后缀名
- 嵌套解压深度
- 密码尝试配置

#### 过滤规则
- 文件过滤规则
- 文件夹过滤规则
- 正则表达式配置

#### 重命名规则
- 文件名格式模板
- 特殊字符处理
- 扁平化文件夹选项

#### ASMR 同步设置
- API 地址配置
- 代理设置
- 重试间隔（Cron 格式）
- 最大重试次数
- LRC 广告清理规则
- 繁简转换开关

#### 已处理压缩包清理
- 按时间/数量/容量清理
- Cron 调度配置
- 启动扫描开关

## 技术架构

### 后端
- **框架**: FastAPI (Python 3.11+)
- **数据库**: SQLite + SQLAlchemy ORM
- **任务调度**: APScheduler + Cron
- **文件处理**: 7-Zip 命令行工具

### 前端
- **框架**: Vue 3 + Vite
- **UI 组件**: Element Plus
- **状态管理**: Pinia
- **HTTP 客户端**: Axios

### 部署方式
- **本地开发**: Python + Node.js
- **打包发布**: PyInstaller 单文件可执行程序
- **Docker**: 支持容器化部署

## 安装与使用

### Windows 打包版本

1. 从 [Releases](https://github.com/canforgive/KikoeruTool/releases) 下载最新版本
2. 解压到任意目录
3. 双击运行 `prekikoeru.exe`
4. 浏览器自动打开 http://localhost:8000

### Docker 部署

```bash
# 拉取镜像
docker pull ghcr.io/canforgive/kikoerutool:latest

# 运行容器
docker run -d \
  --name kikoeru \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./library:/library \
  -v ./input:/input \
  ghcr.io/canforgive/kikoerutool:latest
```

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/canforgive/KikoeruTool.git
cd KikoeruTool

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install

# 启动后端
cd ../backend
python -m app.main

# 启动前端（新终端）
cd frontend
npm run dev
```

## 配置说明

配置文件位于 `data/config/config.yaml`，首次运行自动生成。

### 基础配置示例

```yaml
storage:
  input_path: "./data/input"           # 输入目录
  library_path: "./data/library"       # 库存目录
  temp_path: "./data/temp"             # 临时目录
  processed_archives_path: "./data/processed"  # 已处理压缩包

extract:
  auto_repair_extension: true          # 自动修复后缀名
  max_nested_depth: 3                   # 最大嵌套解压深度

rename:
  template: "{rjcode} {title}"          # 重命名模板
  flatten_single_subfolder: true        # 扁平化单层子文件夹

asmr_sync:
  enabled: true
  api_base_url: "https://api.asmr-200.com/api"
  retry_cron: "0 */1 * * *"             # 每小时重试
  max_retry_count: 10
  lrc_clean_enabled: true               # 启用 LRC 广告清理
  simplify_chinese_enabled: true        # 启用繁简转换
```

## 常见问题

### Q: 压缩包解压失败？

检查以下几点：
1. 确保已安装 7-Zip 并添加到系统 PATH
2. 尝试手动解压确认文件完整性
3. 检查密码库是否包含正确密码

### Q: 元数据获取失败？

1. 检查网络连接
2. 确认 DLsite 网站 accessible
3. 查看日志获取详细错误信息

### Q: 分卷压缩包无法识别？

1. 确保所有分卷文件在同一目录
2. 分卷文件名格式应为：`xxx.part1.rar` 或 `xxx.7z.001`
3. 首卷文件必须存在

### Q: ASMR 同步下载一直重试？

1. 检查该作品是否在 asmr.one 上存在
2. 确认网络连接正常
3. 可以手动取消任务

## 更新日志

### v1.5.0
- 新增 ASMR 同步下载功能
- 新增字幕繁简转换
- 新增 LRC 广告清理
- 优化分卷压缩包识别
- 新增启动扫描配置开关

### v1.4.0
- 新增 Kikoeru 服务器集成
- 新增关联作品递归查重
- 优化元数据获取逻辑

### v1.3.0
- 新增已处理压缩包智能清理
- 新增密码库智能清理
- 优化任务队列管理

## 开源协议

本项目采用 MIT 协议开源。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 联系方式

- GitHub Issues: https://github.com/canforgive/KikoeruTool/issues