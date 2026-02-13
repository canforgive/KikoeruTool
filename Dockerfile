# 多阶段构建 Dockerfile
# 阶段1：构建前端
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制前端依赖
COPY frontend/package*.json ./
RUN npm ci

# 复制前端源码并构建
COPY frontend/ ./
RUN npm run build

# 阶段2：后端运行环境
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（包括 7zip）
RUN apt-get update && apt-get install -y \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

# 复制后端依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/app/ ./app/

# 从前端构建阶段复制静态文件
COPY --from=frontend-builder /app/frontend/dist /app/static

# 验证静态文件是否正确复制
RUN ls -la /app/static/ && \
    if [ -f /app/static/index.html ]; then \
        echo "✓ Static files copied successfully"; \
    else \
        echo "✗ Static files not found!"; \
        exit 1; \
    fi

# 创建必要的目录
RUN mkdir -p /app/data /app/config /input /temp /library /existing /processed

# 环境变量
ENV CONFIG_PATH=/app/config/config.yaml
ENV DATA_PATH=/app/data
ENV PYTHONPATH=/app
ENV STATIC_FILES_PATH=/app/static

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')" || exit 1

# 启动命令
CMD ["python", "-m", "app.main"]
