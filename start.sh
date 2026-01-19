#!/bin/bash

# 启动所有服务的脚本

echo "启动文档脱敏服务系统..."

# 启动脱敏算法服务（后台运行）
echo "启动脱敏算法服务..."
cd desensitive-service
python app.py &
DESENSITIVE_PID=$!
cd ..

# 等待服务启动
sleep 2

# 启动文档处理服务（后台运行，支持Word和PDF）
echo "启动文档处理服务..."
cd document-processor
python app.py &
WORD_PROCESSOR_PID=$!
cd ..

# 等待服务启动
sleep 2

# 启动Gradio前端（前台运行）
echo "启动Gradio前端..."
cd gradio-frontend
python app.py

# 清理：当Gradio前端退出时，停止其他服务
echo "正在停止服务..."
kill $DESENSITIVE_PID $WORD_PROCESSOR_PID 2>/dev/null

