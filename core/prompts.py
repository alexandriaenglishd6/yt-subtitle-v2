"""
AI Prompt 模板集中管理
所有 AI 相关的 Prompt 模板都在这里，使用占位符从 LanguageConfig 注入语言信息
"""

from typing import Optional
from core.language import get_language_name

# Prompt 版本号（当 Prompt 模板有重大变更时更新此版本号）
PROMPT_VERSION = "1.0.0"


def get_translation_prompt(
    source_language: str, target_language: str, subtitle_text: str
) -> str:
    """获取字幕翻译 Prompt

    根据源语言和目标语言生成翻译 Prompt，不硬编码"中文"等语言名称

    Args:
        source_language: 源语言代码（如 "en", "ja"）
        target_language: 目标语言代码（如 "zh-CN", "en-US"）
        subtitle_text: 字幕文本内容

    Returns:
        完整的翻译 Prompt
    """
    source_lang_name = get_language_name(source_language)
    target_lang_name = get_language_name(target_language)

    # 如果是简体中文，在 prompt 中明确说明
    target_lang_spec = target_lang_name
    if target_language.lower() in ["zh-cn", "zh_cn", "zh"]:
        target_lang_spec = "简体中文"
    elif target_language.lower() in ["zh-tw", "zh_tw", "zh-hant"]:
        target_lang_spec = "繁体中文"

    prompt = f"""请将以下字幕从 {source_lang_name} 翻译成 {target_lang_spec}。

要求：
1. 保持字幕的时间轴格式（时间码）
2. 翻译要自然流畅，符合目标语言的表达习惯
3. 保持字幕的原始结构和换行
4. 如果目标语言是中文，请使用简体中文（不要使用繁体中文）

字幕内容：
{subtitle_text}

请直接返回翻译后的字幕内容，保持 SRT 格式。"""

    return prompt


def calculate_suggested_summary_length(
    duration_minutes: int = 0,
    content_length: int = 0,
) -> tuple[int, int]:
    """根据字幕内容长度计算推荐摘要字数范围
    
    规则：
    - 30000+ 字字幕 → 2000-5000 字摘要
    - 5000+ 字字幕 → 800-1500 字摘要
    - 3000-4999 字字幕 → 500-1000 字摘要
    - 3000 字以下 → 300-800 字摘要
    
    Args:
        duration_minutes: 视频时长（分钟，已弃用，保留兼容性）
        content_length: 字幕内容字符数
        
    Returns:
        (最小推荐字数, 最大推荐字数)
    """
    # 根据字幕文本长度计算推荐字数
    if content_length >= 30000:
        return (2000, 5000)
    elif content_length >= 5001:
        return (1500, 4000)
    elif content_length >= 5000:
        return (800, 1500)
    elif content_length >= 3000:
        return (500, 1000)
    else:
        return (300, 800)


def get_summary_prompt(
    summary_language: str,
    subtitle_text: str,
    video_title: Optional[str] = None,
    duration_minutes: int = 0,
) -> str:
    """获取视频摘要 Prompt

    根据字幕文本长度动态调整推荐字数

    Args:
        summary_language: 摘要语言代码（如 "zh-CN", "en-US"）
        subtitle_text: 字幕文本内容
        video_title: 视频标题（可选）
        duration_minutes: 视频时长（分钟，已弃用）

    Returns:
        完整的摘要 Prompt
    """
    summary_lang_name = get_language_name(summary_language)
    
    # 计算推荐字数范围（基于字幕文本长度）
    min_words, max_words = calculate_suggested_summary_length(
        content_length=len(subtitle_text),
    )

    prompt = f"""请用 {summary_lang_name} 为以下视频字幕生成一份详细摘要。

要求：
1. 摘要语言：{summary_lang_name}
2. **内容完整为第一优先级**
   - 建议摘要长度：{min_words}-{max_words} 字
   - 这只是参考范围，如有需要可以增加或减少字数
   - 不强制限制字数，确保覆盖所有重要信息
3. 内容要点：
   - 视频的主要话题和核心观点
   - 关键论点、数据和案例
   - 重要的细节和解释
   - 结论或总结（如有）
4. 输出结构：
   - 开头：视频主旨概述（1-2 句）
   - 正文：按时间线或主题组织内容
   - 结尾：核心结论或要点回顾
5. 格式：使用 Markdown 格式，包含标题和段落，用 **加粗** 标记重要内容
6. 风格：条理清晰，信息密度高，避免空洞表述
7. 根据视频内容自动调整风格：
   - 教程类：突出步骤和操作要点
   - 演讲类：突出核心论点和论据
   - 新闻类：突出事件和关键信息
   - 娱乐类：突出亮点和有趣内容
8. 内容筛选：
   - 跳过广告和赞助商内容
   - 忽略订阅、点赞、关注等号召性用语
   - 简化重复表述，保留核心观点
   - 过滤无意义的寒暄和过渡语"""

    if video_title:
        prompt += f"\n\n视频标题：{video_title}"

    prompt += f"""

字幕内容：
{subtitle_text}

请直接返回摘要内容（Markdown 格式）。"""

    return prompt


