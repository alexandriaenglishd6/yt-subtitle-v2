"""
Task 5 UI 拆分测试脚本
测试拆分后的 UI 模块是否能正常工作
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试所有关键导入"""
    print("=" * 60)
    print("测试 1: 导入测试")
    print("=" * 60)
    
    try:
        from ui.main_window import MainWindow
        print("✅ MainWindow 导入成功")
    except Exception as e:
        print(f"❌ MainWindow 导入失败: {e}")
        return False
    
    try:
        from ui.business_logic import VideoProcessor
        print("✅ VideoProcessor 导入成功")
    except Exception as e:
        print(f"❌ VideoProcessor 导入失败: {e}")
        return False
    
    try:
        from ui.pages.network_settings import NetworkSettingsPage
        print("✅ NetworkSettingsPage 导入成功")
    except Exception as e:
        print(f"❌ NetworkSettingsPage 导入失败: {e}")
        return False
    
    return True

def test_class_instantiation():
    """测试类是否可以实例化（不启动 GUI）"""
    print("\n" + "=" * 60)
    print("测试 2: 类实例化测试（不启动 GUI）")
    print("=" * 60)
    
    try:
        from ui.business_logic import VideoProcessor
        from config.manager import ConfigManager
        
        config_manager = ConfigManager()
        app_config = config_manager.load()
        
        # 测试 VideoProcessor 实例化
        processor = VideoProcessor(config_manager, app_config)
        print("✅ VideoProcessor 实例化成功")
        print(f"   - 代理管理器: {'已初始化' if hasattr(processor, 'proxy_manager') else '未初始化'}")
        print(f"   - Cookie 管理器: {'已初始化' if hasattr(processor, 'cookie_manager') else '未初始化'}")
        print(f"   - 翻译 LLM: {'已初始化' if hasattr(processor, 'translation_llm_client') and processor.translation_llm_client else '未初始化'}")
        print(f"   - 摘要 LLM: {'已初始化' if hasattr(processor, 'summary_llm_client') and processor.summary_llm_client else '未初始化'}")
        
    except Exception as e:
        print(f"❌ VideoProcessor 实例化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_page_imports():
    """测试所有页面导入"""
    print("\n" + "=" * 60)
    print("测试 3: 页面导入测试")
    print("=" * 60)
    
    pages = [
        ("ChannelPage", "ui.pages.channel_page"),
        ("UrlListPage", "ui.pages.url_list_page"),
        ("RunParamsPage", "ui.pages.run_params_page"),
        ("AppearancePage", "ui.pages.appearance_page"),
        ("NetworkAIPage", "ui.pages.network_ai_page"),
        ("SystemPage", "ui.pages.system_page"),
        ("NetworkSettingsPage", "ui.pages.network_settings"),
        ("TranslationSummaryPage", "ui.pages.translation_summary_page"),
    ]
    
    all_passed = True
    for page_name, module_path in pages:
        try:
            module = __import__(module_path, fromlist=[page_name])
            page_class = getattr(module, page_name)
            print(f"✅ {page_name} 导入成功")
        except Exception as e:
            print(f"❌ {page_name} 导入失败: {e}")
            all_passed = False
    
    return all_passed

def test_main_window_structure():
    """测试 MainWindow 的结构"""
    print("\n" + "=" * 60)
    print("测试 4: MainWindow 结构测试")
    print("=" * 60)
    
    try:
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
            if hasattr(MainWindow, method_name):
                print(f"✅ 方法 {method_name} 存在")
            else:
                print(f"❌ 方法 {method_name} 不存在")
                return False
        
        return True
    except Exception as e:
        print(f"❌ MainWindow 结构测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Task 5 UI 拆分测试")
    print("=" * 60)
    
    results = []
    
    # 测试 1: 导入测试
    results.append(("导入测试", test_imports()))
    
    # 测试 2: 类实例化测试
    results.append(("类实例化测试", test_class_instantiation()))
    
    # 测试 3: 页面导入测试
    results.append(("页面导入测试", test_page_imports()))
    
    # 测试 4: MainWindow 结构测试
    results.append(("MainWindow 结构测试", test_main_window_structure()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！UI 拆分成功，功能正常。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

