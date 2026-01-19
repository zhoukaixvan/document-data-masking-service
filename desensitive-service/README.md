# 脱敏算法服务

## 功能说明

提供核心脱敏算法的API服务，包括：
- 文本脱敏
- 批量文本脱敏
- 自定义脱敏规则

## API接口

### 健康检查
- `GET /health` - 服务健康检查

### 文本脱敏
- `POST /api/v1/desensitive/text` - 单文本脱敏

## 启动方式

```bash
python app.py
```

服务默认运行在 `http://localhost:8001`

