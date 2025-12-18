"""
AI Profile 管理器

负责管理 AI Profile 配置，支持从配置文件加载多个 AI 配置组合，
并根据任务类型选择对应的 profile。
"""

import json
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

from config.manager import AIConfig, get_user_data_dir
from core.logger import get_logger

logger = get_logger()


@dataclass
class AIProfile:
    """AI Profile 配置

    表示一个 AI 配置组合，包含完整的 AIConfig 信息
    """

    name: str  # Profile 名称
    ai_config: AIConfig  # AI 配置
    enabled: bool = True  # 是否启用


class AIProfileManager:
    """AI Profile 管理器

    负责加载、管理和查找 AI Profiles
    """

    def __init__(self, profile_file: Optional[Path] = None):
        """初始化 AI Profile 管理器

        Args:
            profile_file: Profile 配置文件路径，如果为 None 则使用默认路径
        """
        if profile_file is None:
            data_dir = get_user_data_dir()
            self.profile_file = data_dir / "ai_profiles.json"
        else:
            self.profile_file = Path(profile_file)

        self.profiles: Dict[str, AIProfile] = {}
        self.task_mapping: Dict[str, str] = {}
        self._loaded = False

    def load(self) -> bool:
        """加载 Profile 配置文件

        Returns:
            是否成功加载（如果文件不存在，返回 False，但不视为错误）
        """
        if self._loaded:
            return True

        if not self.profile_file.exists():
            logger.debug_i18n("ai_profile_file_not_found", path=str(self.profile_file))
            self._loaded = True
            return False

        try:
            with open(self.profile_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 加载 profiles
            profiles_data = data.get("profiles", {})
            for profile_name, profile_config in profiles_data.items():
                try:
                    # 提取 enabled 字段（如果存在）
                    enabled = profile_config.pop("enabled", True)

                    # 创建 AIConfig
                    ai_config = AIConfig.from_dict(profile_config)

                    # 创建 AIProfile
                    profile = AIProfile(
                        name=profile_name, ai_config=ai_config, enabled=enabled
                    )
                    self.profiles[profile_name] = profile
                    logger.debug_i18n(
                        "log.ai_profile_loaded", profile_name=profile_name
                    )
                except Exception as e:
                    logger.warning_i18n(
                        "log.ai_profile_load_failed",
                        profile_name=profile_name,
                        error=str(e),
                    )

            # 加载 task_mapping
            self.task_mapping = data.get("task_mapping", {})

            logger.info_i18n(
                "log.ai_profile_loaded_summary",
                profile_count=len(self.profiles),
                mapping_count=len(self.task_mapping),
            )
            self._loaded = True
            return True

        except json.JSONDecodeError as e:
            logger.error_i18n("log.ai_profile_config_format_error", error=str(e))
            self._loaded = True
            return False
        except Exception as e:
            logger.error_i18n("log.ai_profile_config_load_failed", error=str(e))
            self._loaded = True
            return False

    def get_profile(self, profile_name: str) -> Optional[AIProfile]:
        """获取指定的 Profile

        Args:
            profile_name: Profile 名称

        Returns:
            AIProfile 对象，如果不存在或未启用则返回 None
        """
        if not self._loaded:
            self.load()

        profile = self.profiles.get(profile_name)
        if not profile:
            return None

        if not profile.enabled:
            logger.debug_i18n("log.ai_profile_disabled", profile_name=profile_name)
            return None

        return profile

    def get_profile_for_task(self, task_type: str) -> Optional[AIProfile]:
        """根据任务类型获取对应的 Profile

        Args:
            task_type: 任务类型（如 "subtitle_translate", "subtitle_summarize"）

        Returns:
            AIProfile 对象，如果未配置则返回 None
        """
        if not self._loaded:
            self.load()

        # 从 task_mapping 中查找对应的 profile 名称
        profile_name = self.task_mapping.get(task_type)
        if not profile_name:
            return None

        return self.get_profile(profile_name)

    def get_ai_config_for_task(
        self, task_type: str, fallback_config: Optional[AIConfig] = None
    ) -> Optional[AIConfig]:
        """根据任务类型获取对应的 AIConfig

        Args:
            task_type: 任务类型（如 "subtitle_translate", "subtitle_summarize"）
            fallback_config: 如果未找到 profile，返回此配置（用于向后兼容）

        Returns:
            AIConfig 对象，如果未配置且没有 fallback_config 则返回 None
        """
        profile = self.get_profile_for_task(task_type)
        if profile:
            return profile.ai_config

        # 回退到 fallback_config
        if fallback_config:
            return fallback_config

        return None

    def list_profiles(self) -> Dict[str, AIProfile]:
        """列出所有已加载的 Profiles

        Returns:
            Profile 名称到 AIProfile 对象的映射
        """
        if not self._loaded:
            self.load()

        return self.profiles.copy()

    def list_task_mappings(self) -> Dict[str, str]:
        """列出所有任务类型映射

        Returns:
            任务类型到 Profile 名称的映射
        """
        if not self._loaded:
            self.load()

        return self.task_mapping.copy()

    def create_default_profile_file(self) -> bool:
        """创建默认的 Profile 配置文件（如果不存在）

        Returns:
            是否成功创建
        """
        if self.profile_file.exists():
            return False

        try:
            # 确保目录存在
            self.profile_file.parent.mkdir(parents=True, exist_ok=True)

            # 创建默认配置
            default_config = {
                "profiles": {
                    "subtitle_translate_default": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "base_url": None,
                        "timeout_seconds": 30,
                        "max_retries": 2,
                        "max_concurrency": 5,
                        "api_keys": {"openai": "env:YTSUB_API_KEY"},
                        "enabled": True,
                    },
                    "subtitle_summarize_default": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "base_url": None,
                        "timeout_seconds": 60,
                        "max_retries": 2,
                        "max_concurrency": 3,
                        "api_keys": {"openai": "env:YTSUB_API_KEY"},
                        "enabled": True,
                    },
                },
                "task_mapping": {
                    "subtitle_translate": "subtitle_translate_default",
                    "subtitle_summarize": "subtitle_summarize_default",
                },
            }

            with open(self.profile_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)

            logger.info_i18n(
                "log.ai_profile_default_created", path=str(self.profile_file)
            )
            return True

        except Exception as e:
            logger.error_i18n("log.ai_profile_default_create_failed", error=str(e))
            return False


# 全局单例（可选，用于缓存）
_global_profile_manager: Optional[AIProfileManager] = None


def get_profile_manager(profile_file: Optional[Path] = None) -> AIProfileManager:
    """获取全局 AI Profile 管理器实例（单例模式）

    Args:
        profile_file: Profile 配置文件路径，如果为 None 则使用默认路径

    Returns:
        AIProfileManager 实例
    """
    global _global_profile_manager

    if _global_profile_manager is None:
        _global_profile_manager = AIProfileManager(profile_file)
        _global_profile_manager.load()

    return _global_profile_manager
