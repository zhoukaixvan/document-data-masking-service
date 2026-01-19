# 使用Python 3.9作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # WeasyPrint 依赖
        libpango-1.0-0 \
        libharfbuzz-dev \
        libpangoft2-1.0-0 \
        libgobject-2.0-0 \
        libglib2.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        # PaddlePaddle 依赖
        libgomp1 \
        libssl-dev \
        libffi-dev \
        libjpeg-dev \
        zlib1g-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
    
# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目文件
COPY common/ /app/common/
COPY desensitive-service/ /app/desensitive-service/
COPY document-processor/ /app/document-processor/
COPY gradio-frontend/ /app/gradio-frontend/

# 创建必要的目录
RUN mkdir -p /app/document-processor/outputs \
    /app/document-processor/uploads \
    /app/document-processor/debug_outputs \
    /app/gradio-frontend/outputs \
    /app/desensitive-service/model

# 设置环境变量
ENV PYTHONPATH=/app
ENV DESENSITIVE_SERVICE_URL=http://127.0.0.1:8888
ENV WORD_PROCESSOR_URL=http://127.0.0.1:8002
ENV PDF_PARSE_API_URL=http://127.0.0.1:8191

# 暴露端口
# 8888: 脱敏服务
# 8002: 文档处理服务
# 7860: Gradio前端
EXPOSE 8888 8002 7860

# 创建启动脚本
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 启动入口
ENTRYPOINT ["/app/docker-entrypoint.sh"]
