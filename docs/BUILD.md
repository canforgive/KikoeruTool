# 构建 Windows EXE 文件指南

本文档说明如何从源代码构建 prekikoeru 的 Windows 可执行文件。

## 前置条件

1. **Python 3.9+** 已安装
2. **Node.js 16+** 已安装（用于构建前端）
3. **7-Zip** 已安装（运行时需要）

## 构建步骤

### 1. 进入后端目录

```bash
cd prekikoeru/backend
```

### 2. 激活虚拟环境

Windows (PowerShell):
```powershell
.\venv\Scripts\Activate.ps1
```

Windows (CMD):
```cmd
.\venv\Scripts\activate.bat
```

Windows (Git Bash):
```bash
source venv/Scripts/activate
```

### 3. 安装 PyInstaller（如果尚未安装）

```bash
pip install pyinstaller
```

### 4. 确保前端已构建

前端构建产物需要存在于 `prekikoeru/frontend/dist` 目录。

如果需要重新构建前端：

```bash
cd ../frontend
npm install
npm run build
cd ../backend
```

### 5. 执行构建

```bash
python build.py
```

## 构建产物

构建完成后，会在 `backend/dist/` 目录生成两个可执行文件：

| 文件 | 说明 |
|------|------|
| `prekikoeru.exe` | 带控制台窗口版本，方便调试 |
| `prekikoeru-noconsole.exe` | 无控制台窗口版本，适合日常使用 |

## 构建配置说明

构建脚本 `build.py` 使用 PyInstaller 将 Python 应用打包为单个可执行文件。

关键配置项：
- **入口文件**: `run.py`
- **数据文件**:
  - `app/` - 后端应用代码
  - `../frontend/dist/` - 前端构建产物
- **隐藏导入**: uvicorn, fastapi, sqlalchemy, yaml, watchdog, filetype, requests, aiohttp, pystray, PIL

## 常见问题

### 构建失败：缺少模块

确保虚拟环境已激活，并且所有依赖已安装：

```bash
pip install -r requirements.txt
```

### 前端资源缺失

确保在构建前已执行 `npm run build`，并且 `frontend/dist` 目录存在。

### EXE 体积过大

这是正常的，PyInstaller 会将 Python 运行时和所有依赖打包进单个 EXE。当前体积约 22MB。

### 运行时缺少 7-Zip

确保系统已安装 7-Zip，并且 `7z` 命令在 PATH 中，或者在配置文件中指定 7-Zip 路径。

## 手动构建单个版本

如果只需要构建一个版本，可以使用现有的 spec 文件：

```bash
# 构建带控制台版本
pyinstaller build_prekikoeru.spec --clean

# 构建无控制台版本
pyinstaller build_prekikoeru-noconsole.spec --clean
```

## 相关文件

- `build.py` - 主构建脚本
- `build_prekikoeru.spec` - 带控制台版本配置
- `build_prekikoeru-noconsole.spec` - 无控制台版本配置
- `run.py` - 应用入口文件