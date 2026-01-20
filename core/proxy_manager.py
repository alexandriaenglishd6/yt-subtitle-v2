"""
代理管理器模块
实现多代理列表管理、round-robin 轮询、简单健康检查
"""

import threading
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse

from core.logger import get_logger

logger = get_logger()


@dataclass
class ProxyStatus:
    """代理状态信息"""

    proxy: str
    consecutive_failures: int = 0  # 连续失败次数
    total_failures: int = 0  # 总失败次数
    total_successes: int = 0  # 总成功次数
    last_error: Optional[str] = None  # 最后错误原因
    last_success_time: Optional[datetime] = None  # 最后成功时间
    last_failure_time: Optional[datetime] = None  # 最后失败时间
    marked_unhealthy_time: Optional[datetime] = None  # 标记为不健康的时间
    is_unhealthy: bool = False  # 是否标记为不健康

    def mark_success(self):
        """标记成功"""
        self.consecutive_failures = 0
        self.total_successes += 1
        self.last_success_time = datetime.now()
        was_unhealthy = self.is_unhealthy
        self.is_unhealthy = False
        self.marked_unhealthy_time = None
        self.last_error = None
        return was_unhealthy  # 返回是否从 unhealthy 恢复

    def mark_failure(self, error: Optional[str] = None, failure_threshold: int = 5):
        """标记失败

        Args:
            error: 错误原因
            failure_threshold: 失败阈值（连续失败超过此值标记为不健康），默认 5
        """
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_error = error
        self.last_failure_time = datetime.now()

        if self.consecutive_failures >= failure_threshold and not self.is_unhealthy:
            self.is_unhealthy = True
            self.marked_unhealthy_time = datetime.now()
            logger.warning_i18n(
                "proxy_marked_unhealthy",
                proxy=self.proxy,
                failures=self.consecutive_failures,
            )

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
        failure_threshold: int = 5,
        retry_delay_minutes: int = 10,
        enable_health_probe: bool = True,
        probe_interval_minutes: int = 5,
        quiet: bool = False,
    ):
        """初始化代理管理器

        Args:
            proxies: 代理列表（格式：http://host:port 或 socks5://host:port）
            failure_threshold: 失败阈值（连续失败超过此值标记为不健康），默认 5
            retry_delay_minutes: 重试延迟（分钟），默认 10
            enable_health_probe: 是否启用健康探测，默认 True
            probe_interval_minutes: 健康探测间隔（分钟），默认 5
            quiet: 是否进入静默模式，默认 False
        """
        # 验证并过滤无效代理
        valid_proxies = []
        invalid_proxies = []

        for proxy in proxies or []:
            proxy = proxy.strip()
            if not proxy:
                continue

            if self._is_valid_proxy(proxy):
                valid_proxies.append(proxy)
            else:
                invalid_proxies.append(proxy)
                if not quiet:
                    logger.warning_i18n("proxy_invalid_format_skipped", proxy=proxy)

        self.proxies = valid_proxies
        self.failure_threshold = failure_threshold
        self.retry_delay_minutes = retry_delay_minutes
        self.enable_health_probe = enable_health_probe
        self.probe_interval_minutes = probe_interval_minutes
        self.quiet = quiet
        self.allow_direct_connection = True  # 允许直连降级

        # 初始化代理状态
        self._proxy_statuses: Dict[str, ProxyStatus] = {}
        for proxy in self.proxies:
            self._proxy_statuses[proxy] = ProxyStatus(proxy=proxy)

        # round-robin 索引
        self._current_index = 0
        self._lock = threading.Lock()

        # 启动健康探测线程（如果启用）
        self._probe_thread: Optional[threading.Thread] = None
        self._stop_probe = threading.Event()
        if self.enable_health_probe and self.proxies:
            self._start_health_probe()

        if invalid_proxies and not quiet:
            logger.warning_i18n(
                "proxy_invalid_filtered",
                invalid_count=len(invalid_proxies),
                valid_count=len(self.proxies),
            )

        if not quiet:
            if self.proxies:
                logger.debug_i18n("proxy_manager_init", count=len(self.proxies))
            else:
                if proxies:
                    logger.warning_i18n("proxy_manager_init_all_invalid")
                else:
                    logger.debug_i18n("proxy_manager_init_none")

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

    def get_next_proxy(self, allow_direct: bool = True, exclude: set = None) -> Optional[str]:
        """获取下一个代理（round-robin 轮询）

        Args:
            allow_direct: 如果所有代理都不健康，是否允许返回 None（表示直连），默认 True
            exclude: 要排除的代理集合（用于重试时避免使用同一个代理）

        Returns:
            代理 URL，如果没有可用代理且 allow_direct=True 则返回 None（表示直连），否则返回失败最少的代理
        """
        if not self.proxies:
            return None

        exclude = exclude or set()

        with self._lock:
            # 尝试找到健康的代理（排除已尝试的）
            healthy_proxies = [
                p for p in self.proxies 
                if not self._proxy_statuses[p].is_unhealthy and p not in exclude
            ]

            # 如果没有健康的代理，检查是否有可以重试的（也排除已尝试的）
            if not healthy_proxies:
                retryable_proxies = [
                    p
                    for p in self.proxies
                    if self._proxy_statuses[p].should_retry(self.retry_delay_minutes)
                    and p not in exclude
                ]
                if retryable_proxies:
                    logger.info_i18n(
                        "proxy_retry_attempt", count=len(retryable_proxies)
                    )
                    healthy_proxies = retryable_proxies

            # 如果排除后没有可用代理，但有被排除的健康代理，降级使用
            if not healthy_proxies and exclude:
                # 尝试使用被排除但健康的代理（最后手段）
                excluded_healthy = [
                    p for p in self.proxies 
                    if not self._proxy_statuses[p].is_unhealthy and p in exclude
                ]
                if excluded_healthy:
                    # 选择失败次数最少的
                    best = min(excluded_healthy, 
                               key=lambda p: self._proxy_statuses[p].consecutive_failures)
                    logger.debug(f"所有代理已尝试，降级使用: {best[:30]}...")
                    return best

            # 如果还是没有健康的代理
            if not healthy_proxies:
                if allow_direct and self.allow_direct_connection:
                    # 所有代理都不健康，尝试直连
                    logger.warning_i18n("proxy_all_unhealthy_direct")
                    return None
                else:
                    # 不允许直连，选择失败最少的代理
                    best_proxy = self._get_best_unhealthy_proxy()
                    if best_proxy:
                        logger.warning_i18n(
                            "proxy_all_unhealthy_use_best", proxy=best_proxy
                        )
                        return best_proxy
                    # 如果还是没有，使用所有代理（包括不健康的）
                    logger.warning_i18n("proxy_all_unhealthy_use_unhealthy")
                    healthy_proxies = self.proxies

            # round-robin 选择
            if healthy_proxies:
                proxy = healthy_proxies[self._current_index % len(healthy_proxies)]
                self._current_index += 1
                return proxy

            return None


    def _get_best_unhealthy_proxy(self) -> Optional[str]:
        """获取失败最少的代理（降级策略）

        Returns:
            失败最少的代理 URL，如果没有则返回 None
        """
        if not self.proxies:
            return None

        best_proxy = None
        min_failures = float("inf")

        for proxy, status in self._proxy_statuses.items():
            # 计算失败率（总失败次数 / 总请求次数）
            total_requests = status.total_successes + status.total_failures
            if total_requests == 0:
                # 如果还没有请求记录，优先选择
                return proxy

            failure_rate = status.total_failures / total_requests
            # 优先选择失败率最低的
            if failure_rate < min_failures:
                min_failures = failure_rate
                best_proxy = proxy

        return best_proxy

    def mark_success(self, proxy: str):
        """标记代理成功

        Args:
            proxy: 代理 URL
        """
        if proxy not in self._proxy_statuses:
            return

        with self._lock:
            status = self._proxy_statuses[proxy]
            recovered = status.mark_success()

            if recovered:
                logger.info_i18n("proxy_recovered", proxy=proxy)

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
                1 for status in self._proxy_statuses.values() if not status.is_unhealthy
            )

    def get_unhealthy_count(self) -> int:
        """获取不健康代理数量

        Returns:
            不健康代理数量
        """
        with self._lock:
            return sum(
                1 for status in self._proxy_statuses.values() if status.is_unhealthy
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
            logger.info_i18n("proxy_status_reset", proxy=proxy)

    def reset_all(self):
        """重置所有代理状态"""
        with self._lock:
            for status in self._proxy_statuses.values():
                status.consecutive_failures = 0
                status.is_unhealthy = False
                status.marked_unhealthy_time = None
                status.last_error = None
            logger.info_i18n("proxy_all_status_reset")

    def _start_health_probe(self):
        """启动健康探测线程"""
        if self._probe_thread and self._probe_thread.is_alive():
            return

        def probe_worker():
            """健康探测工作线程"""
            try:
                import requests
            except ImportError:
                logger.warning_i18n("proxy_health_probe_unavailable")
                return

            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            # 配置重试策略
            retry_strategy = Retry(
                total=1,  # 只重试 1 次
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)

            while not self._stop_probe.is_set():
                try:
                    # 等待探测间隔
                    if self._stop_probe.wait(timeout=self.probe_interval_minutes * 60):
                        break  # 收到停止信号

                    # 获取需要探测的代理（unhealthy 且已过重试延迟）
                    with self._lock:
                        unhealthy_proxies = [
                            (proxy, status)
                            for proxy, status in self._proxy_statuses.items()
                            if status.is_unhealthy
                            and status.should_retry(self.retry_delay_minutes)
                        ]

                    if not unhealthy_proxies:
                        continue

                    logger.debug_i18n(
                        "proxy_health_probe_start", count=len(unhealthy_proxies)
                    )

                    # 对每个 unhealthy 代理进行轻量探测
                    for proxy, status in unhealthy_proxies:
                        if self._stop_probe.is_set():
                            break

                        try:
                            # 轻量探测：尝试访问一个简单的 URL
                            session = requests.Session()
                            session.mount("http://", adapter)
                            session.mount("https://", adapter)

                            # 配置代理
                            proxies = {"http": proxy, "https": proxy}

                            # 轻量探测请求（使用 Google 的简单页面）
                            response = session.get(
                                "http://www.google.com",
                                proxies=proxies,
                                timeout=5,  # 5 秒超时
                                allow_redirects=False,
                            )

                            # 如果请求成功（任何状态码都算成功，说明代理可用）
                            if response.status_code in [200, 301, 302, 307, 308]:
                                with self._lock:
                                    if proxy in self._proxy_statuses:
                                        self.mark_success(proxy)
                                        logger.info_i18n(
                                            "proxy_health_probe_success", proxy=proxy
                                        )
                            else:
                                logger.debug_i18n(
                                    "proxy_health_probe_failed_status",
                                    proxy=proxy,
                                    status_code=response.status_code,
                                )

                        except Exception as e:
                            logger.debug_i18n(
                                "proxy_health_probe_failed_error",
                                proxy=proxy,
                                error=str(e),
                            )
                            # 探测失败不影响代理状态（不增加失败计数）

                except Exception as e:
                    logger.warning_i18n("proxy_health_probe_thread_error", error=str(e))

        self._probe_thread = threading.Thread(
            target=probe_worker, daemon=True, name="ProxyHealthProbe"
        )
        self._probe_thread.start()
        if not getattr(self, "quiet", False):
            logger.debug_i18n("proxy_health_probe_started")

    def stop_health_probe(self):
        """停止健康探测线程"""
        if self._probe_thread and self._probe_thread.is_alive():
            self._stop_probe.set()
            self._probe_thread.join(timeout=5)
            logger.info_i18n("proxy_health_probe_stopped")

    def __del__(self):
        """析构函数，确保线程正确停止"""
        try:
            self.stop_health_probe()
        except Exception:
            pass
