import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from paddlenlp import Taskflow
from typing import List, Optional
import re

'''

 * 优化重复实体识别准确率，增加全文二次扫描
 * 优化返回结果，增加匹配方法字段
 * 增加脱敏类型
 - 姓名 地址 企业（机构）名称 
 - 身份证号码 护照号码 港澳通行证 手机号码 固定电话 银行卡号 车牌号码 电子邮箱 统一社会信用代码 纳税人识别号 组织机构代码号码
 * 处理正则冲突：
- 第一优先级 ： 身份证号 （最精确的18位规则）。
- 第二优先级 ： 统一社会信用代码 （18位，排除已标记为身份证的区间）。
- 第三优先级 ： 手机/固定电话/护照/通行证/车牌 。
- 最低优先级 ： 银行卡号 （规则最宽泛，13-19位纯数字，最后匹配且必须避开所有高优先级已占据的区间）。
 * 增加可调参数MAX_CHUNK_LEN

'''

# ---- 脱敏算法配置 ----

MANDATORY_NUMERIC_SCHEMA = [
    "身份证号", "手机号码", "固定电话", "银行卡号",
    "统一社会信用代码", "护照号码", "港澳通行证", "车牌号码",
]
OPTIONAL_SEMANTIC_SCHEMA = ["姓名", "地址", "企业名称", "机构名称", "电子邮箱"]
SCHEMA = MANDATORY_NUMERIC_SCHEMA + OPTIONAL_SEMANTIC_SCHEMA

app = FastAPI(title="脱敏算法服务")

class MaskRequest(BaseModel):
    text: str
    schemalist: Optional[List[str]] = None
    max_chunk_len: Optional[int] = 300

# 三个函数
# - get_regex_entities
# - get_taskflow_entities
# - apply_masking

def get_regex_entities(text: str, labels: List[str]):
    # ……从原文件复制完整实现……
    """使用正则匹配数字类实体"""
    entities = []
    occupied_spans = set() # 记录已被高优先级实体占据的区间
    
    # 1. 身份证号 (最高优先级)
    if "身份证号" in labels:
        pat = re.compile(r'(?<![0-9A-Za-z])[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?![0-9A-Za-z])')
        for m in pat.finditer(text):
            entities.append({"label": "身份证号", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})
            occupied_spans.add((m.start(), m.end()))

    # 2. 统一社会信用代码 (18位，次高优先级)
    if "统一社会信用代码" in labels:
        pat = re.compile(r'(?<![0-9A-Z])[1-9ANY][1-59]\d{6}[0-9ABCDEFGHJKLMNPQRSTUWXY]{10}(?![0-9A-Z])')
        for m in pat.finditer(text):
            span = (m.start(), m.end())
            if any(s <= m.start() and m.end() <= e for s, e in occupied_spans):
                continue
            entities.append({"label": "统一社会信用代码", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})
            occupied_spans.add(span)

    # 3. 手机号码
    if "手机号码" in labels:
        pat = re.compile(r'(?<![0-9A-Za-z])(?:\+86|86)?\s?1[3-9]\d{9}(?![0-9A-Za-z])')
        for m in pat.finditer(text):
            if any(s <= m.start() and m.end() <= e for s, e in occupied_spans):
                continue
            entities.append({"label": "手机号码", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})
            occupied_spans.add((m.start(), m.end()))

    # 4. 固定电话
    if "固定电话" in labels:
        pat = re.compile(r'(?<![0-9A-Za-z])(?:0\d{2,3}-)?\d{7,8}(?![0-9A-Za-z])')
        for m in pat.finditer(text):
            if any(s <= m.start() and m.end() <= e for s, e in occupied_spans):
                continue
            entities.append({"label": "固定电话", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})
            occupied_spans.add((m.start(), m.end()))

    # 5. 银行卡号 (最低优先级，因为位宽最广 13-19位)
    if "银行卡号" in labels:
        pat = re.compile(r'(?<![0-9A-Za-z])((?:\d[ -]?){13,19})(?![0-9A-Za-z])')
        for m in pat.finditer(text):
            val = m.group()
            dc = sum(1 for c in val if c.isdigit())
            if 13 <= dc <= 19:
                if any(s <= m.start() and m.end() <= e for s, e in occupied_spans):
                    continue
                entities.append({"label": "银行卡号", "start": m.start(), "end": m.end(), "text": val, "method": "regex"})
                occupied_spans.add((m.start(), m.end()))

    # 5. 护照号码
    if "护照号码" in labels:
        # 常见中国护照：D/E/G/S/P开头 + 7或8位数字
        pat = re.compile(r'(?<![0-9A-Z])[DEGSP]\d{7,8}(?![0-9A-Z])')
        for m in pat.finditer(text):
            entities.append({"label": "护照号码", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})

    # 6. 港澳通行证
    if "港澳通行证" in labels:
        # C/W/H/M开头 + 8位数字
        pat = re.compile(r'(?<![0-9A-Z])[CWHM]\d{8}(?![0-9A-Z])')
        for m in pat.finditer(text):
            entities.append({"label": "港澳通行证", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})

    # 7. 车牌号码
    if "车牌号码" in labels:
        # 所有省级简称
        provinces = r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]'
        
        # 构建完整正则
        pat = re.compile(
            r'(?<![A-Z0-9])'
            r'(?:'
                # 1. 普通蓝牌/黄牌及新能源车牌 (5-6位字母数字)
                rf'{provinces}[A-Z][\s\-]?[A-Z0-9]{{5,6}}|'
                # 2. 港澳入出境车牌：粤Z + 4位字母数字 + 港/澳
                r'粤Z[\s\-]?[A-Z0-9]{4}[港澳]'
            r')'
            r'(?![A-Z0-9])',
            re.ASCII
        )
        for m in pat.finditer(text):
            entities.append({"label": "车牌号码", "start": m.start(), "end": m.end(), "text": m.group(), "method": "regex"})
                
    return entities

