#!/usr/bin/env python3
"""
测试摘要部分的国际化
可以单独测试摘要功能，无需运行完整流程
"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.logger import get_logger, set_log_context, clear_log_context
from core.models import VideoInfo
from core.language import LanguageConfig
from core.summarizer import Summarizer
from core.i18n import set_language, get_language
from core.llm_client import LLMClient

# 创建一个模拟的 LLM 客户端
class MockLLMClient:
    """模拟的 LLM 客户端，用于测试"""
    def __init__(self):
        self.name = "mock_llm"
        self.provider = "mock"
        # LLMClient 协议要求的属性
        self.supports_vision = False
        self.max_input_tokens = 100000
        self.max_output_tokens = 4000
        self.max_concurrency = 10
    
    def generate(self, prompt: str, **kwargs):
        """模拟生成摘要"""
        from core.llm_client import LLMResult, LLMUsage
        return LLMResult(
            text="This is a mock summary for testing purposes.",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="mock",
            model="mock_model"
        )
    
    def get_model_name(self):
        return "mock_model"

def create_test_subtitle_file(temp_dir: Path, filename: str, content: str = None) -> Path:
    """创建测试用的字幕文件"""
    if content is None:
        # 默认的 SRT 格式内容
        content = """1
00:00:00,000 --> 00:00:05,000
This is the first subtitle line.

2
00:00:05,000 --> 00:00:10,000
This is the second subtitle line.

3
00:00:10,000 --> 00:00:15,000
This is the third subtitle line.
"""
    subtitle_file = temp_dir / filename
    subtitle_file.write_text(content, encoding='utf-8')
    return subtitle_file

def test_summary_i18n(language: str = "en-US"):
    """测试摘要部分的国际化
    
    Args:
        language: 测试语言（"zh-CN" 或 "en-US"）
    """
    print(f"\n{'='*80}")
    print(f"测试摘要部分国际化 - 语言: {language}")
    print(f"{'='*80}\n")
    
    # 设置语言
    set_language(language)
    print(f"当前语言: {get_language()}\n")
    
    # 创建临时目录
    with TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        # 创建测试用的视频信息
        video_info = VideoInfo(
            video_id="test_video_123",
            title="Test Video Title",
            url="https://www.youtube.com/watch?v=test_video_123",
            channel_name="Test Channel",
            channel_id="test_channel_123"
        )
        
        # 创建语言配置
        language_config = LanguageConfig(
            source_language="en",
            subtitle_target_languages=["zh-CN"],
            summary_language="zh-CN"
        )
        
        # 创建测试用的字幕文件
        original_subtitle = create_test_subtitle_file(temp_dir, "original.en.srt")
        translated_subtitle = create_test_subtitle_file(temp_dir, "translated.zh-CN.srt")
        
        # 准备下载结果和翻译结果
        download_result = {
            "original": original_subtitle
        }
        translation_result = {
            "zh-CN": translated_subtitle
        }
        
        # 创建摘要生成器
        mock_llm = MockLLMClient()
        summarizer = Summarizer(llm=mock_llm, language_config=language_config)
        
        # 设置日志上下文
        set_log_context(run_id="test_run", task="summarize", video_id=video_info.video_id)
        
        print("=" * 80)
        print("测试场景 1: 使用翻译字幕作为摘要源")
        print("=" * 80)
        
        # 测试选择摘要源（优先使用翻译字幕）
        source_path = summarizer._select_summary_source(
            summary_language="zh-CN",
            translation_result=translation_result,
            download_result=download_result
        )
        print(f"选择的摘要源: {source_path}\n")
        
        print("=" * 80)
        print("测试场景 2: 只有原始字幕，使用原始字幕作为摘要源")
        print("=" * 80)
        
        # 测试选择摘要源（只有原始字幕）
        source_path2 = summarizer._select_summary_source(
            summary_language="zh-CN",
            translation_result={},  # 没有翻译结果
            download_result=download_result
        )
        print(f"选择的摘要源: {source_path2}\n")
        
        print("=" * 80)
        print("测试场景 3: 使用其他语言的翻译字幕作为摘要源")
        print("=" * 80)
        
        # 测试选择摘要源（使用其他语言的翻译字幕）
        translation_result_other = {
            "ja": create_test_subtitle_file(temp_dir, "translated.ja.srt")
        }
        source_path3 = summarizer._select_summary_source(
            summary_language="zh-CN",  # 目标语言是 zh-CN，但没有对应的翻译
            translation_result=translation_result_other,
            download_result=download_result
        )
        print(f"选择的摘要源: {source_path3}\n")
        
        print("=" * 80)
        print("测试场景 4: 测试摘要 LLM 不可用的情况")
        print("=" * 80)
        
        # 测试摘要 LLM 不可用的情况（在 summarize 方法中）
        summarizer_no_llm = Summarizer(llm=None, language_config=language_config)
        try:
            result = summarizer_no_llm.summarize(
                video_info=video_info,
                language_config=language_config,
                translation_result=translation_result,
                download_result=download_result,
                output_path=temp_dir,
                force_regenerate=False
            )
            print(f"摘要结果: {result}\n")
        except Exception as e:
            print(f"预期错误: {e}\n")
        
        print("=" * 80)
        print("测试场景 5: 测试无可用字幕的情况")
        print("=" * 80)
        
        # 测试无可用字幕的情况
        try:
            result = summarizer.summarize(
                video_info=video_info,
                language_config=language_config,
                translation_result={},  # 没有翻译结果
                download_result={},  # 没有下载结果
                output_path=temp_dir,
                force_regenerate=False
            )
            print(f"摘要结果: {result}\n")
        except Exception as e:
            print(f"预期错误: {e}\n")
        
        print("=" * 80)
        print("测试完成！")
        print("=" * 80)
        print("\n提示：")
        print("  - 检查上面的日志输出，确认所有消息都使用了正确的语言")
        print("  - 如果看到中文硬编码，说明还有未修复的地方")
        print("  - 可以切换语言参数（zh-CN 或 en-US）来测试不同语言")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试摘要部分的国际化")
    parser.add_argument(
        "--lang",
        choices=["zh-CN", "en-US"],
        default="en-US",
        help="测试语言（默认: en-US）"
    )
    
    args = parser.parse_args()
    
    # 测试英文
    test_summary_i18n(language=args.lang)
    
    # 如果测试的是英文，也测试一下中文
    if args.lang == "en-US":
        print("\n\n")
        test_summary_i18n(language="zh-CN")

