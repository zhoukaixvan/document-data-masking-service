# 文档脱敏服务系统

一个基于深度学习和规则匹配的智能文档脱敏系统，支持 Word 和 PDF 文档的自动脱敏处理。

## 📋 项目简介

本项目是一个完整的文档脱敏服务系统，能够自动识别和脱敏文档中的敏感信息，包括身份证号、手机号码、姓名、地址、企业名称等多种类型的敏感数据。系统采用微服务架构，包含三个核心组件，支持通过 Web 界面或 API 接口进行文档处理。

## ✨ 功能特性

- 🔒 **多类型敏感信息识别**：支持身份证号、手机号码、银行卡号、姓名、地址、企业名称等 13+ 种敏感信息类型
- 📄 **多格式文档支持**：支持 Word (.docx) 和 PDF 文档的脱敏处理
- 🎯 **智能识别算法**：结合 PaddleNLP 深度学习模型和正则表达式规则，提高识别准确率
- 🔄 **格式保持**：处理后的文档保持原有格式和样式
- 🌐 **Web 界面**：提供友好的 Gradio Web 界面，方便非技术用户使用
- 🔌 **RESTful API**：提供完整的 API 接口，支持集成到其他系统
- 🐳 **Docker 支持**：支持 Docker 容器化部署，一键启动所有服务
- ⚙️ **灵活配置**：支持自定义脱敏类型和参数配置

## 🏗️ 项目结构

```
document-data-masking/
├── desensitive-service/      # 脱敏算法服务
│   ├── app.py                # FastAPI 服务入口
│   └── model/                # 模型文件目录（不包含在仓库中）
├── document-processor/       # 文档处理服务
│   ├── app.py                # FastAPI 服务入口
│   ├── service.py            # Word/PDF 处理核心逻辑
│   ├── uploads/              # 上传文件目录（不包含在仓库中）
│   ├── outputs/              # 输出文件目录（不包含在仓库中）
│   └── debug_outputs/        # 调试输出目录（不包含在仓库中）
├── gradio-frontend/          # Gradio Web 前端
│   ├── app.py                # Gradio 应用入口
│   └── outputs/              # 输出文件目录（不包含在仓库中）
├── common/                   # 共享模块
│   ├── config.py             # 配置管理
│   └── __init__.py
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 镜像构建文件
├── docker-compose.yml        # Docker Compose 配置
├── docker-entrypoint.sh      # Docker 启动脚本
└── README.md                 # 项目说明文档
```

## 🛠️ 技术栈

- **后端框架**: FastAPI
- **前端界面**: Gradio
- **NLP 模型**: PaddleNLP (PaddlePaddle)
- **文档处理**: 
  - python-docx (Word 文档处理)
  - WeasyPrint (PDF 生成)
- **HTTP 客户端**: httpx, requests
- **容器化**: Docker, Docker Compose

## 📦 安装和配置

### 环境要求

- Python 3.8+
- 至少 4GB 可用内存（用于运行 PaddleNLP 模型）

### 本地安装

1. **克隆项目**

```bash
git clone https://github.com/zhoukaixvan/document-data-masking-service.git
cd document-data-masking-service
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **下载模型文件**

模型文件需要单独下载，请将模型文件放置在 `desensitive-service/model/` 目录下。

4. **配置环境变量（可选）**

创建 `.env` 文件（可选，系统有默认配置）：

```env
DESENSITIVE_SERVICE_URL=http://127.0.0.1:8888
WORD_PROCESSOR_URL=http://127.0.0.1:8002
PDF_PARSE_API_URL=http://127.0.0.1:8191
```

## 🚀 使用方法

### 方式一：本地运行

#### 1. 启动脱敏算法服务

```bash
cd desensitive-service
python app.py
```

服务将运行在 `http://localhost:8888`

#### 2. 启动文档处理服务

```bash
cd document-processor
python app.py
```

服务将运行在 `http://localhost:8002`

#### 3. 启动 Gradio 前端

```bash
cd gradio-frontend
python app.py
```

前端界面将运行在 `http://localhost:7860`

### 方式二：Docker 部署（推荐）

#### 使用 Docker Compose

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 使用 Docker 命令

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
  document-data-masking:latest
```

### 访问服务

- **Gradio Web 界面**: http://localhost:7860
- **文档处理 API 文档**: http://localhost:8002/docs
- **脱敏服务 API 文档**: http://localhost:8888/docs

## 📡 API 接口文档

### 文档处理服务 API

#### 处理 Word 文档

```http
POST /api/v1/process/word
Content-Type: multipart/form-data

