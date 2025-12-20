"""
Tests for core/subtitle/merger.py

运行: python -m pytest tests/test_subtitle_merger.py -v
"""

import pytest
from core.subtitle.merger import (
    SubtitleMerger,
    SubtitleCue,
    MergedBlock,
    MergerConfig,
    merge_subtitle_file,
)


class TestSubtitleCue:
    """SubtitleCue 单元测试"""

    def test_cue_creation(self):
        """测试 cue 创建"""
        cue = SubtitleCue(index=1, start_time=0.0, end_time=1.5, text="Hello world")
        assert cue.index == 1
        assert cue.start_time == 0.0
        assert cue.end_time == 1.5
        assert cue.text == "Hello world"


class TestMergedBlock:
    """MergedBlock 单元测试"""

    def test_block_to_srt_timestamp(self):
        """测试时间戳转换"""
        block = MergedBlock(start_time=3661.500, end_time=3665.750, text="Test")
        assert block.to_srt_timestamp(3661.500) == "01:01:01,500"
        assert block.to_srt_timestamp(0.0) == "00:00:00,000"
        assert block.to_srt_timestamp(59.999) == "00:00:59,999"

    def test_block_to_srt_entry(self):
        """测试 SRT 条目生成"""
        block = MergedBlock(start_time=1.0, end_time=2.5, text="Hello world")
        entry = block.to_srt_entry(1)
        assert "1\n" in entry
        assert "00:00:01,000 --> 00:00:02,500" in entry
        assert "Hello world" in entry


class TestSubtitleMerger:
    """SubtitleMerger 单元测试"""

    def test_merge_empty_cues(self):
        """测试空 cue 列表"""
        merger = SubtitleMerger()
        blocks = merger.merge_cues([])
        assert blocks == []

    def test_merge_single_cue(self):
        """测试单个 cue"""
        merger = SubtitleMerger()
        cues = [SubtitleCue(1, 0.0, 1.0, "Hello")]
        blocks = merger.merge_cues(cues)
        assert len(blocks) == 1
        assert blocks[0].text == "Hello"

    def test_merge_by_punctuation(self):
        """测试标点断句合并"""
        merger = SubtitleMerger()
        cues = [
            SubtitleCue(1, 0.0, 1.0, "Hello"),
            SubtitleCue(2, 1.1, 2.0, "world."),  # 以句号结尾
            SubtitleCue(3, 2.1, 3.0, "New sentence"),
        ]
        blocks = merger.merge_cues(cues)
        # 第一块: "Hello world."
        # 第二块: "New sentence"
        assert len(blocks) == 2
        assert "Hello" in blocks[0].text
        assert "world." in blocks[0].text
        assert blocks[1].text == "New sentence"

    def test_merge_by_time_gap(self):
        """测试时间间隔断句"""
        config = MergerConfig(time_gap_threshold=1.2)
        merger = SubtitleMerger(config)
        cues = [
            SubtitleCue(1, 0.0, 1.0, "First part"),
            SubtitleCue(2, 1.1, 2.0, "continues"),  # 间隔 0.1s，继续合并
            SubtitleCue(3, 5.0, 6.0, "New block"),  # 间隔 3s > 1.2s，新块
        ]
        blocks = merger.merge_cues(cues)
        assert len(blocks) == 2
        assert "First part" in blocks[0].text
        assert "continues" in blocks[0].text
        assert blocks[1].text == "New block"

    def test_merge_by_max_length(self):
        """测试最大长度限制"""
        config = MergerConfig(max_block_length=20)
        merger = SubtitleMerger(config)
        cues = [
            SubtitleCue(1, 0.0, 1.0, "Short text"),
            SubtitleCue(2, 1.1, 2.0, "Another text that is longer"),
        ]
        blocks = merger.merge_cues(cues)
        # 合并后超过 20 字符，应拆分为两块
        assert len(blocks) == 2

    def test_block_time_range(self):
        """测试块时间范围正确性"""
        merger = SubtitleMerger()
        cues = [
            SubtitleCue(1, 0.5, 1.0, "Hello"),
            SubtitleCue(2, 1.1, 2.0, "world"),
            SubtitleCue(3, 2.1, 3.5, "here."),
        ]
        blocks = merger.merge_cues(cues)
        # 应合并为一个块，时间范围 0.5 - 3.5
        assert len(blocks) == 1
        assert blocks[0].start_time == 0.5
        assert blocks[0].end_time == 3.5

    def test_parse_srt_content(self):
        """测试 SRT 内容解析"""
        srt_content = """1
00:00:01,000 --> 00:00:02,500
Hello world

2
00:00:03,000 --> 00:00:04,500
This is a test
"""
        merger = SubtitleMerger()
        cues = merger.parse_srt_content(srt_content)
        assert len(cues) == 2
        assert cues[0].text == "Hello world"
        assert cues[0].start_time == 1.0
        assert cues[0].end_time == 2.5
        assert cues[1].text == "This is a test"

    def test_blocks_to_srt(self):
        """测试块转 SRT 格式"""
        merger = SubtitleMerger()
        blocks = [
            MergedBlock(start_time=1.0, end_time=2.5, text="Hello world"),
            MergedBlock(start_time=3.0, end_time=4.5, text="Next line"),
        ]
        srt = merger.blocks_to_srt(blocks)
        assert "1\n00:00:01,000 --> 00:00:02,500\nHello world" in srt
        assert "2\n00:00:03,000 --> 00:00:04,500\nNext line" in srt

    def test_chinese_punctuation(self):
        """测试中文标点断句"""
        merger = SubtitleMerger()
        cues = [
            SubtitleCue(1, 0.0, 1.0, "你好"),
            SubtitleCue(2, 1.1, 2.0, "世界。"),  # 中文句号
            SubtitleCue(3, 2.1, 3.0, "新句子"),
        ]
        blocks = merger.merge_cues(cues)
        assert len(blocks) == 2
        assert "你好" in blocks[0].text
        assert "世界。" in blocks[0].text