def get_bilingual_subtitle_prompt(
    source_language: str,
    target_language: str,
    source_subtitle_text: str,
    target_subtitle_text: str,
) -> str:
    """获取双语字幕生成 Prompt（P1 功能，先预留接口）

    Args:
        source_language: 源语言代码
        target_language: 目标语言代码
        source_subtitle_text: 源语言字幕文本
        target_subtitle_text: 目标语言字幕文本

    Returns:
        完整的双语字幕生成 Prompt
    """
    source_lang_name = get_language_name(source_language)
    target_lang_name = get_language_name(target_language)

    prompt = f"""请将以下 {source_lang_name} 和 {target_lang_name} 字幕合并为双语字幕。

要求：
1. 保持字幕的时间轴格式（时间码）
2. 每行字幕包含源语言和目标语言，格式：源语言 / 目标语言
3. 保持字幕的原始结构和换行

源语言字幕（{source_lang_name}）：
{source_subtitle_text}

目标语言字幕（{target_lang_name}）：
{target_subtitle_text}

请直接返回合并后的双语字幕内容，保持 SRT 格式。"""

    return prompt


def get_chunk_summary_prompt(
    summary_language: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
) -> str:
    """获取分块摘要 Prompt（Map-Reduce 的 Map 阶段）

    Args:
        summary_language: 摘要语言代码
        chunk_text: 分块文本内容
        chunk_index: 当前分块索引（从 1 开始）
        total_chunks: 总分块数

    Returns:
        完整的分块摘要 Prompt
    """
    summary_lang_name = get_language_name(summary_language)

    prompt = f"""请用 {summary_lang_name} 为以下视频字幕片段生成一份详细摘要。

这是第 {chunk_index}/{total_chunks} 个片段。

要求：
1. 摘要语言：{summary_lang_name}
2. 建议摘要长度：200-500 字
   - 如果该片段内容丰富，可以适当增加字数
   - 确保覆盖该片段的所有关键信息
3. 提取该片段的关键信息和要点：
   - 主要论点和观点
   - 具体数据、案例和例子
   - 重要的细节和解释
4. 直接返回摘要内容，不要加任何前缀或标签

字幕片段：
{chunk_text}"""

    return prompt


def get_reduce_summary_prompt(
    summary_language: str,
    sub_summaries: str,
    video_title: Optional[str] = None,
    total_chunks: int = 0,
    duration_minutes: int = 0,
    text_length: int = 0,
) -> str:
    """获取合并摘要 Prompt（Map-Reduce 的 Reduce 阶段）

    Args:
        summary_language: 摘要语言代码
        sub_summaries: 所有分块摘要的合并文本
        video_title: 视频标题（可选）
        total_chunks: 总分块数
        duration_minutes: 视频时长（分钟）
        text_length: 原始字幕文本长度

    Returns:
        完整的合并摘要 Prompt
    """
    summary_lang_name = get_language_name(summary_language)
    
    # 根据字幕文本长度计算推荐字数（优先使用文本长度）
    # 规则：
    # - 30000+ 字字幕 → 2000-5000 字摘要
    # - 5001-29999 字字幕 → 1500-4000 字摘要
    # - 5000 字字幕 → 800-1500 字摘要
    # - 3000-4999 字字幕 → 500-1000 字摘要
    # - 3000 字以下 → 300-800 字摘要
    if text_length >= 30000:
        min_words = 2000
        max_words = 5000
    elif text_length >= 5001:
        min_words = 1500
        max_words = 4000
    elif text_length >= 5000:
        min_words = 800
        max_words = 1500
    elif text_length >= 3000:
        min_words = 500
        max_words = 1000
    else:
        min_words = 300
        max_words = 800

    prompt = f"""请用 {summary_lang_name} 将以下多个片段摘要合并为一份完整、详细的视频摘要。

要求：
1. 摘要语言：{summary_lang_name}
2. **内容完整为第一优先级**
   - 建议摘要长度：{min_words}-{max_words} 字
   - 这只是参考范围，如有需要可以增加或减少字数
   - 不强制限制字数，确保覆盖所有重要信息
3. 内容要点：
   - 整合所有片段的核心观点和论点
   - 保留具体的数据、案例和例子
   - 去除明显重复的信息，但保持完整性
   - 按逻辑顺序组织内容
4. 格式：使用 Markdown 格式，包含标题和段落
5. 风格：条理清晰，信息密度高，避免空洞表述"""

    if video_title:
        prompt += f"\n\n视频标题：{video_title}"

    prompt += f"""

片段摘要：
{sub_summaries}

请直接返回完整摘要内容（Markdown 格式）。"""

    return prompt

