# Docker 部署指南

## 目录

- [快速部署](#快速部署)
- [Unraid 部署](#unraid-部署)
- [目录映射说明](#目录映射说明)
- [常见问题](#常见问题)

---

## 快速部署

### Docker Compose（推荐）

```yaml
version: '3.8'

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

启动：
```bash
docker-compose up -d
```

### Docker CLI

```bash
docker run -d \
  --name prekikoeru \
  -p 8000:8000 \
  -v ./config:/app/config \
  -v ./data:/app/data \
  -v /path/to/input:/input \
  -v /path/to/library:/library \
  -v /path/to/temp:/temp \
  -e TZ=Asia/Shanghai \
  ghcr.io/canforgive/kikoerutool:latest
```

---

## Unraid 部署

### 方法 1：Community Applications

1. 打开 Unraid Web 界面，进入 **Apps** 标签
2. 搜索 "Prekikoeru"
3. 点击安装，配置映射路径

### 方法 2：手动模板

1. 在 Unraid 中进入 **Docker** → **Add Container**
2. 配置以下映射：

| 容器路径 | 说明 | 建议映射 |
|---------|------|---------|
| `/app/config` | 配置文件 | `appdata/prekikoeru/config` |
| `/app/data` | 数据库和日志 | `appdata/prekikoeru/data` |
| `/input` | 待处理压缩包 | 下载目录 |
| `/temp` | 解压临时文件 | SSD 缓存目录 |
| `/library` | 整理好的作品库 | 媒体库目录 |
| `/existing` | 已有作品（可选） | 已有作品目录 |
| `/processed` | 已处理压缩包（可选） | 备份目录 |

---

## 目录映射说明

### 必须映射

| 路径 | 说明 |
|------|------|
| `/app/config` | 配置文件目录 |
| `/app/data` | 数据库、日志 |
| `/input` | 待处理压缩包 |
| `/library` | 整理后的作品库 |
| `/temp` | 解压临时目录（建议 SSD） |

### 可选映射

| 路径 | 说明 |
|------|------|
| `/existing` | 已有作品文件夹 |
| `/processed` | 已处理压缩包备份 |
| `/Subtitles` | ASMR 同步字幕目录 |

### 数据流

```
/input（下载目录）
    ↓ 监视器检测
/temp（解压）
    ↓ 获取元数据、重命名、分类
/library（作品库）
    ↓
/processed（可选备份）
```

---

## 常见问题

### Q: 无法访问 Web 界面

1. 检查容器状态：`docker ps | grep prekikoeru`
2. 查看日志：`docker logs prekikoeru`
3. 确认端口未被占用

### Q: 文件权限问题

```bash
chmod -R 777 /path/to/library
chmod -R 777 /path/to/temp
```

### Q: 如何更新

```bash
docker-compose pull
docker-compose up -d
```

### Q: 备份建议

**必须备份**：
- `/app/data/app.db` - 数据库
- `/app/config/config.yaml` - 配置文件

---

## 性能优化

1. **临时目录使用 SSD**：解压大文件时显著提升速度
2. **调整文件描述符**：
   ```yaml
   ulimits:
     nofile:
       soft: 65536
       hard: 65536
   ```

## 技术支持

- **GitHub Issues**: https://github.com/canforgive/KikoeruTool/issues
- **API 文档**: http://localhost:8000/docs