"""
Manifest State Machine - 断点续传状态机

实现视频处理的状态管理，支持 kill 后 resume 继续处理。
所有状态写入使用原子操作（tmp + os.replace）确保无半截文件。

设计原则：
- 单一状态机：每个视频只有一个当前阶段
- 单写者：同一时间只有一个进程写入 manifest
- 原子写入：使用 tmp 文件 + os.replace 保证写入完整
- chunk 级恢复：翻译阶段支持 chunk 级别的恢复（通过 completed_chunks）
- P0-3: 脏标记 + 5秒定时保存，减少磁盘 IO
"""

import os
import json
import time
import atexit
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from threading import Lock, Thread, Event
import logging

logger = logging.getLogger(__name__)


class VideoStage(Enum):
    """视频处理阶段

    状态流转：
    PENDING → DETECTING → DOWNLOADING → TRANSLATING → SUMMARIZING → OUTPUTTING → DONE
                                                                              ↘ FAILED
                                                                              ↘ SKIPPED
    """
    PENDING = "pending"  # 待处理
    DETECTING = "detecting"  # 检测字幕中
    DOWNLOADING = "downloading"  # 下载字幕中
    TRANSLATING = "translating"  # 翻译中
    SUMMARIZING = "summarizing"  # 生成摘要中
    OUTPUTTING = "outputting"  # 输出文件中
    DONE = "done"  # 完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过（无字幕等）


@dataclass
class VideoManifest:
    """单个视频的状态 manifest

    Attributes:
        video_id: 视频 ID
        url: 视频 URL
        title: 视频标题
        stage: 当前处理阶段
        error: 错误信息（如果失败）
        error_type: 错误类型（用于判断是否可重试）
        retries: 已重试次数
        completed_chunks: 翻译阶段已完成的 chunk 索引列表
        output_files: 已生成的输出文件路径
        started_at: 开始处理时间
        updated_at: 最后更新时间
    """
    video_id: str
    url: str
    title: str = ""
    stage: VideoStage = VideoStage.PENDING
    error: Optional[str] = None
    error_type: Optional[str] = None
    retries: int = 0
    completed_chunks: List[int] = field(default_factory=list)
    output_files: Dict[str, str] = field(default_factory=dict)
    started_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "video_id": self.video_id,
            "url": self.url,
            "title": self.title,
            "stage": self.stage.value,
            "error": self.error,
            "error_type": self.error_type,
            "retries": self.retries,
            "completed_chunks": self.completed_chunks,
            "output_files": self.output_files,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoManifest":
        """从字典创建实例"""
        return cls(
            video_id=data["video_id"],
            url=data["url"],
            title=data.get("title", ""),
            stage=VideoStage(data.get("stage", "pending")),
            error=data.get("error"),
            error_type=data.get("error_type"),
            retries=data.get("retries", 0),
            completed_chunks=data.get("completed_chunks", []),
            output_files=data.get("output_files", {}),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at"),
        )

    def update_stage(self, new_stage: VideoStage) -> None:
        """更新阶段"""
        self.stage = new_stage
        self.updated_at = datetime.now().isoformat()
        if self.started_at is None:
            self.started_at = self.updated_at

    def mark_failed(self, error: str, error_type: Optional[str] = None) -> None:
        """标记为失败"""
        self.stage = VideoStage.FAILED
        self.error = error
        self.error_type = error_type
        self.updated_at = datetime.now().isoformat()

    def mark_skipped(self, reason: str) -> None:
        """标记为跳过"""
        self.stage = VideoStage.SKIPPED
        self.error = reason
        self.updated_at = datetime.now().isoformat()

    def add_completed_chunk(self, chunk_index: int) -> None:
        """添加已完成的翻译 chunk"""
        if chunk_index not in self.completed_chunks:
            self.completed_chunks.append(chunk_index)
            self.updated_at = datetime.now().isoformat()

    def is_resumable(self) -> bool:
        """是否可以恢复处理

        可恢复条件：
        - 阶段不是 DONE/SKIPPED
        - 如果是 FAILED，检查错误类型是否可重试
        """
        if self.stage in (VideoStage.DONE, VideoStage.SKIPPED):
            return False
        if self.stage == VideoStage.FAILED:
            # 只有可重试的错误类型才能恢复
            non_retryable = {"AUTH", "CONTENT", "INVALID_INPUT"}
            return self.error_type not in non_retryable
        return True


