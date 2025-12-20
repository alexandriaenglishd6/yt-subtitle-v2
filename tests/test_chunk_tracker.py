"""
Tests for core/state/chunk_tracker.py

运行: python -m pytest tests/test_chunk_tracker.py -v
"""

import pytest
import tempfile
from pathlib import Path

from core.state.chunk_tracker import (
    ChunkTracker,
    ChunkProgress,
    SubtitleChunk,
    create_chunk_tracker,
)


# 测试用 SRT 内容
SAMPLE_SRT = """1
00:00:00,000 --> 00:00:02,000
Hello world.

2
00:00:02,000 --> 00:00:04,000
This is a test.

3
00:00:04,000 --> 00:00:06,000
Testing chunk tracker.

4
00:00:06,000 --> 00:00:08,000
Fourth subtitle entry.

5
00:00:08,000 --> 00:00:10,000
Fifth entry here.
"""


class TestChunkProgress:
    """ChunkProgress 测试"""

    def test_create_progress(self):
        """测试创建进度"""
        progress = ChunkProgress(total_chunks=5)
        assert progress.total_chunks == 5
        assert progress.completed_chunks == []

    def test_is_complete(self):
        """测试完成判断"""
        progress = ChunkProgress(total_chunks=3, completed_chunks=[0, 1, 2])
        assert progress.is_complete is True

        progress2 = ChunkProgress(total_chunks=3, completed_chunks=[0, 1])
        assert progress2.is_complete is False

    def test_progress_percent(self):
        """测试进度百分比"""
        progress = ChunkProgress(total_chunks=4, completed_chunks=[0, 1])
        assert progress.progress_percent == 50.0

    def test_to_from_dict(self):
        """测试序列化"""
        progress = ChunkProgress(total_chunks=3, completed_chunks=[0, 1])
        d = progress.to_dict()
        loaded = ChunkProgress.from_dict(d)
        assert loaded.total_chunks == 3
        assert loaded.completed_chunks == [0, 1]


class TestChunkTracker:
    """ChunkTracker 测试"""

    def test_split_subtitle(self):
        """测试字幕拆分"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,  # 每个 chunk 2 个条目
            )
            chunks = tracker.split_subtitle(SAMPLE_SRT)

            # 5 个条目，每个 chunk 2 个，应该有 3 个 chunk
            assert len(chunks) == 3
            assert chunks[0].start_index == 1
            assert chunks[0].end_index == 2
            assert chunks[2].start_index == 5
            assert chunks[2].end_index == 5

    def test_mark_chunk_completed(self):
        """测试标记完成"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,
            )
            tracker.split_subtitle(SAMPLE_SRT)

            # 标记第一个 chunk 完成
            translated = "翻译后的内容"
            success = tracker.mark_chunk_completed(0, translated)
            assert success is True
            assert 0 in tracker.progress.completed_chunks

    def test_get_pending_chunks(self):
        """测试获取待翻译 chunks"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,
            )
            tracker.split_subtitle(SAMPLE_SRT)

            # 初始所有 chunk 都待翻译
            pending = tracker.get_pending_chunks()
            assert len(pending) == 3

            # 完成一个后
            tracker.mark_chunk_completed(0, "translated 0")
            pending = tracker.get_pending_chunks()
            assert len(pending) == 2

    def test_progress_persistence(self):
        """测试进度持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 第一个 tracker 处理部分
            tracker1 = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,
            )
            tracker1.split_subtitle(SAMPLE_SRT)
            tracker1.mark_chunk_completed(0, "translated 0")
            tracker1.mark_chunk_completed(1, "translated 1")

            # 创建新的 tracker（模拟恢复）
            tracker2 = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,
            )
            # 重新拆分以加载 chunks
            tracker2.split_subtitle(SAMPLE_SRT)

            # 应该已经加载了之前的进度
            assert 0 in tracker2.progress.completed_chunks
            assert 1 in tracker2.progress.completed_chunks
            pending = tracker2.get_pending_chunks()
            assert len(pending) == 1  # 只剩一个待翻译

    def test_merge_translated_chunks(self):
        """测试合并翻译结果"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,
            )
            tracker.split_subtitle(SAMPLE_SRT)

            # 翻译所有 chunks
            for i, chunk in enumerate(tracker.chunks):
                tracker.mark_chunk_completed(i, f"Translated chunk {i}")

            merged = tracker.merge_translated_chunks()
            assert merged is not None
            assert "Translated chunk 0" in merged
            assert "Translated chunk 2" in merged

    def test_cleanup(self):
        """测试清理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ChunkTracker(
                video_id="test123",
                target_language="zh-CN",
                work_dir=Path(tmpdir),
                chunk_size=2,
            )
            tracker.split_subtitle(SAMPLE_SRT)

            # 确保文件存在
            assert tracker.chunks_dir.exists()
            assert tracker.progress_file.exists()

            # 清理
            tracker.cleanup()

            assert not tracker.chunks_dir.exists()
            assert not tracker.progress_file.exists()


class TestCreateChunkTracker:
    """create_chunk_tracker 便捷函数测试"""

    def test_create(self):
        """测试创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = create_chunk_tracker(
                video_id="test",
                target_language="en",
                work_dir=Path(tmpdir),
            )
            assert tracker.video_id == "test"
            assert tracker.target_language == "en"
