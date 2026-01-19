"""
Gradio前端服务
提供Web界面，方便用户上传和处理文档
"""
import gradio as gr
import requests
import re
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import settings

# 和后端保持一致的 schema 定义
MANDATORY_NUMERIC_SCHEMA = [
    "身份证号", "手机号码", "固定电话", "银行卡号",
    "统一社会信用代码", "护照号码", "港澳通行证", "车牌号码",
]
OPTIONAL_SEMANTIC_SCHEMA = ["姓名", "地址", "企业名称", "机构名称", "电子邮箱"]
SCHEMA = MANDATORY_NUMERIC_SCHEMA + OPTIONAL_SEMANTIC_SCHEMA

# 服务地址
DESENSITIVE_BACKEND_URL = settings.DESENSITIVE_SERVICE_URL + "/mask/custom"
WORD_PROCESSOR_URL = settings.WORD_PROCESSOR_URL + "/api/v1/process/word"
PDF_PROCESSOR_URL = settings.WORD_PROCESSOR_URL + "/api/v1/process/pdf"

def _call_mask_custom(text, selected_labels, custom_text, max_chunk_len):
    """调用脱敏服务进行文本脱敏"""
    # 合并勾选的标签和自定义标签
    labels = list(selected_labels) if selected_labels else []
    if custom_text:
        extras = [x.strip() for x in re.split(r"[,\s，、]+", custom_text) if x.strip()]
        for ex in extras:
            if ex not in labels:
                labels.append(ex)

    payload = {
        "text": text or "",
        "schemalist": labels,
        "max_chunk_len": int(max_chunk_len),
    }

    try:
        resp = requests.post(DESENSITIVE_BACKEND_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("masked", ""), data
    except Exception as e:
        return f"请求失败: {e}", {"error": str(e)}

def _process_word_file(file, selected_labels, custom_text, max_chunk_len):
    """处理Word文档"""
    if file is None:
        return None, "请上传Word文档"
    
    # 合并勾选的标签和自定义标签
    labels = list(selected_labels) if selected_labels else []
    if custom_text:
        extras = [x.strip() for x in re.split(r"[,\s，、]+", custom_text) if x.strip()]
        for ex in extras:
            if ex not in labels:
                labels.append(ex)
    
    try:
        # 读取文件内容
        # Gradio 3.x 版本，file 是文件对象，可以通过 .name 获取路径
        file_path = file.name if hasattr(file, 'name') else file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # 获取文件名
        filename = os.path.basename(file_path) if isinstance(file_path, str) else "document.docx"
        
        # 准备表单数据
        files = {
            'file': (filename, file_content, 
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        }
        data = {
            'max_chunk_len': int(max_chunk_len)
        }
        
        # 如果有选择的标签，添加到表单数据
        if labels:
            data['schemalist'] = json.dumps(labels, ensure_ascii=False)
        
        # 调用Word处理服务
        resp = requests.post(
            WORD_PROCESSOR_URL,
            files=files,
            data=data,
            timeout=120.0
        )
        resp.raise_for_status()
        
        # 保存返回的文件
        output_filename = f"desensitized_{filename}"
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'wb') as f:
            f.write(resp.content)
        
        return output_path, "处理成功！文档已脱敏并保留原格式。"
    except Exception as e:
        return None, f"处理失败: {str(e)}"

def _process_pdf_file(file, selected_labels, custom_text, max_chunk_len):
    """处理PDF文档"""
    if file is None:
        return None, "请上传PDF文档"
    
    # 合并勾选的标签和自定义标签
    labels = list(selected_labels) if selected_labels else []
    if custom_text:
        extras = [x.strip() for x in re.split(r"[,\s，、]+", custom_text) if x.strip()]
        for ex in extras:
            if ex not in labels:
                labels.append(ex)
    
    try:
        # 读取文件内容
        # Gradio 3.x 版本，file 是文件对象，可以通过 .name 获取路径
        file_path = file.name if hasattr(file, 'name') else file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # 获取文件名
        filename = os.path.basename(file_path) if isinstance(file_path, str) else "document.pdf"
        
        # 准备表单数据
        files = {
            'file': (filename, file_content, 'application/pdf')
        }
        data = {
            'max_chunk_len': int(max_chunk_len),
            'return_pdf': 'false'  # 默认返回Markdown文件
        }
        
        # 如果有选择的标签，添加到表单数据
        if labels:
            data['schemalist'] = json.dumps(labels, ensure_ascii=False)
        
        # 调用PDF处理服务
        resp = requests.post(
            PDF_PROCESSOR_URL,
            files=files,
            data=data,
            timeout=300.0  # PDF处理可能需要更长时间
        )
        resp.raise_for_status()
        
        # 保存返回的文件（Markdown格式）
        base_name = os.path.splitext(filename)[0]
        output_filename = f"desensitized_{base_name}.md"
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'wb') as f:
            f.write(resp.content)
        
        return output_path, "处理成功！已生成脱敏后的Markdown文件。"
    except Exception as e:
        return None, f"处理失败: {str(e)}"

