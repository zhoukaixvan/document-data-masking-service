"""
Word处理服务
读取Word文档，调用脱敏服务，并转换回Word格式
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Optional
import httpx
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import settings
# 使用相对导入避免路径问题
from service import WordProcessor, PdfProcessor

app = FastAPI(title="文档处理服务", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

word_processor = WordProcessor(
    desensitive_service_url=settings.DESENSITIVE_SERVICE_URL
)

pdf_processor = PdfProcessor(
    desensitive_service_url=settings.DESENSITIVE_SERVICE_URL,
    pdf_parse_api_url=settings.PDF_PARSE_API_URL
)

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "document-processor"}

@app.post("/api/v1/process/word")
async def process_word(
    file: UploadFile = File(...),
    schemalist: Optional[str] = Form(None),
    max_chunk_len: Optional[int] = Form(300)
):
    """
    处理Word文档
    1. 读取Word文档
    2. 调用脱敏服务
    3. 生成脱敏后的Word文档（保留原格式）
    
    Args:
        file: Word文档文件
        schemalist: JSON字符串，要脱敏的实体类型列表，例如：["身份证号", "手机号码"]
        max_chunk_len: Taskflow分段长度，默认300
    """
    try:
        # 读取上传的文件
        content = await file.read()
        
        # 解析schemalist参数
        schema_list = None
        if schemalist:
            try:
                schema_list = json.loads(schemalist)
            except json.JSONDecodeError:
                # 如果不是JSON，尝试按逗号分割
                schema_list = [s.strip() for s in schemalist.split(',') if s.strip()]
        
        # 处理Word文档
        output_path = await word_processor.process_document(
            file_content=content,
            filename=file.filename,
            schemalist=schema_list,
            max_chunk_len=max_chunk_len or 300
        )
        
        # 返回处理后的文件
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"desensitized_{file.filename}"
        )
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@app.post("/api/v1/process/pdf")
async def process_pdf(
    file: UploadFile = File(...),
    schemalist: Optional[str] = Form(None),
    max_chunk_len: Optional[int] = Form(300),
    return_pdf: Optional[str] = Form("false")
):
    """
    处理PDF文档
    1. 解析PDF为Markdown
    2. 调用脱敏服务
    3. 返回脱敏后的Markdown文件（默认）或PDF文件（return_pdf=True时）
    
    Args:
        file: PDF文档文件
        schemalist: JSON字符串，要脱敏的实体类型列表，例如：["身份证号", "手机号码"]
        max_chunk_len: Taskflow分段长度，默认300
        return_pdf: 是否返回PDF文件，默认False返回Markdown文件
    """
    try:
        # 验证文件类型
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="只支持PDF文件格式")
        
        # 读取上传的文件
        content = await file.read()
        
        # 解析schemalist参数
        schema_list = None
        if schemalist:
            try:
                schema_list = json.loads(schemalist)
            except json.JSONDecodeError:
                # 如果不是JSON，尝试按逗号分割
                schema_list = [s.strip() for s in schemalist.split(',') if s.strip()]
        
        # 处理return_pdf参数（字符串转布尔值）
        return_pdf_bool = return_pdf and return_pdf.lower() in ('true', '1', 'yes')
        
        # 处理PDF文档
        output_path = await pdf_processor.process_document(
            file_content=content,
            filename=file.filename,
            schemalist=schema_list,
            max_chunk_len=max_chunk_len or 300,
            return_pdf=return_pdf_bool
        )
        
        # 根据文件类型设置media_type和文件名
        if return_pdf_bool:
            media_type = "application/pdf"
            output_filename = f"desensitized_{file.filename}"
        else:
            media_type = "text/markdown"
            base_name = os.path.splitext(file.filename)[0]
            output_filename = f"desensitized_{base_name}.md"
        
        # 返回处理后的文件
        return FileResponse(
            output_path,
            media_type=media_type,
            filename=output_filename
        )
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

