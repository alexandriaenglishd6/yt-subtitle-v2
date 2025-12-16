"""
TRANSLATE 阶段处理器
"""
from pathlib import Path
from typing import Optional, Callable, Any

from core.logger import get_logger, set_log_context, clear_log_context
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.translator import SubtitleTranslator
from ..data_types import StageData

logger = get_logger()


def _lang_matches(lang1: str, lang2: str) -> bool:
    """检查两个语言代码是否匹配（考虑主语言代码）"""
    if lang1 == lang2:
        return True
    
    # 特殊处理：zh-CN 和 zh-TW 不互相匹配
    lang1_lower = lang1.lower()
    lang2_lower = lang2.lower()
    if (lang1_lower in ["zh-cn", "zh_cn"] and lang2_lower in ["zh-tw", "zh_tw"]) or \
       (lang1_lower in ["zh-tw", "zh_tw"] and lang2_lower in ["zh-cn", "zh_cn"]):
        return False
    
    # 其他语言：提取主语言代码进行匹配
    main1 = lang1.split("-")[0].split("_")[0].lower()
    main2 = lang2.split("-")[0].split("_")[0].lower()
    return main1 == main2


class TranslateProcessor:
    """翻译处理器
    
    负责翻译字幕文件
    """
    
    def __init__(
        self,
        language_config,
        translation_llm: Optional[Any],
        force: bool,
        dry_run: bool,
        cancel_token: Optional[CancelToken],
        translation_llm_init_error_type: Optional[ErrorType] = None,
        translation_llm_init_error: Optional[str] = None,
        on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ):
        """初始化翻译处理器
        
        Args:
            language_config: 语言配置
            translation_llm: 翻译 LLM 客户端（可选）
            force: 是否强制重跑
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
            translation_llm_init_error_type: 翻译 LLM 初始化错误类型
            translation_llm_init_error: 翻译 LLM 初始化错误信息
            on_log: 日志回调
        """
        self.language_config = language_config
        self.translation_llm = translation_llm
        self.force = force
        self.dry_run = dry_run
        self.cancel_token = cancel_token
        self.translation_llm_init_error_type = translation_llm_init_error_type
        self.translation_llm_init_error = translation_llm_init_error
        self.on_log = on_log
    
    def process(self, data: StageData) -> StageData:
        """处理 TRANSLATE 阶段
        
        1. 检查哪些语言有官方字幕，哪些需要翻译
        2. 如果有需要翻译的语言，调用翻译器
        3. 合并翻译结果和官方字幕
        4. 检查是否所有目标语言都有翻译结果
        
        Args:
            data: 阶段数据
            
        Returns:
            处理后的阶段数据
        """
        vid = data.video_info.video_id
        
        try:
            # 设置日志上下文
            if data.run_id:
                set_log_context(run_id=data.run_id, task="translate", video_id=vid)
            
            logger.info(f"翻译字幕: {vid}", video_id=vid)
            
            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            
            # 检查是否有必要的输入数据
            if not data.detection_result:
                raise AppException(
                    message="缺少检测结果",
                    error_type=ErrorType.INVALID_INPUT
                )
            if not data.download_result:
                raise AppException(
                    message="缺少下载结果",
                    error_type=ErrorType.INVALID_INPUT
                )
            
            # 优化：先检查哪些语言有官方字幕，哪些需要翻译
            translation_result = {}
            official_translations = data.download_result.get("official_translations", {})
            needs_translation = []  # 需要翻译的语言列表
            
            # 详细日志：记录下载到的所有官方字幕
            logger.info(
                f"翻译决策：已下载的官方字幕: {list(official_translations.keys())}, 目标语言: {self.language_config.subtitle_target_languages}, 策略: {self.language_config.translation_strategy}",
                video_id=vid
            )
            
            # AI_ONLY 策略特殊处理：即使有官方字幕也要调用 AI 翻译
            if self.language_config.translation_strategy == "AI_ONLY" or self.force:
                # AI_ONLY 模式或强制重译：所有语言都需要翻译（忽略官方字幕）
                needs_translation = self.language_config.subtitle_target_languages.copy()
                if self.language_config.translation_strategy == "AI_ONLY":
                    logger.info(
                        f"翻译策略为 AI_ONLY，所有目标语言都需要 AI 翻译（忽略官方字幕）。需要翻译的语言: {needs_translation}",
                        video_id=vid
                    )
                else:
                    logger.info(
                        f"强制重译模式，所有目标语言都需要重新翻译。需要翻译的语言: {needs_translation}",
                        video_id=vid
                    )
            else:
                # OFFICIAL_ONLY 或 OFFICIAL_AUTO_THEN_AI 策略：优先使用官方字幕
                for target_lang in self.language_config.subtitle_target_languages:
                    # 先尝试精确匹配
                    official_path = official_translations.get(target_lang)
                    
                    # 如果精确匹配失败，尝试模糊匹配（如 en-US 匹配 en）
                    if not official_path or not official_path.exists():
                        for detected_lang, path in official_translations.items():
                            if _lang_matches(detected_lang, target_lang) and path and path.exists():
                                official_path = path
                                logger.debug(
                                    f"目标语言 {target_lang} 通过模糊匹配找到官方字幕（检测到的语言: {detected_lang}）",
                                    video_id=vid
                                )
                                break
                    
                    # 检查是否有官方字幕
                    if official_path and official_path.exists():
                        # 有官方字幕，直接使用
                        translation_result[target_lang] = official_path
                        logger.info(
                            f"目标语言 {target_lang} 使用官方字幕: {official_path.name}",
                            video_id=vid
                        )
                    else:
                        # 没有官方字幕，需要翻译
                        needs_translation.append(target_lang)
                        logger.info(
                            f"目标语言 {target_lang} 无官方字幕，需要 AI 翻译",
                            video_id=vid
                        )
                
                # 如果所有语言都有官方字幕，且策略允许，可以完全跳过翻译步骤
                if not needs_translation:
                    logger.info(
                        f"所有目标语言都有官方字幕，跳过翻译步骤（策略: {self.language_config.translation_strategy}）",
                        video_id=vid
                    )
            
            # 如果有语言需要翻译，进入翻译步骤
            if needs_translation:
                logger.info(
                    f"开始翻译步骤，需要翻译的语言: {needs_translation}",
                    video_id=vid
                )
                if not self.translation_llm:
                    # LLM 不可用
                    needs_ai = (
                        self.language_config.translation_strategy in ["AI_ONLY", "OFFICIAL_AUTO_THEN_AI"]
                    )
                    
                    if needs_ai:
                        # 需要翻译但 LLM 不可用
                        if self.translation_llm_init_error:
                            if self.translation_llm_init_error_type == ErrorType.AUTH:
                                warning_msg = f"翻译 AI 初始化失败（API Key 无效或权限不足）：{self.translation_llm_init_error}，以下语言无法翻译：{', '.join(needs_translation)}"
                            else:
                                warning_msg = f"翻译 AI 初始化失败：{self.translation_llm_init_error}，以下语言无法翻译：{', '.join(needs_translation)}"
                        else:
                            warning_msg = f"翻译 AI 不可用（可能是 API Key 无效或未启用），以下语言无法翻译：{', '.join(needs_translation)}"
                        logger.warning(warning_msg, video_id=vid)
                        if self.on_log:
                            try:
                                self.on_log("WARN", warning_msg, vid)
                            except Exception:
                                pass
                    else:
                        # OFFICIAL_ONLY 策略，但部分语言没有官方字幕
                        logger.warning(f"翻译策略为 OFFICIAL_ONLY，但以下语言无官方字幕：{', '.join(needs_translation)}", video_id=vid)
                else:
                    # LLM 可用，调用翻译
                    logger.info(
                        f"调用翻译器，翻译目标语言: {needs_translation}",
                        video_id=vid
                    )
                    translator = SubtitleTranslator(llm=self.translation_llm, language_config=self.language_config)
                    # 只翻译需要的语言
                    partial_result = translator.translate(
                        data.video_info,
                        data.detection_result,
                        self.language_config,
                        data.download_result,
                        data.temp_dir,
                        force_retranslate=self.force,
                        target_languages=needs_translation,
                        cancel_token=self.cancel_token
                    )
                    logger.info(
                        f"翻译器返回结果: {list(partial_result.keys())}",
                        video_id=vid
                    )
                    # 合并翻译结果（已有官方字幕的保持不变）
                    translation_result.update(partial_result)
                    logger.info(
                        f"合并后的翻译结果: {list(translation_result.keys())}",
                        video_id=vid
                    )
            else:
                logger.info(
                    f"无需翻译，直接使用官方字幕。翻译结果: {list(translation_result.keys())}",
                    video_id=vid
                )
            
            # 检查是否有翻译结果
            has_translation = any(
                path and path.exists()
                for path in translation_result.values()
            )
            
            # 检查是否所有目标语言都有翻译结果
            missing_languages = [
                target_lang
                for target_lang in self.language_config.subtitle_target_languages
                if not translation_result.get(target_lang) or not translation_result[target_lang].exists()
            ]
            
            if missing_languages:
                missing_str = ', '.join(missing_languages)
                if self.language_config.translation_strategy == "OFFICIAL_ONLY":
                    # 如果翻译策略是 OFFICIAL_ONLY 且没有可用翻译，应该停止任务
                    error_msg = (
                        f"翻译策略为'只用官方多语言字幕'，但以下目标语言无可用官方字幕：{missing_str}。\n"
                        f"请修改翻译策略为'优先官方字幕/自动翻译，无则用 AI'，或确保视频有对应的官方字幕。"
                    )
                    logger.error(error_msg, video_id=vid)
                    if self.on_log:
                        try:
                            self.on_log("ERROR", error_msg, vid)
                        except Exception:
                            pass
                    if not self.dry_run:
                        # 失败记录会在 StageQueue._log_failure 中处理
                        data.error_type = ErrorType.CONTENT
                        data.processing_failed = True
                    else:
                        data.skip_reason = f"翻译策略为 OFFICIAL_ONLY，但以下语言无可用官方字幕：{missing_str}（Dry Run）"
                    
                    # 创建异常对象用于失败记录
                    data.error = AppException(message=error_msg, error_type=ErrorType.CONTENT)
                    return data
                else:
                    # 其他策略下，翻译失败不视为整体失败，继续处理
                    logger.warning(f"以下目标语言翻译失败或无可用翻译：{missing_str}", video_id=vid)
                    if not self.dry_run:
                        # 如果有初始化失败的错误类型，使用它；否则使用 UNKNOWN
                        error_type = self.translation_llm_init_error_type if self.translation_llm_init_error_type else ErrorType.UNKNOWN
                        # 构建失败原因
                        if self.translation_llm_init_error:
                            if error_type == ErrorType.AUTH:
                                reason = f"翻译 AI 初始化失败（API Key 无效或权限不足）：{self.translation_llm_init_error}，目标语言翻译失败：{missing_str}"
                            else:
                                reason = f"翻译 AI 初始化失败：{self.translation_llm_init_error}，目标语言翻译失败：{missing_str}"
                        else:
                            reason = f"翻译失败或无可用翻译：{missing_str}"
                        
                        # 失败记录会在 StageQueue._log_failure 中处理
                        # 但这里需要设置错误信息以便记录
                        data.error = AppException(message=reason, error_type=error_type)
                        data.error_type = error_type
                        # 注意：这里不设置 processing_failed = True，因为翻译失败不视为整体失败
            
            # 保存翻译结果
            data.translation_result = translation_result
            
            logger.info(f"翻译完成: {vid}", video_id=vid)
            return data
            
        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or "用户取消"
            logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
            data.error = e
            data.error_type = ErrorType.CANCELLED
            data.error_stage = "translate"
            return data
        except AppException as e:
            # 应用异常
            data.error = e
            data.error_type = e.error_type
            data.error_stage = "translate"
            data.processing_failed = True
            logger.error(f"翻译字幕失败: {vid} - {e}", video_id=vid)
            return data
        except Exception as e:
            # 未知异常
            app_error = AppException(
                message=f"翻译字幕失败: {str(e)}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            data.error = app_error
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "translate"
            data.processing_failed = True
            logger.error(f"翻译字幕异常: {vid} - {e}", video_id=vid)
            import traceback
            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 清理日志上下文
            clear_log_context()

