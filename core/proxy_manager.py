"""
代理管理器模块
实现多代理列表管理、round-robin 轮询、简单健康检查
"""
import time
import threading
import re
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

from core.logger import get_logger

logger = get_logger()


@dataclass
class ProxyStatus:
    """代理状态信息"""
    proxy: str
    consecutive_failures: int = 0  # 连续失败次数
    last_error: Optional[str] = None  # 最后错误原因
    last_success_time: Optional[datetime] = None  # 最后成功时间
    marked_unhealthy_time: Optional[datetime] = None  # 标记为不健康的时间
    is_unhealthy: bool = False  # 是否标记为不健康
    
    def mark_success(self):
        """标记成功"""
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        self.is_unhealthy = False
        self.marked_unhealthy_time = None
        self.last_error = None
    
    def mark_failure(self, error: Optional[str] = None, failure_threshold: int = 3):
        """标记失败
        
        Args:
            error: 错误原因
            failure_threshold: 失败阈值（连续失败超过此值标记为不健康）
        """
        self.consecutive_failures += 1
        self.last_error = error
        
        if self.consecutive_failures >= failure_threshold and not self.is_unhealthy:
            self.is_unhealthy = True
            self.marked_unhealthy_time = datetime.now()
            logger.warning(f"代理标记为不健康: {self.proxy} (连续失败 {self.consecutive_failures} 次)")
    
    def should_retry(self, retry_delay_minutes: int = 10) -> bool:
        """判断是否应该重试（探测恢复）
        
        Args:
            retry_delay_minutes: 重试延迟（分钟）
        
        Returns:
            是否应该尝试恢复
        """
        if not self.is_unhealthy:
            return False
        
        if self.marked_unhealthy_time is None:
            return False
        
        elapsed = datetime.now() - self.marked_unhealthy_time
        return elapsed >= timedelta(minutes=retry_delay_minutes)


