#!/bin/bash

# Docker容器启动脚本

echo "=========================================="
echo "启动文档脱敏服务系统"
echo "=========================================="

# 启动脱敏算法服务（后台运行）
echo "启动脱敏算法服务 (端口: 8888)..."
cd /app/desensitive-service
python app.py &
DESENSITIVE_PID=$!
cd /app

# 等待服务启动
sleep 3

# 检查脱敏服务是否启动成功
if ! kill -0 $DESENSITIVE_PID 2>/dev/null; then
    echo "错误: 脱敏服务启动失败"
    exit 1
fi
echo "✓ 脱敏服务启动成功 (PID: $DESENSITIVE_PID)"

# 启动文档处理服务（后台运行）
echo "启动文档处理服务 (端口: 8002)..."
cd /app/document-processor
python app.py &
WORD_PROCESSOR_PID=$!
cd /app

# 等待服务启动
sleep 3

# 检查文档处理服务是否启动成功
if ! kill -0 $WORD_PROCESSOR_PID 2>/dev/null; then
    echo "错误: 文档处理服务启动失败"
    kill $DESENSITIVE_PID 2>/dev/null
    exit 1
fi
echo "✓ 文档处理服务启动成功 (PID: $WORD_PROCESSOR_PID)"

# 启动Gradio前端（前台运行）
echo "启动Gradio前端 (端口: 7860)..."
cd /app/gradio-frontend
python app.py

# 清理：当Gradio前端退出时，停止其他服务
echo "正在停止服务..."
kill $DESENSITIVE_PID $WORD_PROCESSOR_PID 2>/dev/null
echo "所有服务已停止"
