"""
字幕智能合并模块

将 SRT 字幕的短小 cue 合并为自然的句子块，用于 AI 翻译前的预处理。
输出使用块时间范围（block's start/end time），不做字符比例拆分。

合并规则 (MVP 参数):
- 标点断句: 。！？.!?
- 时间间隔: > 1.2 秒视为新句
- 最大长度: 1000 字符
- Overlap: 2 句（可配置，默认关闭）
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path


@dataclass
class SubtitleCue:
    """单个字幕条目"""
    index: int
    start_time: float  # 秒
    end_time: float  # 秒
    text: str


@dataclass
class MergedBlock:
    """合并后的字幕块"""
    start_time: float  # 块起始时间（秒）
    end_time: float  # 块结束时间（秒）
    text: str  # 合并后的文本
    original_cues: List[SubtitleCue] = field(default_factory=list)

    def to_srt_timestamp(self, seconds: float) -> str:
        """将秒数转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_srt_entry(self, index: int) -> str:
        """转换为 SRT 条目格式"""
        start = self.to_srt_timestamp(self.start_time)
        end = self.to_srt_timestamp(self.end_time)
        return f"{index}\n{start} --> {end}\n{self.text}\n"


@dataclass
class MergerConfig:
    """合并配置参数"""
    # 断句标点（遇到这些标点认为句子结束）
    sentence_ending_punctuation: str = "。！？.!?；;："

    # 时间间隔阈值（秒），超过此间隔视为新句
    time_gap_threshold: float = 1.2

    # 单个块的最大字符数
    max_block_length: int = 1000

    # 是否启用 overlap（默认关闭）
    enable_overlap: bool = False

    # overlap 句子数（用于上下文连贯）
    overlap_sentences: int = 2


