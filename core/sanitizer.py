"""
敏感信息脱敏模块

从 logger.py 提取，专注于日志消息敏感信息脱敏处理。
支持脱敏：API Key、Cookie、Authorization 头、URL 敏感参数、密码、代理认证等
"""

import re
from typing import Optional


def sanitize_message(message: str) -> str:
    """脱敏处理：移除敏感信息

    严禁出现在日志中的内容：
    - API Key（sk-开头、各种格式）
    - Cookie 原文
    - Authorization 头
    - 账号密码
    - URL 中的敏感参数

    脱敏策略：保留前后几位，中间用 *** 替换

    Args:
        message: 原始消息

    Returns:
        脱敏后的消息
    """
    if not message:
        return message

    # ============ API Key 脱敏 ============
    # OpenAI API Key (sk-开头)
    def redact_api_key(match):
        key = match.group(0)
        if len(key) <= 8:
            return key
        # 保留前 4 位和后 4 位
        return key[:4] + "***" + key[-4:] if len(key) > 8 else "***REDACTED***"

    message = re.sub(r"sk-[a-zA-Z0-9]{20,}", redact_api_key, message)

    # 其他格式的 API Key（长字符串，可能是各种格式）
    # 匹配长度 >= 32 的字母数字字符串（可能是 API Key）
    def redact_long_key(match):
        key = match.group(0)
        if len(key) < 32:
            return key
        # 保留前 4 位和后 4 位
        return key[:4] + "***" + key[-4:] if len(key) > 8 else "***REDACTED***"

    message = re.sub(r"\b[a-zA-Z0-9]{32,}\b", redact_long_key, message)

    # ============ Cookie 脱敏 ============
    # Cookie: 头格式（处理整个 Cookie 字符串，脱敏每个值）
    def redact_cookie_string(cookie_str: str) -> str:
        """脱敏 Cookie 字符串中的各个值"""
        # 分割 Cookie 字符串为 key=value 对
        parts = cookie_str.split(";")
        redacted_parts = []
        for part in parts:
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                # 只脱敏值，保留键名
                if len(value) > 8:
                    redacted_value = value[:4] + "***" + value[-4:]
                else:
                    redacted_value = "***REDACTED***" if len(value) > 0 else value
                redacted_parts.append(f"{key}={redacted_value}")
            else:
                redacted_parts.append(part)
        return "; ".join(redacted_parts)

    def redact_cookie_header(match):
        full_match = match.group(0)
        cookie_value = match.group(1) if match.lastindex >= 1 else full_match
        redacted = redact_cookie_string(cookie_value)
        return full_match.replace(cookie_value, redacted)

    message = re.sub(
        r"Cookie:\s*([^;\n]+)", redact_cookie_header, message, flags=re.IGNORECASE
    )

    # cookie= 格式（URL 参数或配置中的单个 cookie 值）
    def redact_cookie_param(match):
        cookie_value = match.group(1) if match.lastindex >= 1 else match.group(0)
        if len(cookie_value) <= 8:
            return match.group(0)
        redacted = (
            cookie_value[:4] + "***" + cookie_value[-4:]
            if len(cookie_value) > 8
            else "***REDACTED***"
        )
        return match.group(0).replace(cookie_value, redacted)

    message = re.sub(
        r"cookie\s*=\s*([^;\s\n&]+)", redact_cookie_param, message, flags=re.IGNORECASE
    )

    # ============ Authorization 头脱敏 ============
    # Authorization: Bearer token 或 Basic auth
    def redact_auth_value(auth_value: str) -> str:
        """脱敏认证值"""
        if len(auth_value) <= 8:
            return auth_value
        # 保留前 4 位和后 4 位
        return (
            auth_value[:4] + "***" + auth_value[-4:]
            if len(auth_value) > 8
            else "***REDACTED***"
        )

    def redact_auth_header(match):
        full_match = match.group(0)
        auth_value = match.group(1) if match.lastindex >= 1 else full_match
        redacted = redact_auth_value(auth_value)
        return full_match.replace(auth_value, redacted)

    message = re.sub(
        r"Authorization:\s*([^\s\n]+)", redact_auth_header, message, flags=re.IGNORECASE
    )

    # Bearer token
    def redact_bearer(match):
        token = match.group(1)
        redacted = redact_auth_value(token)
        return f"Bearer {redacted}"

    message = re.sub(
        r"Bearer\s+([a-zA-Z0-9\-_\.]+)", redact_bearer, message, flags=re.IGNORECASE
    )

    # Basic auth (base64 编码)
    def redact_basic(match):
        encoded = match.group(1)
        if len(encoded) <= 8:
            return match.group(0)
        redacted = (
            encoded[:4] + "***" + encoded[-4:] if len(encoded) > 8 else "***REDACTED***"
        )
        return f"Basic {redacted}"

    message = re.sub(
        r"Basic\s+([A-Za-z0-9+/=]{20,})", redact_basic, message, flags=re.IGNORECASE
    )

    # ============ URL 敏感参数脱敏 ============
    # URL 中的 token、key、secret 等参数
    def redact_url_param(match):
        prefix = match.group(1)  # ? 或 &
        param_full = match.group(2)  # token= 或 key=
        param_value = match.group(3)
        if len(param_value) <= 8:
            return match.group(0)
        # 保留前 2 位和后 2 位
        redacted = (
            param_value[:2] + "***" + param_value[-2:]
            if len(param_value) > 4
            else "***REDACTED***"
        )
        return f"{prefix}{param_full}{redacted}"

    # 匹配 URL 参数中的敏感字段
    sensitive_params = [
        "token",
        "key",
        "secret",
        "apikey",
        "api_key",
        "access_token",
        "auth",
        "password",
        "pwd",
    ]
    for param in sensitive_params:
        pattern = rf"([?&])({param}=)([^&\s\n]+)"
        message = re.sub(pattern, redact_url_param, message, flags=re.IGNORECASE)

    # ============ 其他敏感信息 ============
    # 密码字段（password=, pwd=）
    message = re.sub(
        r"(password|pwd)\s*=\s*([^\s\n&]+)",
        lambda m: f"{m.group(1)}=***REDACTED***",
        message,
        flags=re.IGNORECASE,
    )

    # 代理认证信息（proxy://user:pass@host）
    message = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***REDACTED***@", message)

    # ============ 截断过长的文本 ============
    # 截断过长的文本（字幕原文等），避免日志文件过大
    if len(message) > 500:
        message = message[:500] + "... [truncated]"

    return message


# 便于导入的别名（保持向后兼容）
__all__ = ["sanitize_message"]