参数:
- file: Word 文档文件 (.docx)
- schemalist: (可选) JSON 字符串，要脱敏的实体类型列表，例如：["身份证号", "手机号码"]
- max_chunk_len: (可选) Taskflow 分段长度，默认 300
```

#### 处理 PDF 文档

```http
POST /api/v1/process/pdf
Content-Type: multipart/form-data

参数:
- file: PDF 文档文件
- schemalist: (可选) JSON 字符串，要脱敏的实体类型列表
- max_chunk_len: (可选) Taskflow 分段长度，默认 300
- return_pdf: (可选) 是否返回 PDF 文件，默认 "false" 返回 Markdown 文件
```

### 脱敏服务 API

#### 文本脱敏

```http
POST /mask/custom
Content-Type: application/json

{
  "text": "待脱敏的文本内容",
  "schemalist": ["身份证号", "手机号码", "姓名"],
  "max_chunk_len": 300
}
```

响应示例：

```json
{
  "masked": "脱敏后的文本",
  "entities": [
    {
      "text": "原始文本",
      "label": "身份证号",
      "start": 0,
      "end": 18,
      "method": "regex"
    }
  ]
}
```

## 🔍 支持的脱敏类型

### 数字类实体（必选，使用正则匹配）
- 身份证号
- 手机号码
- 固定电话
- 银行卡号
- 统一社会信用代码
- 护照号码
- 港澳通行证
- 车牌号码

### 语义类实体（可选，使用 NLP 模型识别）
- 姓名
- 地址
- 企业名称
- 机构名称
- 电子邮箱

## 📝 使用示例

### Python 调用示例

```python
import requests

# 处理 Word 文档
with open('document.docx', 'rb') as f:
    files = {'file': f}
    data = {
        'schemalist': '["身份证号", "手机号码", "姓名"]',
        'max_chunk_len': 300
    }
    response = requests.post(
        'http://localhost:8002/api/v1/process/word',
        files=files,
        data=data
    )
    
    # 保存处理后的文档
    with open('desensitized_document.docx', 'wb') as out:
        out.write(response.content)
```

### cURL 调用示例

```bash
# 处理 Word 文档
curl -X POST "http://localhost:8002/api/v1/process/word" \
  -F "file=@document.docx" \
  -F 'schemalist=["身份证号", "手机号码"]' \
  -F "max_chunk_len=300" \
  -o desensitized_document.docx
```

## ⚠️ 注意事项

1. **模型文件**: 模型文件不包含在仓库中，需要单独下载并放置在 `desensitive-service/model/` 目录
2. **敏感数据**: 请确保不要将包含真实敏感信息的文档提交到仓库
3. **PDF 解析服务**: PDF 处理功能需要外部 PDF 解析 API 服务（端口 8191），请确保该服务正常运行
4. **内存要求**: PaddleNLP 模型需要较多内存，建议至少 4GB 可用内存
5. **文件大小**: 建议处理的文档大小不超过 50MB

## 🔧 配置说明

### 环境变量

- `DESENSITIVE_SERVICE_URL`: 脱敏服务地址，默认 `http://127.0.0.1:8888`
- `WORD_PROCESSOR_URL`: 文档处理服务地址，默认 `http://127.0.0.1:8002`
- `PDF_PARSE_API_URL`: PDF 解析 API 地址，默认 `http://127.0.0.1:8191`

### 脱敏参数

- `max_chunk_len`: 文本分段长度，影响识别准确率和处理速度，默认 300
- `schemalist`: 指定要识别的实体类型，不指定则识别所有类型

## 🐛 故障排查

### 服务无法启动

1. 检查端口是否被占用
2. 检查模型文件是否存在
3. 查看日志文件获取详细错误信息

### 识别准确率低

1. 调整 `max_chunk_len` 参数
2. 检查文本格式是否正确
3. 确认模型文件版本是否正确

### PDF 处理失败

1. 检查 PDF 解析 API 服务是否正常运行
2. 确认 PDF 文件格式是否支持
3. 查看调试输出目录中的日志文件

## 📄 许可证

本项目采用 MIT 许可证。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系方式

如有问题或建议，请通过 GitHub Issues 联系。

---

**注意**: 本项目仅用于学习和研究目的，请勿用于处理真实敏感数据，除非您已充分了解并接受相关风险。