"""
统一日志系统
符合 logging_spec.md 规范的日志系统
支持：文件输出、控制台输出、UI回调、敏感信息脱敏、上下文字段
"""
import logging
import sys
import json
import re
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
from threading import Lock, local
from logging.handlers import RotatingFileHandler

from config.manager import get_user_data_dir
import time

# Windows 控制台编码修复
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


# 线程本地存储，用于存储上下文信息（run_id, task, video_id等）
_context = local()


def set_log_context(
    run_id: Optional[str] = None,
    task: Optional[str] = None,
    video_id: Optional[str] = None,
    **kwargs
) -> None:
    """设置日志上下文（线程本地）
    
    Args:
        run_id: 批次ID（格式：YYYYMMDD_HHMMSS）
        task: 任务阶段（download, translate, summarize, output, dryrun等）
        video_id: 视频ID
        **kwargs: 其他上下文字段（provider, model, latency_ms, tokens, proxy_id, retries, error_type等）
    """
    _context.run_id = run_id
    _context.task = task
    _context.video_id = video_id
    _context.extra_fields = kwargs


def clear_log_context() -> None:
    """清除日志上下文"""
    if hasattr(_context, 'run_id'):
        delattr(_context, 'run_id')
    if hasattr(_context, 'task'):
        delattr(_context, 'task')
    if hasattr(_context, 'video_id'):
        delattr(_context, 'video_id')
    if hasattr(_context, 'extra_fields'):
        delattr(_context, 'extra_fields')


def _sanitize_message(message: str) -> str:
    """脱敏处理：移除敏感信息
    
    严禁出现在日志中的内容：
    - API Key（sk-开头、各种格式）
    - Cookie 原文
    - Authorization 头
    - 账号密码
    
    Args:
        message: 原始消息
    
    Returns:
        脱敏后的消息
    """
    # API Key 模式（sk-开头、各种格式）
    message = re.sub(r'sk-[a-zA-Z0-9]{20,}', 'sk-***REDACTED***', message)
    message = re.sub(r'[a-zA-Z0-9]{32,}', lambda m: '***REDACTED***' if len(m.group()) > 40 else m.group(), message)
    
    # Cookie 模式
    message = re.sub(r'Cookie:\s*[^;]+', 'Cookie: ***REDACTED***', message, flags=re.IGNORECASE)
    message = re.sub(r'cookie\s*=\s*[^;]+', 'cookie=***REDACTED***', message, flags=re.IGNORECASE)
    
    # Authorization 头
    message = re.sub(r'Authorization:\s*[^\s]+', 'Authorization: ***REDACTED***', message, flags=re.IGNORECASE)
    message = re.sub(r'Bearer\s+[a-zA-Z0-9\-_\.]+', 'Bearer ***REDACTED***', message, flags=re.IGNORECASE)
    
    # 截断过长的文本（字幕原文等）
    if len(message) > 500:
        message = message[:500] + '... [truncated]'
    
    return message


