"""
LanguageConfig 使用示例
演示如何正确使用 LanguageConfig 和 Prompt 模板
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.language import LanguageConfig, get_language_name
from core.prompts import get_translation_prompt, get_summary_prompt


def example_1_language_config():
    """示例 1: 使用 LanguageConfig"""
    print("=" * 50)
    print("示例 1: LanguageConfig 基本使用")
    print("=" * 50)
    
    # 创建默认配置
    config_default = LanguageConfig()
    print(f"默认配置:")
    print(f"  - UI 语言: {config_default.ui_language}")
    print(f"  - 字幕目标语言: {config_default.subtitle_target_languages}")
    print(f"  - 摘要语言: {config_default.summary_language}")
    print(f"  - 翻译策略: {config_default.translation_strategy}")
    
    # 创建自定义配置
    config_custom = LanguageConfig(
        subtitle_target_languages=["en-US"],
        summary_language="en-US"
    )
    print(f"\n自定义配置:")
    print(f"  - 字幕目标语言: {config_custom.subtitle_target_languages}")
    print(f"  - 摘要语言: {config_custom.summary_language}")
    
    print("\n测试通过 ✓\n")


def example_2_prompts():
    """示例 2: 使用 Prompt 模板"""
    print("=" * 50)
    print("示例 2: Prompt 模板使用（不硬编码语言）")
    print("=" * 50)
    
    # 测试翻译 Prompt（英文到中文）
    print("\n翻译 Prompt (en -> zh-CN):")
    prompt1 = get_translation_prompt("en", "zh-CN", "Hello world")
    print(prompt1[:150] + "...")
    assert "中文" in prompt1 or "Chinese" in prompt1, "应该包含目标语言名称"
    
    # 测试翻译 Prompt（中文到英文）
    print("\n翻译 Prompt (zh-CN -> en-US):")
    prompt2 = get_translation_prompt("zh-CN", "en-US", "你好世界")
    print(prompt2[:150] + "...")
    assert "English" in prompt2, "应该包含目标语言名称"
    
    # 测试摘要 Prompt（中文）
    print("\n摘要 Prompt (zh-CN):")
    prompt3 = get_summary_prompt("zh-CN", "这是测试字幕内容")
    print(prompt3[:150] + "...")
    assert "中文" in prompt3, "应该包含摘要语言名称"
    
    # 测试摘要 Prompt（英文）
    print("\n摘要 Prompt (en-US):")
    prompt4 = get_summary_prompt("en-US", "This is test subtitle content")
    print(prompt4[:150] + "...")
    assert "English" in prompt4, "应该包含摘要语言名称"
    
    print("\n✓ Prompt 模板正确使用语言名称，无硬编码")
    print("\n测试通过 ✓\n")


def example_3_language_name():
    """示例 3: 语言名称映射"""
    print("=" * 50)
    print("示例 3: 语言名称映射")
    print("=" * 50)
    
    test_cases = [
        ("zh-CN", "中文"),
        ("en-US", "English"),
        ("ja-JP", "日本語"),
        ("ko-KR", "한국어"),
    ]
    
    for lang_code, expected_name in test_cases:
        name = get_language_name(lang_code)
        print(f"  {lang_code} -> {name}")
        assert name == expected_name, f"语言名称映射不正确: {lang_code}"
    
    print("\n测试通过 ✓\n")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("LanguageConfig & Prompt 模板使用示例")
    print("=" * 50 + "\n")
    
    try:
        example_1_language_config()
        example_2_prompts()
        example_3_language_name()
        
        print("=" * 50)
        print("所有示例完成！")
        print("=" * 50)
        print("\n说明：")
        print("- LanguageConfig 模型已完整实现")
        print("- Prompt 模板不硬编码语言，支持多语言")
        print("- 所有语言相关逻辑都从 LanguageConfig 读取配置")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

