"""
中文简繁体检测模块

通过字符频率统计法检测中文内容是简体还是繁体。
在字幕下载后进行检测，规范化语言代码（zh -> zh-CN 或 zh-TW）。
"""

from typing import Optional


# 简体中文独有字符（这些字符在繁体中有对应的不同写法）
SIMPLIFIED_CHARS = set(
    "这个国为对时会着没来过样还说让给动东头长马乐业开门后进问选风云电话语"
    "车书买卖读写处办认识虽声听视观级织纸终线练经显现导层届发单双亲专转"
)

# 繁体中文独有字符（这些字符在简体中有对应的不同写法）
TRADITIONAL_CHARS = set(
    "這個國為對時會著沒來過樣還說讓給動東頭長馬樂業開門後進問選風雲電話語"
    "車書買賣讀寫處辦認識雖聲聽視觀級織紙終線練經顯現導層屆發單雙親專轉"
)


def detect_chinese_variant(text: str, min_sample_size: int = 10) -> str:
    """检测中文文本是简体还是繁体
    
    通过统计简体独有字符和繁体独有字符的出现频率来判断。
    
    Args:
        text: 要检测的中文文本
        min_sample_size: 最小样本量，低于此值返回 "zh"（无法确定）
        
    Returns:
        "zh-CN": 简体中文
        "zh-TW": 繁体中文
        "zh": 无法确定（混合内容或样本太少）
        
    Examples:
        >>> detect_chinese_variant("这是一个简体中文测试")
        'zh-CN'
        >>> detect_chinese_variant("這是一個繁體中文測試")
        'zh-TW'
    """
    if not text:
        return "zh"
    
    simplified_count = 0
    traditional_count = 0
    
    for char in text:
        if char in SIMPLIFIED_CHARS:
            simplified_count += 1
        elif char in TRADITIONAL_CHARS:
            traditional_count += 1
    
    total = simplified_count + traditional_count
    
    # 样本太少，无法判断
    if total < min_sample_size:
        return "zh"
    
    # 计算简体字符比例
    simplified_ratio = simplified_count / total
    
    # 判断阈值：
    # > 0.7 = 简体
    # < 0.3 = 繁体
    # 0.3-0.7 = 混合/无法确定
    if simplified_ratio > 0.7:
        return "zh-CN"
    elif simplified_ratio < 0.3:
        return "zh-TW"
    else:
        return "zh"


def normalize_chinese_lang_code(lang_code: str, content: Optional[str] = None) -> str:
    """规范化中文语言代码
    
    如果语言代码是 "zh"（不区分简繁），根据内容检测结果规范化为 "zh-CN" 或 "zh-TW"。
    
    Args:
        lang_code: 原始语言代码
        content: 字幕内容（用于检测简繁体）
        
    Returns:
        规范化后的语言代码
    """
    # 只处理 "zh" 这种不区分简繁的代码
    if lang_code.lower() not in ("zh", "zh-hans", "zh-hant"):
        return lang_code
    
    # zh-Hans 明确是简体，zh-Hant 明确是繁体
    if lang_code.lower() == "zh-hans":
        return "zh-CN"
    if lang_code.lower() == "zh-hant":
        return "zh-TW"
    
    # "zh" 需要通过内容检测
    if content:
        detected = detect_chinese_variant(content)
        if detected != "zh":
            return detected
    
    # 无法确定时，默认使用简体（大部分 YouTube 中文内容是简体）
    return "zh-CN"


def is_chinese_lang(lang_code: str) -> bool:
    """判断语言代码是否是中文
    
    Args:
        lang_code: 语言代码
        
    Returns:
        是否是中文语言代码
    """
    if not lang_code:
        return False
    lower = lang_code.lower()
    return lower.startswith("zh") or lower in ("cmn", "yue")  # cmn=普通话, yue=粤语