@dataclass
class BatchManifest:
    """批次处理的状态 manifest

    用于存储整个批次（频道/播放列表/URL 列表）的处理状态

    Attributes:
        batch_id: 批次 ID（格式：YYYYMMDD_HHMMSS）
        source: 来源描述（频道 URL / 播放列表 URL / "URL 列表"）
        total_videos: 总视频数
        videos: 各视频的状态
        created_at: 创建时间
        updated_at: 最后更新时间
    """
    batch_id: str
    source: str
    total_videos: int = 0
    videos: Dict[str, VideoManifest] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "batch_id": self.batch_id,
            "source": self.source,
            "total_videos": self.total_videos,
            "videos": {vid: v.to_dict() for vid, v in self.videos.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchManifest":
        """从字典创建实例"""
        videos = {}
        for vid, v_data in data.get("videos", {}).items():
            videos[vid] = VideoManifest.from_dict(v_data)

        return cls(
            batch_id=data["batch_id"],
            source=data["source"],
            total_videos=data.get("total_videos", 0),
            videos=videos,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def add_video(self, video_id: str, url: str, title: str = "") -> VideoManifest:
        """添加视频到批次"""
        if video_id not in self.videos:
            self.videos[video_id] = VideoManifest(
                video_id=video_id,
                url=url,
                title=title,
            )
            self.total_videos = len(self.videos)
        return self.videos[video_id]

    def get_video(self, video_id: str) -> Optional[VideoManifest]:
        """获取视频状态"""
        return self.videos.get(video_id)

    def get_resumable_videos(self) -> List[VideoManifest]:
        """获取可恢复的视频列表"""
        return [v for v in self.videos.values() if v.is_resumable()]

    def get_statistics(self) -> Dict[str, int]:
        """获取统计信息"""
        stats = {stage.value: 0 for stage in VideoStage}
        for video in self.videos.values():
            stats[video.stage.value] += 1
        return stats


class ManifestManager:
    """Manifest 管理器

    负责 manifest 的读写操作，保证：
    1. 原子写入：使用 tmp + os.replace
    2. 单写者：使用文件锁避免并发写入冲突
    3. P0-3: 脏标记 + 5秒定时保存，减少磁盘 IO
    """
    
    # P0-3: 定时保存间隔（秒）
    SAVE_INTERVAL_SECONDS = 5

    def __init__(self, manifest_dir: Path, auto_save: bool = True):
        """初始化管理器

        Args:
            manifest_dir: manifest 文件存储目录
            auto_save: 是否启用自动保存（默认 True）
        """
        self.manifest_dir = Path(manifest_dir)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        
        # P0-3: 脏标记和当前 manifest 引用
        self._dirty = False
        self._current_manifest: Optional[BatchManifest] = None
        
        # P0-3: 定时保存线程
        self._auto_save = auto_save
        self._stop_event = Event()
        self._save_thread: Optional[Thread] = None
        
        if auto_save:
            self._start_auto_save()
            # 注册 atexit 补充（异常退出时不会执行，但正常退出会）
            atexit.register(self.shutdown)
    
    def _start_auto_save(self) -> None:
        """启动定时保存线程"""
        self._save_thread = Thread(
            target=self._auto_save_loop,
            name="ManifestAutoSave",
            daemon=True
        )
        self._save_thread.start()
        logger.debug("Manifest auto-save thread started")
    
    def _auto_save_loop(self) -> None:
        """定时保存循环"""
        while not self._stop_event.wait(self.SAVE_INTERVAL_SECONDS):
            self.flush()
    
    def mark_dirty(self, manifest: Optional[BatchManifest] = None) -> None:
        """标记当前 manifest 为脏（有未保存的更改）
        
        Args:
            manifest: 要标记的 manifest，如果为 None 则使用当前 manifest
        """
        with self._lock:
            self._dirty = True
            if manifest is not None:
                self._current_manifest = manifest
    
    def flush(self) -> bool:
        """立即保存脏 manifest
        
        Returns:
            是否保存成功（如果没有脏数据，返回 True）
        """
        with self._lock:
            if not self._dirty or self._current_manifest is None:
                return True
            
            manifest = self._current_manifest
            self._dirty = False
        
        # 在锁外执行 IO 操作避免阻塞
        result = self._save_batch_internal(manifest)
        if result:
            logger.debug(f"Auto-saved manifest: {manifest.batch_id}")
        return result
    
    def shutdown(self) -> None:
        """关闭管理器，停止定时保存线程并保存最后的脏数据
        
        应在窗口关闭时调用
        """
        # 停止定时保存线程
        self._stop_event.set()
        if self._save_thread and self._save_thread.is_alive():
            self._save_thread.join(timeout=2.0)
        
        # 保存最后的脏数据
        self.flush()
        
        # 注销 atexit
        try:
            atexit.unregister(self.shutdown)
        except Exception:
            pass
        
        logger.debug("Manifest manager shutdown complete")

    def _get_manifest_path(self, batch_id: str) -> Path:
        """获取 manifest 文件路径"""
        return self.manifest_dir / f"{batch_id}.manifest.json"

    def _atomic_write(
        self, path: Path, data: Dict[str, Any], max_retries: int = 5
    ) -> bool:
        """原子写入 JSON 文件

        使用 tmp + os.replace 模式确保写入完整
        添加重试机制解决 Windows 并发写入冲突

        Args:
            path: 目标文件路径
            data: 要写入的数据
            max_retries: 最大重试次数

        Returns:
            是否写入成功
        """
        import time
        import uuid
        
        content = json.dumps(data, ensure_ascii=False, indent=2)
        
        for attempt in range(max_retries):
            # 使用唯一的 tmp 文件名避免冲突
            tmp_path = path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
            try:
                # 写入临时文件
                tmp_path.write_text(content, encoding="utf-8")
                # 原子替换
                os.replace(tmp_path, path)
                return True
            except OSError as e:
                # Windows 文件锁冲突 (winerror 5, 32) 或 Permission denied (errno 13)
                is_retryable = (
                    (hasattr(e, 'winerror') and e.winerror in (5, 32)) or
                    e.errno == 13  # Permission denied
                )
                if is_retryable:
                    # 指数退避重试
                    wait_time = (2 ** attempt) * 0.01 + (0.01 * (attempt + 1))
                    logger.debug(
                        f"Write conflict (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.3f}s"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Atomic write failed: {e}")
                    break
            finally:
                # 清理临时文件
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
        
        return False

    def create_batch(self, batch_id: str, source: str) -> BatchManifest:
        """创建新的批次 manifest

        Args:
            batch_id: 批次 ID
            source: 来源描述

        Returns:
            BatchManifest 实例
        """
        manifest = BatchManifest(
            batch_id=batch_id,
            source=source,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        return manifest

    def load_batch(self, batch_id: str, max_retries: int = 5) -> Optional[BatchManifest]:
        """加载批次 manifest

        Args:
            batch_id: 批次 ID
            max_retries: 最大重试次数

        Returns:
            BatchManifest 实例，如果不存在则返回 None
        """
        import time
        
        path = self._get_manifest_path(batch_id)
        if not path.exists():
            return None

        for attempt in range(max_retries):
            try:
                content = path.read_text(encoding="utf-8")
                data = json.loads(content)
                return BatchManifest.from_dict(data)
            except OSError as e:
                # Windows 文件锁冲突 (winerror 5, 32) 或 Permission denied (errno 13)
                is_retryable = (
                    (hasattr(e, 'winerror') and e.winerror in (5, 32)) or
                    e.errno == 13  # Permission denied
                )
                if is_retryable:
                    wait_time = (2 ** attempt) * 0.01 + (0.01 * (attempt + 1))
                    logger.debug(
                        f"Read conflict (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.3f}s"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to load manifest {path}: {e}")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse manifest {path}: {e}")
                return None
        
        logger.error(f"Failed to load manifest after {max_retries} retries: {path}")
        return None

    def _save_batch_internal(self, manifest: BatchManifest) -> bool:
        """内部保存方法（不使用脏标记）
        
        Args:
            manifest: BatchManifest 实例
            
        Returns:
            是否保存成功
        """
        manifest.updated_at = datetime.now().isoformat()
        path = self._get_manifest_path(manifest.batch_id)
        return self._atomic_write(path, manifest.to_dict())

    def save_batch(self, manifest: BatchManifest, immediate: bool = True) -> bool:
        """保存批次 manifest

        P0-3: 默认立即保存，immediate=False 时使用脏标记延迟保存

        Args:
            manifest: BatchManifest 实例
            immediate: 是否立即保存（默认 True），设为 False 使用脏标记延迟保存

        Returns:
            是否保存成功（延迟保存时始终返回 True）
        """
        if immediate or not self._auto_save:
            # 立即保存
            with self._lock:
                return self._save_batch_internal(manifest)
        else:
            # 延迟保存：标记为脏
            self.mark_dirty(manifest)
            return True

    def update_video_stage(
        self,
        manifest: BatchManifest,
        video_id: str,
        new_stage: VideoStage,
        save: bool = True,
    ) -> bool:
        """更新视频阶段

        Args:
            manifest: 批次 manifest
            video_id: 视频 ID
            new_stage: 新阶段
            save: 是否立即保存

        Returns:
            是否更新成功
        """
        video = manifest.get_video(video_id)
        if video is None:
            return False

        video.update_stage(new_stage)

        if save:
            return self.save_batch(manifest)
        return True

    def mark_video_failed(
        self,
        manifest: BatchManifest,
        video_id: str,
        error: str,
        error_type: Optional[str] = None,
        save: bool = True,
    ) -> bool:
        """标记视频失败

        Args:
            manifest: 批次 manifest
            video_id: 视频 ID
            error: 错误信息
            error_type: 错误类型
            save: 是否立即保存

        Returns:
            是否更新成功
        """
        video = manifest.get_video(video_id)
        if video is None:
            return False

        video.mark_failed(error, error_type)

        if save:
            return self.save_batch(manifest)
        return True

    def add_completed_chunk(
        self,
        manifest: BatchManifest,
        video_id: str,
        chunk_index: int,
        save: bool = True,
    ) -> bool:
        """添加已完成的翻译 chunk

        Args:
            manifest: 批次 manifest
            video_id: 视频 ID
            chunk_index: chunk 索引
            save: 是否立即保存

        Returns:
            是否更新成功
        """
        video = manifest.get_video(video_id)
        if video is None:
            return False

        video.add_completed_chunk(chunk_index)

        if save:
            return self.save_batch(manifest)
        return True

    def list_batches(self) -> List[str]:
        """列出所有批次 ID

        Returns:
            批次 ID 列表
        """
        batch_ids = []
        for path in self.manifest_dir.glob("*.manifest.json"):
            batch_id = path.stem.replace(".manifest", "")
            batch_ids.append(batch_id)
        return sorted(batch_ids, reverse=True)  # 最新的在前

    def delete_batch(self, batch_id: str) -> bool:
        """删除批次 manifest

        Args:
            batch_id: 批次 ID

        Returns:
            是否删除成功
        """
        path = self._get_manifest_path(batch_id)
        try:
            if path.exists():
                path.unlink()
            return True
        except OSError as e:
            logger.error(f"Failed to delete manifest {path}: {e}")
            return False


# 便捷函数
def generate_batch_id() -> str:
    """生成批次 ID

    格式：YYYYMMDD_HHMMSS

    Returns:
        批次 ID 字符串
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")
