"""
Word文档处理服务 - 基于OpenXML实现
流程：Word (.docx) → OpenXML (document.xml) → 解析/替换 → 回写 → 新的 Word (.docx)
"""
import os
import httpx
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import List, Dict, Tuple
import sys
import re
import logging
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('word_processor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Word XML命名空间
W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

class WordProcessor:
    """Word文档处理器 - 基于OpenXML"""
    
    def __init__(self, desensitive_service_url: str):
        self.desensitive_service_url = desensitive_service_url
        self.upload_dir = "uploads"
        self.output_dir = "outputs"
        self.debug_dir = "debug_outputs"  # 调试输出目录
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
    
    def _extract_text_from_xml(self, xml_content: str) -> Tuple[str, List[Dict], ET.Element]:
        """
        从document.xml中提取纯文本，并记录每个文本节点的位置信息
        
        Returns:
            (完整文本, 文本节点映射列表, root元素)
        """
        try:
            root = ET.fromstring(xml_content)
            text_parts = []
            node_mapping = []
            
            current_pos = 0
            
            # 遍历所有文本节点
            for t_elem in root.iter(f'{W_NS}t'):
                text = t_elem.text or ""
                if text:
                    start_pos = current_pos
                    end_pos = current_pos + len(text)
                    text_parts.append(text)
                    node_mapping.append({
                        'start': start_pos,
                        'end': end_pos,
                        'element': t_elem,
                        'text': text,
                        'is_text': True,
                        'is_tail': False
                    })
                    current_pos = end_pos
                
                # 处理tail文本（元素后的文本），如果只处理text会丢失文本格式信息！
                if t_elem.tail:
                    tail_text = t_elem.tail
                    start_pos = current_pos
                    end_pos = current_pos + len(tail_text)
                    text_parts.append(tail_text)
                    node_mapping.append({
                        'start': start_pos,
                        'end': end_pos,
                        'element': t_elem,
                        'text': tail_text,
                        'is_text': False,
                        'is_tail': True
                    })
                    current_pos = end_pos
            
            full_text = ''.join(text_parts)
            logger.info(f"提取文本完成，文本长度: {len(full_text)}, 节点数量: {len(node_mapping)}")
            return full_text, node_mapping, root
        except Exception as e:
            logger.error(f"提取文本失败: {e}", exc_info=True)
            raise
    
    def _save_debug_info(self, filename: str, step: str, data: any, data_type: str = "text"):
        """保存调试信息"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(filename)[0]
        debug_file = os.path.join(self.debug_dir, f"{base_name}_{step}_{timestamp}")
        
        try:
            if data_type == "xml":
                debug_file += ".xml"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(data)
            elif data_type == "json":
                debug_file += ".json"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                debug_file += ".txt"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(str(data))
            
            logger.info(f"调试信息已保存: {debug_file}")
            return debug_file
        except Exception as e:
            logger.error(f"保存调试信息失败: {e}", exc_info=True)
            return None
    
    def _generate_replacements(self, original_text: str, masked_text: str, 
                              entities: List[Dict]) -> List[Dict]:
        """
        生成替换映射，基于字符级别的差异
        
        Args:
            original_text: 原始文本
            masked_text: 脱敏后文本
            entities: 实体列表（用于辅助定位，可选）
        
        Returns:
            替换映射列表，按start位置排序
        """
        replacements = []
        
        logger.info(f"生成替换映射 - 原始文本长度: {len(original_text)}, 脱敏文本长度: {len(masked_text)}")
        
        # 方法：使用简单的字符比对，找出所有不同的连续段
        # 脱敏算法通常保持文本长度不变（只替换字符），所以优先使用逐字符比对
        if len(original_text) == len(masked_text):
            i = 0
            while i < len(original_text):
                if original_text[i] != masked_text[i]:
                    start = i
                    # 找到差异段的结束位置
                    while i < len(original_text) and original_text[i] != masked_text[i]:
                        i += 1
                    end = i
                    replacements.append({
                        'start': start,
                        'end': end,
                        'new_text': masked_text[start:end]
                    })
                    logger.debug(f"发现差异段: [{start}:{end}] '{original_text[start:end]}' -> '{masked_text[start:end]}'")
                else:
                    i += 1
        else:
            # 长度不同，使用基于实体的替换
            logger.warning(f"文本长度不同，使用基于实体的替换方法")
            sorted_entities = sorted(entities, key=lambda x: x['start'])
            
            for entity in sorted_entities:
                start = entity['start']
                end = entity['end']
                original_segment = original_text[start:end]
                
                # 在masked_text中找到对应的位置
                if start < len(masked_text):
                    masked_end = min(end, len(masked_text))
                    masked_segment = masked_text[start:masked_end]
                    
                    if masked_segment != original_segment:
                        replacements.append({
                            'start': start,
                            'end': end,
                            'new_text': masked_segment
                        })
                        logger.debug(f"实体替换: [{start}:{end}] '{original_segment}' -> '{masked_segment}'")
        
        # 合并重叠的替换项
        if replacements:
            replacements = sorted(replacements, key=lambda x: x['start'])
            merged = []
            for rep in replacements:
                if not merged or rep['start'] >= merged[-1]['end']:
                    merged.append(rep)
                else:
                    # 重叠，合并
                    logger.warning(f"发现重叠替换项: {merged[-1]} 和 {rep}")
                    merged[-1]['end'] = max(merged[-1]['end'], rep['end'])
                    merged[-1]['new_text'] = rep['new_text']
            replacements = merged
        
        logger.info(f"生成替换映射完成，共 {len(replacements)} 个替换项")
        return replacements
    
    def _apply_replacements_to_xml(self, xml_content: str, replacements: List[Dict],
                                  node_mapping: List[Dict], root: ET.Element) -> str:
        """
        在XML中应用文本替换 - 使用最简单的方法：直接在原始XML字符串上替换
        
        Args:
            xml_content: 原始XML内容（完全保留原始格式和命名空间）
            replacements: 替换映射列表，按start位置排序
            node_mapping: 文本节点映射（用于定位文本在XML中的位置）
            root: XML根元素（未使用，保留以兼容接口）
        
        Returns:
            修改后的XML内容
        """
        try:
            # 如果没有替换项，直接返回原始XML
            if not replacements:
                logger.info("没有替换项，返回原始XML")
                return xml_content
            
            # 最简单可靠的方法：修改ElementTree节点，然后重新序列化
            # 但保留原始XML的根元素标签（包含所有命名空间声明）
            
            # 按位置排序替换项（从后往前处理，避免位置偏移）
            sorted_replacements = sorted(replacements, key=lambda x: x['start'], reverse=True)
            
            logger.info(f"开始应用 {len(sorted_replacements)} 个替换项到XML")
            
            # 修改ElementTree节点
            modified_count = 0
            for node_info in node_mapping:
                elem = node_info['element']
                node_start = node_info['start']
                node_end = node_info['end']
                is_text = node_info.get('is_text', False)
                is_tail = node_info.get('is_tail', False)
                original_text = node_info.get('text', '')
                
                if not (is_text or is_tail) or not original_text:
                    continue
                
                # 检查哪些替换项影响这个节点
                modified_text = original_text
                
                for rep in sorted_replacements:
                    rep_start = rep['start']
                    rep_end = rep['end']
                    
                    if rep_start < node_end and rep_end > node_start:
                        local_start = max(0, rep_start - node_start)
                        local_end = min(len(original_text), rep_end - node_start)
                        
                        if local_start < local_end:
                            new_segment = rep['new_text']
                            modified_text = (
                                modified_text[:local_start] + 
                                new_segment + 
                                modified_text[local_end:]
                            )
                
                # 更新节点文本
                if modified_text != original_text:
                    if is_text:
                        elem.text = modified_text
                    elif is_tail:
                        elem.tail = modified_text
                    modified_count += 1
                    logger.debug(f"更新节点文本: '{original_text}' -> '{modified_text}'")
            
            logger.info(f"完成XML节点修改，修改了 {modified_count} 个节点")
            
            # 简单序列化：直接序列化整个XML树，不做复杂的命名空间修复
            # 注意：这可能会导致命名空间前缀变成ns0:、ns1:等，Word可能会提示"无法读取的内容"
            # 但用户点击"是"后可以正常打开和使用
            result = ET.tostring(root, encoding='unicode', method='xml', xml_declaration=False)
            
            # 添加XML声明
            if xml_content.strip().startswith('<?xml'):
                xml_declaration_end = xml_content.find('?>') + 2
                next_char_idx = xml_declaration_end
                while next_char_idx < len(xml_content) and xml_content[next_char_idx] in ['\n', '\r', ' ']:
                    next_char_idx += 1
                original_declaration = xml_content[:next_char_idx]
                result = original_declaration + result
            
            # 验证XML格式
            try:
                ET.fromstring(result)
                logger.info("XML格式验证通过")
            except ET.ParseError as e:
                logger.error(f"XML格式验证失败: {e}")
                logger.error(f"错误位置: {e.position if hasattr(e, 'position') else 'unknown'}")
                return xml_content
            
            return result
        except Exception as e:
            logger.error(f"应用替换到XML失败: {e}", exc_info=True)
            raise
    
    async def process_document(self, file_content: bytes, filename: str, 
                               schemalist: List[str] = None, 
                               max_chunk_len: int = 300) -> str:
        """
        处理Word文档 - 基于OpenXML
        
        Args:
            file_content: Word文档的二进制内容
            filename: 原始文件名
            schemalist: 要脱敏的实体类型列表
            max_chunk_len: Taskflow分段长度
            
        Returns:
            处理后的文件路径
        """
        logger.info(f"开始处理Word文档: {filename}")
        
        # 使用临时目录处理文件
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. 解压docx文件（docx本质是zip）
                docx_path = os.path.join(temp_dir, "input.docx")
                with open(docx_path, 'wb') as f:
                    f.write(file_content)
                
                logger.info("步骤1: 解压docx文件完成")
                
                # 2. 提取document.xml
                with zipfile.ZipFile(docx_path, 'r') as zip_ref:
                    # 读取document.xml
                    document_xml = zip_ref.read('word/document.xml').decode('utf-8')
                    
                    # 保存原始XML用于调试
                    self._save_debug_info(filename, "01_original_xml", document_xml, "xml")
                    
                    logger.info("步骤2: 提取document.xml完成")
                    
                    # 3. 从XML中提取纯文本（同时返回root以便后续使用）
                    full_text, node_mapping, xml_root = self._extract_text_from_xml(document_xml)
                    
                    # 保存提取的文本用于调试
                    self._save_debug_info(filename, "02_extracted_text", full_text, "text")
                    # 保存节点映射时，移除Element对象以避免序列化错误
                    node_mapping_for_debug = []
                    for node in (node_mapping[:10] if len(node_mapping) > 10 else node_mapping):
                        debug_node = {
                            'start': node['start'],
                            'end': node['end'],
                            'text': node.get('text', ''),
                            'is_text': node.get('is_text', False),
                            'is_tail': node.get('is_tail', False),
                            'tag': node['element'].tag if hasattr(node['element'], 'tag') else str(node['element'])
                        }
                        node_mapping_for_debug.append(debug_node)
                    self._save_debug_info(filename, "03_node_mapping", {
                        'total_nodes': len(node_mapping),
                        'sample_nodes': node_mapping_for_debug
                    }, "json")
                    
                    if not full_text.strip():
                        # 如果没有文本内容，直接复制原文件
                        logger.warning("文档中没有文本内容，直接复制原文件")
                        output_path = os.path.join(self.output_dir, f"desensitized_{filename}")
                        with open(output_path, 'wb') as f:
                            f.write(file_content)
                        return output_path
                    
                    # 4. 调用脱敏服务
                    logger.info(f"步骤3: 调用脱敏服务，文本长度: {len(full_text)}")
                    desensitive_result = await self._call_desensitive_service(
                        full_text, 
                        schemalist=schemalist,
                        max_chunk_len=max_chunk_len
                    )
                    
                    masked_text = desensitive_result.get('masked', full_text)
                    entities = desensitive_result.get('entities_found', [])
                    
                    # 保存脱敏结果用于调试
                    self._save_debug_info(filename, "04_masked_text", masked_text, "text")
                    self._save_debug_info(filename, "05_entities", {
                        'total_entities': len(entities),
                        'entities': entities
                    }, "json")
                    
                    logger.info(f"步骤4: 脱敏完成，识别到 {len(entities)} 个实体")
                    
                    # 5. 比对原文本和脱敏后文本，生成替换映射
                    replacements = self._generate_replacements(full_text, masked_text, entities)
                    
                    # 保存替换映射用于调试
                    self._save_debug_info(filename, "06_replacements", {
                        'total_replacements': len(replacements),
                        'replacements': replacements
                    }, "json")
                    
                    logger.info(f"步骤5: 生成替换映射完成，共 {len(replacements)} 个替换项")
                    
                    # 6. 在XML中应用替换（传入root以确保使用同一个元素引用）
                    modified_xml = self._apply_replacements_to_xml(document_xml, replacements, node_mapping, xml_root)
                    
                    # 保存修改后的XML用于调试
                    self._save_debug_info(filename, "07_modified_xml", modified_xml, "xml")
                    
                    logger.info("步骤6: XML替换完成")
                    
                    # 7. 重新打包docx
                    output_path = os.path.join(self.output_dir, f"desensitized_{filename}")
                    
                    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                        # 复制所有原有文件
                        with zipfile.ZipFile(docx_path, 'r') as zip_in:
                            for item in zip_in.infolist():
                                if item.filename == 'word/document.xml':
                                    # 写入修改后的document.xml
                                    zip_out.writestr(item.filename, modified_xml.encode('utf-8'))
                                    logger.info(f"写入修改后的document.xml: {item.filename}")
                                else:
                                    # 复制其他文件
                                    zip_out.writestr(item, zip_in.read(item.filename))
                    
                    logger.info(f"步骤7: 重新打包完成，输出文件: {output_path}")
                    
                    # 验证输出文件
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        logger.info(f"处理成功，文件大小: {os.path.getsize(output_path)} 字节")
                    else:
                        logger.error(f"输出文件验证失败: {output_path}")
                    
                    return output_path
                    
            except Exception as e:
                logger.error(f"处理Word文档失败: {e}", exc_info=True)
                # 保存错误信息
                self._save_debug_info(filename, "99_error", {
                    'error': str(e),
                    'error_type': type(e).__name__
                }, "json")
                raise
    
    async def _call_desensitive_service(self, text: str, 
                                       schemalist: List[str] = None,
                                       max_chunk_len: int = 300) -> Dict:
        """
        调用脱敏服务
        
        Args:
            text: 待脱敏的文本
            schemalist: 要脱敏的实体类型列表
            max_chunk_len: Taskflow分段长度
            
        Returns:
            脱敏结果字典
        """
        # 注意：脱敏服务的端口是8888，接口是/mask/custom
        service_url = self.desensitive_service_url.replace(':8001', ':8888')
        endpoint = f"{service_url}/mask/custom"
        
        payload = {
            "text": text,
            "schemalist": schemalist,
            "max_chunk_len": max_chunk_len
        }
        
        logger.info(f"调用脱敏服务: {endpoint}, 文本长度: {len(text)}")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                result = response.json()
                logger.info(f"脱敏服务调用成功，识别到 {len(result.get('entities_found', []))} 个实体")
                return result
        except Exception as e:
            logger.error(f"调用脱敏服务失败: {e}", exc_info=True)
            raise


class PdfProcessor:
    """PDF文档处理器 - 基于PDF解析API和Markdown转换"""
    
    def __init__(self, desensitive_service_url: str, pdf_parse_api_url: str):
        self.desensitive_service_url = desensitive_service_url
        self.pdf_parse_api_url = pdf_parse_api_url
        self.upload_dir = "uploads"
        self.output_dir = "outputs"
        self.debug_dir = "debug_outputs"  # 调试输出目录
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
    
    def _save_debug_info(self, filename: str, step: str, data: any, data_type: str = "text"):
        """保存调试信息"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(filename)[0]
        debug_file = os.path.join(self.debug_dir, f"{base_name}_{step}_{timestamp}")
        
        try:
            if data_type == "json":
                debug_file += ".json"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                debug_file += ".txt"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(str(data))
            
            logger.info(f"调试信息已保存: {debug_file}")
            return debug_file
        except Exception as e:
            logger.error(f"保存调试信息失败: {e}", exc_info=True)
            return None
    
    async def _parse_pdf_to_markdown(self, file_content: bytes, filename: str) -> str:
        """
        调用PDF解析API将PDF转换为Markdown
        
        Args:
            file_content: PDF文件的二进制内容
            filename: 文件名
            
        Returns:
            Markdown格式的文本内容
        """
        parse_url = f"{self.pdf_parse_api_url}/file_parse"
        
        # 使用列表格式，与示例脚本保持一致
        # httpx 支持列表格式: [('field_name', (filename, content, content_type))]
        files = [
            ('files', (filename, file_content, 'application/pdf'))
        ]
        
        # 保持与测试脚本完全一致的格式
        # httpx 应该能够处理列表、布尔值和整数类型
        # 如果不行，我们再尝试转换为字符串
        data = {
            'backend': 'pipeline',
            'lang_list': ['ch'],  # 保持列表格式，与测试脚本一致
            'parse_method': 'auto',
            'formula_enable': True,  # 保持布尔值格式
            'table_enable': True,
            'return_md': True,
            'return_middle_json': False,
            'return_content_list': False,
            'return_images': False,
            'start_page_id': 0,  # 保持整数格式
            'end_page_id': 99999
        }
        
        logger.info(f"调用PDF解析API: {parse_url}, 文件名: {filename}, 文件大小: {len(file_content)} 字节")
        logger.debug(f"请求参数: {data}")
        
        start_time = datetime.now()
        try:
            # 直接使用requests库，与测试脚本保持一致
            # 通过asyncio在线程池中运行，保持异步特性
            import asyncio
            import requests
            
            logger.info("开始发送PDF解析请求...")
            # 在线程池中运行同步的requests调用
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    parse_url,
                    files=files,
                    data=data,
                    timeout=(10, 600)  # (connect_timeout, read_timeout)
                )
            )
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"PDF解析API响应时间: {elapsed_time:.2f} 秒")
            
            # 检查响应状态并处理错误
            if response.status_code == 502:
                error_msg = (
                    f"PDF解析API服务不可用 (502 Bad Gateway)。"
                    f"请检查PDF解析API服务是否正在运行: {self.pdf_parse_api_url}"
                )
                logger.error(error_msg)
                raise ConnectionError(error_msg)
            elif response.status_code != 200:
                error_msg = f"PDF解析API返回错误: HTTP {response.status_code}"
                try:
                    error_body = response.text
                    logger.error(f"{error_msg}, 响应内容: {error_body[:500]}")
                except:
                    logger.error(error_msg)
                raise ValueError(f"{error_msg}. 请检查PDF解析API服务状态。")
            
            result = response.json()
            
            logger.debug(f"PDF解析API响应: backend={result.get('backend')}, version={result.get('version')}")
            
            # 从结果中提取Markdown内容
            if 'results' in result and result['results']:
                # 获取第一个文件的结果
                file_result = list(result['results'].values())[0]
                if 'md_content' in file_result:
                    markdown = file_result['md_content']
                    logger.info(f"PDF解析成功，Markdown长度: {len(markdown)}")
                    return markdown
                else:
                    logger.error(f"PDF解析结果中未找到md_content字段，可用字段: {list(file_result.keys())}")
                    raise ValueError("PDF解析结果中未找到md_content字段")
            else:
                logger.error(f"PDF解析结果为空，响应内容: {result}")
                raise ValueError("PDF解析结果为空")
        except requests.exceptions.ConnectionError as e:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            error_msg = (
                f"无法连接到PDF解析API服务: {self.pdf_parse_api_url}。"
                f"请确保PDF解析API服务正在运行。"
                f"（耗时: {elapsed_time:.2f} 秒）"
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
        except requests.exceptions.Timeout as e:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            error_msg = (
                f"PDF解析API请求超时（已等待 {elapsed_time:.2f} 秒）。"
                f"PDF文件可能太大或太复杂，需要更长的处理时间。"
                f"请检查PDF解析API服务是否正常运行: {self.pdf_parse_api_url}"
            )
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e
        except (ConnectionError, ValueError, TimeoutError) as e:
            # 重新抛出已处理的错误
            raise
        except Exception as e:
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"调用PDF解析API失败: {e}，耗时: {elapsed_time:.2f} 秒", exc_info=True)
            raise
    
    def _markdown_to_pdf(self, markdown_content: str, output_path: str):
        """
        将Markdown内容转换为PDF文件
        
        Args:
            markdown_content: Markdown格式的文本内容
            output_path: 输出PDF文件路径
        """
        try:
            import markdown
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            # 将Markdown转换为HTML
            html_content = markdown.markdown(
                markdown_content,
                extensions=['extra', 'codehilite', 'tables']
            )
            
            # 添加基本样式以支持中文
            html_with_style = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    @page {{
                        size: A4;
                        margin: 2cm;
                    }}
                    body {{
                        font-family: "SimSun", "宋体", "STSong", "Arial", sans-serif;
                        font-size: 12pt;
                        line-height: 1.6;
                        color: #333;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        font-family: "SimHei", "黑体", "STHeiti", "Arial", sans-serif;
                        margin-top: 1em;
                        margin-bottom: 0.5em;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 1em 0;
                    }}
                    table th, table td {{
                        border: 1px solid #ddd;
                        padding: 8px;
                        text-align: left;
                    }}
                    table th {{
                        background-color: #f2f2f2;
                        font-weight: bold;
                    }}
                    code {{
                        background-color: #f4f4f4;
                        padding: 2px 4px;
                        border-radius: 3px;
                        font-family: "Courier New", monospace;
                    }}
                    pre {{
                        background-color: #f4f4f4;
                        padding: 10px;
                        border-radius: 5px;
                        overflow-x: auto;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            
            # 使用WeasyPrint将HTML转换为PDF
            font_config = FontConfiguration()
            HTML(string=html_with_style).write_pdf(
                output_path,
                font_config=font_config
            )
            
            logger.info(f"Markdown转PDF成功: {output_path}")
        except ImportError as e:
            logger.error(f"缺少必要的库: {e}")
            logger.error("请安装: pip install markdown weasyprint")
            raise
        except Exception as e:
            logger.error(f"Markdown转PDF失败: {e}", exc_info=True)
            raise
    
    async def process_document(self, file_content: bytes, filename: str,
                               schemalist: List[str] = None,
                               max_chunk_len: int = 300,
                               return_pdf: bool = False) -> str:
        """
        处理PDF文档
        
        Args:
            file_content: PDF文档的二进制内容
            filename: 原始文件名
            schemalist: 要脱敏的实体类型列表
            max_chunk_len: Taskflow分段长度
            return_pdf: 是否返回PDF文件（False则返回Markdown文件，用于调试）
            
        Returns:
            处理后的文件路径（Markdown或PDF）
        """
        logger.info(f"开始处理PDF文档: {filename}, return_pdf={return_pdf}")
        
        try:
            # 1. 调用PDF解析API，将PDF转换为Markdown
            logger.info("步骤1: 调用PDF解析API")
            markdown_content = await self._parse_pdf_to_markdown(file_content, filename)
            
            # 保存原始Markdown用于调试
            self._save_debug_info(filename, "01_parsed_markdown", markdown_content, "text")
            
            if not markdown_content.strip():
                logger.warning("PDF解析结果为空，无法继续处理")
                raise ValueError("PDF解析结果为空")
            
            # 2. 调用脱敏服务
            logger.info(f"步骤2: 调用脱敏服务，文本长度: {len(markdown_content)}")
            desensitive_result = await self._call_desensitive_service(
                markdown_content,
                schemalist=schemalist,
                max_chunk_len=max_chunk_len
            )
            
            masked_text = desensitive_result.get('masked', markdown_content)
            entities = desensitive_result.get('entities_found', [])
            
            # 保存脱敏结果用于调试
            self._save_debug_info(filename, "02_masked_markdown", masked_text, "text")
            self._save_debug_info(filename, "03_entities", {
                'total_entities': len(entities),
                'entities': entities
            }, "json")
            
            logger.info(f"步骤3: 脱敏完成，识别到 {len(entities)} 个实体")
            
            # 3. 根据return_pdf参数决定返回Markdown还是PDF
            base_name = os.path.splitext(filename)[0]
            
            if return_pdf:
                # 将脱敏后的Markdown转换为PDF（用于调试）
                logger.info("步骤4: 将Markdown转换为PDF")
                output_path = os.path.join(self.output_dir, f"desensitized_{base_name}.pdf")
                
                self._markdown_to_pdf(masked_text, output_path)
                
                logger.info(f"处理成功，输出PDF文件: {output_path}")
                
                # 验证输出文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"文件大小: {os.path.getsize(output_path)} 字节")
                else:
                    logger.error(f"输出文件验证失败: {output_path}")
            else:
                # 直接返回Markdown文件
                logger.info("步骤4: 保存脱敏后的Markdown文件")
                output_path = os.path.join(self.output_dir, f"desensitized_{base_name}.md")
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(masked_text)
                
                logger.info(f"处理成功，输出Markdown文件: {output_path}")
                
                # 验证输出文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"文件大小: {os.path.getsize(output_path)} 字节")
                else:
                    logger.error(f"输出文件验证失败: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"处理PDF文档失败: {e}", exc_info=True)
            # 保存错误信息
            self._save_debug_info(filename, "99_error", {
                'error': str(e),
                'error_type': type(e).__name__
            }, "json")
            raise
    
    async def _call_desensitive_service(self, text: str,
                                       schemalist: List[str] = None,
                                       max_chunk_len: int = 300) -> Dict:
        """
        调用脱敏服务
        
        Args:
            text: 待脱敏的文本
            schemalist: 要脱敏的实体类型列表
            max_chunk_len: Taskflow分段长度
            
        Returns:
            脱敏结果字典
        """
        # 注意：脱敏服务的端口是8888，接口是/mask/custom
        service_url = self.desensitive_service_url.replace(':8001', ':8888')
        endpoint = f"{service_url}/mask/custom"
        
        payload = {
            "text": text,
            "schemalist": schemalist,
            "max_chunk_len": max_chunk_len
        }
        
        logger.info(f"调用脱敏服务: {endpoint}, 文本长度: {len(text)}")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                result = response.json()
                logger.info(f"脱敏服务调用成功，识别到 {len(result.get('entities_found', []))} 个实体")
                return result
        except Exception as e:
            logger.error(f"调用脱敏服务失败: {e}", exc_info=True)
            raise
