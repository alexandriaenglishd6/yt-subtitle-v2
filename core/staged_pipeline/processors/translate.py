"""
TRANSLATE 阶段处理器
"""
from pathlib import Path
from typing import Optional, Callable, Any

from core.logger import get_logger, set_log_context, clear_log_context, translate_log
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
            
            logger.info_i18n("translating_subtitle", video_id=vid)
            
            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or translate_log("user_cancelled")
                raise TaskCancelledError(reason)
            
            # 检查是否有必要的输入数据
            if not data.detection_result:
                raise AppException(
                    message=translate_log("missing_detection_result"),
                    error_type=ErrorType.INVALID_INPUT
                )
            if not data.download_result:
                raise AppException(
                    message=translate_log("missing_download_result"),
                    error_type=ErrorType.INVALID_INPUT
                )
            
            # 优化：先检查哪些语言有官方字幕，哪些需要翻译
            translation_result = {}
            official_translations = data.download_result.get("official_translations", {})
            needs_translation = []  # 需要翻译的语言列表
            
            # 详细日志：记录下载到的所有官方字幕
            logger.info_i18n(
                "translation_decision",
                official_langs=list(official_translations.keys()),
                target_langs=self.language_config.subtitle_target_languages,
                strategy=self.language_config.translation_strategy,
                video_id=vid
            )
            
            # AI_ONLY 策略特殊处理：即使有官方字幕也要调用 AI 翻译
            if self.language_config.translation_strategy == "AI_ONLY" or self.force:
                # AI_ONLY 模式或强制重译：所有语言都需要翻译（忽略官方字幕）
                needs_translation = self.language_config.subtitle_target_languages.copy()
                if self.language_config.translation_strategy == "AI_ONLY":
                    logger.info_i18n("translation_strategy_ai_only", languages=needs_translation, video_id=vid)
                else:
                    logger.info_i18n("force_retranslate_mode", languages=needs_translation, video_id=vid)
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
                                logger.debug_i18n("target_lang_fuzzy_match", target_lang=target_lang, detected_lang=detected_lang, video_id=vid)
                                break
                    
                    # 检查是否有官方字幕
                    if official_path and official_path.exists():
                        # 有官方字幕，直接使用
                        translation_result[target_lang] = official_path
                        logger.info_i18n("target_lang_using_official", target_lang=target_lang, file_name=official_path.name, video_id=vid)
                    else:
                        # 没有官方字幕，需要翻译
                        needs_translation.append(target_lang)
                        logger.info_i18n("target_lang_no_official_need_ai", target_lang=target_lang, video_id=vid)
                
                # 如果所有语言都有官方字幕，且策略允许，可以完全跳过翻译步骤
                if not needs_translation:
                    logger.info_i18n("all_target_langs_have_official", strategy=self.language_config.translation_strategy, video_id=vid)
            
            # 如果有语言需要翻译，进入翻译步骤
            if needs_translation:
                logger.info_i18n("translation_step_start", languages=needs_translation, video_id=vid)
                if not self.translation_llm:
                    # LLM 不可用
                    needs_ai = (
                        self.language_config.translation_strategy in ["AI_ONLY", "OFFICIAL_AUTO_THEN_AI"]
                    )
                    
                    if needs_ai:
                        # 需要翻译但 LLM 不可用
                        if self.translation_llm_init_error:
                            if self.translation_llm_init_error_type == ErrorType.AUTH:
                                warning_msg = translate_log("translation_ai_init_failed_auth", error=self.translation_llm_init_error, languages=', '.join(needs_translation))
                            else:
                                warning_msg = translate_log("translation_ai_init_failed_generic", error=self.translation_llm_init_error, languages=', '.join(needs_translation))
                        else:
                            warning_msg = translate_log("translation_ai_unavailable", languages=', '.join(needs_translation))
                        logger.warning(warning_msg, video_id=vid)
                        if self.on_log:
                            try:
                                self.on_log("WARN", warning_msg, vid)
                            except Exception:
                                pass
                    else:
                        # OFFICIAL_ONLY 策略，但部分语言没有官方字幕
                        logger.warning_i18n("translation_strategy_official_only_no_subtitle", languages=', '.join(needs_translation), video_id=vid)
                else:
                    # LLM 可用，调用翻译
                    logger.info_i18n("calling_translator", languages=needs_translation, video_id=vid)
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
                        translate_log("translator_result", languages=list(partial_result.keys())),
                        video_id=vid
                    )
                    # 合并翻译结果（已有官方字幕的保持不变）
                    translation_result.update(partial_result)
                    logger.info(
                        translate_log("translation_merged", languages=list(translation_result.keys())),
                        video_id=vid
                    )
            else:
                logger.info_i18n("no_translation_needed_official", languages=list(translation_result.keys()), video_id=vid)
            
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
                    error_msg = translate_log("translation_strategy_official_only_missing", languages=missing_str)
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
                        data.skip_reason = translate_log("translation_strategy_official_only_missing", languages=missing_str) + " (Dry Run)"
                    
                    # 创建异常对象用于失败记录
                    data.error = AppException(message=error_msg, error_type=ErrorType.CONTENT)
                    return data
                else:
                    # 其他策略下，翻译失败不视为整体失败，继续处理
                    logger.warning_i18n("translation_missing_languages", languages=missing_str, video_id=vid)
                    if not self.dry_run:
                        # 如果有初始化失败的错误类型，使用它；否则使用 UNKNOWN
                        error_type = self.translation_llm_init_error_type if self.translation_llm_init_error_type else ErrorType.UNKNOWN
                        # 构建失败原因
                        if self.translation_llm_init_error:
                            if error_type == ErrorType.AUTH:
                                reason = translate_log("translation_ai_init_failed_auth_missing", error=self.translation_llm_init_error, languages=missing_str)
                            else:
                                reason = translate_log("translation_ai_init_failed_generic_missing", error=self.translation_llm_init_error, languages=missing_str)
                        else:
                            reason = translate_log("translation_failed_missing", languages=missing_str)
                        
                        # 失败记录会在 StageQueue._log_failure 中处理
                        # 但这里需要设置错误信息以便记录
                        data.error = AppException(message=reason, error_type=error_type)
                        data.error_type = error_type
                        # 注意：这里不设置 processing_failed = True，因为翻译失败不视为整体失败
            
            # 保存翻译结果
            data.translation_result = translation_result
            
            logger.info(translate_log("translation_complete_video", video_id=vid), video_id=vid)
            return data
            
        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or translate_log("user_cancelled")
            logger.info_i18n("task_cancelled", video_id=vid, reason=reason)
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
            logger.error_i18n("translation_failed", video_id=vid, error=str(e))
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
            logger.error_i18n("translation_exception", video_id=vid, error=str(e))
            import traceback
            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 清理日志上下文
            clear_log_context()