def get_taskflow_entities(text: str, labels: List[str], max_chunk_len: int = 300):
    """使用 Taskflow 匹配中文/语义实体（增加长文本分段处理逻辑）"""
    if not labels:
        return []
    ie_model = Taskflow("information_extraction", schema=OPTIONAL_SEMANTIC_SCHEMA, task_path='./model')    
    # 设定单段最大长度
    MAX_CHUNK_LEN = max_chunk_len
    
    # 1. 智能分段逻辑：优先按换行、句号等分句，避免截断实体
    def split_into_chunks(text, max_len):
        chunks = []
        start = 0
        # 匹配句子结束标志
        delimiters = r'(\n|。|！|？|；)'
        parts = re.split(delimiters, text)
        
        current_chunk = ""
        current_start = 0
        
        for i in range(0, len(parts)-1, 2):
            content = parts[i] + parts[i+1] # 文本 + 分隔符
            if len(current_chunk) + len(content) > max_len and current_chunk:
                chunks.append((current_chunk, current_start))
                current_chunk = content
                current_start = text.find(content, current_start + len(chunks[-1][0]))
            else:
                if not current_chunk:
                    current_start = text.find(content, current_start)
                current_chunk += content
        
        # 剩余部分
        last_part = parts[-1]
        if len(current_chunk) + len(last_part) > max_len and current_chunk:
            chunks.append((current_chunk, current_start))
            chunks.append((last_part, text.find(last_part, current_start + len(chunks[-1][0]))))
        else:
            current_chunk += last_part
            if current_chunk:
                chunks.append((current_chunk, current_start))
        
        return chunks

    all_taskflow_entities = []
    chunks = split_into_chunks(text, MAX_CHUNK_LEN)
    
    try:
        ie_model.set_schema(labels)
        for chunk_text, chunk_offset in chunks:
            if not chunk_text.strip():
                continue
            
            results = ie_model(chunk_text)
            res = results[0] if results else {}
            
            for label, items in res.items():
                for item in items:
                    all_taskflow_entities.append({
                        "label": label,
                        "start": item['start'] + chunk_offset, # 加上偏移量
                        "end": item['end'] + chunk_offset,     # 加上偏移量
                        "text": item['text'],
                        "method": "taskflow_chunk"
                    })
        return all_taskflow_entities
    except Exception as e:
        print(f"Taskflow error: {e}")
        return []

