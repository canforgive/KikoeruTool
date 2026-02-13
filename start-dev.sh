#!/bin/bash
# start-dev.sh - Prekikoeru 本地开发启动脚本

set -e

echo "========================================"
echo "   Prekikoeru 本地开发环境启动器"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

echo "检查依赖..."
check_dependency python3 || exit 1
check_dependency node || exit 1

# 检查7z
if command -v 7z &> /dev/null; then
    echo -e "${GREEN}✓${NC} 7-Zip 已安装"
else
    echo -e "${YELLOW}!${NC} 未找到7-Zip，尝试安装..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y p7zip-full
    elif command -v yum &> /dev/null; then
        sudo yum install -y p7zip p7zip-plugins
    elif command -v brew &> /dev/null; then
        brew install p7zip
    else
        echo -e "${YELLOW}!${NC} 请手动安装 7-Zip"
    fi
fi

# 创建测试目录
echo ""
echo "创建测试目录..."
mkdir -p test_data/input
mkdir -p test_data/library
mkdir -p test_data/temp
mkdir -p data

# 安装后端依赖
echo ""
echo "安装后端依赖..."
cd backend

if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}后端依赖安装失败${NC}"
    exit 1
fi

cd ..

# 安装前端依赖
echo ""
echo "安装前端依赖..."
cd frontend

if [ ! -d "node_modules" ]; then
    npm install
    if [ $? -ne 0 ]; then
        echo -e "${RED}前端依赖安装失败${NC}"
        exit 1
    fi
fi

cd ..

# 启动服务
echo ""
echo "========================================"
echo "启动服务..."
echo "========================================"
echo ""
echo -e "后端服务: ${GREEN}http://localhost:8000${NC}"
echo -e "前端界面: ${GREEN}http://localhost:5173${NC}"
echo -e "API文档:  ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动后端（后台）
cd backend
source venv/bin/activate
python -m app.main &
BACKEND_PID=$!
cd ..

# 等待后端启动
sleep 3

# 启动前端
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# 捕获Ctrl+C
trap "
echo ''
echo '正在关闭服务...'
kill $BACKEND_PID 2>/dev/null
kill $FRONTEND_PID 2>/dev/null
echo -e '${GREEN}服务已停止${NC}'
exit 0
" INT

# 等待
wait
