"""
代理测试模块
负责代理连通性测试逻辑
"""

import subprocess
import shutil
from urllib.parse import urlparse
from typing import List, Dict, Callable, Optional

from ui.i18n_manager import t
from core.logger import get_logger

logger = get_logger()


class ProxyTesterMixin:
    """代理测试 Mixin

    提供代理测试相关的方法
    """

    def _test_proxy_list(
        self,
        proxies: List[str],
        on_log_message: Optional[Callable[[str, str], None]] = None,
    ) -> List[Dict]:
        """测试代理列表

        Args:
            proxies: 代理列表
            on_log_message: 日志回调

        Returns:
            测试结果列表
        """
        try:
            import requests
        except ImportError:
            if on_log_message:
                on_log_message("ERROR", t("proxy_test_requires_requests"))
            return []

        # 检查是否有 SOCKS 代理，并验证依赖
        has_socks = False
        for proxy in proxies:
            if proxy:
                parsed = urlparse(proxy)
                if parsed.scheme and parsed.scheme.lower() in [
                    "socks4",
                    "socks5",
                    "socks5h",
                ]:
                    has_socks = True
                    break

        if has_socks:
            # 检查是否安装了 PySocks
            try:
                import socks  # noqa: F401
            except ImportError:
                if on_log_message:
                    on_log_message("ERROR", t("proxy_test_socks_required"))
                return []

        # 使用多个测试URL，提高成功率
        test_urls = [
            "https://www.google.com",
            "https://www.baidu.com",
            "https://httpbin.org/ip",
            "https://api.ipify.org?format=json",
        ]
        timeout = 15  # 超时时间（秒）

        results = []
        total = len(proxies)

        def log_info(msg):
            """在GUI线程中记录日志"""
            if on_log_message:

                def log():
                    on_log_message("INFO", msg)

                self.after(0, log)

        def log_error(msg):
            """在GUI线程中记录错误"""
            if on_log_message:

                def log():
                    on_log_message("ERROR", msg)

                self.after(0, log)

        def log_debug(msg):
            """在GUI线程中记录调试信息"""
            if on_log_message:

                def log():
                    on_log_message("DEBUG", msg)

                self.after(0, log)

        for i, proxy in enumerate(proxies, 1):
            if not proxy:
                continue

            # 验证代理格式
            parsed = urlparse(proxy)

            # 隐藏密码的代理URL（用于日志显示）
            if parsed.username or parsed.password:
                safe_proxy = f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}"
            else:
                safe_proxy = proxy
            log_info(t("log.proxy_test_item", current=i, total=total, proxy=safe_proxy))

            try:
                if not parsed.scheme or not parsed.hostname:
                    error_msg = t("proxy_format_invalid")
                    log_error(t("proxy_format_invalid_detail", index=i, proxy=proxy))
                    results.append(
                        {"proxy": proxy, "success": False, "error": error_msg}
                    )
                    continue

                # 记录代理类型和认证信息
                proxy_type = parsed.scheme.upper()
                has_auth = parsed.username is not None or parsed.password is not None
                auth_info = ""
                if has_auth:
                    username_display = parsed.username or t("username_none")
                    password_status = (
                        t("password_set") if parsed.password else t("password_not_set")
                    )
                    auth_info = f", {t('username_label')}: {username_display}, {t('password_label')}: {password_status}"
                log_info(
                    t(
                        "log.proxy_type",
                        type=proxy_type,
                        address=f"{parsed.hostname}:{parsed.port or 'default'}{auth_info}",
                    )
                )

                # 验证代理URL格式
                if has_auth:
                    password_status = (
                        t("password_set") if parsed.password else t("password_not_set")
                    )
                    log_debug(
                        t(
                            "log.proxy_has_auth",
                            username=parsed.username,
                            password_status=password_status,
                        )
                    )
                    if parsed.username and not parsed.password:
                        log_error(t("proxy_warning_username_no_password"))

                test_proxy_url = proxy

                # 对于SOCKS代理，验证URL格式
                if parsed.scheme.lower() in ["socks4", "socks5", "socks5h"]:
                    if has_auth:
                        log_debug(
                            t(
                                "log.proxy_socks_with_auth",
                                proxy=f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}",
                            )
                        )
                        if not parsed.username or not parsed.password:
                            log_error(
                                t(
                                    "proxy_warning_socks_auth_incomplete",
                                    username_status=t("username_status_yes") if parsed.username else t("username_status_no"),
                                    password_status=t("password_status_yes") if parsed.password else t("password_status_no"),
                                )
                            )
                    else:
                        log_debug(
                            t(
                                "log.proxy_socks_no_auth",
                                proxy=f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                            )
                        )

                    if has_auth and "@" not in test_proxy_url:
                        log_error(t("proxy_error_url_format"))

                # 使用 yt-dlp 测试代理（与实际使用场景一致）
                log_debug(t("log.proxy_test_ytdlp"))

                # 查找 yt-dlp 可执行文件
                yt_dlp_path = shutil.which("yt-dlp")
                if not yt_dlp_path:
                    yt_dlp_path = shutil.which("yt-dlp.exe")

                test_success = False
                last_error = None
                last_exception = None

                if not yt_dlp_path:
                    # 如果没有找到 yt-dlp，回退到使用 requests 的方式
                    log_debug(t("log.ytdlp_not_found_fallback_requests"))
                    test_success, last_error, last_exception = (
                        self._test_proxy_with_requests(
                            proxy,
                            test_proxy_url,
                            test_urls,
                            timeout,
                            parsed,
                            i,
                            log_info,
                            log_debug,
                        )
                    )
                else:
                    # 使用 yt-dlp 测试代理
                    test_success, last_error, last_exception = (
                        self._test_proxy_with_ytdlp(
                            proxy,
                            test_proxy_url,
                            yt_dlp_path,
                            timeout,
                            parsed,
                            i,
                            log_info,
                            log_debug,
                        )
                    )

                if test_success:
                    results.append({"proxy": proxy, "success": True, "error": None})
                else:
                    # 处理测试失败的情况
                    if last_exception and isinstance(last_exception, Exception):
                        raise last_exception
                    elif last_error:
                        # 根据错误信息模拟抛出相应的异常
                        error_lower = last_error.lower()
                        if (
                            "max retries exceeded" in error_lower
                            or "connection refused" in error_lower
                        ):
                            raise requests.exceptions.ConnectionError(last_error)
                        elif "timeout" in error_lower or "timed out" in error_lower:
                            raise requests.exceptions.Timeout(last_error)
                        elif (
                            "socks" in error_lower
                            or "missing dependencies" in error_lower
                        ):
                            raise requests.exceptions.ProxyError(last_error)
                        else:
                            raise requests.exceptions.ConnectionError(last_error)
                    else:
                        results.append(
                            {
                                "proxy": proxy,
                                "success": False,
                                "error": t("log.proxy_all_test_urls_failed"),
                            }
                        )

            except requests.exceptions.ProxyError as e:
                error_msg = str(e)
                if (
                    "Missing dependencies for SOCKS" in error_msg
                    or "SOCKS support" in error_msg
                ):
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("proxy_test_socks_required_short"),
                        }
                    )
                elif (
                    "Max retries exceeded" in error_msg
                    or "Connection refused" in error_msg
                ):
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("log.proxy_server_no_response"),
                        }
                    )
                else:
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("log.proxy_connection_failed", detail=error_msg[:80]),
                        }
                    )
            except requests.exceptions.Timeout:
                results.append(
                    {
                        "proxy": proxy,
                        "success": False,
                        "error": t("log.proxy_connection_failed_slow"),
                    }
                )
            except requests.exceptions.ConnectionError as e:
                error_msg = str(e)
                log_error(
                    t("log.proxy_connection_error", index=i, error=error_msg[:200])
                )

                # 分析连接错误类型
                if "Max retries exceeded" in error_msg:
                    error_detail = t("log.proxy_connection_failed_no_response")
                    if parsed.scheme.lower() in ["socks4", "socks5", "socks5h"]:
                        error_detail += (
                            f" ({t('log.proxy_connection_failed_socks_detail')})"
                        )
                    results.append(
                        {"proxy": proxy, "success": False, "error": error_detail}
                    )
                elif "Connection refused" in error_msg:
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("log.proxy_connection_failed_refused"),
                        }
                    )
                elif "SOCKS" in error_msg:
                    if (
                        "authentication" in error_msg.lower()
                        or "auth" in error_msg.lower()
                    ):
                        results.append(
                            {
                                "proxy": proxy,
                                "success": False,
                                "error": t("log.proxy_connection_failed_auth"),
                            }
                        )
                    else:
                        results.append(
                            {
                                "proxy": proxy,
                                "success": False,
                                "error": t("log.proxy_connection_failed_socks"),
                            }
                        )
                else:
                    if "Caused by" in error_msg:
                        caused_by_part = error_msg.split("Caused by")[-1].strip()
                        if len(caused_by_part) > 60:
                            caused_by_part = caused_by_part[:60] + "..."
                        results.append(
                            {
                                "proxy": proxy,
                                "success": False,
                                "error": t(
                                    "log.proxy_connection_failed", detail=caused_by_part
                                ),
                            }
                        )
                    else:
                        results.append(
                            {
                                "proxy": proxy,
                                "success": False,
                                "error": t(
                                    "log.proxy_connection_failed", detail=error_msg[:80]
                                ),
                            }
                        )
            except Exception as e:
                error_msg = str(e)
                if (
                    "Missing dependencies for SOCKS" in error_msg
                    or "SOCKS support" in error_msg
                ):
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("proxy_test_socks_required_short"),
                        }
                    )
                elif "Max retries exceeded" in error_msg:
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("log.proxy_connection_failed_no_response"),
                        }
                    )
                else:
                    results.append(
                        {
                            "proxy": proxy,
                            "success": False,
                            "error": t("log.unknown_error_prefix", msg=error_msg[:80]),
                        }
                    )

        return results

    def _test_proxy_with_requests(
        self,
        proxy: str,
        test_proxy_url: str,
        test_urls: List[str],
        timeout: int,
        parsed,
        index: int,
        log_info: Callable,
        log_debug: Callable,
    ) -> tuple:
        """使用 requests 测试代理

        Returns:
            (test_success, last_error, last_exception)
        """
        import requests

        proxies_dict = {"http": test_proxy_url, "https": test_proxy_url}
        test_success = False
        last_error = None
        last_exception = None

        for url_idx, test_url in enumerate(test_urls, 1):
            try:
                log_debug(
                    t(
                        "log.proxy_test_item",
                        current=url_idx,
                        total=len(test_urls),
                        proxy=test_url,
                    )
                )
                response = requests.get(
                    test_url,
                    proxies=proxies_dict,
                    timeout=timeout,
                    allow_redirects=True,
                )
                if response.status_code in [200, 301, 302, 303, 307, 308]:
                    safe_proxy = (
                        f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}"
                        if (parsed.username or parsed.password)
                        else proxy
                    )
                    log_info(
                        t(
                            "log.proxy_test_success_http",
                            index=index,
                            proxy=safe_proxy,
                            test_url=test_url,
                            status_code=response.status_code,
                        )
                    )
                    test_success = True
                    last_error = None
                    break
                else:
                    last_error = f"HTTP {response.status_code}"
            except Exception as e:
                last_error = str(e)
                last_exception = e
                log_debug(
                    t("log.proxy_connection_error", index=url_idx, error=str(e)[:100])
                )

        return test_success, last_error, last_exception

    def _test_proxy_with_ytdlp(
        self,
        proxy: str,
        test_proxy_url: str,
        yt_dlp_path: str,
        timeout: int,
        parsed,
        index: int,
        log_info: Callable,
        log_debug: Callable,
    ) -> tuple:
        """使用 yt-dlp 测试代理

        Returns:
            (test_success, last_error, last_exception)
        """
        test_video_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 公开的测试视频

        try:
            log_debug(t("log.proxy_test_ytdlp_connecting"))

            # 构建 yt-dlp 命令
            cmd = [
                yt_dlp_path,
                "--proxy",
                test_proxy_url,
                "--dump-json",
                "--no-warnings",
                "--quiet",
                "--no-playlist",
                test_video_url,
            ]

            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="ignore",
            )

            # 提取错误输出
            error_output = result.stderr if result.stderr else result.stdout
            error_lines = [
                line
                for line in error_output.split("\n")
                if line.strip() and not line.startswith("WARNING:")
            ]
            error_msg = "\n".join(error_lines[:3])[:200] if error_lines else ""
            error_lower = error_msg.lower()

            if result.returncode == 0:
                safe_proxy = (
                    f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}"
                    if (parsed.username or parsed.password)
                    else proxy
                )
                log_info(
                    t("log.proxy_test_success_ytdlp", index=index, proxy=safe_proxy)
                )
                return True, None, None
            elif any(
                keyword in error_lower
                for keyword in [
                    "sign in to confirm",
                    "you're not a bot",
                    "cookies",
                    "authentication",
                    "cookie",
                ]
            ):
                safe_proxy = (
                    f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}"
                    if (parsed.username or parsed.password)
                    else proxy
                )
                log_info(
                    t(
                        "log.proxy_test_success_cookie_required",
                        index=index,
                        proxy=safe_proxy,
                    )
                )
                log_debug(t("log.proxy_note", message=error_msg[:150]))
                return True, None, None
            elif any(
                keyword in error_lower
                for keyword in [
                    "unable to connect",
                    "connection refused",
                    "connection timeout",
                    "network is unreachable",
                    "name resolution failed",
                    "failed to resolve",
                    "proxy",
                    "socks",
                ]
            ):
                last_error = (
                    error_msg if error_msg else f"{t('ytdlp_error_code_prefix')}{result.returncode}"
                )
                log_debug(t("log.ytdlp_test_failed_connection", error=last_error))
                return False, last_error, None
            else:
                if "ERROR:" in error_output and "youtube" in error_lower:
                    safe_proxy = (
                        f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}"
                        if (parsed.username or parsed.password)
                        else proxy
                    )
                    log_info(
                        t(
                            "log.proxy_test_success_youtube",
                            index=index,
                            proxy=safe_proxy,
                        )
                    )
                    log_debug(t("log.proxy_detail", message=error_msg[:150]))
                    return True, None, None
                else:
                    last_error = (
                        error_msg
                        if error_msg
                        else f"{t('ytdlp_error_code_prefix')}{result.returncode}"
                    )
                    log_debug(t("log.ytdlp_test_failed", error=last_error))
                    return False, last_error, None
        except subprocess.TimeoutExpired:
            last_error = t("log.proxy_connection_timeout", timeout=timeout)
            log_debug(t("log.proxy_test_ytdlp_timeout"))
            return False, last_error, None
        except Exception as e:
            error_msg = str(e)
            last_error = error_msg[:200]
            log_debug(t("log.unknown_error_prefix", msg=last_error))
            return False, last_error, e
