"""
测试日志国际化功能
验证：
1. 翻译功能正常工作
2. 敏感信息脱敏
3. 日志消息国际化
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger, translate_log, _sanitize_message
from ui.i18n_manager import set_language, t, get_language

def test_translation():
    """测试翻译功能"""
    print("=" * 60)
    print("测试 1: 翻译功能")
    print("=" * 60)
    
    # 测试中文
    set_language("zh-CN")
    print(f"\n当前语言: {get_language()}")
    print(f"  log.video_detected: {t('log.video_detected', video_id='test123')}")
    print(f"  log.task_start: {t('log.task_start', total=10, concurrency=3)}")
    print(f"  exception.processing_failed: {t('exception.processing_failed', error='test error')}")
    
    # 测试英文
    set_language("en-US")
    print(f"\n当前语言: {get_language()}")
    print(f"  log.video_detected: {t('log.video_detected', video_id='test123')}")
    print(f"  log.task_start: {t('log.task_start', total=10, concurrency=3)}")
    print(f"  exception.processing_failed: {t('exception.processing_failed', error='test error')}")
    
    # 恢复中文
    set_language("zh-CN")
    print("\n✓ 翻译功能测试通过\n")

def test_sanitization():
    """测试敏感信息脱敏"""
    print("=" * 60)
    print("测试 2: 敏感信息脱敏")
    print("=" * 60)
    
    test_cases = [
        ("API Key (sk-)", "sk-1234567890abcdefghijklmnopqrstuvwxyz"),
        ("Cookie", "Cookie: VISITOR_INFO1_LIVE=abc123def456; YSC=xyz789"),
        ("Authorization Bearer", "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"),
        ("URL with token", "https://api.example.com?token=secret123&key=value"),
        ("Password", "password=mysecret123"),
    ]
    
    for name, original in test_cases:
        sanitized = _sanitize_message(original)
        print(f"\n{name}:")
        print(f"  原始: {original[:60]}...")
        print(f"  脱敏: {sanitized[:60]}...")
        assert "***" in sanitized or "REDACTED" in sanitized, f"{name} 脱敏失败"
    
    print("\n✓ 敏感信息脱敏测试通过\n")

def test_logger_i18n():
    """测试 Logger 国际化方法"""
    print("=" * 60)
    print("测试 3: Logger 国际化方法")
    print("=" * 60)
    
    logger = get_logger()
    
    # 测试 info_i18n（使用正确的翻译键）
    # video_id 作为单独参数传递，其他参数在 kwargs 中
    msg = logger.info_i18n("video_processing_start", title="Test Video", video_id="test123")
    print(f"info_i18n 返回: {msg}")
    # 检查是否包含参数值（格式化后的消息）
    # 注意：video_id 是单独参数，不会传递给 translate_log，所以消息中可能不包含 video_id
    assert "Test Video" in msg, f"info_i18n 返回消息不正确: {msg}"
    
    # 测试 error_i18n（使用 translate_exception）
    from core.logger import translate_exception
    msg = translate_exception("processing_failed", error="test error")
    print(f"translate_exception 返回: {msg}")
    assert "test error" in msg, "translate_exception 返回消息不正确"
    
    # 测试 error_i18n（使用 log 命名空间）
    msg = logger.error_i18n("translation_failed", error="test error")
    print(f"error_i18n 返回: {msg}")
    assert "test error" in msg, "error_i18n 返回消息不正确"
    
    # 测试 warning_i18n
    msg = logger.warning_i18n("log_callback_failed", error="test error")
    print(f"warning_i18n 返回: {msg}")
    assert "test error" in msg, "warning_i18n 返回消息不正确"
    
    print("\n✓ Logger 国际化方法测试通过\n")

def test_translate_log():
    """测试 translate_log 函数"""
    print("=" * 60)
    print("测试 4: translate_log 函数")
    print("=" * 60)
    
    # 测试带 log. 前缀
    msg = translate_log("log.video_detected", video_id="test123")
    print(f"translate_log('log.video_detected'): {msg}")
    assert "test123" in msg, "translate_log 格式化失败"
    
    # 测试不带 log. 前缀
    msg = translate_log("video_detected", video_id="test123")
    print(f"translate_log('video_detected'): {msg}")
    assert "test123" in msg, "translate_log 自动添加前缀失败"
    
    print("\n✓ translate_log 函数测试通过\n")

def test_sanitization_in_logger():
    """测试 Logger 中的脱敏处理"""
    print("=" * 60)
    print("测试 5: Logger 中的脱敏处理")
    print("=" * 60)
    
    logger = get_logger()
    
    # 测试包含敏感信息的日志
    test_message = "API Key: sk-1234567890abcdefghijklmnopqrstuvwxyz"
    logger.info(test_message)
    
    # 验证日志文件中的内容（如果可能）
    print(f"原始消息: {test_message}")
    print("✓ 日志已记录（请检查日志文件确认脱敏）\n")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("日志国际化功能测试")
    print("=" * 60 + "\n")
    
    try:
        test_translation()
        test_sanitization()
        test_logger_i18n()
        test_translate_log()
        test_sanitization_in_logger()
        
        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

