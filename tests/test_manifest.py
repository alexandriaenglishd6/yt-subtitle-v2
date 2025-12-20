"""
Tests for core/state/manifest.py

运行: python -m pytest tests/test_manifest.py -v
"""

import pytest
import tempfile
from pathlib import Path

from core.state.manifest import (
    VideoStage,
    VideoManifest,
    BatchManifest,
    ManifestManager,
    generate_batch_id,
)


class TestVideoStage:
    """VideoStage 枚举测试"""

    def test_stage_values(self):
        """测试阶段值"""
        assert VideoStage.PENDING.value == "pending"
        assert VideoStage.DONE.value == "done"
        assert VideoStage.FAILED.value == "failed"

    def test_stage_from_string(self):
        """测试从字符串创建阶段"""
        stage = VideoStage("pending")
        assert stage == VideoStage.PENDING


class TestVideoManifest:
    """VideoManifest 测试"""

    def test_create_manifest(self):
        """测试创建 manifest"""
        m = VideoManifest(
            video_id="test123",
            url="https://youtube.com/watch?v=test123",
            title="Test Video",
        )
        assert m.video_id == "test123"
        assert m.stage == VideoStage.PENDING
        assert m.completed_chunks == []

    def test_to_dict(self):
        """测试转换为字典"""
        m = VideoManifest(video_id="test", url="http://example.com")
        d = m.to_dict()
        assert d["video_id"] == "test"
        assert d["stage"] == "pending"

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "video_id": "test",
            "url": "http://example.com",
            "stage": "downloading",
        }
        m = VideoManifest.from_dict(data)
        assert m.video_id == "test"
        assert m.stage == VideoStage.DOWNLOADING

    def test_update_stage(self):
        """测试更新阶段"""
        m = VideoManifest(video_id="test", url="http://example.com")
        m.update_stage(VideoStage.DETECTING)
        assert m.stage == VideoStage.DETECTING
        assert m.started_at is not None
        assert m.updated_at is not None

    def test_mark_failed(self):
        """测试标记失败"""
        m = VideoManifest(video_id="test", url="http://example.com")
        m.mark_failed("Test error", "NETWORK")
        assert m.stage == VideoStage.FAILED
        assert m.error == "Test error"
        assert m.error_type == "NETWORK"

    def test_is_resumable(self):
        """测试可恢复判断"""
        m = VideoManifest(video_id="test", url="http://example.com")
        assert m.is_resumable() is True

        m.update_stage(VideoStage.DONE)
        assert m.is_resumable() is False

        m2 = VideoManifest(video_id="test2", url="http://example.com")
        m2.mark_failed("Network error", "NETWORK")
        assert m2.is_resumable() is True  # NETWORK 可重试

        m3 = VideoManifest(video_id="test3", url="http://example.com")
        m3.mark_failed("Auth error", "AUTH")
        assert m3.is_resumable() is False  # AUTH 不可重试

    def test_add_completed_chunk(self):
        """测试添加已完成 chunk"""
        m = VideoManifest(video_id="test", url="http://example.com")
        m.add_completed_chunk(0)
        m.add_completed_chunk(1)
        m.add_completed_chunk(0)  # 重复添加
        assert m.completed_chunks == [0, 1]


class TestBatchManifest:
    """BatchManifest 测试"""

    def test_create_batch(self):
        """测试创建批次"""
        b = BatchManifest(batch_id="20231219_120000", source="test")
        assert b.batch_id == "20231219_120000"
        assert b.total_videos == 0

    def test_add_video(self):
        """测试添加视频"""
        b = BatchManifest(batch_id="test", source="test")
        v = b.add_video("vid1", "http://example.com/1", "Video 1")
        assert v.video_id == "vid1"
        assert b.total_videos == 1

    def test_get_resumable_videos(self):
        """测试获取可恢复视频"""
        b = BatchManifest(batch_id="test", source="test")
        b.add_video("vid1", "http://example.com/1")
        b.add_video("vid2", "http://example.com/2")
        b.videos["vid2"].update_stage(VideoStage.DONE)

        resumable = b.get_resumable_videos()
        assert len(resumable) == 1
        assert resumable[0].video_id == "vid1"


class TestManifestManager:
    """ManifestManager 测试"""

    def test_create_and_save_batch(self):
        """测试创建和保存批次"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ManifestManager(Path(tmpdir))
            batch = manager.create_batch("test_batch", "test source")
            batch.add_video("vid1", "http://example.com/1")

            success = manager.save_batch(batch)
            assert success is True

            # 验证文件存在
            path = Path(tmpdir) / "test_batch.manifest.json"
            assert path.exists()

    def test_load_batch(self):
        """测试加载批次"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ManifestManager(Path(tmpdir))
            batch = manager.create_batch("test_batch", "test source")
            batch.add_video("vid1", "http://example.com/1")
            manager.save_batch(batch)

            loaded = manager.load_batch("test_batch")
            assert loaded is not None
            assert loaded.batch_id == "test_batch"
            assert len(loaded.videos) == 1

    def test_update_video_stage(self):
        """测试更新视频阶段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ManifestManager(Path(tmpdir))
            batch = manager.create_batch("test", "test")
            batch.add_video("vid1", "http://example.com/1")

            success = manager.update_video_stage(
                batch, "vid1", VideoStage.DOWNLOADING
            )
            assert success is True
            assert batch.videos["vid1"].stage == VideoStage.DOWNLOADING


class TestGenerateBatchId:
    """generate_batch_id 测试"""

    def test_format(self):
        """测试格式"""
        batch_id = generate_batch_id()
        # 格式: YYYYMMDD_HHMMSS
        assert len(batch_id) == 15
        assert batch_id[8] == "_"
