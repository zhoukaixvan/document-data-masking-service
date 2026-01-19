# 文档脱敏服务系统

## 项目简介

本项目是一个文档脱敏服务系统，包含三个核心组件：
1. **脱敏算法服务** - 提供核心脱敏算法API服务
2. **Word处理服务** - 读取Word文档，调用脱敏服务，并转换回Word格式
3. **Gradio前端服务** - 提供Web界面，方便用户上传和处理文档

## 项目结构

```
all-desensitive-service/
├── desensitive-service/      # 脱敏算法服务
├── word-processor/           # Word处理服务
├── gradio-frontend/          # Gradio前端服务
├── common/                   # 共享工具和配置
├── requirements.txt          # Python依赖
└── README.md                 # 项目说明
```

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动服务

1. 启动脱敏算法服务
```bash
cd desensitive-service
python app.py
```

2. 启动Word处理服务
```bash
cd word-processor
python app.py
```

3. 启动Gradio前端
```bash
cd gradio-frontend
python app.py
```

## 技术栈

- Python 3.8+
- FastAPI (脱敏服务和Word处理服务)
- Gradio (前端界面)
- python-docx (Word文档处理)

