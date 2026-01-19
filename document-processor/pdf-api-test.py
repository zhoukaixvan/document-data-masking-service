import requests
import sys
import os

# API 端点
url = "http://127.0.0.1:8000/file_parse"

# 获取文件路径（支持命令行参数或默认使用指定文件）
if len(sys.argv) > 1:
    pdf_file_path = sys.argv[1]
else:
    # 默认使用用户指定的文件
    pdf_file_path = r"C:\Users\kaixu\Desktop\test\small_ocr.pdf"

# 检查文件是否存在
if not os.path.exists(pdf_file_path):
    print(f"错误: 文件不存在: {pdf_file_path}")
    sys.exit(1)

# 获取文件名（用于上传）
filename = os.path.basename(pdf_file_path)

print(f"正在处理文件: {pdf_file_path}")
print(f"文件名: {filename}")

# 准备文件
with open(pdf_file_path, 'rb') as f:
    files = [
        ('files', (filename, f.read(), 'application/pdf'))
    ]

# 请求参数
data = {
    'backend': 'pipeline',  # 或 'pipeline', 'vlm-auto-engine' 等
    'lang_list': ['ch'],  # 语言列表
    'parse_method': 'auto',  # 'auto', 'txt', 'ocr'
    'formula_enable': True,
    'table_enable': True,
    'return_md': True,  # 返回 Markdown
    'return_middle_json': False,
    'return_content_list': False,
    'return_images': False,
    'start_page_id': 0,
    'end_page_id': 99999
}

# 发送请求
response = requests.post(url, files=files, data=data)

# 处理响应
if response.status_code == 200:
    result = response.json()
    print(f"\n✓ 解析成功!")
    print(f"Backend: {result.get('backend', 'N/A')}")
    print(f"Version: {result.get('version', 'N/A')}")
    
    # 获取解析结果
    if 'results' in result and result['results']:
        for file_name, file_result in result['results'].items():
            if 'md_content' in file_result:
                markdown = file_result['md_content']
                print(f"\n{file_name} 的 Markdown 内容:")
                print("=" * 80)
                print(markdown)
                print("=" * 80)
                
                # 可选：保存Markdown到文件
                output_md_path = os.path.splitext(pdf_file_path)[0] + "_parsed.md"
                try:
                    with open(output_md_path, 'w', encoding='utf-8') as md_file:
                        md_file.write(markdown)
                    print(f"\n✓ Markdown已保存到: {output_md_path}")
                except Exception as e:
                    print(f"\n⚠ 保存Markdown文件失败: {e}")
            else:
                print(f"\n⚠ {file_name} 的解析结果中未找到 md_content 字段")
    else:
        print("\n⚠ 解析结果为空")
else:
    print(f"\n✗ 错误: HTTP {response.status_code}")
    print(response.text)