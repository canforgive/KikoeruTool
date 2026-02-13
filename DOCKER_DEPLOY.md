# Prekikoeru Docker 部署指南

## 目录

- [Unraid 部署（推荐）](#unraid-部署推荐)
- [Docker Compose 部署](#docker-compose-部署)
- [Docker CLI 部署](#docker-cli-部署)
- [构建自己的镜像](#构建自己的镜像)
- [目录结构说明](#目录结构说明)
- [常见问题](#常见问题)

---

## Unraid 部署（推荐）

### 方法 1：使用 Community Applications

1. 打开 Unraid Web 界面，进入 **Apps** 标签
2. 搜索 "Prekikoeru"
3. 点击安装，配置以下参数：

**必须配置的映射路径：**
- **配置目录**: `/mnt/user/appdata/prekikoeru/config`
- **数据目录**: `/mnt/user/appdata/prekikoeru/data`
- **输入目录**: 你的下载目录，如 `/mnt/user/downloads/dl/done`
- **临时目录**: 建议映射到 SSD，`/mnt/cache/appdata/prekikoeru/temp`
- **作品库目录**: 你的媒体库目录，如 `/mnt/user/media/dlsite`

**可选映射路径：**
- **已有文件夹目录**: 如果你有已整理的作品
- **已处理压缩包目录**: 用于备份已处理的压缩包

4. 点击 **Apply** 安装

### 方法 2：手动导入 XML 模板

1. 下载 `unraid-template.xml` 文件
2. 在 Unraid 中进入 **Docker** → **Add Container**
3. 点击 **Import** 按钮，选择 XML 文件
4. 修改路径为你实际的目录
5. 点击 **Apply**

---

## Docker Compose 部署

### 1. 创建项目目录

```bash
mkdir -p /mnt/user/appdata/prekikoeru
cd /mnt/user/appdata/prekikoeru
```

### 2. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  prekikoeru:
    image: prekikoeru/prekikoeru:latest
    container_name: prekikoeru
    ports:
      - "8000:8000"
    volumes:
      # 配置目录
      - ./config:/app/config
      # 数据目录
      - ./data:/app/data
      # 输入目录（修改为你的下载目录）
      - /mnt/user/downloads/dl/done:/input
      # 临时目录（建议 SSD）
      - /mnt/cache/appdata/prekikoeru/temp:/temp
      # 作品库目录
      - /mnt/user/media/dlsite:/library
      # 已有文件夹目录（可选）
      - /mnt/user/media/dlsite:/existing
      # 已处理压缩包目录（可选）
      - ./processed:/processed
    environment:
      - TZ=Asia/Shanghai
    privileged: true
    restart: unless-stopped
```

### 3. 启动服务

```bash
docker-compose up -d
```

### 4. 查看日志

```bash
docker-compose logs -f
```

---

## Docker CLI 部署

```bash
docker run -d \
  --name prekikoeru \
  --privileged \
  -p 8000:8000 \
  -v /mnt/user/appdata/prekikoeru/config:/app/config \
  -v /mnt/user/appdata/prekikoeru/data:/app/data \
  -v /mnt/user/downloads/dl/done:/input \
  -v /mnt/cache/appdata/prekikoeru/temp:/temp \
  -v /mnt/user/media/dlsite:/library \
  -v /mnt/user/media/dlsite:/existing \
  -v /mnt/user/appdata/prekikoeru/processed:/processed \
  -e TZ=Asia/Shanghai \
  --ulimit nofile=65536:65536 \
  --restart unless-stopped \
  prekikoeru/prekikoeru:latest
```

---

## 构建自己的镜像

如果你想自己构建镜像（例如修改代码后）：

### 1. 克隆代码

```bash
git clone https://github.com/anomalyco/prekikoeru.git
cd prekikoeru
```

### 2. 构建镜像

```bash
docker build -t prekikoeru:local .
```

### 3. 运行

修改 docker-compose.yml 中的镜像名：

```yaml
services:
  prekikoeru:
    image: prekikoeru:local  # 使用本地构建的镜像
    # ... 其他配置
```

---

## 目录结构说明

### 容器内路径

| 容器路径 | 说明 | 建议映射 |
|---------|------|---------|
| `/app/config` | 配置文件 | `./config` 或 `appdata/prekikoeru/config` |
| `/app/data` | 数据库和日志 | `./data` 或 `appdata/prekikoeru/data` |
| `/input` | 待处理的压缩包 | 下载目录 |
| `/temp` | 解压临时文件 | SSD 缓存目录 |
| `/library` | 整理好的作品库 | 媒体库目录 |
| `/existing` | 已有作品文件夹 | 可选，已有作品目录 |
| `/processed` | 已处理压缩包 | 可选，备份目录 |

### 数据流

```
下载目录 (/input)
    ↓
监视器检测新文件
    ↓
解压到临时目录 (/temp)
    ↓
获取元数据（DLsite API）
    ↓
重命名和分类
    ↓
移动到作品库 (/library)
    ↓
（可选）备份压缩包到 /processed
```

---

## 首次使用配置

### 1. 访问 Web 界面

打开浏览器访问：`http://your-unraid-ip:8000`

### 2. 初始配置

进入 **设置** 页面：

1. **存储设置**: 确认路径正确（Docker 映射已配置好，通常无需修改）
2. **解压设置**: 
   - 7z 路径已内置，无需修改
   - 配置密码列表（可选）
3. **重命名设置**: 选择喜欢的命名模板
4. **分类设置**: 配置分类规则（如按社团、系列分类）
5. **元数据设置**: 配置代理（如果需要）

### 3. 测试运行

1. 将一个测试压缩包放入 `/input` 目录
2. 在 **任务** 页面查看处理进度
3. 检查 `/library` 目录是否正确整理

---

## 常见问题

### Q: 容器启动后无法访问 Web 界面

**排查步骤：**
1. 检查容器是否运行：`docker ps | grep prekikoeru`
2. 查看日志：`docker logs prekikoeru`
3. 确认端口映射正确
4. 检查防火墙设置

### Q: 文件权限问题

**解决方案：**
容器使用 privileged 模式运行，应该能正常访问文件。如果遇到权限问题：

```bash
# 修改映射目录权限
chmod -R 777 /mnt/user/appdata/prekikoeru
chmod -R 777 /mnt/user/media/dlsite
```

### Q: 如何处理 Windows 移植过来的数据？

如果之前使用 Windows 版本：

1. **数据库迁移**：将 Windows 的 `data/app.db` 复制到 `/mnt/user/appdata/prekikoeru/data/`
2. **配置文件**：将 Windows 的 `config/config.yaml` 复制到 `/mnt/user/appdata/prekikoeru/config/`
3. **作品库**：将 Windows 的作品库直接复制到映射的 `/library` 目录

### Q: 临时目录使用 SSD 的好处

解压大文件时会产生大量 I/O：
- **机械硬盘**：解压速度慢，影响阵列性能
- **SSD 缓存**：解压速度快，减少机械硬盘磨损

### Q: 如何更新到最新版本？

**Docker Compose：**
```bash
cd /mnt/user/appdata/prekikoeru
docker-compose pull
docker-compose up -d
```

**Unraid CA：**
在 Docker 页面点击 "Check for Updates"

### Q: 备份策略建议

**必须备份：**
- `/app/data/app.db` - 数据库（包含所有作品信息、任务历史）
- `/app/config/config.yaml` - 配置文件

**可选备份：**
- `/library` - 作品库（文件较大，按需备份）
- `/processed` - 已处理压缩包

**自动备份脚本示例：**
```bash
#!/bin/bash
# 添加到 Unraid User Scripts 插件
DATE=$(date +%Y%m%d)
mkdir -p /mnt/user/backups/prekikoeru
cp /mnt/user/appdata/prekikoeru/data/app.db /mnt/user/backups/prekikoeru/app.db.$DATE
cp /mnt/user/appdata/prekikoeru/config/config.yaml /mnt/user/backups/prekikoeru/config.yaml.$DATE
# 保留最近 30 天备份
find /mnt/user/backups/prekikoeru -name "*.db.*" -mtime +30 -delete
```

---

## 性能优化建议

### 1. 使用 SSD 作为临时目录

```yaml
volumes:
  - /mnt/cache/appdata/prekikoeru/temp:/temp
```

### 2. 调整文件描述符限制

已在 docker-compose 中配置：
```yaml
ulimits:
  nofile:
    soft: 65536
    hard: 65536
```

### 3. 内存使用

- **最小内存**: 512MB
- **推荐内存**: 1-2GB（处理大文件时）
- **Unraid 设置**: 在容器设置中分配适当的内存限制

---

## 技术支持

- **GitHub Issues**: https://github.com/anomalyco/prekikoeru/issues
- **文档**: 参见项目 README.md
- **Unraid 论坛**: 在 Unraid 社区论坛搜索 "Prekikoeru"

---

## 更新日志

### v1.0.0
- 首次 Docker 版本发布
- 支持 Unraid 部署
- 集成前端构建
- 优化路径映射