class ProxyManager:
    """代理管理器
    
    实现 round-robin 轮询策略和简单健康管理。
    支持多代理列表（数量不锁死），连续失败超过阈值暂时禁用，延迟后重试。
    """
    
    def __init__(
        self,
        proxies: List[str],
        failure_threshold: int = 3,
        retry_delay_minutes: int = 10
    ):
        """初始化代理管理器
        
        Args:
            proxies: 代理列表（格式：http://host:port 或 socks5://host:port）
            failure_threshold: 失败阈值（连续失败超过此值标记为不健康），默认 3
            retry_delay_minutes: 重试延迟（分钟），默认 10
        """
        # 验证并过滤无效代理
        valid_proxies = []
        invalid_proxies = []
        
        for proxy in (proxies or []):
            proxy = proxy.strip()
            if not proxy:
                continue
            
            if self._is_valid_proxy(proxy):
                valid_proxies.append(proxy)
            else:
                invalid_proxies.append(proxy)
                logger.warning(f"无效的代理格式，已跳过: {proxy}")
        
        self.proxies = valid_proxies
        self.failure_threshold = failure_threshold
        self.retry_delay_minutes = retry_delay_minutes
        
        # 初始化代理状态
        self._proxy_statuses: Dict[str, ProxyStatus] = {}
        for proxy in self.proxies:
            self._proxy_statuses[proxy] = ProxyStatus(proxy=proxy)
        
        # round-robin 索引
        self._current_index = 0
        self._lock = threading.Lock()
        
        if invalid_proxies:
            logger.warning(f"已过滤 {len(invalid_proxies)} 个无效代理，保留 {len(self.proxies)} 个有效代理")
        
        if self.proxies:
            logger.info(f"代理管理器初始化: {len(self.proxies)} 个有效代理")
        else:
            if proxies:
                logger.warning("代理管理器初始化: 所有代理都无效，将不使用代理")
            else:
                logger.info("代理管理器初始化: 无代理配置")
    
    def _is_valid_proxy(self, proxy: str) -> bool:
        """验证代理格式是否有效
        
        Args:
            proxy: 代理 URL
            
        Returns:
            如果格式有效则返回 True
        """
        if not proxy:
            return False
        
        try:
            parsed = urlparse(proxy)
            # 检查是否有 scheme（http://, https://, socks5:// 等）
            if not parsed.scheme:
                return False
            
            # 检查 scheme 是否支持
            if parsed.scheme not in ["http", "https", "socks4", "socks5", "socks5h"]:
                return False
            
            # 检查是否有 hostname
            if not parsed.hostname:
                return False
            
            # 检查端口（如果有）
            if parsed.port is not None and (parsed.port < 1 or parsed.port > 65535):
                return False
            
            return True
        except Exception:
            return False
    
    def get_next_proxy(self) -> Optional[str]:
        """获取下一个代理（round-robin 轮询）
        
        Returns:
            代理 URL，如果没有可用代理则返回 None
        """
        if not self.proxies:
            return None
        
        with self._lock:
            # 尝试找到健康的代理
            healthy_proxies = [
                p for p in self.proxies
                if not self._proxy_statuses[p].is_unhealthy
            ]
            
            # 如果没有健康的代理，检查是否有可以重试的
            if not healthy_proxies:
                retryable_proxies = [
                    p for p in self.proxies
                    if self._proxy_statuses[p].should_retry(self.retry_delay_minutes)
                ]
                if retryable_proxies:
                    logger.info(f"尝试恢复代理: {len(retryable_proxies)} 个代理可重试")
                    healthy_proxies = retryable_proxies
            
            # 如果还是没有，使用所有代理（包括不健康的）
            if not healthy_proxies:
                logger.warning("所有代理都不健康，将使用不健康代理")
                healthy_proxies = self.proxies
            
            # round-robin 选择
            if healthy_proxies:
                proxy = healthy_proxies[self._current_index % len(healthy_proxies)]
                self._current_index += 1
                return proxy
            
            return None
    
    def mark_success(self, proxy: str):
        """标记代理成功
        
        Args:
            proxy: 代理 URL
        """
        if proxy not in self._proxy_statuses:
            return
        
        with self._lock:
            status = self._proxy_statuses[proxy]
            was_unhealthy = status.is_unhealthy
            status.mark_success()
            
            if was_unhealthy:
                logger.info(f"代理已恢复健康: {proxy}")
    
    def mark_failure(self, proxy: str, error: Optional[str] = None):
        """标记代理失败
        
        Args:
            proxy: 代理 URL
            error: 错误原因
        """
        if proxy not in self._proxy_statuses:
            return
        
        with self._lock:
            self._proxy_statuses[proxy].mark_failure(error, self.failure_threshold)
    
    def get_proxy_status(self, proxy: str) -> Optional[ProxyStatus]:
        """获取代理状态
        
        Args:
            proxy: 代理 URL
        
        Returns:
            代理状态，如果不存在则返回 None
        """
        return self._proxy_statuses.get(proxy)
    
    def get_all_statuses(self) -> Dict[str, ProxyStatus]:
        """获取所有代理状态
        
        Returns:
            代理状态字典
        """
        with self._lock:
            return self._proxy_statuses.copy()
    
    def get_healthy_count(self) -> int:
        """获取健康代理数量
        
        Returns:
            健康代理数量
        """
        with self._lock:
            return sum(
                1 for status in self._proxy_statuses.values()
                if not status.is_unhealthy
            )
    
    def get_unhealthy_count(self) -> int:
        """获取不健康代理数量
        
        Returns:
            不健康代理数量
        """
        with self._lock:
            return sum(
                1 for status in self._proxy_statuses.values()
                if status.is_unhealthy
            )
    
    def reset_proxy(self, proxy: str):
        """重置代理状态（手动恢复）
        
        Args:
            proxy: 代理 URL
        """
        if proxy not in self._proxy_statuses:
            return
        
        with self._lock:
            status = self._proxy_statuses[proxy]
            status.consecutive_failures = 0
            status.is_unhealthy = False
            status.marked_unhealthy_time = None
            status.last_error = None
            logger.info(f"代理状态已重置: {proxy}")
    
    def reset_all(self):
        """重置所有代理状态"""
        with self._lock:
            for status in self._proxy_statuses.values():
                status.consecutive_failures = 0
                status.is_unhealthy = False
                status.marked_unhealthy_time = None
                status.last_error = None
            logger.info("所有代理状态已重置")

