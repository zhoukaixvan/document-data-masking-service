"""
测试Markdown转PDF功能
测试步骤4: 将Markdown转换为PDF
支持用户指定输入文件
"""
import os
import sys
from datetime import datetime

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from service import PdfProcessor
from common.config import settings


def test_markdown_to_pdf(input_file: str, output_file: str = None):
    """
    测试_markdown_to_pdf函数
    
    Args:
        input_file: 输入的Markdown文件路径
        output_file: 输出的PDF文件路径（可选，默认自动生成）
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"[ERROR] 输入文件不存在: {input_file}")
        return False
    
    # 读取Markdown文件
    print(f"正在读取Markdown文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        print(f"[OK] 成功读取文件，内容长度: {len(markdown_content)} 字符")
    except Exception as e:
        print(f"[ERROR] 读取文件失败: {e}")
        return False
    
    # 生成输出文件名（如果未指定）
    if output_file is None:
        input_basename = os.path.splitext(os.path.basename(input_file))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_outputs/{input_basename}_output_{timestamp}.pdf"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file) or "test_outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建PdfProcessor实例
    pdf_processor = PdfProcessor(
        desensitive_service_url=settings.DESENSITIVE_SERVICE_URL,
        pdf_parse_api_url=settings.PDF_PARSE_API_URL
    )
    
    print(f"\n{'='*60}")
    print("开始测试Markdown转PDF功能")
    print(f"{'='*60}")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"Markdown内容长度: {len(markdown_content)} 字符")
    print(f"{'='*60}\n")
    
    try:
        # 调用_markdown_to_pdf方法
        pdf_processor._markdown_to_pdf(markdown_content, output_file)
        
        # 检查输出文件
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"\n{'='*60}")
            print("[SUCCESS] 测试成功！")
            print(f"{'='*60}")
            print(f"PDF文件已生成: {output_file}")
            print(f"文件大小: {file_size} 字节 ({file_size / 1024:.2f} KB)")
            print(f"\n请打开PDF文件查看效果。")
            print(f"{'='*60}")
            return True
        else:
            print(f"\n[ERROR] 测试失败：PDF文件未生成")
            return False
            
    except ImportError as e:
        print(f"[ERROR] 导入错误: {e}")
        print("\n请确保已安装必要的依赖:")
        print("  pip install markdown weasyprint")
        return False
    except OSError as e:
        error_msg = str(e)
        if 'libgobject' in error_msg or 'GTK' in error_msg:
            print(f"[ERROR] WeasyPrint需要GTK+库（Windows系统）")
            print("\n解决方案：")
            print("1. 安装GTK+ for Windows:")
            print("   下载地址: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases")
            print("\n2. 或者使用其他PDF生成库（如reportlab、fpdf等）")
            print("\n3. 在Linux/Mac系统上运行（WeasyPrint在Linux/Mac上更容易安装）")
        else:
            print(f"[ERROR] 系统库加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"[ERROR] 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("Markdown转PDF功能测试工具")
    print("="*60)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        # 交互式输入
        print("\n请输入Markdown文件路径:")
        print("(可以直接拖拽文件到终端，或输入文件路径)")
        input_file = input("> ").strip().strip('"').strip("'")
        
        if not input_file:
            print("[ERROR] 未输入文件路径")
            return
        
        # 询问是否指定输出文件
        print("\n是否指定输出PDF文件路径？(直接回车使用默认路径)")
        output_file = input("> ").strip().strip('"').strip("'")
        if not output_file:
            output_file = None
    
    # 执行测试
    test_markdown_to_pdf(input_file, output_file)


if __name__ == "__main__":
    main()