class SubtitleMerger:
    """字幕合并器

    将短小的 SRT 字幕 cue 合并为自然的句子块，
    提升 AI 翻译的上下文理解和翻译质量。

    使用方法:
        merger = SubtitleMerger()
        blocks = merger.merge_file("input.srt")
        # 或
        blocks = merger.merge_cues(cues)
    """

    def __init__(self, config: Optional[MergerConfig] = None):
        """初始化合并器

        Args:
            config: 合并配置，如果为 None 则使用默认配置
        """
        self.config = config or MergerConfig()

    def parse_srt_file(self, file_path: Path) -> List[SubtitleCue]:
        """解析 SRT 文件

        Args:
            file_path: SRT 文件路径

        Returns:
            字幕条目列表
        """
        content = file_path.read_text(encoding="utf-8")
        return self.parse_srt_content(content)

    def parse_srt_content(self, content: str) -> List[SubtitleCue]:
        """解析 SRT 内容

        Args:
            content: SRT 文件内容

        Returns:
            字幕条目列表
        """
        cues = []
        # SRT 条目格式：
        # 1
        # 00:00:01,000 --> 00:00:04,000
        # 字幕文本
        # (空行)

        # 使用正则匹配 SRT 条目
        pattern = re.compile(
            r"(\d+)\s*\n"  # 序号
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"  # 时间
            r"((?:(?!\n\n|\n\d+\n\d{2}:\d{2}:\d{2}).)*)",  # 文本（非贪婪，直到空行或下一条目）
            re.DOTALL,
        )

        for match in pattern.finditer(content):
            index = int(match.group(1))
            start_time = self._parse_timestamp(match.group(2))
            end_time = self._parse_timestamp(match.group(3))
            text = match.group(4).strip()

            if text:  # 忽略空文本
                cues.append(SubtitleCue(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text,
                ))

        return cues

    def _parse_timestamp(self, timestamp: str) -> float:
        """解析 SRT 时间戳为秒数

        Args:
            timestamp: SRT 时间格式 (HH:MM:SS,mmm 或 HH:MM:SS.mmm)

        Returns:
            秒数（浮点数）
        """
        # 支持逗号和点号作为毫秒分隔符
        timestamp = timestamp.replace(",", ".")
        parts = timestamp.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_parts = parts[2].split(".")
        seconds = int(seconds_parts[0])
        millis = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

        return hours * 3600 + minutes * 60 + seconds + millis / 1000

    def merge_file(self, file_path: Path) -> List[MergedBlock]:
        """合并 SRT 文件

        Args:
            file_path: SRT 文件路径

        Returns:
            合并后的块列表
        """
        cues = self.parse_srt_file(file_path)
        return self.merge_cues(cues)

    def merge_cues(self, cues: List[SubtitleCue]) -> List[MergedBlock]:
        """合并字幕条目为块

        核心合并逻辑：
        1. 遇到断句标点 → 结束当前块
        2. 时间间隔 > 阈值 → 结束当前块
        3. 达到最大长度 → 结束当前块

        Args:
            cues: 字幕条目列表

        Returns:
            合并后的块列表
        """
        if not cues:
            return []

        blocks = []
        current_block_cues: List[SubtitleCue] = []
        current_text = ""

        for i, cue in enumerate(cues):
            # 检查是否需要开始新块
            should_start_new = False

            if current_block_cues:
                # 规则 1: 时间间隔
                last_cue = current_block_cues[-1]
                time_gap = cue.start_time - last_cue.end_time
                if time_gap > self.config.time_gap_threshold:
                    should_start_new = True

                # 规则 2: 上一个 cue 以断句标点结尾
                if self._ends_with_sentence_punctuation(last_cue.text):
                    should_start_new = True

                # 规则 3: 达到最大长度
                if len(current_text) + len(cue.text) > self.config.max_block_length:
                    should_start_new = True

            if should_start_new and current_block_cues:
                # 保存当前块
                blocks.append(self._create_block(current_block_cues, current_text))
                current_block_cues = []
                current_text = ""

            # 添加当前 cue 到块
            current_block_cues.append(cue)
            if current_text:
                current_text += " " + cue.text
            else:
                current_text = cue.text

        # 处理最后一个块
        if current_block_cues:
            blocks.append(self._create_block(current_block_cues, current_text))

        return blocks

    def _ends_with_sentence_punctuation(self, text: str) -> bool:
        """检查文本是否以断句标点结尾

        Args:
            text: 文本

        Returns:
            是否以断句标点结尾
        """
        text = text.strip()
        if not text:
            return False
        return text[-1] in self.config.sentence_ending_punctuation

    def _create_block(self, cues: List[SubtitleCue], text: str) -> MergedBlock:
        """创建合并块

        Args:
            cues: 组成此块的 cue 列表
            text: 合并后的文本

        Returns:
            MergedBlock 实例
        """
        return MergedBlock(
            start_time=cues[0].start_time,
            end_time=cues[-1].end_time,
            text=text.strip(),
            original_cues=cues.copy(),
        )

    def blocks_to_srt(self, blocks: List[MergedBlock]) -> str:
        """将合并块转换回 SRT 格式

        注意：使用块时间范围，不按字符比例拆分

        Args:
            blocks: 合并块列表

        Returns:
            SRT 格式字符串
        """
        srt_entries = []
        for i, block in enumerate(blocks, start=1):
            srt_entries.append(block.to_srt_entry(i))
        return "\n".join(srt_entries)

    def merge_for_translation(
        self, file_path: Path
    ) -> Tuple[List[MergedBlock], str]:
        """为翻译准备合并后的字幕

        Args:
            file_path: SRT 文件路径

        Returns:
            (合并块列表, 合并后的纯文本用于翻译)
        """
        blocks = self.merge_file(file_path)

        # 生成用于翻译的纯文本（保留块分隔）
        translation_texts = []
        for i, block in enumerate(blocks):
            # 使用块编号标记，便于翻译后对齐
            translation_texts.append(f"[BLOCK_{i+1}]\n{block.text}")

        translation_input = "\n\n".join(translation_texts)
        return blocks, translation_input

    def apply_translation(
        self, blocks: List[MergedBlock], translated_text: str
    ) -> List[MergedBlock]:
        """将翻译结果应用到块

        Args:
            blocks: 原始合并块
            translated_text: 翻译后的文本（包含 [BLOCK_N] 标记）

        Returns:
            包含翻译文本的新块列表
        """
        # 解析翻译结果
        block_pattern = re.compile(r"\[BLOCK_(\d+)\]\s*\n(.*?)(?=\[BLOCK_|\Z)", re.DOTALL)
        translated_blocks = {}

        for match in block_pattern.finditer(translated_text):
            block_num = int(match.group(1))
            block_text = match.group(2).strip()
            translated_blocks[block_num] = block_text

        # 创建翻译后的块
        result = []
        for i, block in enumerate(blocks):
            block_num = i + 1
            translated = translated_blocks.get(block_num, block.text)
            result.append(MergedBlock(
                start_time=block.start_time,
                end_time=block.end_time,
                text=translated,
                original_cues=block.original_cues,
            ))

        return result


# 便捷函数
def merge_subtitle_file(
    file_path: Path,
    config: Optional[MergerConfig] = None,
) -> List[MergedBlock]:
    """合并字幕文件的便捷函数

    Args:
        file_path: SRT 文件路径
        config: 合并配置

    Returns:
        合并后的块列表
    """
    merger = SubtitleMerger(config)
    return merger.merge_file(file_path)


def merge_and_prepare_for_translation(
    file_path: Path,
    config: Optional[MergerConfig] = None,
) -> Tuple[List[MergedBlock], str]:
    """合并字幕并准备翻译输入

    Args:
        file_path: SRT 文件路径
        config: 合并配置

    Returns:
        (合并块列表, 翻译输入文本)
    """
    merger = SubtitleMerger(config)
    return merger.merge_for_translation(file_path)