with gr.Blocks(title="非结构化数据脱敏工具", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 📄 非结构化数据脱敏工具")
    gr.Markdown("上传Word/PDF文档或输入文本进行脱敏处理，保留原文档格式")
    
    with gr.Tabs():
        with gr.TabItem("Word文档处理"):
            gr.Markdown("### 上传Word文档进行脱敏处理")
            gr.Markdown("支持.docx格式，处理后会保留原文档的所有格式（字体、样式、表格等）")
            
            with gr.Row():
                with gr.Column():
                    word_input = gr.File(
                        label="上传Word文档",
                        file_types=[".docx"]
                    )
                    
                    word_schema_select = gr.CheckboxGroup(
                        choices=list(SCHEMA),
                        value=list(SCHEMA),
                        label="选择要脱敏的实体类型 (默认全选)",
                    )
                    
                    word_custom_schema = gr.Textbox(
                        label="追加自定义脱敏项 (可选，中英文逗号分隔)",
                        placeholder="例如：金额, 贷款项目",
                    )
                    
                    with gr.Accordion("高级设置", open=False):
                        word_max_chunk_slider = gr.Slider(
                            minimum=50,
                            maximum=500,
                            value=300,
                            step=10,
                            label="Taskflow 分段长度 (MAX_CHUNK_LEN)",
                            info="较小值识别更准但速度慢，较大值速度快但可能漏识别",
                        )
                    
                    word_btn = gr.Button("开始处理Word文档", variant="primary", size="lg")
                
                with gr.Column():
                    word_output = gr.File(label="处理后的Word文档")
                    word_status = gr.Textbox(label="处理状态", interactive=False, lines=3)
            
            word_btn.click(
                fn=_process_word_file,
                inputs=[word_input, word_schema_select, word_custom_schema, word_max_chunk_slider],
                outputs=[word_output, word_status]
            )
        
        with gr.TabItem("PDF文档处理"):
            gr.Markdown("### 上传PDF文档进行脱敏处理")
            gr.Markdown("支持.pdf格式，处理后会生成脱敏后的Markdown文件（.md格式）")
            
            with gr.Row():
                with gr.Column():
                    pdf_input = gr.File(
                        label="上传PDF文档",
                        file_types=[".pdf"]
                    )
                    
                    pdf_schema_select = gr.CheckboxGroup(
                        choices=list(SCHEMA),
                        value=list(SCHEMA),
                        label="选择要脱敏的实体类型 (默认全选)",
                    )
                    
                    pdf_custom_schema = gr.Textbox(
                        label="追加自定义脱敏项 (可选，中英文逗号分隔)",
                        placeholder="例如：金额, 贷款项目",
                    )
                    
                    with gr.Accordion("高级设置", open=False):
                        pdf_max_chunk_slider = gr.Slider(
                            minimum=50,
                            maximum=500,
                            value=300,
                            step=10,
                            label="Taskflow 分段长度 (MAX_CHUNK_LEN)",
                            info="较小值识别更准但速度慢，较大值速度快但可能漏识别",
                        )
                    
                    pdf_btn = gr.Button("开始处理PDF文档", variant="primary", size="lg")
                
                with gr.Column():
                    pdf_output = gr.File(label="处理后的Markdown文件")
                    pdf_status = gr.Textbox(label="处理状态", interactive=False, lines=3)
            
            pdf_btn.click(
                fn=_process_pdf_file,
                inputs=[pdf_input, pdf_schema_select, pdf_custom_schema, pdf_max_chunk_slider],
                outputs=[pdf_output, pdf_status]
            )
        
        with gr.TabItem("文本脱敏"):
            gr.Markdown("### 文本脱敏处理")
            
            with gr.Row():
                with gr.Column():
                    input_text = gr.Textbox(
                        label="输入文本",
                        lines=10,
                        placeholder="在此输入待脱敏文本..."
                    )
                    schema_select = gr.CheckboxGroup(
                        choices=list(SCHEMA),
                        value=list(SCHEMA),
                        label="选择要脱敏的实体类型 (默认全选)",
                    )
                    custom_schema = gr.Textbox(
                        label="追加自定义脱敏项 (可选，中英文逗号分隔)",
                        placeholder="例如：合同编号, 贷款项目",
                    )

                    with gr.Accordion("高级设置", open=False):
                        max_chunk_slider = gr.Slider(
                            minimum=50,
                            maximum=500,
                            value=300,
                            step=10,
                            label="Taskflow 分段长度 (MAX_CHUNK_LEN)",
                            info="较小值识别更准但速度慢，较大值速度快但可能漏识别",
                        )

                    run_btn = gr.Button("开始脱敏", variant="primary", size="lg")

                with gr.Column():
                    masked_out = gr.Textbox(
                        label="脱敏结果",
                        lines=10,
                        show_copy_button=True
                    )
                    detail_out = gr.JSON(label="识别实体详情")

            run_btn.click(
                _call_mask_custom,
                inputs=[input_text, schema_select, custom_schema, max_chunk_slider],
                outputs=[masked_out, detail_out],
            )
    
    # 添加版权信息
    gr.Markdown(
        "<div style='text-align: center; margin-top: 30px; padding: 20px; color: #666; font-size: 14px;'>Copyright @ 智能分析团队</div>",
        elem_classes="copyright"
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
