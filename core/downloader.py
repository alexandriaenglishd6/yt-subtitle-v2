"""
字幕下载模块
根据检测结果下载原始字幕和官方翻译字幕
"""
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger

logger = get_logger()


class SubtitleDownloader:
    """字幕下载器
    
    负责下载原始字幕和官方翻译字幕
    """
    
    def __init__(self, yt_dlp_path: Optional[str] = None, output_dir: Optional[Path] = None):
        """初始化字幕下载器
        
        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
            output_dir: 输出目录，如果为 None 则使用当前目录
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.output_dir = output_dir or Path(".")
    
    def download(
        self,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        output_path: Path
    ) -> Dict[str, Optional[Path]]:
        """下载字幕文件
        
        Args:
            video_info: 视频信息
            detection_result: 字幕检测结果
            language_config: 语言配置
            output_path: 输出目录路径（视频的输出目录）
        
        Returns:
            字典，包含下载的字幕文件路径：
            {
                "original": Path,  # 原始字幕文件路径（原语言）
                "official_translations": {  # 官方翻译字幕文件路径（按语言代码）
                    "zh-CN": Path,
                    ...
                }
            }
        """
        result = {
            "original": None,
            "official_translations": {}
        }
        
        if not detection_result.has_subtitles:
            logger.warning(f"视频无可用字幕，跳过下载: {video_info.video_id}")
            return result
        
        try:
            # 确保输出目录存在
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 步骤 1: 确定原始字幕语言（优先人工字幕，其次自动字幕）
            source_lang = self._determine_source_language(detection_result)
            
            if source_lang:
                # 下载原始字幕
                original_path = self._download_subtitle(
                    video_info.url,
                    source_lang,
                    output_path,
                    f"original.{source_lang}.srt",
                    is_auto=False  # 优先使用人工字幕
                )
                result["original"] = original_path
                
                if original_path:
                    logger.info(f"已下载原始字幕: {original_path.name}", video_id=video_info.video_id)
            
            # 步骤 2: 下载官方翻译字幕（针对每个目标语言）
            for target_lang in language_config.subtitle_target_languages:
                # 检查是否有官方字幕（人工或自动）匹配目标语言
                has_official = (
                    target_lang in detection_result.manual_languages or
                    target_lang in detection_result.auto_languages
                )
                
                if has_official:
                    # 下载官方翻译字幕
                    official_path = self._download_subtitle(
                        video_info.url,
                        target_lang,
                        output_path,
                        f"translated.{target_lang}.srt",
                        is_auto=(target_lang not in detection_result.manual_languages)
                    )
                    
                    if official_path:
                        result["official_translations"][target_lang] = official_path
                        logger.info(
                            f"已下载官方翻译字幕 ({target_lang}): {official_path.name}",
                            video_id=video_info.video_id
                        )
                    else:
                        logger.warning(
                            f"无法下载官方翻译字幕 ({target_lang})",
                            video_id=video_info.video_id
                        )
                else:
                    logger.info(
                        f"目标语言 {target_lang} 无可用官方字幕",
                        video_id=video_info.video_id
                    )
            
            return result
            
        except Exception as e:
            logger.error(f"下载字幕失败: {e}", video_id=video_info.video_id)
            return result
    
    def _determine_source_language(self, detection_result: DetectionResult) -> Optional[str]:
        """确定原始字幕语言
        
        优先使用人工字幕，如果没有则使用自动字幕
        
        Args:
            detection_result: 字幕检测结果
        
        Returns:
            语言代码，如果没有字幕则返回 None
        """
        if detection_result.manual_languages:
            # 优先使用第一个人工字幕语言
            return detection_result.manual_languages[0]
        elif detection_result.auto_languages:
            # 如果没有人工字幕，使用第一个自动字幕语言
            return detection_result.auto_languages[0]
        else:
            return None
    
    def _download_subtitle(
        self,
        url: str,
        lang_code: str,
        output_dir: Path,
        output_filename: str,
        is_auto: bool = False
    ) -> Optional[Path]:
        """使用 yt-dlp 下载字幕文件
        
        Args:
            url: 视频 URL
            lang_code: 语言代码（如 "en", "zh-CN"）
            output_dir: 输出目录
            output_filename: 输出文件名
            is_auto: 是否为自动字幕（True）或人工字幕（False）
        
        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        try:
            output_path = output_dir / output_filename
            
            # 构建 yt-dlp 命令
            # --write-subs: 下载字幕（人工字幕）
            # --write-auto-subs: 下载自动字幕（如果需要）
            # --sub-langs: 指定语言代码
            # --skip-download: 不下载视频
            # --convert-subs: 转换为 srt 格式
            # --output: 输出文件路径模板
            
            # yt-dlp 输出格式：<output_template>.<lang>.srt
            # 我们使用临时文件名，然后重命名
            temp_output = output_dir / f"temp_{output_path.stem}"
            
            cmd = [
                self.yt_dlp_path,
                "--skip-download",
                "--convert-subs", "srt",
                "--no-warnings",
                "--output", str(temp_output),
                url
            ]
            
            # 根据是否为自动字幕选择不同的参数
            if is_auto:
                # 下载自动字幕
                cmd.extend(["--write-auto-subs", "--sub-langs", lang_code])
            else:
                # 下载人工字幕
                cmd.extend(["--write-subs", "--sub-langs", lang_code])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"yt-dlp 下载字幕失败: {result.stderr}")
                return None
            
            # yt-dlp 下载的字幕文件名格式：<temp_output>.<lang>.srt
            # 查找下载的文件
            expected_path = output_path
            actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.srt"))
            
            if actual_paths:
                # 找到下载的文件，重命名为目标文件名
                actual_path = actual_paths[0]
                if actual_path != expected_path:
                    actual_path.rename(expected_path)
                # 清理其他可能的临时文件
                for temp_file in output_dir.glob("temp_*"):
                    if temp_file != actual_path:
                        try:
                            temp_file.unlink()
                        except:
                            pass
                return expected_path
            else:
                # 检查是否已经存在目标文件
                if expected_path.exists():
                    return expected_path
                logger.warning(f"未找到下载的字幕文件: {output_filename}")
                return None
            
        except subprocess.TimeoutExpired:
            logger.error(f"下载字幕超时: {lang_code}")
            return None
        except Exception as e:
            logger.error(f"下载字幕时出错: {e}")
            return None
    
    def download_by_lang(
        self,
        url: str,
        lang_code: str,
        output_path: Path,
        is_auto: bool = False
    ) -> Optional[Path]:
        """直接按语言代码下载字幕（便捷方法）
        
        Args:
            url: 视频 URL
            lang_code: 语言代码
            output_path: 输出文件路径（完整路径，包含文件名）
            is_auto: 是否为自动字幕
        
        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        output_dir = output_path.parent
        output_filename = output_path.name
        return self._download_subtitle(url, lang_code, output_dir, output_filename, is_auto)
