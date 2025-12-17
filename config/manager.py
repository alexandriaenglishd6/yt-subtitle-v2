"""
配置模型 + 读写逻辑（用户目录）
配置管理器
"""
import json
import os
import platform
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from core.language import LanguageConfig


def get_user_data_dir() -> Path:
    """获取用户数据目录路径（跨平台）
    
    根据 v2_final_plan.md 约定：
    - Windows: %APPDATA%/yt-subtitle-v2/
    - Linux: ~/.config/yt-subtitle-v2/
    - macOS: ~/Library/Application Support/yt-subtitle-v2/
    
    Returns:
        用户数据目录的 Path 对象
    """
    system = platform.system()
    
    if system == "Windows":
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":  # macOS
        base_dir = Path.home() / "Library" / "Application Support"
    else:  # Linux 和其他 Unix-like
        base_dir = Path.home() / ".config"
    
    data_dir = base_dir / "yt-subtitle-v2"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    return data_dir


@dataclass
class AIConfig:
    """AI 配置
    
    符合 ai_design.md 规范的配置结构
    """
    enabled: bool = True  # 是否启用此 AI 功能
    provider: str = "openai"  # openai, anthropic, gemini, groq, local 等
    model: str = "gpt-4o-mini"  # 模型名称
    base_url: Optional[str] = None  # 可选，自定义 API 网关或代理
    timeout_seconds: int = 30  # 超时时间（秒）
    max_retries: int = 2  # 最大重试次数
    max_concurrency: int = 5  # 最大并发数（用于内部限流）
    api_keys: dict[str, str] = field(default_factory=lambda: {
        "openai": "env:YTSUB_API_KEY",
        "anthropic": "env:YTSUB_API_KEY"
    })  # API Key 字典，格式如 {"openai": "env:OPENAI_API_KEY"}
    
    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_concurrency": self.max_concurrency,
            "api_keys": self.api_keys,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AIConfig":
        # 向后兼容：如果存在旧的 api_key_env，转换为 api_keys
        api_keys = data.get("api_keys")
        if not api_keys and "api_key_env" in data:
            api_key_env = data["api_key_env"]
            api_keys = {
                "openai": f"env:{api_key_env}",
                "anthropic": f"env:{api_key_env}"
            }
        
        # 处理 base_url：如果为 None 或空字符串，保持为 None（表示使用官方 API）
        base_url = data.get("base_url")
        if base_url == "":
            base_url = None
        
        return cls(
            enabled=data.get("enabled", True),  # 默认启用，向后兼容
            provider=data.get("provider", "openai"),
            model=data.get("model", "gpt-4o-mini"),
            base_url=base_url,
            timeout_seconds=data.get("timeout_seconds", 30),
            max_retries=data.get("max_retries", 2),
            max_concurrency=data.get("max_concurrency", 5),  # 默认 5
            api_keys=api_keys,
        )


