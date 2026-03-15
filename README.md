# Prekikoeru - DLsite 音声作品智能整理工具

现代化的 DLsite 音声作品压缩包自动处理工具，支持智能解压、元数据获取、文件分类、ASMR 同步下载等功能。

> **重要提示**: 使用本软件即表示您已阅读并同意 [免责声明与使用条款](DISCLAIMER.md)。本软件仅限 18 周岁及以上成年人使用。

## 功能亮点

- **智能解压**: 自动识别压缩格式、修复后缀名、支持密码爆破、分卷合并、自动检测日区编码
- **元数据获取**: 自动从 DLsite 获取作品信息，支持关联作品查询、日语元数据选项
- **智能分类**: 按社团、系列等规则自动分类到存储库
- **ASMR 同步下载**: 扫描字幕文件夹，自动下载对应资源
- **重复检测**: 检测重复作品和多语言版本
- **Web UI**: 现代化的 Web 界面，支持实时进度查看

## 快速开始

### Windows 用户

1. 从 [Releases](https://github.com/canforgive/KikoeruTool/releases) 下载最新版本
2. 解压后双击运行 `prekikoeru.exe`
3. 浏览器访问 http://localhost:8000

### Docker 部署

```bash
docker pull ghcr.io/canforgive/kikoerutool:latest
```

```yaml
version: '3'
services:
  prekikoeru:
    image: ghcr.io/canforgive/kikoerutool:latest
    container_name: prekikoeru
    ports:
      - "8000:8000"
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Asia/Shanghai
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - /path/to/input:/input
      - /path/to/library:/library
      - /path/to/temp:/temp
    restart: unless-stopped
```

详细部署说明请查看 [Docker 部署指南](docs/DOCKER.md)。

## 文档

| 文档 | 说明 |
|------|------|
| [免责声明](DISCLAIMER.md) | 使用软件前请务必阅读 |
| [功能介绍](docs/INTRODUCTION.md) | 详细功能说明和使用指南 |
| [Docker 部署](docs/DOCKER.md) | Docker 和 Unraid 部署指南 |
| [开发指南](docs/DEVELOPMENT.md) | 本地开发、构建、测试 |

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

## 致谢

本项目参考和借鉴了以下开源项目：

- [Sakyoriii/prekikoeru](https://github.com/Sakyoriii/prekikoeru)
- [yodhcn/dlsite-doujin-renamer](https://github.com/yodhcn/dlsite-doujin-renamer)
- [Number178/kikoeru-quasar](https://github.com/Number178/kikoeru-quasar)