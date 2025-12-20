"""
Chunk Tracker - 翻译 chunk 级恢复模块

将长字幕文件拆分为多个 chunk 进行翻译，支持中途失败后恢复。
与 manifest.py 状态机集成，记录已完成的 chunk。

设计原则：
- 每个 chunk 独立翻译和保存
- 失败后可从最后一个成功的 chunk 继续
- 原子写入保证每个 chunk 完整性
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class SubtitleChunk:
    """字幕块

    Attributes:
        index: chunk 索引（从 0 开始）
        start_index: 起始字幕条目序号
        end_index: 结束字幕条目序号
        content: chunk 内容（SRT 格式）
        translated: 翻译后的内容
        is_completed: 是否已完成翻译
    """
    index: int
    start_index: int
    end_index: int
    content: str
    translated: Optional[str] = None
    is_completed: bool = False


@dataclass
class ChunkProgress:
    """Chunk 进度信息

    Attributes:
        total_chunks: 总 chunk 数
        completed_chunks: 已完成的 chunk 索引列表
        failed_chunks: 失败的 chunk 索引列表
        last_error: 最后的错误信息
        started_at: 开始时间
        updated_at: 更新时间
    """
    total_chunks: int = 0
    completed_chunks: List[int] = field(default_factory=list)
    failed_chunks: List[int] = field(default_factory=list)
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_chunks": self.total_chunks,
            "completed_chunks": self.completed_chunks,
            "failed_chunks": self.failed_chunks,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkProgress":
        """从字典创建"""
        return cls(
            total_chunks=data.get("total_chunks", 0),
            completed_chunks=data.get("completed_chunks", []),
            failed_chunks=data.get("failed_chunks", []),
            last_error=data.get("last_error"),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at"),
        )

    @property
    def is_complete(self) -> bool:
        """是否全部完成"""
        return len(self.completed_chunks) >= self.total_chunks

    @property
    def progress_percent(self) -> float:
        """完成百分比"""
        if self.total_chunks == 0:
            return 0.0
        return len(self.completed_chunks) / self.total_chunks * 100


class ChunkTracker:
    """Chunk 进度追踪器

    负责：
    1. 将字幕拆分为 chunk
    2. 追踪翻译进度
    3. 保存/加载进度（支持恢复）
    """

    # 默认配置
    DEFAULT_CHUNK_SIZE = 50  # 默认每个 chunk 包含的字幕条目数
    DEFAULT_MAX_CHARS = 8000  # 默认每个 chunk 的最大字符数

    def __init__(
        self,
        video_id: str,
        target_language: str,
        work_dir: Path,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_chars: int = DEFAULT_MAX_CHARS,
    ):
        """初始化 Chunk 追踪器

        Args:
            video_id: 视频 ID
            target_language: 目标语言
            work_dir: 工作目录（存放进度文件和临时 chunk）
            chunk_size: 每个 chunk 的字幕条目数
            max_chars: 每个 chunk 的最大字符数
        """
        self.video_id = video_id
        self.target_language = target_language
        self.work_dir = Path(work_dir)
        self.chunk_size = chunk_size
        self.max_chars = max_chars

        # 进度文件路径
        self.progress_file = self.work_dir / f".chunk_progress.{target_language}.json"
        self.chunks_dir = self.work_dir / f".chunks.{target_language}"

        # 加载或创建进度
        self.progress = self._load_progress()
        self.chunks: List[SubtitleChunk] = []

    def _load_progress(self) -> ChunkProgress:
        """加载进度"""
        if self.progress_file.exists():
            try:
                data = json.loads(self.progress_file.read_text(encoding="utf-8"))
                progress = ChunkProgress.from_dict(data)
                logger.info(
                    f"Loaded chunk progress: {len(progress.completed_chunks)}/{progress.total_chunks} completed"
                )
                return progress
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load chunk progress: {e}")
        return ChunkProgress(started_at=datetime.now().isoformat())

    def _save_progress(self, max_retries: int = 5) -> bool:
        """保存进度（原子写入 + 重试机制）
        
        Args:
            max_retries: 最大重试次数
            
        Returns:
            是否保存成功
        """
        import time
        import uuid
        
        self.progress.updated_at = datetime.now().isoformat()
        content = json.dumps(self.progress.to_dict(), ensure_ascii=False, indent=2)
        
        for attempt in range(max_retries):
            # 使用唯一的 tmp 文件名避免冲突
            tmp_path = self.progress_file.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
            try:
                tmp_path.write_text(content, encoding="utf-8")
                os.replace(tmp_path, self.progress_file)
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
                        f"Progress save conflict (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.3f}s"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to save chunk progress: {e}")
                    break
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
        
        return False

    def split_subtitle(self, srt_content: str) -> List[SubtitleChunk]:
        """将 SRT 内容拆分为 chunks

        Args:
            srt_content: SRT 格式的字幕内容

        Returns:
            SubtitleChunk 列表
        """
        # 解析 SRT 为条目列表
        entries = self._parse_srt(srt_content)

        if not entries:
            return []

        # 按条目数和字符数拆分
        chunks = []
        current_entries = []
        current_chars = 0
        chunk_index = 0

        for entry in entries:
            entry_text = self._format_entry(entry)
            entry_chars = len(entry_text)

            # 检查是否需要开始新 chunk
            should_split = False
            if current_entries:
                if len(current_entries) >= self.chunk_size:
                    should_split = True
                elif current_chars + entry_chars > self.max_chars:
                    should_split = True

            if should_split:
                # 保存当前 chunk
                chunks.append(self._create_chunk(chunk_index, current_entries))
                chunk_index += 1
                current_entries = []
                current_chars = 0

            current_entries.append(entry)
            current_chars += entry_chars

        # 处理最后一个 chunk
        if current_entries:
            chunks.append(self._create_chunk(chunk_index, current_entries))

        # 更新进度
        self.chunks = chunks
        self.progress.total_chunks = len(chunks)
        self._save_progress()

        # 保存各 chunk 到文件
        self._save_chunks_to_files()

        logger.info(f"Split subtitle into {len(chunks)} chunks")
        return chunks

    def _parse_srt(self, content: str) -> List[Dict]:
        """解析 SRT 内容为条目列表"""
        import re

        entries = []
        pattern = re.compile(
            r"(\d+)\s*\n"
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"
            r"((?:(?!\n\n|\n\d+\n\d{2}:\d{2}:\d{2}).)*)",
            re.DOTALL,
        )

        for match in pattern.finditer(content):
            entries.append({
                "index": int(match.group(1)),
                "start": match.group(2),
                "end": match.group(3),
                "text": match.group(4).strip(),
            })

        return entries

    def _format_entry(self, entry: Dict) -> str:
        """格式化单个条目为 SRT 格式"""
        return f"{entry['index']}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n"

    def _create_chunk(self, index: int, entries: List[Dict]) -> SubtitleChunk:
        """创建 SubtitleChunk"""
        content = "".join(self._format_entry(e) for e in entries)
        return SubtitleChunk(
            index=index,
            start_index=entries[0]["index"],
            end_index=entries[-1]["index"],
            content=content,
            is_completed=index in self.progress.completed_chunks,
        )

    def _save_chunks_to_files(self) -> None:
        """保存 chunks 到临时文件"""
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        for chunk in self.chunks:
            chunk_file = self.chunks_dir / f"chunk_{chunk.index:04d}.srt"
            if not chunk_file.exists():
                chunk_file.write_text(chunk.content, encoding="utf-8")

    def get_pending_chunks(self) -> List[SubtitleChunk]:
        """获取待翻译的 chunks"""
        return [c for c in self.chunks if not c.is_completed]

    def mark_chunk_completed(
        self, chunk_index: int, translated_content: str
    ) -> bool:
        """标记 chunk 完成

        Args:
            chunk_index: chunk 索引
            translated_content: 翻译后的内容

        Returns:
            是否成功
        """
        if chunk_index >= len(self.chunks):
            return False

        chunk = self.chunks[chunk_index]
        chunk.translated = translated_content
        chunk.is_completed = True

        # 保存翻译结果
        translated_file = self.chunks_dir / f"chunk_{chunk_index:04d}.translated.srt"
        try:
            translated_file.write_text(translated_content, encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to save translated chunk: {e}")
            return False

        # 更新进度
        if chunk_index not in self.progress.completed_chunks:
            self.progress.completed_chunks.append(chunk_index)
        if chunk_index in self.progress.failed_chunks:
            self.progress.failed_chunks.remove(chunk_index)

        return self._save_progress()

    def mark_chunk_failed(self, chunk_index: int, error: str) -> bool:
        """标记 chunk 失败

        Args:
            chunk_index: chunk 索引
            error: 错误信息

        Returns:
            是否成功保存
        """
        if chunk_index not in self.progress.failed_chunks:
            self.progress.failed_chunks.append(chunk_index)
        self.progress.last_error = error

        return self._save_progress()

    def merge_translated_chunks(self) -> Optional[str]:
        """合并所有已翻译的 chunks

        Returns:
            合并后的 SRT 内容，如果有未完成的 chunk 则返回 None
        """
        if not self.progress.is_complete:
            pending = len(self.chunks) - len(self.progress.completed_chunks)
            logger.warning(f"Cannot merge: {pending} chunks not translated")
            return None

        # 按索引排序并合并
        merged_parts = []
        for i in range(len(self.chunks)):
            chunk = self.chunks[i]
            if chunk.translated:
                merged_parts.append(chunk.translated)
            else:
                # 尝试从文件加载
                translated_file = self.chunks_dir / f"chunk_{i:04d}.translated.srt"
                if translated_file.exists():
                    merged_parts.append(translated_file.read_text(encoding="utf-8"))
                else:
                    logger.error(f"Missing translated chunk {i}")
                    return None

        return "\n".join(merged_parts)

    def cleanup(self) -> None:
        """清理临时文件"""
        import shutil

        try:
            if self.chunks_dir.exists():
                shutil.rmtree(self.chunks_dir)
            if self.progress_file.exists():
                self.progress_file.unlink()
        except OSError as e:
            logger.warning(f"Failed to cleanup chunk files: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "video_id": self.video_id,
            "target_language": self.target_language,
            "total_chunks": self.progress.total_chunks,
            "completed": len(self.progress.completed_chunks),
            "failed": len(self.progress.failed_chunks),
            "pending": self.progress.total_chunks - len(self.progress.completed_chunks),
            "progress_percent": self.progress.progress_percent,
            "is_complete": self.progress.is_complete,
        }


# 便捷函数
def create_chunk_tracker(
    video_id: str,
    target_language: str,
    work_dir: Path,
    chunk_size: int = ChunkTracker.DEFAULT_CHUNK_SIZE,
) -> ChunkTracker:
    """创建 Chunk 追踪器

    Args:
        video_id: 视频 ID
        target_language: 目标语言
        work_dir: 工作目录

    Returns:
        ChunkTracker 实例
    """
    return ChunkTracker(
        video_id=video_id,
        target_language=target_language,
        work_dir=work_dir,
        chunk_size=chunk_size,
    )