class ContextFormatter(logging.Formatter):
    """支持上下文字段的日志格式化器
    
    格式：[时间] [级别] [run:<batch_id>] [task:<stage>] [video:<id>] 消息 [额外字段]
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # 脱敏处理
        if hasattr(record, 'msg'):
            record.msg = _sanitize_message(str(record.msg))
        
        # 构建上下文字段
        context_parts = []
        
        # run_id
        run_id = getattr(_context, 'run_id', None) or getattr(record, 'run_id', None)
        if run_id:
            context_parts.append(f"[run:{run_id}]")
        
        # task
        task = getattr(_context, 'task', None) or getattr(record, 'task', None)
        if task:
            context_parts.append(f"[task:{task}]")
        
        # video_id
        video_id = getattr(_context, 'video_id', None) or getattr(record, 'video_id', None)
        if video_id:
            context_parts.append(f"[video:{video_id}]")
        
        # 额外字段（provider, model, latency_ms, tokens, proxy_id, retries, error_type等）
        extra_fields = getattr(_context, 'extra_fields', {}) or {}
        extra_parts = []
        for key in ['provider', 'model', 'latency_ms', 'tokens', 'proxy_id', 'retries', 'error_type']:
            value = extra_fields.get(key) or getattr(record, key, None)
            if value is not None:
                extra_parts.append(f"{key}={value}")
        
        # 构建完整消息
        context_str = " ".join(context_parts) if context_parts else ""
        extra_str = " " + " ".join(extra_parts) if extra_parts else ""
        
        # 格式化时间戳（到毫秒）
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # 级别（固定宽度）
        level_str = f"{record.levelname:5s}"
        
        # 完整格式：[时间] [级别] [run:...] [task:...] [video:...] 消息 [额外字段]
        formatted = f"[{timestamp}] [{level_str}] {context_str} {record.getMessage()}{extra_str}"
        
        return formatted


class Logger:
    """统一日志管理器
    
    符合 logging_spec.md 规范：
    - 日志格式包含 run/task/video 字段
    - 敏感信息脱敏
    - 统一字段支持
    - 日志轮转（20MB x 5份）
    - 回退策略（目录不可写时回退到控制台）
    """
    
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
        enable_json_events: bool = False,
        cleanup_old_logs: bool = True,
        max_log_age_days: int = 14,
    ):
        """初始化日志器
        
        Args:
            name: 日志器名称
            log_file: 日志文件路径，如果为 None 则使用默认路径
            level: 日志级别（DEBUG/INFO/WARN/ERROR）
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            enable_json_events: 是否启用 JSON 事件输出（用于统计脚本）
            cleanup_old_logs: 是否在初始化时清理过期日志（默认 True）
            max_log_age_days: 日志最大保留天数（默认 14 天）
        """
        self.name = name
        self.level = self.LEVELS.get(level.upper(), logging.INFO)
        self.console_output = console_output
        self.file_output = file_output
        self.enable_json_events = enable_json_events
        
        # 回调函数列表（供 UI 使用）
        self._callbacks: List[Callable[[str, str, Optional[str]], None]] = []
        self._callback_lock = Lock()
        
        # 创建标准 logging.Logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level)
        
        # 避免重复添加 handler（如果 logger 已经存在）
        if self.logger.handlers:
            return
        
        # 清理过期日志（在创建 handler 之前）
        if cleanup_old_logs and file_output:
            try:
                log_dir = log_file.parent if log_file else get_user_data_dir() / "logs"
                cleaned_count = cleanup_old_logs(log_dir, max_log_age_days)
                if cleaned_count > 0:
                    # 使用标准 logging 记录清理信息（此时还没有自定义 logger）
                    temp_logger = logging.getLogger(f"{name}.cleanup")
                    temp_logger.info(f"已清理 {cleaned_count} 个过期日志文件（超过 {max_log_age_days} 天）")
            except Exception:
                # 清理失败不影响日志系统初始化
                pass
        
        # 创建格式化器
        formatter = ContextFormatter()
        
        # 控制台输出
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # 文件输出（带回退策略）
        if file_output:
            file_handler = self._create_file_handler(log_file, formatter)
            if file_handler:
                self.logger.addHandler(file_handler)
            else:
                # 如果文件 handler 创建失败，回退到控制台
                if not console_output:
                    console_handler = logging.StreamHandler(sys.stdout)
                    console_handler.setLevel(self.level)
                    console_handler.setFormatter(formatter)
                    self.logger.addHandler(console_handler)
                self.logger.critical("日志目录不可写，已回退到控制台输出")
    
    def _create_file_handler(
        self,
        log_file: Optional[Path],
        formatter: logging.Formatter
    ) -> Optional[RotatingFileHandler]:
        """创建文件 handler（带错误处理）
        
        Args:
            log_file: 日志文件路径
            formatter: 格式化器
        
        Returns:
            RotatingFileHandler 实例，如果创建失败则返回 None
        """
        try:
            if log_file is None:
                log_dir = get_user_data_dir() / "logs"
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except (OSError, PermissionError) as e:
                    # 目录创建失败，回退到控制台
                    return None
                log_file = log_dir / "app.log"
            
            # 使用 RotatingFileHandler 自动轮转（最大 20MB，保留 5 个备份）
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=20 * 1024 * 1024,  # 20MB（符合 logging_spec.md）
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(self.level)
            file_handler.setFormatter(formatter)
            return file_handler
        except (OSError, PermissionError, IOError):
            # 文件创建失败，返回 None（由调用方处理回退）
            return None
    
    def add_callback(self, callback: Callable[[str, str, Optional[str]], None]) -> None:
        """添加日志回调函数（供 UI 使用）
        
        Args:
            callback: 回调函数，参数为 (level, message, video_id)
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
                    pass
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        video_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """带上下文的日志记录
        
        Args:
            level: 日志级别
            message: 日志消息（会自动脱敏）
            video_id: 视频ID（可选，会覆盖上下文中的video_id）
            **kwargs: 额外字段（provider, model, latency_ms, tokens, proxy_id, retries, error_type等）
        """
        # 脱敏处理
        sanitized_message = _sanitize_message(message)
        
        # 获取当前上下文
        run_id = getattr(_context, 'run_id', None)
        task = getattr(_context, 'task', None)
        ctx_video_id = getattr(_context, 'video_id', None)
        extra_fields = getattr(_context, 'extra_fields', {}) or {}
        
        # video_id 优先级：参数 > 上下文
        final_video_id = video_id or ctx_video_id
        
        # 合并额外字段
        merged_extra = {**extra_fields, **kwargs}
        
        # 创建 LogRecord（注入上下文信息）
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "",  # filename
            0,   # lineno
            sanitized_message,
            (),  # args
            None,  # exc_info
            func="",
            extra={
                'run_id': run_id,
                'task': task,
                'video_id': final_video_id,
                **merged_extra
            }
        )
        
        # 记录日志
        self.logger.handle(record)
        
        # 输出 JSON 事件（如果启用）
        if self.enable_json_events and level >= logging.INFO:
            self._emit_json_event(level, run_id, task, final_video_id, sanitized_message, merged_extra)
        
        # 调用回调函数
        level_name = logging.getLevelName(level)
        self._invoke_callbacks(level_name, sanitized_message, final_video_id)
    
    def _emit_json_event(
        self,
        level: int,
        run_id: Optional[str],
        task: Optional[str],
        video_id: Optional[str],
        message: str,
        extra: Dict[str, Any]
    ) -> None:
        """输出 JSON 事件（用于统计脚本）
        
        格式：{"ts":"...", "level":"INFO", "event":"...", "run":"...", "video":"...", ...}
        """
        try:
            event_data = {
                "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": logging.getLevelName(level),
                "message": message[:200],  # 截断长消息
            }
            
            if run_id:
                event_data["run"] = run_id
            if task:
                event_data["task"] = task
            if video_id:
                event_data["video"] = video_id
            
            # 添加额外字段
            for key in ['provider', 'model', 'latency_ms', 'tokens', 'proxy_id', 'retries', 'error_type']:
                if key in extra and extra[key] is not None:
                    event_data[key] = extra[key]
            
            # 输出 JSON 行（追加到日志文件，或单独的文件）
            json_line = json.dumps(event_data, ensure_ascii=False)
            # 注意：这里只是示例，实际可以输出到单独的文件或通过特殊 handler
            # 当前实现：在日志消息后追加 JSON 行（如果启用）
            pass  # 暂时不实现，避免日志文件过大
        except Exception:
            pass  # JSON 输出失败不影响主日志
    
    def debug(self, message: str, video_id: Optional[str] = None, **kwargs) -> None:
        """记录 DEBUG 级别日志"""
        self._log_with_context(logging.DEBUG, message, video_id, **kwargs)
    
    def info(self, message: str, video_id: Optional[str] = None, **kwargs) -> None:
        """记录 INFO 级别日志"""
        self._log_with_context(logging.INFO, message, video_id, **kwargs)
    
    def warning(self, message: str, video_id: Optional[str] = None, **kwargs) -> None:
        """记录 WARNING 级别日志"""
        self._log_with_context(logging.WARNING, message, video_id, **kwargs)
    
    def warn(self, message: str, video_id: Optional[str] = None, **kwargs) -> None:
        """记录 WARNING 级别日志（别名）"""
        self.warning(message, video_id, **kwargs)
    
    def error(self, message: str, video_id: Optional[str] = None, **kwargs) -> None:
        """记录 ERROR 级别日志"""
        self._log_with_context(logging.ERROR, message, video_id, **kwargs)
    
    def critical(self, message: str, video_id: Optional[str] = None, **kwargs) -> None:
        """记录 CRITICAL 级别日志"""
        self._log_with_context(logging.CRITICAL, message, video_id, **kwargs)
    
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
    enable_json_events: bool = False,
    cleanup_old_logs: bool = True,
    max_log_age_days: int = 14,
) -> Logger:
    """获取全局 logger 实例（单例模式）
    
    Args:
        name: 日志器名称
        log_file: 日志文件路径
        level: 日志级别
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        enable_json_events: 是否启用 JSON 事件输出
        cleanup_old_logs: 是否在初始化时清理过期日志（默认 True）
        max_log_age_days: 日志最大保留天数（默认 14 天）
    
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
            enable_json_events=enable_json_events,
            cleanup_old_logs=cleanup_old_logs,
            max_log_age_days=max_log_age_days,
        )
    
    return _global_logger


def set_global_logger(logger: Logger) -> None:
    """设置全局 logger 实例（用于测试或自定义配置）"""
    global _global_logger
    _global_logger = logger


def cleanup_old_logs(log_dir: Optional[Path] = None, max_age_days: int = 14) -> int:
    """清理过期的日志文件
    
    根据 logging_spec.md 规范：启动时清理超过 N 天（默认 14 天）的日志
    
    Args:
        log_dir: 日志目录路径，如果为 None 则使用默认路径
        max_age_days: 最大保留天数（默认 14 天）
    
    Returns:
        清理的文件数量
    """
    if log_dir is None:
        log_dir = get_user_data_dir() / "logs"
    
    if not log_dir.exists():
        return 0
    
    try:
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        cleaned_count = 0
        
        # 遍历日志目录中的所有文件
        for log_file in log_dir.iterdir():
            if not log_file.is_file():
                continue
            
            # 检查文件是否匹配日志文件模式（app.log, app.log.1, app.log.2 等）
            if log_file.name.startswith("app.log"):
                try:
                    # 获取文件修改时间
                    file_mtime = log_file.stat().st_mtime
                    age_seconds = current_time - file_mtime
                    
                    # 如果文件超过最大保留天数，删除它
                    if age_seconds > max_age_seconds:
                        log_file.unlink()
                        cleaned_count += 1
                except (OSError, PermissionError) as e:
                    # 忽略无法删除的文件（可能被其他进程占用）
                    pass
        
        return cleaned_count
    except (OSError, PermissionError):
        # 日志目录不可访问，返回 0
        return 0
