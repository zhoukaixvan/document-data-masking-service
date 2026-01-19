# Gradio前端服务

## 功能说明

提供基于Gradio的Web界面，包括：
- Word文档上传和处理
- 文本脱敏功能
- 处理结果下载

## 启动方式

```bash
python app.py
```

前端默认运行在 `http://localhost:7860`

## 依赖服务

需要以下服务运行：
- 脱敏算法服务: `http://localhost:8001`
- Word处理服务: `http://localhost:8002`

