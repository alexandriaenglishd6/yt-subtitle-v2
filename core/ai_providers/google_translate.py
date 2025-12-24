"""
Google 翻译客户端（免费版）

使用 deep-translator 库调用 Google 翻译的免费接口
注意：这不是 LLM，但实现 LLMClient 接口以便统一使用
"""

import threading
from typing import Optional, Sequence

from config.manager import AIConfig
from core.exceptions import TaskCancelledError
from core.llm_client import LLMResult, LLMUsage, LLMException, LLMErrorType
from core.logger import get_logger, translate_exception, translate_log

logger = get_logger()


class GoogleTranslateClient:
    """Google 翻译客户端（免费版）

    使用 deep-translator 库调用 Google 翻译的免费接口
    注意：这不是 LLM，但实现 LLMClient 接口以便统一使用
    """

    def __init__(self, ai_config: AIConfig):
        """初始化 Google 翻译客户端

        Args:
            ai_config: AI 配置（虽然不需要 API Key，但保持接口一致）
        """
        self.ai_config = ai_config
        self.provider_name = "google_translate"

        # 检查依赖
        try:
            from deep_translator import GoogleTranslator

            self._translator_class = GoogleTranslator
        except ImportError:
            raise LLMException(
                translate_exception("exception.ai_dependency_missing", library="deep-translator"),
                LLMErrorType.UNKNOWN,
            )

        # 必需属性（Google 翻译不是 LLM，设置合理的默认值）
        self.supports_vision = False
        self.max_input_tokens = (
            50000  # Google 翻译单次可翻译约 5000 字符，这里设置较大值
        )
        self.max_output_tokens = 50000
        self.max_concurrency = ai_config.max_concurrency  # 使用配置的并发限制

        # 创建 Semaphore 用于并发限流
        self._sem = threading.Semaphore(self.max_concurrency)

        # 取消令牌（用于支持取消操作，由 SubtitleTranslator 在调用前设置）
        self._cancel_token = None

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """使用 Google 翻译进行翻译

        注意：prompt 应该包含字幕文本，格式由 get_translation_prompt 生成
        我们需要从 prompt 中提取字幕文本，翻译后重新组装

        Args:
            prompt: 翻译提示词（包含字幕文本）
            system: 系统提示词（忽略，Google 翻译不需要）
            max_tokens: 最大 token 数（忽略）
            temperature: 温度参数（忽略）
            stop: 停止序列（忽略）

        Returns:
            LLMResult 对象，包含翻译后的文本

        Raises:
            LLMException: 当翻译失败时抛出
        """
        try:
            # 从 prompt 中提取字幕文本
            # prompt 格式：请将以下字幕从 X 翻译成 Y...\n\n字幕内容：\n{字幕文本}\n\n请直接返回...
            subtitle_text = self._extract_subtitle_from_prompt(prompt)

            # 提取源语言和目标语言
            source_lang, target_lang = self._extract_languages_from_prompt(prompt)

            # 如果无法从 prompt 中提取字幕格式，尝试其他方法
            if not subtitle_text or not source_lang or not target_lang:
                # 尝试从 prompt 中提取目标语言名称（即使字幕提取失败）
                import re

                # 尝试提取目标语言名称
                target_match = re.search(r"翻译成\s+(\S+)", prompt)
                if target_match:
                    target_lang_name = target_match.group(1).rstrip("。")
                    target_lang = self._language_name_to_code(target_lang_name)
                    # 使用自动检测源语言
                    source_lang_short = "auto"
                    target_lang_short = self._normalize_lang_code(target_lang)
                else:
                    # 完全无法提取，使用默认值（但这是不应该发生的情况）
                    logger.warning_i18n("ai_extract_language_failed")
                    source_lang_short = "auto"
                    target_lang_short = "zh-CN"

                # 如果没有字幕文本，尝试从 prompt 中提取（简单文本模式）
                if not subtitle_text:
                    subtitle_text = prompt.strip()

                # 如果还是没有字幕文本，直接翻译整个 prompt（用于测试）
                if subtitle_text:
                    # 直接翻译文本（不解析 SRT 格式）
                    # 使用 Semaphore 进行并发限流
                    from deep_translator import GoogleTranslator

                    with self._sem:
                        translator = GoogleTranslator(
                            source=source_lang_short, target=target_lang_short
                        )
                        translated_text = translator.translate(subtitle_text)
                else:
                    from core.logger import translate_log

                    raise LLMException(
                        translate_log("subtitle_text_extract_failed"),
                        LLMErrorType.UNKNOWN,
                    )
            else:
                # 正常模式：提取到了字幕格式
                # 转换语言代码格式（Google 翻译使用短格式，如 "zh", "en"）
                source_lang_short = self._normalize_lang_code(source_lang)
                target_lang_short = self._normalize_lang_code(target_lang)

                # 翻译字幕（保持 SRT 格式）
                # 使用 Semaphore 进行并发限流
                # 从实例属性获取 cancel_token（由 SubtitleTranslator 在调用前设置）
                with self._sem:
                    translated_text = self._translate_srt(
                        subtitle_text,
                        source_lang_short,
                        target_lang_short,
                        cancel_token=self._cancel_token,
                    )

            return LLMResult(
                text=translated_text,
                usage=LLMUsage(),  # Google 翻译不提供 token 统计
                provider="google_translate",
                model="google_translate_free",
            )

        except LLMException:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if (
                "network" in error_msg
                or "connection" in error_msg
                or "timeout" in error_msg
            ):
                raise LLMException(
                    translate_exception("exception.google_translate_connection_failed", error=str(e)),
                    LLMErrorType.NETWORK,
                )
            elif "quota" in error_msg or "limit" in error_msg:
                raise LLMException(
                    translate_exception("exception.google_translate_rate_limit", error=str(e)),
                    LLMErrorType.RATE_LIMIT,
                )
            else:
                raise LLMException(
                    translate_exception("exception.google_translate_failed", error=str(e)),
                    LLMErrorType.UNKNOWN,
                )

    def _extract_subtitle_from_prompt(self, prompt: str) -> Optional[str]:
        """从 prompt 中提取字幕文本

        Args:
            prompt: 翻译提示词

        Returns:
            字幕文本，如果无法提取则返回 None
        """
        # prompt 格式：...\n\n字幕内容：\n{字幕文本}\n\n请直接返回...
        markers = ["字幕内容：", "字幕内容:", "Subtitle content:", "Subtitle content："]
        for marker in markers:
            if marker in prompt:
                parts = prompt.split(marker, 1)
                if len(parts) > 1:
                    subtitle_part = parts[1]
                    # 移除最后的提示文本（"请直接返回..."）
                    if "请直接返回" in subtitle_part:
                        subtitle_part = subtitle_part.split("请直接返回")[0]
                    elif "Please return" in subtitle_part:
                        subtitle_part = subtitle_part.split("Please return")[0]
                    return subtitle_part.strip()
        return None

    def _extract_languages_from_prompt(
        self, prompt: str
    ) -> tuple[Optional[str], Optional[str]]:
        """从 prompt 中提取源语言和目标语言

        Args:
            prompt: 翻译提示词

        Returns:
            (源语言代码, 目标语言代码)，如果无法提取则返回 (None, None)
        """
        # prompt 格式：请将以下字幕从 {源语言名称} 翻译成 {目标语言名称}
        # 注意：prompt 中使用的是语言名称（如"中文"、"English"），需要转换为语言代码
        import re

        patterns = [
            r"从\s+(\S+)\s+翻译成\s+(\S+)",
            r"from\s+(\S+)\s+to\s+(\S+)",
            r"从\s+(\S+)\s+翻\s+(\S+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                source_lang_name = match.group(1).rstrip("。")  # 移除可能的句号
                target_lang_name = match.group(2).rstrip("。")
                # 将语言名称转换为语言代码
                source_code = self._language_name_to_code(source_lang_name)
                target_code = self._language_name_to_code(target_lang_name)
                return source_code, target_code
        return None, None

    def _language_name_to_code(self, lang_name: str) -> str:
        """将语言名称转换为语言代码

        Args:
            lang_name: 语言名称（如 "中文", "English", "日本語"）或语言代码（如 "ar", "zh-CN"）

        Returns:
            语言代码（如 "zh-CN", "en-US", "ja-JP", "ar"），如果无法识别则返回原值
        """
        # 语言名称到语言代码的映射（与 core/language.py 中的 get_language_name 对应）
        name_to_code = {
            "中文": "zh-CN",
            "简体中文": "zh-CN",  # 简体中文别名
            "繁體中文": "zh-TW",
            "繁体中文": "zh-TW",  # 繁体中文别名
            "English": "en-US",
            "英语": "en",  # 英语中文名
            "英文": "en",  # 英文中文名
            "日本語": "ja-JP",
            "日语": "ja",  # 日语中文名
            "日文": "ja",  # 日文中文名
            "한국어": "ko-KR",
            "韩语": "ko",  # 韩语中文名
            "韩文": "ko",  # 韩文中文名
            "Español": "es-ES",
            "西班牙语": "es",  # 西班牙语中文名
            "Français": "fr-FR",
            "法语": "fr",  # 法语中文名
            "Deutsch": "de-DE",
            "德语": "de",  # 德语中文名
            "Русский": "ru-RU",
            "俄语": "ru",  # 俄语中文名
            "Português": "pt-PT",
            "葡萄牙语": "pt",  # 葡萄牙语中文名
            "Italiano": "it-IT",
            "意大利语": "it",  # 意大利语中文名
            "العربية": "ar",  # 阿拉伯语
            "阿拉伯语": "ar",  # 阿拉伯语中文名
            "ar": "ar",  # 直接支持语言代码
            "हिन्दी": "hi-IN",  # 印地语
            "印地语": "hi",  # 印地语中文名
        }
        # 如果输入已经是语言代码（短代码或标准代码），直接返回
        # 常见的语言代码格式：2-3 字母（如 "ar", "zh", "en"）或带地区后缀（如 "ar-SA", "zh-CN"）
        if len(lang_name) <= 5 and ("-" in lang_name or lang_name.isalpha()):
            # 可能是语言代码，先尝试映射，如果没有则直接返回
            return name_to_code.get(lang_name, lang_name)
        # 否则作为语言名称查找
        return name_to_code.get(lang_name, lang_name)

    def _normalize_lang_code(self, lang_code: str) -> str:
        """标准化语言代码（转换为 Google 翻译支持的格式）

        注意：deep-translator 库的 GoogleTranslator 需要特定的语言代码格式：
        - 简体中文需要使用 "zh-CN"（大写）
        - 繁体中文需要使用 "zh-TW"（大写）
        - 其他语言使用 2 字母 ISO 639-1 代码（小写）

        Args:
            lang_code: 语言代码（如 "zh-CN", "en-US", "ar"）

        Returns:
            标准化后的语言代码（如 "zh-CN", "zh-TW", "en", "ar"）
        """
        # 提取主语言代码
        lang_code_lower = lang_code.lower()
        main_code = lang_code_lower.split("-")[0]

        # 特殊处理：中文需要区分简体和繁体
        if main_code == "zh":
            if lang_code_lower in ["zh-tw", "zh_tw", "zh-hant"]:
                normalized = "zh-TW"
            else:
                # zh, zh-cn, zh_cn, zh-hans 等都视为简体中文
                normalized = "zh-CN"
            return normalized

        # 其他语言：使用小写的主语言代码
        lang_map = {
            "en": "en",
            "ja": "ja",
            "ko": "ko",
            "es": "es",
            "fr": "fr",
            "de": "de",
            "ru": "ru",
            "pt": "pt",
            "it": "it",
            "ar": "ar",
            "hi": "hi",
        }

        normalized = lang_map.get(main_code, main_code)

        return normalized

    def _translate_srt(
        self, srt_text: str, source_lang: str, target_lang: str, cancel_token=None
    ) -> str:
        """翻译 SRT 或 VTT 字幕文件（保持时间轴格式）

        支持两种格式：
        1. SRT 格式：序号、时间轴（-->）、文本、空行
        2. VTT 格式：WEBVTT 头部、时间轴（-->）、文本、空行

        Args:
            srt_text: SRT 或 VTT 字幕文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
            cancel_token: 取消令牌（可选）

        Returns:
            翻译后的 SRT 字幕文本（统一转换为 SRT 格式）

        Raises:
            LLMException: 当翻译失败时抛出
            TaskCancelledError: 当取消令牌被触发时抛出
        """

        try:
            # 检查是否是 VTT 格式
            is_vtt = srt_text.strip().startswith("WEBVTT") or "WEBVTT" in srt_text[:100]

            if is_vtt:
                # 处理 VTT 格式
                return self._translate_vtt_to_srt(
                    srt_text, source_lang, target_lang, cancel_token=cancel_token
                )
            else:
                # 处理 SRT 格式
                return self._translate_srt_format(
                    srt_text, source_lang, target_lang, cancel_token=cancel_token
                )

        except TaskCancelledError:
            # 取消操作，直接重新抛出（不要包装成 LLMException）
            raise
        except Exception as e:
            raise LLMException(
                translate_exception("exception.translate_subtitle_failed", error=str(e)),
                LLMErrorType.UNKNOWN,
            )

    def _translate_srt_format(
        self, srt_text: str, source_lang: str, target_lang: str, cancel_token=None
    ) -> str:
        """翻译 SRT 格式字幕（保持时间轴格式）

        Args:
            srt_text: SRT 字幕文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
            cancel_token: 取消令牌（可选）

        Returns:
            翻译后的 SRT 字幕文本

        Raises:
            TaskCancelledError: 如果取消令牌被触发
        """
        # 解析 SRT 格式：序号、时间轴、文本、空行
        lines = srt_text.split("\n")
        translated_lines = []
        current_block = []

        # 预先计算总块数以显示进度
        total_blocks = 0
        for line in lines:
            if "-->" in line:
                total_blocks += 1
        
        processed_blocks = 0
        last_log_percent = -20 # 初始设置，每 20% 输出一次

        for line in lines:
            # 检查取消状态（在处理每个字幕块前）
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            line_stripped = line.strip()

            # 空行：结束当前字幕块
            if not line_stripped:
                if current_block:
                    translated_block = self._translate_subtitle_block(
                        current_block,
                        source_lang,
                        target_lang,
                        cancel_token=cancel_token,
                    )
                    translated_lines.extend(translated_block)
                    translated_lines.append("")
                    current_block = []
                    
                    # 进度汇总日志（DEBUG 级别，避免并发时日志混乱）
                    processed_blocks += 1
                    if total_blocks > 0:
                        percent = (processed_blocks * 100) // total_blocks
                        # 只在 100% 时输出（DEBUG），主要进度在 translator 层
                        if processed_blocks == total_blocks:
                            logger.debug(
                                translate_log(
                                    "log.translation_progress",
                                    target_lang=target_lang,
                                    current=processed_blocks,
                                    total=total_blocks,
                                    percent=percent
                                )
                            )
                            last_log_percent = percent
                else:
                    translated_lines.append("")
                continue

            # 判断是否是序号（纯数字）
            if line_stripped.isdigit() and not current_block:
                # 新字幕块开始
                current_block = [line]
                continue

            # 判断是否是时间轴（包含 -->）
            if "-->" in line:
                if current_block:  # 确保有序号
                    current_block.append(line)
                continue

            # 其他行：字幕文本（添加到当前块）
            if current_block:
                current_block.append(line)
            else:
                # 没有序号，可能是格式问题，直接添加
                translated_lines.append(line)

        # 处理最后一个块
        if current_block:
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            translated_block = self._translate_subtitle_block(
                current_block, source_lang, target_lang, cancel_token=cancel_token
            )
            translated_lines.extend(translated_block)

        return "\n".join(translated_lines)

    def _translate_vtt_to_srt(
        self, vtt_text: str, source_lang: str, target_lang: str, cancel_token=None
    ) -> str:
        """将 VTT 格式转换为 SRT 格式并翻译

        Args:
            vtt_text: VTT 字幕文本
            source_lang: 源语言代码
            target_lang: 目标语言代码

        Returns:
            翻译后的 SRT 字幕文本
        """
        lines = vtt_text.split("\n")
        translated_lines = []
        current_block = []
        subtitle_index = 1  # SRT 格式需要序号
        skip_header = True

        # 预先计算总块数
        total_blocks = 0
        for line in lines:
            if "-->" in line:
                total_blocks += 1
        
        processed_blocks = 0
        last_log_percent = -20

        for line in lines:
            line_stripped = line.strip()

            # 跳过 VTT 头部（WEBVTT 及其元数据）
            if skip_header:
                if line_stripped.upper().startswith("WEBVTT"):
                    continue
                if line_stripped.startswith("Kind:") or line_stripped.startswith(
                    "Language:"
                ):
                    continue
                if line_stripped.startswith("Translator:") or line_stripped.startswith(
                    "Reviewer:"
                ):
                    continue
                # 如果遇到空行且还没开始字幕块，继续跳过
                if not line_stripped and not current_block:
                    continue
                # 遇到时间轴，开始处理字幕
                if "-->" in line:
                    skip_header = False
                elif (
                    line_stripped
                    and not line_stripped.startswith("WEBVTT")
                    and "-->" not in line
                ):
                    # 可能是注释或其他元数据，继续跳过
                    continue

            # 空行：结束当前字幕块
            if not line_stripped:
                if current_block:
                    # 添加序号到块的开头（如果是 VTT，可能没有序号）
                    if not current_block[0].strip().isdigit():
                        current_block.insert(0, str(subtitle_index))

                    translated_block = self._translate_subtitle_block(
                        current_block,
                        source_lang,
                        target_lang,
                        cancel_token=cancel_token,
                    )
                    translated_lines.extend(translated_block)
                    translated_lines.append("")
                    current_block = []
                    
                    # 进度汇总日志（DEBUG 级别，避免并发时日志混乱）
                    processed_blocks += 1
                    if total_blocks > 0:
                        percent = (processed_blocks * 100) // total_blocks
                        # 只在 100% 时输出（DEBUG），主要进度在 translator 层
                        if processed_blocks == total_blocks:
                            logger.debug(
                                translate_log(
                                    "log.translation_progress",
                                    target_lang=target_lang,
                                    current=processed_blocks,
                                    total=total_blocks,
                                    percent=percent
                                )
                            )
                            last_log_percent = percent
                    
                    subtitle_index += 1
                else:
                    translated_lines.append("")
                continue

            # 判断是否是时间轴（包含 -->）
            if "-->" in line:
                # VTT 时间轴格式：00:00:00.000 --> 00:00:02.000
                # 转换为 SRT 时间轴格式：00:00:00,000 --> 00:00:02,000 (点改为逗号)
                srt_time_line = line.replace(".", ",")
                if not current_block:
                    # 新字幕块，添加序号
                    current_block = [str(subtitle_index)]
                current_block.append(srt_time_line)
                continue

            # 其他行：字幕文本（添加到当前块）
            if current_block:
                current_block.append(line)
            elif not skip_header:
                # 不在头部，且没有时间轴，可能是格式问题，直接添加
                translated_lines.append(line)

        # 处理最后一个块
        if current_block:
            if not current_block[0].strip().isdigit():
                current_block.insert(0, str(subtitle_index))
            translated_block = self._translate_subtitle_block(
                current_block, source_lang, target_lang, cancel_token=cancel_token
            )
            translated_lines.extend(translated_block)

        return "\n".join(translated_lines)

    def _translate_subtitle_block(
        self, block: list[str], source_lang: str, target_lang: str, cancel_token=None
    ) -> list[str]:
        """翻译单个字幕块

        Args:
            block: 字幕块（序号、时间轴、文本行）
            source_lang: 源语言代码
            target_lang: 目标语言代码
            cancel_token: 取消令牌（可选）

        Returns:
            翻译后的字幕块

        Raises:
            TaskCancelledError: 如果取消令牌被触发
        """
        from deep_translator import GoogleTranslator

        # 检查取消状态（在每个字幕块翻译开始时）
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or "用户取消"
            raise TaskCancelledError(reason)

        if len(block) < 3:
            return block  # 格式不正确，返回原样

        # 序号和时间轴保持不变
        result = [block[0], block[1]]

        # 收集所有文本行（跳过序号和时间轴）
        text_lines = []
        for line in block[2:]:
            if line.strip():  # 非空行
                text_lines.append(line)

        if not text_lines:
            return block  # 没有文本，返回原样

        # 合并文本行进行翻译（Google 翻译可以处理多行）
        text_to_translate = "\n".join(text_lines)

        # 再次检查取消状态（在调用阻塞的 translate 之前）
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or "用户取消"
            raise TaskCancelledError(reason)

        try:
            from core.logger import translate_log

            # 语言标准化（不再每块都输出 debug 日志）
            actual_source_lang = self._normalize_lang_code(
                self._language_name_to_code(source_lang)
            )
            actual_target_lang = self._language_name_to_code(target_lang)
            if actual_target_lang.lower() in ["zh-cn", "zh_cn", "zh", "chinese"]:
                actual_target_lang = "zh-CN"
            elif actual_target_lang.lower() in ["zh-tw", "zh_tw"]:
                actual_target_lang = "zh-TW"
            else:
                actual_target_lang = self._normalize_lang_code(actual_target_lang)

            translator = GoogleTranslator(
                source=actual_source_lang, target=actual_target_lang
            )
            # 注意：translator.translate() 是阻塞调用，无法在调用期间中断
            translated_text = translator.translate(text_to_translate)

            # 检查翻译结果是否与原文相同
            if translated_text == text_to_translate:
                logger.warning_i18n(
                    "log.google_translate_returned_same_text",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    preview=text_to_translate[:100],
                )
                # 即使翻译失败（返回原文），也继续使用翻译结果（可能是同语言翻译或其他原因）

            # 将翻译结果按行分割（如果原文本是多行）
            if "\n" in translated_text:
                translated_lines = translated_text.split("\n")
            else:
                # 单行翻译结果，尝试保持原行数结构（如果原文是多行）
                # 使用原始文本（去除说明后的）来判断
                if "\n" in text_to_translate:
                    # 原文是多行，但翻译结果是单行，保持原行数
                    original_lines = text_to_translate.split("\n")
                    translated_lines = [
                        translated_text if i == 0 else ""
                        for i in range(len(original_lines))
                    ]
                else:
                    # 原文是单行，翻译结果也是单行
                    translated_lines = [translated_text]

            # 添加翻译后的文本行
            # 如果翻译结果的行数与原文不一致，尽量保持原行数结构
            if len(translated_lines) != len(text_lines):
                logger.debug_i18n(
                    "log.google_translate_line_mismatch",
                    source_lines=len(text_lines),
                    target_lines=len(translated_lines),
                )
                # 如果翻译结果是单行但原文是多行，将单行结果作为所有行的内容
                if len(translated_lines) == 1 and len(text_lines) > 1:
                    # 将单行翻译结果分配给所有行
                    for i, orig_line in enumerate(text_lines):
                        if i == 0:
                            result.append(translated_lines[0])
                        else:
                            result.append("")  # 其他行保持空行
                else:
                    # 其他情况，直接使用翻译结果（可能行数不一致）
                    result.extend(translated_lines)
            else:
                # 行数一致，直接添加
                result.extend(translated_lines)

        except TaskCancelledError:
            # 取消操作，直接重新抛出
            raise
        except Exception as e:
            # 翻译失败，返回原文（但保留序号和时间轴）
            logger.error_i18n(
                "log.google_translate_failed_fallback",
                error=str(e),
                source_lang=source_lang,
                target_lang=target_lang,
                text_length=len(text_to_translate),
            )
            # 保留序号和时间轴，使用原文文本
            result.extend(text_lines)

        return result
