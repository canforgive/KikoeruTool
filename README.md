# Prekikoeru - DLsite 作品整理工具

现代化的 DLsite 音声作品压缩包自动处理工具。

## 🚀 快速开始（本地开发）

### 环境要求

- Python 3.11+
- Node.js 18+
- 7-Zip (Windows) / p7zip (Linux)

### 一键启动

**Windows:**
```cmd
start-dev.bat
```

**Linux/Mac:**
```bash
chmod +x start-dev.sh
./start-dev.sh
```

然后访问 http://localhost:5173

### 手动启动

**1. 安装依赖**

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

**2. 创建测试目录**

```bash
mkdir -p test_data/input
mkdir -p test_data/library
mkdir -p test_data/temp
```

**3. 启动服务**

终端1（后端）：
```bash
cd backend
python -m app.main
```

终端2（前端）：
```bash
cd frontend
npm run dev
```

**4. 开始测试**

- 复制压缩包到 `test_data/input/`
- 打开 http://localhost:5173
- 查看任务处理进度

## 📦 功能特性

- ✅ **智能解压**: 自动检测文件类型、修复后缀名、支持密码爆破、分卷自动合并
- ✅ **文件过滤**: 基于正则表达式的灵活过滤系统
- ✅ **元数据获取**: 自动从 DLsite 获取作品信息并缓存
- ✅ **智能分类**: 按社团、系列等规则自动分类到存储库
- ✅ **重复检测**: 检测重复作品和多语言版本
- ✅ **文件夹监视**: 自动监视文件夹，新文件自动处理
- ✅ **Web UI**: 现代化的 Web 界面，支持实时进度查看

## 🏗️ 项目结构

```
prekikoeru/
├── backend/           # FastAPI 后端
├── frontend/          # Vue3 前端
├── config/           # 配置文件
├── test_data/        # 测试数据（自动创建）
├── start-dev.bat     # Windows启动脚本
├── start-dev.sh      # Linux/Mac启动脚本
└── docker-compose.yml # Docker配置
```

## 🧪 测试

```bash
# 创建测试数据
./create_test_data.sh

# 运行测试
./test.sh

# 详细测试文档
docs/LOCAL_DEV.md
docs/TESTING.md
```

## 🐳 Docker 部署

```bash
# 修改 docker-compose.yml 中的路径
# 启动服务
docker-compose up -d

# 访问 http://localhost:8000
```

## 📖 文档

- [本地开发指南](docs/LOCAL_DEV.md)
- [测试指南](docs/TESTING.md)
- [API文档](http://localhost:8000/docs) (服务启动后)

## 📝 配置

编辑 `config/config.yaml`：

```yaml
storage:
  input_path: "./test_data/input"      # 待处理文件夹
  temp_path: "./test_data/temp"        # 临时文件夹
  library_path: "./test_data/library"  # 库存文件夹
```

## 🔧 故障排除

**端口被占用？**
- 后端：修改 `backend/app/main.py` 中的端口
- 前端：修改 `frontend/vite.config.js` 中的端口

**7z 未找到？**
- Windows: 安装 7-Zip 并添加到 PATH
- Linux: `sudo apt-get install p7zip-full`

**权限错误？**
- Windows: 以管理员身份运行
- Linux: `chmod -R 777 test_data`

## 📄 许可证

MIT License
