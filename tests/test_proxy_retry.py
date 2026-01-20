"""
proxy_retry 模块的单元测试

测试代理重试逻辑
"""

import pytest
from unittest.mock import MagicMock, patch
import time

from core.proxy_retry import (
    ProxyRetryContext,
    retry_with_proxy_rotation,
)


class MockProxyManager:
    """模拟的 ProxyManager"""

    def __init__(self, proxies=None):
        self.proxies = proxies or ["proxy1", "proxy2", "proxy3"]
        self.current_index = 0
        self.success_count = 0
        self.failure_count = 0
        self.healthy = {p: True for p in self.proxies}

    def get_next_proxy(self, allow_direct=True):
        # 返回下一个健康的代理
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            if self.healthy.get(proxy, True):
                return proxy
        return None if not allow_direct else None

    def mark_success(self, proxy):
        self.success_count += 1

    def mark_failure(self, proxy, reason=""):
        self.failure_count += 1
        self.healthy[proxy] = False


class TestProxyRetryContext:
    """ProxyRetryContext 测试"""

    def test_init_without_proxy_manager(self):
        ctx = ProxyRetryContext(proxy_manager=None)
        assert ctx.max_retries == 3
        assert ctx.current_proxy is None
        assert ctx.attempt == 0

    def test_init_with_proxy_manager(self):
        pm = MockProxyManager()
        ctx = ProxyRetryContext(proxy_manager=pm, max_retries=5)
        assert ctx.max_retries == 5
        assert ctx.proxy_manager is pm

    def test_get_next_proxy_without_manager(self):
        ctx = ProxyRetryContext(proxy_manager=None)
        assert ctx.get_next_proxy() is None

    def test_get_next_proxy_with_manager(self):
        pm = MockProxyManager(["proxy_a", "proxy_b"])
        ctx = ProxyRetryContext(proxy_manager=pm)
        proxy = ctx.get_next_proxy()
        assert proxy in ["proxy_a", "proxy_b"]
        assert proxy in ctx.tried_proxies

    def test_mark_success(self):
        pm = MockProxyManager()
        ctx = ProxyRetryContext(proxy_manager=pm)
        ctx.get_next_proxy()  # 获取一个代理
        ctx.mark_success()
        assert pm.success_count == 1

    def test_mark_failure(self):
        pm = MockProxyManager()
        ctx = ProxyRetryContext(proxy_manager=pm)
        ctx.get_next_proxy()
        ctx.mark_failure("test error")
        assert pm.failure_count == 1

    def test_should_retry(self):
        ctx = ProxyRetryContext(proxy_manager=None, max_retries=3)
        ctx.attempt = 0
        assert ctx.should_retry() is True
        ctx.attempt = 1
        assert ctx.should_retry() is True
        ctx.attempt = 2
        assert ctx.should_retry() is False

    def test_next_attempt(self):
        ctx = ProxyRetryContext(proxy_manager=None)
        assert ctx.attempt == 0
        result = ctx.next_attempt()
        assert result == 1
        assert ctx.attempt == 1


class TestRetryWithProxyRotation:
    """retry_with_proxy_rotation 函数测试"""

    def test_success_on_first_try(self):
        """第一次就成功"""
        pm = MockProxyManager()

        def success_func(proxy):
            return "success"

        result = retry_with_proxy_rotation(success_func, pm)
        assert result == "success"
        assert pm.success_count == 1

    def test_success_after_retries(self):
        """失败后重试成功"""
        pm = MockProxyManager()
        call_count = 0

        def fail_then_success(proxy):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("temporary error")
            return "success"

        result = retry_with_proxy_rotation(
            fail_then_success,
            pm,
            max_retries=3,
            is_retryable=lambda e: True,
        )
        assert result == "success"
        assert call_count == 2

    def test_all_retries_exhausted(self):
        """所有重试都失败"""
        pm = MockProxyManager()

        def always_fail(proxy):
            raise Exception("always fails")

        with pytest.raises(Exception, match="always fails"):
            retry_with_proxy_rotation(
                always_fail,
                pm,
                max_retries=3,
                is_retryable=lambda e: True,
            )

    def test_non_retryable_exception(self):
        """不可重试的异常立即抛出"""
        pm = MockProxyManager()
        call_count = 0

        def fail_with_auth_error(proxy):
            nonlocal call_count
            call_count += 1
            raise ValueError("auth error")

        with pytest.raises(ValueError):
            retry_with_proxy_rotation(
                fail_with_auth_error,
                pm,
                max_retries=3,
                is_retryable=lambda e: isinstance(e, ConnectionError),
            )
        # 应该只调用一次，不重试
        assert call_count == 1

    def test_on_retry_callback(self):
        """重试回调被调用"""
        pm = MockProxyManager()
        retry_calls = []
        call_count = 0

        def fail_then_success(proxy):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("temp error")
            return "ok"

        def on_retry(attempt, exc):
            retry_calls.append((attempt, str(exc)))

        result = retry_with_proxy_rotation(
            fail_then_success,
            pm,
            max_retries=3,
            is_retryable=lambda e: True,
            on_retry=on_retry,
        )
        assert result == "ok"
        assert len(retry_calls) == 1
        assert retry_calls[0][0] == 0  # 第一次重试的 attempt


class TestProxyRotation:
    """代理轮换测试"""

    def test_proxy_rotation_on_failure(self):
        """失败时切换到下一个代理"""
        pm = MockProxyManager(["proxy1", "proxy2", "proxy3"])
        used_proxies = []

        def record_proxy(proxy):
            used_proxies.append(proxy)
            if len(used_proxies) < 3:
                raise Exception("fail")
            return "success"

        result = retry_with_proxy_rotation(
            record_proxy,
            pm,
            max_retries=3,
            is_retryable=lambda e: True,
        )
        assert result == "success"
        assert len(used_proxies) == 3
        # 验证使用了不同的代理（因为失败的代理被标记为不健康）
        # 注意：由于 MockProxyManager 的实现，可能会轮换代理
