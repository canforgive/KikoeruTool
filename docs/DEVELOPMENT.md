# 开发指南

## 快速开始

### 1. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

### 2. 启动开发服务器

**Windows**:
```cmd
start-dev.bat
```

**Linux/Mac**:
```bash
chmod +x start-dev.sh
./start-dev.sh
```

**手动启动**:
```bash
# 终端1 - 后端
cd backend && python -m app.main

# 终端2 - 前端
cd frontend && npm run dev
```

### 3. 访问应用

- 前端界面: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

---

## 7-Zip 配置

### Windows

1. 安装 7-Zip：https://www.7-zip.org/
2. 安装时勾选 **"Add 7-Zip to PATH"**
3. 在设置页面保持路径为 `7z` 或填写完整路径：
   ```
   C:\Program Files\7-Zip\7z.exe
   ```

### Linux/Docker

无需配置，镜像已内置 7zip。

### 验证

```bash
# Windows
7z --help
# 或
"C:\Program Files\7-Zip\7z.exe" --help

# Linux
which 7z
```

---

## 构建 EXE

### 前置条件

- Python 3.9+
- Node.js 16+
- 7-Zip

### 构建步骤

```bash
# 1. 构建前端
cd frontend
npm install
npm run build

# 2. 构建 EXE
cd ../backend
pip install pyinstaller
python build.py
```

### 构建产物

| 文件 | 说明 |
|------|------|
| `prekikoeru.exe` | 带控制台版本，方便调试 |
| `prekikoeru-noconsole.exe` | 无控制台版本，日常使用 |

### 手动构建单个版本

```bash
pyinstaller build_prekikoeru.spec --clean
pyinstaller build_prekikoeru-noconsole.spec --clean
```

---

## 测试

### 后端测试

```bash
cd backend
pip install -r requirements-test.txt
pytest
pytest --cov=app --cov-report=html
```

### 前端测试

```bash
cd frontend
npm run build
```

### 功能测试清单

- [ ] 普通压缩包解压
- [ ] 带密码压缩包
- [ ] 分卷压缩包
- [ ] 日文编码文件名
- [ ] 元数据获取
- [ ] 重复检测
- [ ] 任务暂停/恢复/取消

### 测试数据

```bash
mkdir -p test_data/input test_data/library test_data/temp

# 创建测试压缩包
cd test_data/input
echo "test" > test.txt
zip test_normal.zip test.txt
zip -P 123456 test_password.zip test.txt
```

---

## 调试

### 启用详细日志

```bash
# Windows
set LOG_LEVEL=DEBUG
python -m app.main

# Linux/Mac
LOG_LEVEL=DEBUG python -m app.main
```

### 查看日志

```bash
# 本地
tail -f backend/logs/app.log

# Docker
docker logs -f prekikoeru
```

### 数据库检查

```bash
sqlite3 data/cache.db
SELECT * FROM tasks;
SELECT rjcode, work_name FROM work_metadata;
```

---

## 常见问题

### 前端无法连接后端

- 检查后端是否在 8000 端口运行
- 检查 `frontend/vite.config.js` 中的代理配置

### 文件无法解压

- 确保 7-Zip 已安装
- Windows: `where 7z`
- Linux: `which 7z`

### 端口被占用

- 后端默认 8000，前端默认 5173
- 修改 `backend/app/main.py` 或 `frontend/vite.config.js`

### 权限错误

```bash
chmod -R 777 test_data
```

---

## 项目结构

```
prekikoeru/
├── backend/
│   ├── app/
│   │   ├── api/routes.py      # API 路由
│   │   ├── core/              # 核心服务
│   │   │   ├── extract_service.py
│   │   │   ├── metadata_service.py
│   │   │   ├── rename_service.py
│   │   │   └── task_engine.py
│   │   ├── models/            # 数据模型
│   │   └── config/            # 配置管理
│   ├── build.py               # 构建脚本
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── api/               # API 封装
│   │   └── stores/            # 状态管理
│   └── package.json
└── docs/
```