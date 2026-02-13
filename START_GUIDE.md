# Prekikoeru 快速启动指南

## 安装（首次使用）

双击运行 `setup.bat`，自动安装所有依赖。

## 日常启动

### 方式1：一键启动（推荐）
双击 `start-all.bat`
- 自动启动前后端服务
- 打开两个命令行窗口
- 关闭窗口即可停止服务

### 方式2：单独启动
- **只启动后端**: 双击 `backend\start.bat`
- **只启动前端**: 双击 `frontend\start.bat`

## 访问地址

- **前端界面**: http://localhost:5173
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 目录说明

```
prekikoeru/
├── start-all.bat      # 一键启动（用这个！）
├── setup.bat          # 首次安装
├── backend/
│   └── start.bat      # 后端启动
├── frontend/
│   └── start.bat      # 前端启动
├── test_data/         # 测试数据目录
└── config/            # 配置文件
```

## 常见问题

### 1. 提示缺少Python
安装 Python 3.11+：https://www.python.org/downloads/

### 2. 提示缺少Node.js
安装 Node.js 18+：https://nodejs.org/

### 3. 端口被占用
- 后端端口 8000
- 前端端口 5173

在 config/config.yaml 中修改端口配置。

### 4. 如何停止服务？
直接关闭命令行窗口，或按 `Ctrl+C`

## 测试数据

将压缩包放入 `test_data\input\` 目录，系统会自动处理。
