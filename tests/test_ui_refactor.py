"""
Task 5 UI 拆分测试脚本
测试拆分后的 UI 模块是否能正常工作
"""
import sys
import pytest
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """测试所有关键导入"""
    # 测试 MainWindow 导入
    from ui.main_window import MainWindow
    assert MainWindow is not None, "MainWindow 应该能成功导入"
    
    # 测试 VideoProcessor 导入
    from ui.business_logic import VideoProcessor
    assert VideoProcessor is not None, "VideoProcessor 应该能成功导入"
    
    # 测试 NetworkSettingsPage 导入
    from ui.pages.network_settings import NetworkSettingsPage
    assert NetworkSettingsPage is not None, "NetworkSettingsPage 应该能成功导入"


def test_class_instantiation():
    """测试类是否可以实例化（不启动 GUI）"""
    from ui.business_logic import VideoProcessor
    from config.manager import ConfigManager
    
    config_manager = ConfigManager()
    app_config = config_manager.load()
    
    # 测试 VideoProcessor 实例化
    processor = VideoProcessor(config_manager, app_config)
    assert processor is not None, "VideoProcessor 应该能成功实例化"
    assert hasattr(processor, 'proxy_manager'), "应该有 proxy_manager 属性"
    assert hasattr(processor, 'cookie_manager'), "应该有 cookie_manager 属性"


def test_page_imports():
    """测试所有页面导入"""
    pages = [
        ("UrlListPage", "ui.pages.url_list_page"),
        ("RunParamsPage", "ui.pages.run_params_page"),
        ("AppearancePage", "ui.pages.appearance_page"),
        ("SystemPage", "ui.pages.system_page"),
        ("NetworkSettingsPage", "ui.pages.network_settings"),
        ("TranslationSummaryPage", "ui.pages.translation_summary_page"),
    ]
    
    for page_name, module_path in pages:
        module = __import__(module_path, fromlist=[page_name])
        page_class = getattr(module, page_name)
        assert page_class is not None, f"{page_name} 应该能成功导入"


def test_main_window_structure():
    """测试 MainWindow 的结构"""
    from ui.main_window import MainWindow
    
    # 检查关键方法是否存在
    required_methods = [
        "__init__",
        "_build_ui",
        "_switch_page",
        "_on_start_processing",
        "_on_save_cookie",
        "_on_language_changed",
        "_on_theme_changed",
    ]
    
    for method_name in required_methods:
        assert hasattr(MainWindow, method_name), f"方法 {method_name} 应该存在"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