@dataclass
class AppConfig:
    """应用配置模型
    
    所有可持久化配置的统一入口
    """
    language: LanguageConfig = field(default_factory=LanguageConfig)
    concurrency: int = 10  # 下载并发数，默认 10
    retry_count: int = 2  # 重试次数，默认 2（用于网络错误、限流等可重试错误）
    proxies: list[str] = field(default_factory=list)  # 代理列表
    cookie: str = ""  # Cookie 字符串
    network_region: Optional[str] = None  # 网络地区（从 Cookie 测试中检测，格式如 "US", "CN" 等）
    output_dir: str = "out"  # 输出目录（相对路径）
    translation_ai: AIConfig = field(default_factory=AIConfig)  # 翻译 AI 配置
    summary_ai: AIConfig = field(default_factory=AIConfig)  # 摘要 AI 配置
    # 保留 ai 字段用于向后兼容（已废弃，将在未来版本移除）
    ai: Optional[AIConfig] = None
    ui_language: str = "zh-CN"  # UI 语言（zh-CN / en-US）
    theme: str = "light"  # UI 主题（light / light_gray / dark_gray / claude_warm）
    force_rerun: bool = False  # 强制重跑选项（忽略历史记录）
    
    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        result = {
            "language": self.language.to_dict(),
            "concurrency": self.concurrency,
            "retry_count": self.retry_count,
            "proxies": self.proxies,
            "cookie": self.cookie,
            "network_region": self.network_region,
            "output_dir": self.output_dir,
            "translation_ai": self.translation_ai.to_dict(),
            "summary_ai": self.summary_ai.to_dict(),
            "ui_language": self.ui_language,
            "theme": self.theme,
            "force_rerun": self.force_rerun,
        }
        # 向后兼容：如果 ai 字段存在，也保存（用于旧版本兼容）
        if self.ai is not None:
            result["ai"] = self.ai.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建（用于 JSON 反序列化）
        
        向后兼容：如果存在旧的 ai 配置，将其复制到 translation_ai 和 summary_ai
        """
        # 向后兼容：处理旧的 ai 配置
        old_ai = data.get("ai")
        translation_ai_data = data.get("translation_ai")
        summary_ai_data = data.get("summary_ai")
        
        # 如果存在旧的 ai 配置，且没有新的 translation_ai/summary_ai，则迁移
        if old_ai and not translation_ai_data and not summary_ai_data:
            # 将旧的 ai 配置复制到 translation_ai 和 summary_ai
            translation_ai_data = old_ai
            summary_ai_data = old_ai
        
        # 如果只有 translation_ai 或 summary_ai，另一个使用默认值
        if translation_ai_data and not summary_ai_data:
            summary_ai_data = AIConfig.from_dict({}).to_dict()
        elif summary_ai_data and not translation_ai_data:
            translation_ai_data = AIConfig.from_dict({}).to_dict()
        
        return cls(
            language=LanguageConfig.from_dict(data.get("language", {})),
            concurrency=data.get("concurrency", 10),  # 默认下载并发数 10
            retry_count=data.get("retry_count", 2),
            proxies=data.get("proxies", []),
            cookie=data.get("cookie", ""),
            network_region=data.get("network_region"),  # 可选字段，默认为 None
            output_dir=data.get("output_dir", "out"),
            translation_ai=AIConfig.from_dict(translation_ai_data or {}),
            summary_ai=AIConfig.from_dict(summary_ai_data or {}),
            ai=AIConfig.from_dict(old_ai) if old_ai else None,  # 保留用于向后兼容
            ui_language=data.get("ui_language", "zh-CN"),
            theme=data.get("theme", "light"),
            force_rerun=data.get("force_rerun", False),  # 默认 False
        )
    
    @classmethod
    def default(cls) -> "AppConfig":
        """创建默认配置"""
        return cls()


class ConfigManager:
    """配置管理器
    
    负责在用户数据目录读写 config.json
    """
    
    def __init__(self, config_file: Optional[Path] = None):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径，如果为 None 则使用默认路径
        """
        if config_file is None:
            self.data_dir = get_user_data_dir()
            self.config_file = self.data_dir / "config.json"
        else:
            self.config_file = Path(config_file)
            self.data_dir = self.config_file.parent
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 确保 archives 和 logs 目录存在
        (self.data_dir / "archives").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
    
    def load(self) -> AppConfig:
        """加载配置
        
        Returns:
            AppConfig 对象，如果文件不存在则返回默认配置
        """
        if not self.config_file.exists():
            # 文件不存在，返回默认配置并保存
            config = AppConfig.default()
            self.save(config)
            return config
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # 配置文件损坏，使用默认配置并备份旧文件
            backup_file = self.config_file.with_suffix(".json.bak")
            if self.config_file.exists():
                self.config_file.rename(backup_file)
            config = AppConfig.default()
            self.save(config)
            return config
    
    def save(self, config: AppConfig) -> None:
        """保存配置
        
        Args:
            config: 要保存的配置对象
        """
        try:
            # 先写入临时文件，再重命名（原子操作）
            temp_file = self.config_file.with_suffix(".json.tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            temp_file.replace(self.config_file)
        except Exception as e:
            # 保存失败，但不抛出异常（避免影响主流程）
            # 实际项目中可以记录日志
            pass
    
    def get_archives_dir(self) -> Path:
        """获取增量记录目录
        
        Returns:
            archives 目录的 Path 对象
        """
        return self.data_dir / "archives"
    
    def get_logs_dir(self) -> Path:
        """获取日志目录
        
        Returns:
            logs 目录的 Path 对象
        """
        return self.data_dir / "logs"