def apply_masking(text: str, entities: List[dict]):
    """合并所有实体并执行脱敏"""
    # 1. 按起始位置排序
    entities.sort(key=lambda x: x['start'])
    
    # 2. 合并重叠区间（注意：这里只合并真正重叠的区间，紧邻但不重叠的区间要分开处理）
    merged_spans = []
    for ent in entities:
        s, e = ent['start'], ent['end']
        label = ent['label']
        # 只有当当前实体的起始位置小于上一个实体的结束位置时，才认为存在重叠
        # 例如：[3,5] 和 [5,23] 只是“挨着”，不应该合并，这样可以避免“姓名+身份证号”被合并成一个大区间
        if not merged_spans or s >= merged_spans[-1][1]:
            merged_spans.append([s, e, label])
        else:
            # 存在真正的重叠，取并集
            merged_spans[-1][1] = max(merged_spans[-1][1], e)
            # 如果之前的标签是语义类，当前的标签是数字类，优先保留数字类标签
            if label in MANDATORY_NUMERIC_SCHEMA:
                merged_spans[-1][2] = label
    
    # 3. 执行替换
    out = []
    prev = 0
    for s, e, label in merged_spans:
        out.append(text[prev:s])
        
        # 不同类型的脱敏策略
        segment = text[s:e]
        if label == "身份证号":
            # 隐藏后六位
            digits = [i for i, c in enumerate(segment) if c.isdigit() or c.lower() == 'x']
            masked_seg = list(segment)
            if len(digits) >= 6:
                for i in digits[-6:]:
                    masked_seg[i] = '*'
            else:
                for i in digits: masked_seg[i] = '*'
            out.append("".join(masked_seg))
        elif label == "手机号码":
            # 手机号隐藏第4到第7位
            digits = [i for i, c in enumerate(segment) if c.isdigit()]
            masked_seg = list(segment)
            if len(digits) >= 11:
                # 针对11位及以上（含86）隐藏倒数第8到第5位，或简单处理
                # 这里简单处理：隐藏中间4位
                start_idx = 3 if len(digits) == 11 else len(digits) - 8
                for i in digits[start_idx : start_idx + 4]:
                    masked_seg[i] = '*'
            out.append("".join(masked_seg))
        elif label == "固定电话":
            # 固定电话中间部分掩码
            digits = [i for i, c in enumerate(segment) if c.isdigit()]
            masked_seg = list(segment)
            mid = len(digits) // 2
            for i in digits[max(0, mid-2):mid+2]:
                masked_seg[i] = '*'
            out.append("".join(masked_seg))
        elif label == "姓名":
            # 隐藏第一个字
            masked_seg = list(segment)
            if len(masked_seg) > 0:
                masked_seg[0] = '*'
            out.append("".join(masked_seg))
        elif label in ["银行卡号", "统一社会信用代码"]:
            # 保留末尾4位
            digits = [i for i, c in enumerate(segment) if c.isdigit() or c.isalpha()]
            masked_seg = list(segment)
            if len(digits) > 4:
                for i in digits[:-4]:
                    masked_seg[i] = '*'
            else:
                for i in digits: masked_seg[i] = '*'
            out.append("".join(masked_seg))
        elif label == "护照号码":
            # 护照：保留首尾，中间掩码
            masked_seg = list(segment)
            if len(masked_seg) > 2:
                for i in range(1, len(masked_seg)-1):
                    masked_seg[i] = '*'
            out.append("".join(masked_seg))
        elif label == "港澳通行证":
            # 港澳通行证：隐藏中间4位
            masked_seg = list(segment)
            if len(masked_seg) >= 9:
                for i in range(2, 6):
                    masked_seg[i] = '*'
            out.append("".join(masked_seg))
        elif label == "车牌号码":
            # 车牌：隐藏中间部分
            masked_seg = list(segment)
            if len(masked_seg) >= 7:
                # 隐藏第3到第5位（如：粤B·****8）
                for i in range(2, len(masked_seg)-1):
                    if masked_seg[i].isalnum():
                        masked_seg[i] = '*'
            out.append("".join(masked_seg))
        else:
            # 其他语义类：全掩码
            out.append("*" * len(segment))
            
        prev = e
    out.append(text[prev:])
    return "".join(out)

# ---- API 路由 ----

@app.post("/mask/custom")
def mask_custom(req: MaskRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")

    selected_labels = req.schemalist or []

    # 1. 正则匹配 (数字类)
    numeric_to_match = [l for l in selected_labels if l in MANDATORY_NUMERIC_SCHEMA]
    regex_ents = get_regex_entities(req.text, numeric_to_match) if numeric_to_match else []

    # 2. Taskflow 匹配 (语义类)
    tf_labels = [l for l in selected_labels if l not in MANDATORY_NUMERIC_SCHEMA]
    tf_ents = get_taskflow_entities(req.text, tf_labels, max_chunk_len=req.max_chunk_len or 300) if tf_labels else []

    # 3. 二次扫描与合并实体（这一整段逻辑也从你现在的文件里原样复制即可）
    final_ents_map = {}
    for ent in regex_ents:
        final_ents_map[(ent["start"], ent["end"])] = ent

    tf_original_map = {(e["start"], e["end"]): e for e in tf_ents}
    tf_text_to_label = {}
    for e in tf_ents:
        t, l = e["text"], e["label"]
        if t and t not in tf_text_to_label:
            tf_text_to_label[t] = l

    for t, l in tf_text_to_label.items():
        for m in re.finditer(re.escape(t), req.text, re.IGNORECASE):
            span = (m.start(), m.end())
            if span in final_ents_map:
                continue
            if span in tf_original_map:
                final_ents_map[span] = tf_original_map[span]
            else:
                final_ents_map[span] = {
                    "label": l,
                    "start": m.start(),
                    "end": m.end(),
                    "text": m.group(),
                    "method": "taskflow_global_scan",
                }

    for span, ent in tf_original_map.items():
        if span not in final_ents_map:
            final_ents_map[span] = ent

    global_ents = sorted(final_ents_map.values(), key=lambda x: x["start"])
    masked_text = apply_masking(req.text, global_ents)

    return {
        "original": req.text,
        "masked": masked_text,
        "entities_found": global_ents,
        "mandatory": MANDATORY_NUMERIC_SCHEMA,
        "optional_selected": tf_labels,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8888)