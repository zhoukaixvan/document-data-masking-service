# Docker部署说明

## 快速开始

### 使用docker-compose（推荐）

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 使用Docker命令

```bash
# 构建镜像
docker build -t document-data-masking:latest .

# 运行容器
docker run -d \
  --name document-masking \
  -p 8888:8888 \
  -p 8002:8002 \
  -p 7860:7860 \
  -v $(pwd)/document-processor/outputs:/app/document-processor/outputs \
  -v $(pwd)/gradio-frontend/outputs:/app/gradio-frontend/outputs \
  -e PDF_PARSE_API_URL=http://host.docker.internal:8000 \
  document-data-masking:latest
```

## 访问服务

- **Gradio前端**: http://localhost:7860
- **文档处理API**: http://localhost:8002
- **脱敏服务API**: http://localhost:8888

## 环境变量配置

可以通过环境变量配置服务地址：

```bash
# PDF解析API地址（如果PDF解析服务在宿主机上运行）
PDF_PARSE_API_URL=http://host.docker.internal:8000

# 或者如果PDF解析服务也在Docker中
PDF_PARSE_API_URL=http://pdf-parse-service:8000
```

## 注意事项

1. **PDF解析API服务**: 如果PDF解析API服务（端口8000）在宿主机上运行，需要使用 `host.docker.internal` 访问
2. **数据持久化**: 输出文件会保存在挂载的卷中，方便查看结果
3. **调试模式**: 可以通过设置 `return_pdf=true` 参数来测试PDF转换功能

## 调试PDF转换功能

在容器内测试PDF转换：

```bash
# 进入容器
docker exec -it document-masking bash

# 运行测试脚本
cd /app/document-processor
python test_markdown_to_pdf.py <markdown文件路径>
```

## 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f document-masking
```
