"""
本地模型专用客户端（Ollama、LM Studio）
- 继承 OpenAICompatibleClient
- 增强：长超时、心跳检测、预热、友好报错
"""
from __future__ import annotations

from typing import Optional
import requests
import threading

from .openai_compatible import OpenAICompatibleClient
from core.exceptions import LocalModelError
from core.logger import get_logger

logger = get_logger()


class LocalModelClient(OpenAICompatibleClient):
    """本地模型专用客户端"""

    MIN_TIMEOUT = 300
    WARMUP_TIMEOUT = 30
    HEALTH_CHECK_TIMEOUT = 5

    def __init__(self, ai_config):
        # 强制使用更长的超时时间
        original_timeout = ai_config.timeout_seconds
        ai_config.timeout_seconds = max(ai_config.timeout_seconds, self.MIN_TIMEOUT)
        if ai_config.timeout_seconds != original_timeout:
            logger.debug_i18n("log.local_model_timeout_adjusted", original_timeout=original_timeout, new_timeout=ai_config.timeout_seconds)

        super().__init__(ai_config)

        self._warmed_up = False
        self._service_checked = False

    def _normalize_base_url(self) -> str:
        """
        规范化 base_url 到 OpenAI 兼容的 /v1 根路径：
        - 允许用户填：http://localhost:11434 或 http://localhost:11434/v1 或 .../v1/
        - 最终统一为：.../v1（不带尾部 /）
        """
        base = (self.ai_config.base_url or "").rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    def _check_service_available(self) -> bool:
        """检查本地模型服务是否可用（心跳）"""
        check_url = f"{self._normalize_base_url()}/models"  # GET /v1/models

        try:
            response = requests.get(check_url, timeout=self.HEALTH_CHECK_TIMEOUT)
            return response.status_code == 200
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.warning_i18n("log.local_model_not_running")
            return False
        except Exception as e:
            logger.debug_i18n("log.local_model_service_check_error", error=str(e))
            return False

    def _warmup(self) -> None:
        """预热本地模型：发送轻量级请求唤醒模型，避免首次正式请求超时"""
        logger.info_i18n("log.local_model_warming_up")

        try:
            original_timeout = self.ai_config.timeout_seconds
            self.ai_config.timeout_seconds = self.WARMUP_TIMEOUT

            super().generate("Hi", max_tokens=5)

            self.ai_config.timeout_seconds = original_timeout
            logger.info_i18n("log.local_model_warmup_complete", model=self.ai_config.model)

        except Exception as e:
            logger.debug_i18n("log.local_model_warmup_failed", error=str(e))

        self._warmed_up = True

    def generate(self, prompt: str, **kwargs):
        """生成文本：首次调用时进行服务检查和预热"""
        if not self._service_checked:
            if not self._check_service_available():
                raise LocalModelError()
            self._service_checked = True

        if not self._warmed_up:
            self._warmup()

        return super().generate(prompt, **kwargs)

