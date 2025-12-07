"""
统一日志系统
支持文件输出、控制台输出，并为 UI 提供回调接口
"""
import logging
import sys
import io
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime
from threading import Lock
from logging.handlers import RotatingFileHandler

from config.manager import get_user_data_dir

# Windows 控制台编码修复
if sys.platform == "win32":
    try:
        # 尝试设置控制台为 UTF-8 编码（Python 3.7+）
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        # 如果设置失败，忽略（不影响功能）
        pass


class Logger:
    """统一日志管理器
    
    支持：
    - 写入日志文件（用户数据目录 logs/app.log）
    - 控制台输出
    - 日志级别过滤
    - 回调函数（供 UI 使用）
    - 线程安全
    """
    
    # 日志级别映射
    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    def __init__(
        self,
        name: str = "yt-subtitle-v2",
        log_file: Optional[Path] = None,
        level: str = "INFO",
        console_output: bool = True,
        file_output: bool = True,
    ):
        """初始化日志器
        
        Args:
            name: 日志器名称
            log_file: 日志文件路径，如果为 None 则使用默认路径（用户数据目录/logs/app.log）
            level: 日志级别（DEBUG/INFO/WARN/ERROR）
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
        """
        self.name = name
        self.level = self.LEVELS.get(level.upper(), logging.INFO)
        self.console_output = console_output
        self.file_output = file_output
        
        # 回调函数列表（供 UI 使用）
        self._callbacks: List[Callable[[str, str, Optional[str]], None]] = []
        self._callback_lock = Lock()
        
        # 创建标准 logging.Logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level)
        
        # 避免重复添加 handler（如果 logger 已经存在）
        if self.logger.handlers:
            return
        
        # 日志格式：[时间] [级别] [视频ID] 消息
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # 控制台输出
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # 文件输出
        if file_output:
            if log_file is None:
                log_dir = get_user_data_dir() / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "app.log"
            
            # 使用 RotatingFileHandler 自动轮转（最大 10MB，保留 5 个备份）
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(self.level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def add_callback(self, callback: Callable[[str, str, Optional[str]], None]) -> None:
        """添加日志回调函数（供 UI 使用）
        
        Args:
            callback: 回调函数，参数为 (level, message, video_id)
                - level: 日志级别（"INFO", "WARN", "ERROR" 等）
                - message: 日志消息
                - video_id: 视频 ID（可选）
        """
        with self._callback_lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[str, str, Optional[str]], None]) -> None:
        """移除日志回调函数"""
        with self._callback_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def _invoke_callbacks(self, level: str, message: str, video_id: Optional[str] = None) -> None:
        """调用所有回调函数"""
        with self._callback_lock:
            for callback in self._callbacks:
                try:
                    callback(level, message, video_id)
                except Exception:
                    # 回调函数出错不应该影响日志系统
                    pass
    
    def _log_with_video_id(
        self,
        level: int,
        message: str,
        video_id: Optional[str] = None,
        *args,
        **kwargs
    ) -> None:
        """带视频 ID 的日志记录"""
        # 格式化消息
        if video_id:
            formatted_message = f"[{video_id}] {message}"
        else:
            formatted_message = message
        
        # 记录日志
        self.logger.log(level, formatted_message, *args, **kwargs)
        
        # 调用回调函数
        level_name = logging.getLevelName(level)
        self._invoke_callbacks(level_name, message, video_id)
    
    def debug(self, message: str, video_id: Optional[str] = None) -> None:
        """记录 DEBUG 级别日志"""
        self._log_with_video_id(logging.DEBUG, message, video_id)
    
    def info(self, message: str, video_id: Optional[str] = None) -> None:
        """记录 INFO 级别日志"""
        self._log_with_video_id(logging.INFO, message, video_id)
    
    def warning(self, message: str, video_id: Optional[str] = None) -> None:
        """记录 WARNING 级别日志"""
        self._log_with_video_id(logging.WARNING, message, video_id)
    
    def warn(self, message: str, video_id: Optional[str] = None) -> None:
        """记录 WARNING 级别日志（别名）"""
        self.warning(message, video_id)
    
    def error(self, message: str, video_id: Optional[str] = None) -> None:
        """记录 ERROR 级别日志"""
        self._log_with_video_id(logging.ERROR, message, video_id)
    
    def critical(self, message: str, video_id: Optional[str] = None) -> None:
        """记录 CRITICAL 级别日志"""
        self._log_with_video_id(logging.CRITICAL, message, video_id)
    
    def set_level(self, level: str) -> None:
        """设置日志级别"""
        self.level = self.LEVELS.get(level.upper(), logging.INFO)
        self.logger.setLevel(self.level)
        for handler in self.logger.handlers:
            handler.setLevel(self.level)


# 全局 logger 实例（单例模式）
_global_logger: Optional[Logger] = None


def get_logger(
    name: str = "yt-subtitle-v2",
    log_file: Optional[Path] = None,
    level: str = "INFO",
    console_output: bool = True,
    file_output: bool = True,
) -> Logger:
    """获取全局 logger 实例（单例模式）
    
    Args:
        name: 日志器名称
        log_file: 日志文件路径
        level: 日志级别
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
    
    Returns:
        Logger 实例
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = Logger(
            name=name,
            log_file=log_file,
            level=level,
            console_output=console_output,
            file_output=file_output,
        )
    
    return _global_logger


def set_global_logger(logger: Logger) -> None:
    """设置全局 logger 实例（用于测试或自定义配置）"""
    global _global_logger
    _global_logger = logger

