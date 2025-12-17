"""
业务逻辑模块
处理视频检测、下载、翻译、摘要等核心业务逻辑
"""
from typing import Optional
from pathlib import Path

from core.logger import get_logger
from core.fetcher import VideoFetcher
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.proxy_manager import ProxyManager
from core.cookie_manager import CookieManager
from core.ai_providers import create_llm_client
from core.llm_client import LLMException
from core.cancel_token import CancelToken
from config.manager import ConfigManager
from ui.i18n_manager import t

# 导入 mixin 模块
from .video_fetcher import VideoFetcherMixin
from .subtitle_detector import SubtitleDetectorMixin
from .task_runner import TaskRunnerMixin
from .processing_pipeline import ProcessingPipelineMixin

logger = get_logger()


class VideoProcessor(VideoFetcherMixin, SubtitleDetectorMixin, TaskRunnerMixin, ProcessingPipelineMixin):
    """视频处理器
    
    封装视频检测、处理等业务逻辑
    """
    
    def __init__(self, config_manager: ConfigManager, app_config):
        self.config_manager = config_manager
        self.app_config = app_config
        # 初始化取消令牌（初始为 None，任务开始时创建）
        self.cancel_token: Optional[CancelToken] = None
        self._init_components()
    
    def _init_components(self):
        """初始化核心组件"""
        # 初始化代理管理器
        if self.app_config.proxies:
            self.proxy_manager = ProxyManager(self.app_config.proxies)
            logger.info(t("proxies_loaded", count=len(self.app_config.proxies)))
        else:
            self.proxy_manager = None
            logger.info(t("no_proxy"))
        
        # 初始化 Cookie 管理器
        if self.app_config.cookie:
            self.cookie_manager = CookieManager(self.app_config.cookie)
            logger.info(t("cookie_loaded"))
        else:
            self.cookie_manager = None
        
        # 初始化 VideoFetcher
        self.video_fetcher = VideoFetcher(
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager
        )
        
        # 初始化 OutputWriter
        output_dir = Path(self.app_config.output_dir)
        self.output_writer = OutputWriter(output_dir)
        
        # 初始化 IncrementalManager
        self.incremental_manager = IncrementalManager()
        
        # 初始化 FailureLogger
        self.failure_logger = FailureLogger(output_dir)
        
        # 初始化翻译 LLMClient（可能失败，允许为 None）
        # 优先使用 AI Profile 配置，如果未配置则使用原有的 translation_ai 配置
        from core.ai_profile_manager import get_profile_manager
        
        profile_manager = get_profile_manager()
        
        self.translation_llm_init_error = None  # 保存初始化失败的原因
        self.translation_llm_init_error_type = None  # 保存初始化失败的错误类型
        
        # 获取翻译 AI 配置（优先使用 Profile）
        translation_ai_config = profile_manager.get_ai_config_for_task(
            "subtitle_translate",
            fallback_config=self.app_config.translation_ai if self.app_config.translation_ai.enabled else None
        )
        
        if translation_ai_config and translation_ai_config.enabled:
            try:
                self.translation_llm_client = create_llm_client(translation_ai_config)
                profile_name = profile_manager.task_mapping.get("subtitle_translate", t("profile_default"))
                logger.info(t("translation_ai_client_init_success", 
                             provider=translation_ai_config.provider, 
                             model=translation_ai_config.model) + f" (Profile: {profile_name})")
            except LLMException as e:
                # 翻译异常消息
                error_msg = str(e)
                # 如果异常消息看起来像翻译键，尝试翻译
                if error_msg.startswith("exception."):
                    from core.logger import translate_exception
                    # 尝试解析翻译键和参数
                    if ":" in error_msg:
                        key_part = error_msg.split(":")[0]
                        # 简单解析参数（格式：key:param1=value1,param2=value2）
                        params = {}
                        if ":" in error_msg:
                            param_str = error_msg.split(":", 1)[1]
                            for param in param_str.split(","):
                                if "=" in param:
                                    k, v = param.split("=", 1)
                                    params[k.strip()] = v.strip()
                        error_msg = translate_exception(key_part, **params)
                    else:
                        error_msg = translate_exception(error_msg)
                logger.warning(t("translation_ai_client_init_failed", error=error_msg))
                self.translation_llm_client = None
                # 保存初始化失败的原因和错误类型（用于后续提示和错误分类）
                self.translation_llm_init_error = str(e)
                # 将 LLMErrorType 映射为 ErrorType
                from core.exceptions import ErrorType, map_llm_error_to_app_error
                self.translation_llm_init_error_type = map_llm_error_to_app_error(e.error_type.value)
        else:
            logger.info(t("translation_ai_disabled"))
            self.translation_llm_client = None
            self.translation_llm_init_error = "翻译 AI 未启用"
            self.translation_llm_init_error_type = None
        
        # 初始化摘要 LLMClient（可能失败，允许为 None）
        # 优先使用 AI Profile 配置，如果未配置则使用原有的 summary_ai 配置
        summary_ai_config = profile_manager.get_ai_config_for_task(
            "subtitle_summarize",
            fallback_config=self.app_config.summary_ai if self.app_config.summary_ai.enabled else None
        )
        
        if summary_ai_config and summary_ai_config.enabled:
            try:
                self.summary_llm_client = create_llm_client(summary_ai_config)
                profile_name = profile_manager.task_mapping.get("subtitle_summarize", t("profile_default"))
                logger.info(t("summary_ai_client_init_success", 
                             provider=summary_ai_config.provider, 
                             model=summary_ai_config.model) + f" (Profile: {profile_name})")
            except LLMException as e:
                # 翻译异常消息
                error_msg = str(e)
                # 如果异常消息看起来像翻译键，尝试翻译
                if error_msg.startswith("exception."):
                    from core.logger import translate_exception
                    # 尝试解析翻译键和参数
                    if ":" in error_msg:
                        key_part = error_msg.split(":")[0]
                        # 简单解析参数（格式：key:param1=value1,param2=value2）
                        params = {}
                        if ":" in error_msg:
                            param_str = error_msg.split(":", 1)[1]
                            for param in param_str.split(","):
                                if "=" in param:
                                    k, v = param.split("=", 1)
                                    params[k.strip()] = v.strip()
                        error_msg = translate_exception(key_part, **params)
                    else:
                        error_msg = translate_exception(error_msg)
                logger.warning(t("summary_ai_client_init_failed", error=error_msg))
                self.summary_llm_client = None
        else:
            logger.info(t("summary_ai_disabled"))
            self.summary_llm_client = None
        
        # 向后兼容：保留 llm_client 属性（指向 translation_llm_client）
        self.llm_client = self.translation_llm_client
