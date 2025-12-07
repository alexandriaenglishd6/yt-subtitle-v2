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
    """AI 配置"""
    provider: str = "openai"  # openai, anthropic, 等
    model: str = "gpt-4o-mini"  # 模型名称
    api_key_env: str = "YTSUB_API_KEY"  # API Key 环境变量名
    
    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key_env": self.api_key_env,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AIConfig":
        return cls(
            provider=data.get("provider", "openai"),
            model=data.get("model", "gpt-4o-mini"),
            api_key_env=data.get("api_key_env", "YTSUB_API_KEY"),
        )


@dataclass
class AppConfig:
    """应用配置模型
    
    所有可持久化配置的统一入口
    """
    language: LanguageConfig = field(default_factory=LanguageConfig)
    concurrency: int = 3  # 并发数，默认 3
    proxies: list[str] = field(default_factory=list)  # 代理列表
    cookie: str = ""  # Cookie 字符串
    output_dir: str = "out"  # 输出目录（相对路径）
    ai: AIConfig = field(default_factory=AIConfig)
    
    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "language": self.language.to_dict(),
            "concurrency": self.concurrency,
            "proxies": self.proxies,
            "cookie": self.cookie,
            "output_dir": self.output_dir,
            "ai": self.ai.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建（用于 JSON 反序列化）"""
        return cls(
            language=LanguageConfig.from_dict(data.get("language", {})),
            concurrency=data.get("concurrency", 3),
            proxies=data.get("proxies", []),
            cookie=data.get("cookie", ""),
            output_dir=data.get("output_dir", "out"),
            ai=AIConfig.from_dict(data.get("ai", {})),
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
