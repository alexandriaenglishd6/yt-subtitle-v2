"""
代理重试工具模块

提供带代理轮换的重试功能，减少 fetcher.py 和 downloader.py 中的重复代码
"""

import time
import random
from typing import Optional, TypeVar, Callable, Set, Any
from functools import wraps

from core.logger import get_logger

logger = get_logger()

T = TypeVar("T")


class ProxyRetryContext:
    """代理重试上下文，跟踪重试状态"""
    
    def __init__(
        self,
        proxy_manager,
        max_retries: int = 3,
        retry_delay_range: tuple = (2.0, 5.0),
        initial_delay_range: tuple = (0.5, 1.5),
    ):
        """
        Args:
            proxy_manager: ProxyManager 实例（可为 None）
            max_retries: 最大重试次数
            retry_delay_range: 重试延迟范围 (min, max) 秒
            initial_delay_range: 首次请求延迟范围 (min, max) 秒
        """
        self.proxy_manager = proxy_manager
        self.max_retries = max_retries
        self.retry_delay_range = retry_delay_range
        self.initial_delay_range = initial_delay_range
        self.tried_proxies: Set[str] = set()
        self.attempt = 0
        self.current_proxy: Optional[str] = None
    
    def get_next_proxy(self, allow_direct: bool = True) -> Optional[str]:
        """获取下一个代理
        
        Returns:
            代理地址，如果没有可用代理则返回 None（表示直连）
        """
        if not self.proxy_manager:
            return None
        
        proxy = self.proxy_manager.get_next_proxy(allow_direct=allow_direct)
        
        if proxy:
            if proxy in self.tried_proxies:
                logger.debug(f"重试代理: {proxy} (尝试 {self.attempt + 1}/{self.max_retries})")
            self.tried_proxies.add(proxy)
        
        self.current_proxy = proxy
        return proxy
    
    def mark_success(self) -> None:
        """标记当前代理成功"""
        if self.current_proxy and self.proxy_manager:
            self.proxy_manager.mark_success(self.current_proxy)
    
    def mark_failure(self, reason: str = "") -> None:
        """标记当前代理失败"""
        if self.current_proxy and self.proxy_manager:
            self.proxy_manager.mark_failure(self.current_proxy, reason[:200])
    
    def should_retry(self) -> bool:
        """是否应该重试"""
        return self.attempt < self.max_retries - 1
    
    def wait_before_request(self) -> None:
        """请求前等待（添加随机延迟避免限流）"""
        if self.attempt > 0:
            delay = random.uniform(*self.retry_delay_range)
            logger.debug(f"等待 {delay:.1f}s 后重试...")
        else:
            delay = random.uniform(*self.initial_delay_range)
        time.sleep(delay)
    
    def next_attempt(self) -> int:
        """进入下一次尝试，返回当前尝试次数"""
        self.attempt += 1
        return self.attempt


def with_proxy_retry(
    max_retries: int = 3,
    retry_on_exceptions: tuple = (Exception,),
    retry_on_status_codes: tuple = (429, 503),
    log_prefix: str = "",
):
    """代理重试装饰器
    
    用于装饰需要代理重试逻辑的函数。被装饰函数必须接受 proxy_manager 参数。
    
    Args:
        max_retries: 最大重试次数
        retry_on_exceptions: 触发重试的异常类型
        retry_on_status_codes: 触发重试的 HTTP 状态码
        log_prefix: 日志前缀
        
    Example:
        @with_proxy_retry(max_retries=3, retry_on_status_codes=(429,))
        def download_file(url: str, proxy_manager=None) -> bytes:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            proxy_manager = kwargs.get("proxy_manager")
            ctx = ProxyRetryContext(proxy_manager, max_retries=max_retries)
            
            last_error = None
            
            for attempt in range(max_retries):
                ctx.attempt = attempt
                proxy = ctx.get_next_proxy()
                
                # 注入代理到 kwargs
                if "proxy" not in kwargs:
                    kwargs["_current_proxy"] = proxy
                
                try:
                    result = func(*args, **kwargs)
                    ctx.mark_success()
                    return result
                except retry_on_exceptions as e:
                    last_error = e
                    ctx.mark_failure(str(e)[:200])
                    
                    if ctx.should_retry():
                        ctx.wait_before_request()
                        if log_prefix:
                            logger.info(f"{log_prefix} 重试 ({attempt + 1}/{max_retries})")
                        continue
                    raise
            
            if last_error:
                raise last_error
            return None  # type: ignore
        
        return wrapper
    return decorator


def retry_with_proxy_rotation(
    func: Callable[..., T],
    proxy_manager,
    max_retries: int = 3,
    is_retryable: Callable[[Exception], bool] = lambda e: True,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    """函数式代理重试工具
    
    适用于不便使用装饰器的场景
    
    Args:
        func: 要执行的函数
        proxy_manager: ProxyManager 实例
        max_retries: 最大重试次数
        is_retryable: 判断异常是否可重试的函数
        on_retry: 重试时的回调 (attempt, exception)
        
    Returns:
        函数执行结果
        
    Raises:
        最后一次尝试的异常
    """
    ctx = ProxyRetryContext(proxy_manager, max_retries=max_retries)
    last_error = None
    
    for attempt in range(max_retries):
        ctx.attempt = attempt
        proxy = ctx.get_next_proxy()
        
        try:
            result = func(proxy)
            ctx.mark_success()
            return result
        except Exception as e:
            last_error = e
            
            if not is_retryable(e):
                raise
            
            ctx.mark_failure(str(e)[:200])
            
            if ctx.should_retry():
                ctx.wait_before_request()
                if on_retry:
                    on_retry(attempt, e)
                continue
            raise
    
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected: no result and no error")
