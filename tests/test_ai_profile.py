"""
AI Profile 功能测试脚本

测试 AI Profile 管理器的基本功能，包括：
1. 加载配置文件
2. 根据任务类型获取配置
3. 创建 LLM 客户端
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.ai_profile_manager import AIProfileManager, get_profile_manager
from config.manager import ConfigManager, AIConfig
from core.logger import get_logger

logger = get_logger()


def test_profile_manager():
    """测试 Profile 管理器基本功能"""
    print("=" * 60)
    print("测试 1: Profile 管理器基本功能")
    print("=" * 60)
    
    manager = AIProfileManager()
    loaded = manager.load()
    
    if loaded:
        print(f"✅ 成功加载配置文件: {manager.profile_file}")
    else:
        print(f"ℹ️  配置文件不存在或为空: {manager.profile_file}")
        print("   这是正常的，如果没有创建配置文件的话")
    
    # 列出所有 Profiles
    profiles = manager.list_profiles()
    print(f"\n已加载的 Profiles ({len(profiles)} 个):")
    for name, profile in profiles.items():
        status = "启用" if profile.enabled else "禁用"
        print(f"  - {name}: {profile.ai_config.provider}/{profile.ai_config.model} ({status})")
    
    # 列出任务映射
    mappings = manager.list_task_mappings()
    print(f"\n任务映射 ({len(mappings)} 个):")
    for task_type, profile_name in mappings.items():
        print(f"  - {task_type} -> {profile_name}")
    
    return manager


def test_get_config_for_task():
    """测试根据任务类型获取配置"""
    print("\n" + "=" * 60)
    print("测试 2: 根据任务类型获取配置")
    print("=" * 60)
    
    manager = get_profile_manager()
    config_manager = ConfigManager()
    app_config = config_manager.load()
    
    # 测试翻译任务
    translation_config = manager.get_ai_config_for_task(
        "subtitle_translate",
        fallback_config=app_config.translation_ai
    )
    
    if translation_config:
        print(f"✅ 翻译任务配置:")
        print(f"   Provider: {translation_config.provider}")
        print(f"   Model: {translation_config.model}")
        print(f"   Enabled: {translation_config.enabled}")
        profile = manager.get_profile_for_task("subtitle_translate")
        if profile:
            print(f"   Profile: {profile.name}")
        else:
            print(f"   Profile: 使用回退配置")
    else:
        print("ℹ️  翻译任务未配置")
    
    # 测试摘要任务
    summary_config = manager.get_ai_config_for_task(
        "subtitle_summarize",
        fallback_config=app_config.summary_ai
    )
    
    if summary_config:
        print(f"\n✅ 摘要任务配置:")
        print(f"   Provider: {summary_config.provider}")
        print(f"   Model: {summary_config.model}")
        print(f"   Enabled: {summary_config.enabled}")
        profile = manager.get_profile_for_task("subtitle_summarize")
        if profile:
            print(f"   Profile: {profile.name}")
        else:
            print(f"   Profile: 使用回退配置")
    else:
        print("\nℹ️  摘要任务未配置")


def test_create_llm_client():
    """测试创建 LLM 客户端（不实际调用 API）"""
    print("\n" + "=" * 60)
    print("测试 3: 创建 LLM 客户端（验证配置）")
    print("=" * 60)
    
    manager = get_profile_manager()
    config_manager = ConfigManager()
    app_config = config_manager.load()
    
    # 获取翻译配置
    translation_config = manager.get_ai_config_for_task(
        "subtitle_translate",
        fallback_config=app_config.translation_ai
    )
    
    if translation_config and translation_config.enabled:
        try:
            from core.ai_providers import create_llm_client
            client = create_llm_client(translation_config)
            print(f"✅ 翻译 LLM 客户端创建成功:")
            print(f"   Provider: {translation_config.provider}")
            print(f"   Model: {translation_config.model}")
            print(f"   Max Concurrency: {client.max_concurrency}")
        except Exception as e:
            print(f"⚠️  翻译 LLM 客户端创建失败: {e}")
            print("   这可能是正常的（例如 API Key 未配置）")
    else:
        print("ℹ️  翻译任务未启用或未配置")
    
    # 获取摘要配置
    summary_config = manager.get_ai_config_for_task(
        "subtitle_summarize",
        fallback_config=app_config.summary_ai
    )
    
    if summary_config and summary_config.enabled:
        try:
            from core.ai_providers import create_llm_client
            client = create_llm_client(summary_config)
            print(f"\n✅ 摘要 LLM 客户端创建成功:")
            print(f"   Provider: {summary_config.provider}")
            print(f"   Model: {summary_config.model}")
            print(f"   Max Concurrency: {client.max_concurrency}")
        except Exception as e:
            print(f"\n⚠️  摘要 LLM 客户端创建失败: {e}")
            print("   这可能是正常的（例如 API Key 未配置）")
    else:
        print("\nℹ️  摘要任务未启用或未配置")


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "=" * 60)
    print("测试 4: 向后兼容性")
    print("=" * 60)
    
    manager = get_profile_manager()
    config_manager = ConfigManager()
    app_config = config_manager.load()
    
    # 测试：如果没有 Profile，应该使用回退配置
    # 创建一个不存在的任务类型
    fake_config = manager.get_ai_config_for_task(
        "fake_task",
        fallback_config=app_config.translation_ai
    )
    
    if fake_config:
        print(f"✅ 向后兼容性测试通过:")
        print(f"   未配置的任务类型正确回退到默认配置")
        print(f"   Provider: {fake_config.provider}")
        print(f"   Model: {fake_config.model}")
    else:
        print("⚠️  向后兼容性测试失败: 未找到回退配置")


def main():
    """主测试函数"""
    print("AI Profile 功能测试")
    print("=" * 60)
    print()
    
    try:
        # 测试 1: Profile 管理器基本功能
        test_profile_manager()
        
        # 测试 2: 根据任务类型获取配置
        test_get_config_for_task()
        
        # 测试 3: 创建 LLM 客户端
        test_create_llm_client()
        
        # 测试 4: 向后兼容性
        test_backward_compatibility()
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print("\n提示:")
        print("1. 如果配置文件不存在，这是正常的")
        print("2. 可以将 config/ai_profiles.json.example 复制到用户数据目录")
        print("3. 如果 LLM 客户端创建失败，可能是 API Key 未配置，这是正常的")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

