#!/usr/bin/env python
"""
断点恢复端到端测试脚本

测试场景：
1. Manifest 状态机基本功能
2. 模拟 kill 后恢复
3. ChunkTracker 分块恢复
4. 原子写入验证
5. 状态机一致性

用法：
    python scripts/test_checkpoint_resume.py
"""

import sys
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    details: Optional[str] = None


def test_manifest_state_machine():
    """测试 manifest 状态机基本功能"""
    from core.state.manifest import ManifestManager, VideoStage, BatchManifest
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_dir = Path(tmpdir)
        manager = ManifestManager(manifest_dir)
        
        # 创建批次
        batch_id = "test_batch_001"
        batch = manager.create_batch(batch_id, source="test")
        
        assert batch is not None
        assert isinstance(batch, BatchManifest)
        
        # 添加视频
        batch.add_video("test_video_001", "https://youtube.com/watch?v=123", "Test Video")
        
        # 验证视频状态
        video = batch.get_video("test_video_001")
        assert video is not None
        assert video.stage == VideoStage.PENDING
        
        # 更新阶段
        video.update_stage(VideoStage.DETECTING)
        assert video.stage == VideoStage.DETECTING
        
        video.update_stage(VideoStage.DOWNLOADING)
        assert video.stage == VideoStage.DOWNLOADING
        
        # 保存批次 (save_batch 只需要 manifest 参数)
        success = manager.save_batch(batch)
        assert success
        
        return TestResult(
            name="Manifest State Machine",
            passed=True,
            message="状态机推进正常: PENDING → DETECTING → DOWNLOADING"
        )


def test_manifest_persistence():
    """测试 manifest 持久化（模拟 kill 后恢复）"""
    from core.state.manifest import ManifestManager, VideoStage
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_dir = Path(tmpdir)
        batch_id = "persist_test"
        
        # 第一次运行：创建并更新状态
        manager1 = ManifestManager(manifest_dir)
        batch1 = manager1.create_batch(batch_id, source="test")
        batch1.add_video("vid_001", "url1", "Video 1")
        batch1.add_video("vid_002", "url2", "Video 2")
        
        vid1 = batch1.get_video("vid_001")
        vid1.update_stage(VideoStage.TRANSLATING)
        
        manager1.save_batch(batch1)
        
        # "kill" - 释放 manager1（模拟进程终止）
        del manager1, batch1
        
        # 第二次运行：恢复状态
        manager2 = ManifestManager(manifest_dir)
        batch2 = manager2.load_batch(batch_id)
        
        # 验证状态被正确恢复
        assert batch2 is not None
        assert len(batch2.videos) == 2
        
        vid1_restored = batch2.get_video("vid_001")
        assert vid1_restored.stage == VideoStage.TRANSLATING
        
        vid2_restored = batch2.get_video("vid_002")
        assert vid2_restored.stage == VideoStage.PENDING
        
        return TestResult(
            name="Manifest Persistence (Kill → Resume)",
            passed=True,
            message="状态持久化正常: 2 个视频状态正确恢复"
        )


def test_chunk_tracker_resume():
    """测试 ChunkTracker 分块恢复"""
    from core.state.chunk_tracker import ChunkTracker
    
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        
        # 模拟字幕内容
        test_srt = """1
00:00:00,000 --> 00:00:05,000
Hello world

2
00:00:05,000 --> 00:00:10,000
This is a test

3
00:00:10,000 --> 00:00:15,000
Third subtitle

4
00:00:15,000 --> 00:00:20,000
Fourth line

5
00:00:20,000 --> 00:00:25,000
Fifth entry
"""
        
        # 第一次运行：处理部分 chunk
        tracker1 = ChunkTracker(
            video_id="test_vid",
            target_language="zh-CN",
            work_dir=work_dir,
            chunk_size=2
        )
        chunks = tracker1.split_subtitle(test_srt)
        assert len(chunks) >= 2
        
        # 完成前 2 个 chunk
        tracker1.mark_chunk_completed(0, "翻译结果 1")
        tracker1.mark_chunk_completed(1, "翻译结果 2")
        
        # 获取状态确认已完成
        status1 = tracker1.get_status()
        assert status1["completed"] >= 2
        
        # "kill"
        del tracker1
        
        # 第二次运行：恢复
        tracker2 = ChunkTracker(
            video_id="test_vid",
            target_language="zh-CN",
            work_dir=work_dir,
            chunk_size=2
        )
        # 需要重新拆分以建立 chunk 列表
        tracker2.split_subtitle(test_srt)
        
        # 验证已完成的不再是 pending
        pending = tracker2.get_pending_chunks()
        status2 = tracker2.get_status()
        
        # 应该有 2 个已完成
        assert status2["completed"] >= 2, f"Expected 2 completed, got {status2['completed']}"
        
        return TestResult(
            name="Chunk Tracker Resume",
            passed=True,
            message=f"分块恢复正常: {status2['completed']} 个已完成, {len(pending)} 个待处理"
        )


