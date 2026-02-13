#!/bin/bash
# create_test_data.sh - 创建测试数据

set -e

echo "创建测试数据..."

# 创建目录
mkdir -p test_data/input
mkdir -p test_data/library
mkdir -p test_data/temp

cd test_data/input

# 创建测试文件
echo "This is a test file" > test.txt
echo "RJ123456 test content" > RJ123456_test.txt

# 创建普通ZIP
echo "创建普通ZIP文件..."
zip -q normal.zip test.txt

# 创建带密码的ZIP
echo "创建带密码的ZIP文件..."
zip -q -P 123456 password.zip test.txt

# 创建7z文件（如果安装了7z）
if command -v 7z &> /dev/null; then
    echo "创建7z文件..."
    7z a -y archive.7z test.txt > /dev/null
    
    echo "创建错误后缀名的7z文件..."
    7z a -y test.7 test.txt > /dev/null
else
    echo "警告: 7z未安装，跳过7z测试文件创建"
fi

# 创建分卷RAR（如果安装了rar）
if command -v rar &> /dev/null; then
    echo "创建分卷RAR文件..."
    rar a -v1m -y multipart.rar test.txt > /dev/null
else
    echo "警告: rar未安装，跳过分卷RAR测试文件创建"
fi

# 创建错误后缀名的文件
echo "创建错误后缀名文件..."
cp normal.zip test.zi
cp normal.zip test.zp

# 创建包含RJ号的文件
zip -q RJ01071451_测试作品.zip RJ123456_test.txt

echo ""
echo "测试数据创建完成！"
echo ""
echo "文件列表:"
ls -lh
echo ""
echo "使用说明:"
echo "1. 将这些文件放入 input 目录"
echo "2. 启动服务: docker-compose up -d"
echo "3. 访问 http://localhost:8000 查看处理进度"
echo ""

# 返回上级目录
cd ../..
