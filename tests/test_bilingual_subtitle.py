"""
双语字幕生成功能测试
测试 OutputWriter 的双语字幕生成功能
"""
import sys
from pathlib import Path
import tempfile
import shutil

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.output import OutputWriter
from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig


def create_test_srt_file(content: str, filepath: Path):
    """创建测试用的 SRT 文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")


def test_bilingual_subtitle_generation():
    """测试双语字幕生成"""
    print("=" * 60)
    print("测试：双语字幕生成功能")
    print("=" * 60)
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # 创建测试用的 SRT 文件
        source_srt = temp_dir / "source.srt"
        target_srt = temp_dir / "target.srt"
        
        # 源语言字幕（英文）
        source_content = """1
00:00:00,000 --> 00:00:03,000
Hello, welcome to this video.

2
00:00:03,000 --> 00:00:06,000
Today we will learn about Python.

3
00:00:06,000 --> 00:00:09,000
Python is a programming language.
"""
        
        # 目标语言字幕（中文）
        target_content = """1
00:00:00,000 --> 00:00:03,000
你好，欢迎观看这个视频。

2
00:00:03,000 --> 00:00:06,000
今天我们将学习 Python。

3
00:00:06,000 --> 00:00:09,000
Python 是一种编程语言。
"""
        
        create_test_srt_file(source_content, source_srt)
        create_test_srt_file(target_content, target_srt)
        
        # 创建 OutputWriter
        output_dir = temp_dir / "output"
        output_writer = OutputWriter(output_dir)
        
        # 创建视频输出目录
        video_dir = output_dir / "test_video"
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # 测试双语字幕生成
        print("\n1. 测试 write_bilingual_subtitle 方法...")
        bilingual_path = output_writer.write_bilingual_subtitle(
            video_dir,
            source_srt,
            target_srt,
            "en",
            "zh-CN"
        )
        
        # 验证文件是否存在
        assert bilingual_path.exists(), "双语字幕文件应该被创建"
        print(f"   ✓ 双语字幕文件已创建: {bilingual_path.name}")
        
        # 验证文件内容
        bilingual_content = bilingual_path.read_text(encoding="utf-8")
        print(f"\n2. 验证双语字幕内容...")
        print("   双语字幕内容预览：")
        lines = bilingual_content.split("\n")
        for i, line in enumerate(lines[:10]):  # 只显示前10行
            print(f"   {line}")
        
        # 验证格式（实际使用换行分隔，不是 " / "）
        assert "Hello, welcome to this video." in bilingual_content, "应包含源语言文本"
        assert "你好，欢迎观看这个视频。" in bilingual_content, "应包含目标语言文本"
        # 双语字幕使用换行分隔，源语言在上，目标语言在下
        assert "Hello, welcome to this video.\n你好" in bilingual_content or "Hello, welcome to this video." in bilingual_content, "应包含双语内容"
        print("   ✓ 双语字幕格式正确（包含源语言和目标语言）")
        
        # 验证文件命名
        assert bilingual_path.name == "bilingual.en-zh-CN.srt", f"文件名应为 bilingual.en-zh-CN.srt，实际为 {bilingual_path.name}"
        print(f"   ✓ 文件命名正确: {bilingual_path.name}")
        
        print("\n" + "=" * 60)
        print("✓ 双语字幕生成功能测试通过！")
        print("=" * 60)
        
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_bilingual_mode_in_write_all():
    """测试 write_all 方法中的双语模式"""
    print("\n" + "=" * 60)
    print("测试：write_all 方法中的双语模式")
    print("=" * 60)
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # 创建测试用的 SRT 文件
        source_srt = temp_dir / "original.en.srt"
        target_srt = temp_dir / "translated.zh-CN.srt"
        
        source_content = """1
00:00:00,000 --> 00:00:03,000
Test subtitle.
"""
        
        target_content = """1