def test_atomic_write():
    """测试原子写入（tmp + replace）"""
    from core.state.manifest import ManifestManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_dir = Path(tmpdir)
        batch_id = "atomic_test"
        
        # 创建 manifest
        manager = ManifestManager(manifest_dir)
        batch = manager.create_batch(batch_id, source="atomic_test")
        batch.add_video("atomic_video", "url", "Atomic Test Video")
        manager.save_batch(batch)
        
        # 验证文件存在且可解析
        manifest_path = manifest_dir / f"{batch_id}.manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert "videos" in data
        assert "atomic_video" in data["videos"]
        
        # 验证没有遗留 .tmp 文件
        tmp_files = list(manifest_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"发现遗留 tmp 文件: {tmp_files}"
        
        return TestResult(
            name="Atomic Write (tmp + replace)",
            passed=True,
            message="原子写入正常: 文件完整, 无遗留 tmp"
        )


def test_state_machine_consistency():
    """测试状态机一致性（done 状态）"""
    from core.state.manifest import ManifestManager, VideoStage
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_dir = Path(tmpdir)
        manager = ManifestManager(manifest_dir)
        
        batch = manager.create_batch("consistency_test", source="test")
        batch.add_video("done_vid", "url", "Done Video")
        
        video = batch.get_video("done_vid")
        
        # 推进到 DONE
        video.update_stage(VideoStage.DETECTING)
        video.update_stage(VideoStage.DOWNLOADING)
        video.update_stage(VideoStage.TRANSLATING)
        video.update_stage(VideoStage.SUMMARIZING)
        video.update_stage(VideoStage.OUTPUTTING)
        video.update_stage(VideoStage.DONE)
        
        assert video.stage == VideoStage.DONE
        
        # 验证 is_resumable 返回 False
        assert not video.is_resumable()
        
        return TestResult(
            name="State Machine Consistency",
            passed=True,
            message="状态机一致性: DONE 状态验证通过, is_resumable=False"
        )


def test_resumable_detection():
    """测试可恢复状态检测"""
    from core.state.manifest import ManifestManager, VideoStage
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_dir = Path(tmpdir)
        manager = ManifestManager(manifest_dir)
        
        batch = manager.create_batch("resumable_test", source="test")
        
        # 添加不同状态的视频
        batch.add_video("vid_pending", "url1", "Pending")
        batch.add_video("vid_translating", "url2", "Translating")
        batch.add_video("vid_done", "url3", "Done")
        batch.add_video("vid_failed", "url4", "Failed")
        
        batch.get_video("vid_translating").update_stage(VideoStage.TRANSLATING)
        batch.get_video("vid_done").update_stage(VideoStage.DONE)
        batch.get_video("vid_failed").mark_failed("Test error", "NETWORK")
        
        # 获取可恢复列表
        resumable = batch.get_resumable_videos()
        resumable_ids = [v.video_id for v in resumable]
        
        # PENDING 和 TRANSLATING 应该可恢复
        assert "vid_pending" in resumable_ids
        assert "vid_translating" in resumable_ids
        # DONE 不可恢复
        assert "vid_done" not in resumable_ids
        # FAILED 可能可恢复（取决于错误类型）
        
        return TestResult(
            name="Resumable Detection",
            passed=True,
            message=f"可恢复检测正常: {len(resumable)} 个可恢复"
        )


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("断点恢复端到端测试")
    print("=" * 60)
    print()
    
    tests = [
        test_manifest_state_machine,
        test_manifest_persistence,
        test_chunk_tracker_resume,
        test_atomic_write,
        test_state_machine_consistency,
        test_resumable_detection,
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status} | {result.name}")
            print(f"       {result.message}")
            if result.details:
                print(f"       {result.details}")
            print()
        except Exception as e:
            import traceback
            results.append(TestResult(
                name=test_func.__name__,
                passed=False,
                message=str(e)
            ))
            print(f"❌ FAIL | {test_func.__name__}")
            print(f"       Error: {e}")
            traceback.print_exc()
            print()
    
    print("=" * 60)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"结果: {passed}/{total} 通过")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
