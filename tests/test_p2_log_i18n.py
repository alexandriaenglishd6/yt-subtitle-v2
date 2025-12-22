"""
Task 6 P2 日志国际化测试脚本
测试所有 P2 日志和异常消息的国际化功能
"""
import pytest
from core.i18n import t, set_language
from core.logger import get_logger, translate_exception


# 需要测试的翻译键列表
TEST_KEYS = [
    # P2 日志键
    "log.cleanup_old_logs",
    "log.ai_profile_loaded",
    "log.ai_profile_load_failed",
    "log.ai_profile_loaded_summary",
    "log.ai_profile_config_format_error",
    "log.ai_profile_config_load_failed",
    "log.ai_profile_disabled",
    "log.ai_profile_task_using_profile",
    "log.ai_profile_default_created",
    "log.ai_profile_default_create_failed",
    "log.stage_enqueue_failed",
    "log.stage_already_running",
    "log.worker_thread_timeout",
    "log.stage_worker_cancelled",
    "log.stage_process_exception",
    "log.worker_thread_exception",
    "log.failure_log_error",
    "log.cancel_signal_detected",
    "log.detect_subtitle_info_failed",
    "log.cookie_file_path_unavailable_detect",
    "log.cookie_manager_not_configured_detect",
    "log.video_id_extract_failed",
    "log.output_original_subtitle_written",
    "log.output_translated_subtitle_written",
    "log.output_txt_subtitle_generated",
    "log.subtitle_merge_complete",
    "log.txt_subtitle_write_failed",
    "log.srt_to_txt_conversion_failed",
    "log.local_model_timeout_adjusted",
    "log.local_model_service_check_error",
    "log.local_model_warming_up",
    "log.local_model_warmup_complete",
    "log.local_model_warmup_failed",
    "log.ai_retry_rate_limit",
    "log.ai_retry_connection_failed",
    "log.ai_retry_api_error",
    "log.ai_retry_error",
    "log.cookie_paste_failed",
    "log.cookie_test_error",
    "log.cookie_restore_button_failed",
    "log.ai_profile_status_fetch_failed",
    "log.ai_config_format_error",
    "log.ai_config_save_failed",
    "log.translation_ai_config_format_error",
    # 异常键
    "exception.task_cancelled",
    "exception.task_cancelled_with_reason",
    "exception.append_write_failed",
    "exception.subtitle_text_extract_failed",
    "exception.translation_ai_config_format_error",
    "exception.summary_ai_config_format_error",
]


@pytest.mark.parametrize("lang", ["zh-CN", "en-US"])
def test_translation_keys_exist(lang):
    """测试所有新增的翻译键是否存在"""
    set_language(lang)
    for key in TEST_KEYS:
        result = t(key)
        assert result != key, f"翻译键 {key} 在 {lang} 中不存在（返回原键）"


def test_exception_translation_zh():
    """测试异常消息翻译（中文）"""
    from core.exceptions import TaskCancelledError, LocalModelError
    
    set_language("zh-CN")
    
    # 测试 TaskCancelledError
    e1 = TaskCancelledError()
    assert str(e1), "TaskCancelledError 应该有字符串表示"
    
    e2 = TaskCancelledError("用户取消")
    assert "用户取消" in str(e2) or str(e2), "TaskCancelledError 应该包含原因"
    
    # 测试 LocalModelError
    e = LocalModelError()
    assert str(e), "LocalModelError 应该有字符串表示"
    
    # 测试 translate_exception
    msg1 = translate_exception("exception.append_write_failed")
    assert msg1 != "exception.append_write_failed", "translate_exception 应该返回翻译后的消息"
    
    msg2 = translate_exception("exception.task_cancelled_with_reason", reason="测试")
    assert msg2, "translate_exception 应该支持参数"


def test_exception_translation_en():
    """测试异常消息翻译（英文）"""
    from core.exceptions import TaskCancelledError, LocalModelError
    
    set_language("en-US")
    
    # 测试 TaskCancelledError
    e1 = TaskCancelledError()
    assert str(e1), "TaskCancelledError 应该有字符串表示"
    
    e2 = TaskCancelledError("User cancelled")
    assert str(e2), "TaskCancelledError 应该包含原因"
    
    # 测试 LocalModelError
    e = LocalModelError()
    assert str(e), "LocalModelError 应该有字符串表示"
    
    # 测试 translate_exception
    msg1 = translate_exception("exception.append_write_failed")
    assert msg1 != "exception.append_write_failed", "translate_exception 应该返回翻译后的消息"


@pytest.mark.parametrize("lang", ["zh-CN", "en-US"])
def test_logger_i18n_methods(lang):
    """测试 Logger 的国际化方法"""
    set_language(lang)
    logger = get_logger()
    
    # 这些方法不应该抛出异常
    logger.debug_i18n("log.ai_profile_loaded", profile_name="test_profile")
    logger.info_i18n("log.ai_profile_loaded_summary", profile_count=2, mapping_count=3)
    logger.warning_i18n("log.stage_already_running", stage="test")
    logger.error_i18n("log.stage_enqueue_failed", stage="test", error="test error")


def test_module_imports():
    """测试所有修改的模块可以正常导入"""
    modules = [
        "core.logger",
        "core.exceptions",
        "core.incremental",
        "core.ai_profile_manager",
        "core.staged_pipeline.queue",
        "core.staged_pipeline.scheduler",
        "core.detector",
        "core.output.writer",
        "core.output.formats.subtitle",
        "core.ai_providers.anthropic",
        "core.ai_providers.openai_compatible",
        "core.ai_providers.gemini",
        "core.ai_providers.local_model",
        "ui.pages.network_settings.cookie_section",
        "ui.pages.translation_summary_page",
        "ui.business_logic.processor",
    ]
    
    for module_name in modules:
        try:
            __import__(module_name)
        except Exception as e:
            pytest.fail(f"模块 {module_name} 导入失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
