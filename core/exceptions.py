"""
统一异常定义
符合 error_handling.md 规范的错误处理基础设施
"""
from enum import Enum
from typing import Optional


class ErrorType(str, Enum):
    """统一错误类型枚举
    
    所有模块抛错必须映射到以下类型，与 LLMErrorType 对齐
    """
    NETWORK = "network"  # 网络不可达、DNS 失败、连接重置、超时等
    TIMEOUT = "timeout"  # 显式超时（与 NETWORK 可合并，但建议保留独立可视化）
    RATE_LIMIT = "rate_limit"  # 对方限流（429）、配额耗尽、频率限制
    AUTH = "auth"  # 无效/缺失凭证（API Key、Cookie）
    CONTENT = "content"  # 违规/不可处理内容（YouTube 限制、模型安全策略拦截）
    FILE_IO = "file_io"  # 文件系统异常（权限不足、磁盘满、路径非法、原子重命名失败）
    PARSE = "parse"  # 数据结构/字幕解析失败、JSON 解析失败
    INVALID_INPUT = "invalid_input"  # URL 非法、参数不完整、配置错误
    CANCELLED = "cancelled"  # 用户主动取消（CancelToken）
    EXTERNAL_SERVICE = "external_service"  # 第三方服务异常但非网络问题（例如 yt-dlp 返回码）
    UNKNOWN = "unknown"  # 无法归类的其他错误


class AppException(Exception):
    """统一应用异常
    
    所有模块的异常都应该映射为这个类型，包含 error_type 和可选的原始异常
    
    Attributes:
        error_type: 错误类型（ErrorType 枚举）
        cause: 原始异常（可选）
    """
    
    def __init__(
        self,
        message: str,
        *,
        error_type: ErrorType,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.error_type = error_type
        self.cause = cause
    
    def __str__(self) -> str:
        base = f"[{self.error_type.value}] {super().__str__()}"
        if self.cause:
            base += f" (caused by: {type(self.cause).__name__}: {self.cause})"
        return base


class TaskCancelledError(AppException):
    """任务已取消异常
    
    当用户主动取消任务时抛出此异常。
    应该被捕获并记录"任务已取消"日志，然后清理临时资源。
    """
    
    def __init__(self, reason: Optional[str] = None):
        """初始化任务取消异常
        
        Args:
            reason: 取消原因（可选）
        """
        message = f"任务已取消{f'：{reason}' if reason else ''}"
        super().__init__(
            message=message,
            error_type=ErrorType.CANCELLED
        )
        self.reason = reason


class LocalModelError(AppException):
    """本地模型服务未启动异常
    
    当本地模型服务（Ollama/LM Studio）未启动时抛出此异常。
    """
    
    def __init__(self):
        """初始化本地模型错误"""
        super().__init__(
            message="本地模型服务未启动，请先运行 Ollama 或 LM Studio",
            error_type=ErrorType.EXTERNAL_SERVICE
        )


def map_llm_error_to_app_error(llm_error_type: str) -> ErrorType:
    """将 LLMErrorType 映射为 AppException 的 ErrorType
    
    Args:
        llm_error_type: LLM 错误类型字符串（如 "network", "auth" 等）
    
    Returns:
        对应的 ErrorType
    """
    mapping = {
        "network": ErrorType.NETWORK,
        "auth": ErrorType.AUTH,
        "rate_limit": ErrorType.RATE_LIMIT,
        "content": ErrorType.CONTENT,
        "unknown": ErrorType.UNKNOWN,
    }
    return mapping.get(llm_error_type, ErrorType.UNKNOWN)


def should_retry(error_type: ErrorType) -> bool:
    """判断错误类型是否应该重试
    
    根据 error_handling.md 的重试策略表：
    - NETWORK, TIMEOUT, RATE_LIMIT, EXTERNAL_SERVICE, UNKNOWN: 可重试
    - AUTH, CONTENT, PARSE, INVALID_INPUT, CANCELLED: 不重试
    - FILE_IO: 根据具体情况（路径/权限错误不重试，磁盘临时繁忙可重试）
    
    Args:
        error_type: 错误类型
    
    Returns:
        是否应该重试
    """
    # 明确不重试的类型
    no_retry_types = {
        ErrorType.AUTH,
        ErrorType.CONTENT,
        ErrorType.PARSE,
        ErrorType.INVALID_INPUT,
        ErrorType.CANCELLED,
    }
    
    if error_type in no_retry_types:
        return False
    
    # 明确可重试的类型
    retry_types = {
        ErrorType.NETWORK,
        ErrorType.TIMEOUT,
        ErrorType.RATE_LIMIT,
        ErrorType.EXTERNAL_SERVICE,
        ErrorType.UNKNOWN,
    }
    
    if error_type in retry_types:
        return True
    
    # FILE_IO 需要根据具体情况判断（这里返回 False，由调用方根据具体情况决定）
    if error_type == ErrorType.FILE_IO:
        return False
    
    # 默认不重试（安全策略）
    return False

