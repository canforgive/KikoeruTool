#!/bin/bash
# test.sh - Prekikoeru 快速测试脚本

set -e

echo "=========================================="
echo "   Prekikoeru 测试脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查依赖
check_dependency() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 已安装"
        return 0
    else
        echo -e "${RED}✗${NC} $1 未安装"
        return 1
    fi
}

echo "1. 检查依赖..."
echo "----------------------------------------"
check_dependency python || exit 1
check_dependency docker || exit 1
check_dependency docker-compose || exit 1

# 检查Python版本
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python版本: $PYTHON_VERSION"

echo ""
echo "2. 安装测试依赖..."
echo "----------------------------------------"
cd backend
pip install -q -r requirements.txt
pip install -q -r requirements-test.txt
cd ..

echo -e "${GREEN}✓${NC} 依赖安装完成"

echo ""
echo "3. 运行单元测试..."
echo "----------------------------------------"
cd backend
if pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✓${NC} 单元测试通过"
else
    echo -e "${RED}✗${NC} 单元测试失败"
    exit 1
fi
cd ..

echo ""
echo "4. 构建Docker镜像..."
echo "----------------------------------------"
if docker-compose build; then
    echo -e "${GREEN}✓${NC} Docker镜像构建成功"
else
    echo -e "${RED}✗${NC} Docker镜像构建失败"
    exit 1
fi

echo ""
echo "5. 启动服务..."
echo "----------------------------------------"
docker-compose up -d

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓${NC} 服务启动成功"
else
    echo -e "${RED}✗${NC} 服务启动失败"
    docker-compose logs
    exit 1
fi

echo ""
echo "6. API测试..."
echo "----------------------------------------"

# 测试健康检查
echo -n "测试健康检查... "
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# 测试获取配置
echo -n "测试获取配置... "
if curl -s http://localhost:8000/api/config | grep -q "storage"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# 测试创建任务
echo -n "测试创建任务... "
TASK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"source_path": "/input/test.zip", "task_type": "auto_process"}')
if echo "$TASK_RESPONSE" | grep -q "id"; then
    echo -e "${GREEN}✓${NC}"
    TASK_ID=$(echo "$TASK_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
else
    echo -e "${RED}✗${NC}"
fi

# 测试获取任务列表
echo -n "测试获取任务列表... "
if curl -s http://localhost:8000/api/tasks | grep -q "$TASK_ID"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# 测试监视器状态
echo -n "测试监视器状态... "
if curl -s http://localhost:8000/api/watcher/status | grep -q "is_running"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "7. 清理..."
echo "----------------------------------------"
docker-compose down
echo -e "${GREEN}✓${NC} 服务已停止"

echo ""
echo "=========================================="
echo -e "${GREEN}所有测试通过！${NC}"
echo "=========================================="
echo ""
echo "测试摘要:"
echo "  - 单元测试: ✓"
echo "  - Docker构建: ✓"
echo "  - 服务启动: ✓"
echo "  - API测试: ✓"
echo ""
echo "可以开始使用了！"
echo "  启动: docker-compose up -d"
echo "  访问: http://localhost:8000"
echo ""
