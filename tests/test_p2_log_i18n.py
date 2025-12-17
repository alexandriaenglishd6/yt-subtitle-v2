"""
Task 6 P2 日志国际化测试脚本
测试所有 P2 日志和异常消息的国际化功能
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_translation_keys():
    """测试所有新增的翻译键是否存在"""
    print("=" * 60)
    print("测试 1: 翻译键存在性检查")
    print("=" * 60)
    
    from ui.i18n_manager import t, set_language
    
    # 需要测试的翻译键列表
    test_keys = [
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
    
    failed_keys = []
    
    # 测试中文
    set_language("zh-CN")
    print("\n测试中文翻译...")
    for key in test_keys:
        try:
            result = t(key)
            if result == key:
                print(f"  [FAIL] {key}: 翻译键不存在（返回原键）")
                failed_keys.append(key)
            else:
                print(f"  [OK] {key}: {result[:50]}...")
        except Exception as e:
            print(f"  [FAIL] {key}: 翻译失败 - {e}")
            failed_keys.append(key)
    
    # 测试英文
    set_language("en-US")
    print("\n测试英文翻译...")
    for key in test_keys:
        try:
            result = t(key)
            if result == key:
                print(f"  [FAIL] {key}: 翻译键不存在（返回原键）")
                if key not in failed_keys:
                    failed_keys.append(key)
            else:
                print(f"  [OK] {key}: {result[:50]}...")
        except Exception as e:
            print(f"  [FAIL] {key}: 翻译失败 - {e}")
            if key not in failed_keys:
                failed_keys.append(key)
    
    if failed_keys:
        print(f"\n[FAIL] 失败: {len(failed_keys)} 个翻译键缺失")
        return False
    else:
        print(f"\n[OK] 成功: 所有 {len(test_keys)} 个翻译键都存在")
        return True


def test_exception_translation():
    """测试异常消息翻译"""
    print("\n" + "=" * 60)
    print("测试 2: 异常消息翻译")
    print("=" * 60)
    
    from ui.i18n_manager import set_language
    from core.exceptions import TaskCancelledError, LocalModelError
    from core.logger import translate_exception
    
    # 测试 TaskCancelledError
    set_language("zh-CN")
    print("\n测试 TaskCancelledError（中文）...")
    try:
        e1 = TaskCancelledError()
        print(f"  [OK] 无原因: {str(e1)}")
        
        e2 = TaskCancelledError("用户取消")
        print(f"  [OK] 有原因: {str(e2)}")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    set_language("en-US")
    print("\n测试 TaskCancelledError（英文）...")
    try:
        e1 = TaskCancelledError()
        print(f"  [OK] 无原因: {str(e1)}")
        
        e2 = TaskCancelledError("User cancelled")
        print(f"  [OK] 有原因: {str(e2)}")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    # 测试 LocalModelError
    set_language("zh-CN")
    print("\n测试 LocalModelError（中文）...")
    try:
        e = LocalModelError()
        print(f"  [OK] {str(e)}")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    set_language("en-US")
    print("\n测试 LocalModelError（英文）...")
    try:
        e = LocalModelError()
        print(f"  [OK] {str(e)}")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    # 测试 translate_exception
    set_language("zh-CN")
    print("\n测试 translate_exception（中文）...")
    try:
        msg1 = translate_exception("exception.append_write_failed")
        print(f"  [OK] {msg1}")
        
        msg2 = translate_exception("exception.task_cancelled_with_reason", reason="测试")
        print(f"  [OK] {msg2}")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    set_language("en-US")
    print("\n测试 translate_exception（英文）...")
    try:
        msg1 = translate_exception("exception.append_write_failed")
        print(f"  [OK] {msg1}")
        
        msg2 = translate_exception("exception.task_cancelled_with_reason", reason="test")
        print(f"  [OK] {msg2}")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    return True


def test_logger_i18n_methods():
    """测试 Logger 的国际化方法"""
    print("\n" + "=" * 60)
    print("测试 3: Logger 国际化方法")
    print("=" * 60)
    
    from ui.i18n_manager import set_language
    from core.logger import get_logger
    
    logger = get_logger()
    
    # 测试中文
    set_language("zh-CN")
    print("\n测试中文日志...")
    try:
        # 这些方法会输出到控制台，我们只测试它们不会抛出异常
        logger.debug_i18n("log.ai_profile_loaded", profile_name="test_profile")
        logger.info_i18n("log.ai_profile_loaded_summary", profile_count=2, mapping_count=3)
        logger.warning_i18n("log.stage_already_running", stage="test")
        logger.error_i18n("log.stage_enqueue_failed", stage="test", error="test error")
        print("  [OK] 所有日志方法调用成功")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    # 测试英文
    set_language("en-US")
    print("\n测试英文日志...")
    try:
        logger.debug_i18n("log.ai_profile_loaded", profile_name="test_profile")
        logger.info_i18n("log.ai_profile_loaded_summary", profile_count=2, mapping_count=3)
        logger.warning_i18n("log.stage_already_running", stage="test")
        logger.error_i18n("log.stage_enqueue_failed", stage="test", error="test error")
        print("  [OK] 所有日志方法调用成功")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False
    
    return True


def test_imports():
    """测试所有修改的模块可以正常导入"""
    print("\n" + "=" * 60)
    print("测试 4: 模块导入测试")
    print("=" * 60)
    
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
        "ui.pages.network_ai_page",
        "ui.pages.translation_summary_page",
        "ui.business_logic.processor",
    ]
    
    failed_modules = []
    
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"  [OK] {module_name}")
        except Exception as e:
            print(f"  [FAIL] {module_name}: {e}")
            failed_modules.append(module_name)
    
    if failed_modules:
        print(f"\n[FAIL] 失败: {len(failed_modules)} 个模块导入失败")
        return False
    else:
        print(f"\n[OK] 成功: 所有 {len(modules)} 个模块导入成功")
        return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Task 6 P2 日志国际化测试")
    print("=" * 60)
    
    results = []
    
    # 测试 1: 翻译键存在性
    results.append(("翻译键存在性", test_translation_keys()))
    
    # 测试 2: 异常消息翻译
    results.append(("异常消息翻译", test_exception_translation()))
    
    # 测试 3: Logger 国际化方法
    results.append(("Logger 国际化方法", test_logger_i18n_methods()))
    
    # 测试 4: 模块导入
    results.append(("模块导入", test_imports()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过！P2 日志国际化完成，功能正常。")
        return 0
    else:
        print("\n[WARNING] 部分测试失败，请检查错误信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
