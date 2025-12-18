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


def get_summary_prompt(
    summary_language: str, subtitle_text: str, video_title: Optional[str] = None
) -> str:
    """获取视频摘要 Prompt

    根据摘要语言生成摘要 Prompt，不硬编码"中文"等语言名称

    Args:
        summary_language: 摘要语言代码（如 "zh-CN", "en-US"）
        subtitle_text: 字幕文本内容
        video_title: 视频标题（可选）

    Returns:
        完整的摘要 Prompt
    """
    summary_lang_name = get_language_name(summary_language)

    prompt = f"""请用 {summary_lang_name} 为以下视频字幕生成一份摘要。

要求：
1. 摘要语言：{summary_lang_name}
2. 摘要长度：200-500 字（或等价的英文单词数）
3. 内容要点：
   - 视频的主要话题和核心观点
   - 关键信息和数据（如有）
   - 结论或总结（如有）
4. 格式：使用 Markdown 格式，包含标题和段落"""

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