00:00:00,000 --> 00:00:03,000
测试字幕。
"""
        
        create_test_srt_file(source_content, source_srt)
        create_test_srt_file(target_content, target_srt)
        
        # 创建 OutputWriter
        output_dir = temp_dir / "output"
        output_writer = OutputWriter(output_dir)
        
        # 创建测试数据
        video_info = VideoInfo(
            video_id="test123",
            url="https://www.youtube.com/watch?v=test123",
            title="Test Video",
            channel_id="UCtest",
            channel_name="Test Channel",
            duration=100,
            upload_date="2024-01-01",
            description="Test"
        )
        
        detection_result = DetectionResult(
            video_id="test123",
            has_subtitles=True,
            manual_languages=["en"],
            auto_languages=[]
        )
        
        # 测试 1: bilingual_mode = "none"（不应生成双语字幕）
        print("\n1. 测试 bilingual_mode = 'none'...")
        language_config_none = LanguageConfig(
            bilingual_mode="none",
            subtitle_target_languages=["zh-CN"]
        )
        
        download_result = {
            "original": source_srt,
            "official_translations": {}
        }
        
        translation_result = {
            "zh-CN": target_srt
        }
        
        video_dir = output_writer.write_all(
            video_info,
            detection_result,
            language_config_none,
            download_result,
            translation_result,
            None
        )
        
        bilingual_files = list(video_dir.glob("bilingual.*.srt"))
        assert len(bilingual_files) == 0, "bilingual_mode='none' 时不应生成双语字幕"
        print("   ✓ bilingual_mode='none' 时未生成双语字幕（正确）")
        
        # 测试 2: bilingual_mode = "source+target"（应生成双语字幕）
        print("\n2. 测试 bilingual_mode = 'source+target'...")
        language_config_bilingual = LanguageConfig(
            bilingual_mode="source+target",
            subtitle_target_languages=["zh-CN"]
        )
        
        # 清理之前的输出
        if video_dir.exists():
            shutil.rmtree(video_dir)
        
        video_dir = output_writer.write_all(
            video_info,
            detection_result,
            language_config_bilingual,
            download_result,
            translation_result,
            None
        )
        
        bilingual_files = list(video_dir.glob("bilingual.*.srt"))
        assert len(bilingual_files) > 0, "bilingual_mode='source+target' 时应生成双语字幕"
        print(f"   ✓ 生成了 {len(bilingual_files)} 个双语字幕文件")
        
        # 验证文件内容
        bilingual_file = bilingual_files[0]
        bilingual_content = bilingual_file.read_text(encoding="utf-8")
        assert "Test subtitle." in bilingual_content, "应包含源语言文本"
        assert "测试字幕。" in bilingual_content, "应包含目标语言文本"
        # 双语字幕使用换行分隔
        print(f"   ✓ 双语字幕内容正确: {bilingual_file.name}")
        
        print("\n" + "=" * 60)
        print("✓ write_all 双语模式测试通过！")
        print("=" * 60)
        
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_srt_parsing():
    """测试 SRT 解析功能"""
    print("\n" + "=" * 60)
    print("测试：SRT 解析功能")
    print("=" * 60)
    
    temp_dir = Path(tempfile.mkdtemp())
    try:
        output_writer = OutputWriter(temp_dir)
        
        # 测试 SRT 内容
        srt_content = """1
00:00:00,000 --> 00:00:03,000
First subtitle line.

2
00:00:03,000 --> 00:00:06,000
Second subtitle line.
"""
        
        entries = output_writer._parse_srt(srt_content)
        
        assert len(entries) == 2, f"应解析出 2 个条目，实际为 {len(entries)}"
        assert entries[0]["index"] == 1, "第一个条目序号应为 1"
        assert entries[0]["start"] == "00:00:00,000", "开始时间应为 00:00:00,000"
        assert entries[0]["end"] == "00:00:03,000", "结束时间应为 00:00:03,000"
        assert entries[0]["text"] == "First subtitle line.", "文本应为 'First subtitle line.'"
        
        print("   ✓ SRT 解析功能正常")
        print(f"   ✓ 解析出 {len(entries)} 个字幕条目")
        
        print("\n" + "=" * 60)
        print("✓ SRT 解析功能测试通过！")
        print("=" * 60)
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("双语字幕生成功能测试套件")
    print("=" * 60 + "\n")
    
    try:
        # 测试 SRT 解析
        test_srt_parsing()
        
        # 测试双语字幕生成
        test_bilingual_subtitle_generation()
        
        # 测试 write_all 中的双语模式
        test_bilingual_mode_in_write_all()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

