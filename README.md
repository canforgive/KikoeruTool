# Prekikoeru - DLsite 音声作品智能整理工具

现代化的 DLsite 音声作品压缩包自动处理工具，支持智能解压、元数据获取、文件分类、ASMR 同步下载等功能。

> **重要提示**: 使用本软件前请务必阅读 [免责声明与使用条款](DISCLAIMER.md)。本软件仅限 18 周岁及以上成年人使用。

## 功能亮点

- **智能解压**: 自动识别压缩格式、修复后缀名、支持密码爆破、分卷合并
- **元数据获取**: 自动从 DLsite 获取作品信息，支持关联作品查询
- **智能分类**: 按社团、系列等规则自动分类到存储库
- **ASMR 同步下载**: 扫描字幕文件夹，自动下载对应资源
- **字幕处理**: LRC 广告清理、繁简转换
- **重复检测**: 检测重复作品和多语言版本
- **文件夹监视**: 自动监视文件夹，新文件自动处理
- **Web UI**: 现代化的 Web 界面，支持实时进度查看

## 快速开始

### Windows 用户

1. 从 [Releases](https://github.com/canforgive/KikoeruTool/releases) 下载最新版本
2. 解压后双击运行 `prekikoeru.exe`
3. 浏览器访问 http://localhost:8000

### Docker 部署

```bash
# 拉取镜像
docker pull ghcr.io/canforgive/kikoerutool:latest

# 运行
docker run -d -p 8000:8000 \
  -v ./data:/app/data \
  -v ./library:/library \
  ghcr.io/canforgive/kikoerutool:latest
```

### 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt
python -m app.main

# 前端（新终端）
cd frontend && npm install
npm run dev
```

## 文档

- **[免责声明与使用条款](DISCLAIMER.md)** - 请务必阅读
- [软件介绍](docs/INTRODUCTION.md) - 详细功能说明和使用指南
- [本地开发指南](docs/LOCAL_DEV.md) - 开发环境配置
- [构建指南](docs/BUILD.md) - 打包和发布
- [API 文档](http://localhost:8000/docs) - 服务启动后访问

## 项目结构

```
prekikoeru/
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/       # API 路由
│   │   ├── core/      # 核心服务
│   │   ├── models/    # 数据模型
│   │   └── config/    # 配置管理
│   └── requirements.txt
├── frontend/          # Vue3 前端
│   ├── src/
│   │   ├── views/     # 页面组件
│   │   ├── api/       # API 封装
│   │   └── stores/    # 状态管理
│   └── package.json
└── docs/              # 文档
```

## 许可证

MIT License
