"""
字幕下载模块
根据检测结果下载原始字幕和官方翻译字幕
符合 error_handling.md 规范：将 yt-dlp 错误映射为 AppException，使用原子写文件
"""
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger
from core.exceptions import AppException, ErrorType
from core.fetcher import _map_ytdlp_error_to_app_error
from core.failure_logger import _atomic_write

logger = get_logger()


class SubtitleDownloader:
    """字幕下载器
    
    负责下载原始字幕和官方翻译字幕
    """
    
    def __init__(self, yt_dlp_path: Optional[str] = None, output_dir: Optional[Path] = None, proxy_manager=None, cookie_manager=None):
        """初始化字幕下载器
        
        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
            output_dir: 输出目录，如果为 None 则使用当前目录
            proxy_manager: ProxyManager 实例，如果为 None 则不使用代理
            cookie_manager: CookieManager 实例，如果为 None 则不使用 Cookie
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.output_dir = output_dir or Path(".")
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
    
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
                        # 验证下载的字幕语言是否正确
                        actual_lang = self._verify_subtitle_language(official_path, target_lang)
                        if actual_lang and actual_lang != target_lang:
                            logger.warning(
                                f"下载的字幕语言不匹配：请求 {target_lang}，实际为 {actual_lang}。文件: {official_path.name}",
                                video_id=video_info.video_id
                            )
                            # 仍然保存，但记录警告
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
            
        except AppException as e:
            logger.error(
                f"下载字幕失败: {e}",
                video_id=video_info.video_id,
                error_type=e.error_type.value
            )
            return result
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"下载字幕失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"下载字幕失败: {app_error}",
                video_id=video_info.video_id,
                error_type=app_error.error_type.value
            )
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
            
            proxy = None
            if self.proxy_manager:
                proxy = self.proxy_manager.get_next_proxy()
            
            cmd = [
                self.yt_dlp_path,
                "--skip-download",
                "--convert-subs", "srt",
                "--no-warnings",
                "--output", str(temp_output),
                # 如果 ffmpeg 不可用，尝试不使用 ffmpeg 进行转换
                # 某些字幕格式可能不需要 ffmpeg
                "--no-check-formats",  # 跳过格式检查，避免需要 ffmpeg
            ]
            
            # 如果配置了代理，添加代理参数
            if proxy:
                cmd.extend(["--proxy", proxy])
                logger.debug(f"使用代理下载字幕: {proxy}")
            
            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.info(f"使用 Cookie 文件下载字幕: {cookie_file}")
                else:
                    logger.warning("Cookie 管理器存在，但无法获取 Cookie 文件路径（字幕下载）")
            else:
                logger.debug("未配置 Cookie 管理器（字幕下载）")
            
            cmd.append(url)
            
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
                error_msg = result.stderr
                
                # 检查是否是 ffmpeg 错误
                is_ffmpeg_error = "ffmpeg" in error_msg.lower() or "ffmpeg-location" in error_msg.lower()
                
                # 即使 yt-dlp 报错，也检查文件是否已经生成（某些情况下文件可能已经下载）
                # yt-dlp 生成的文件名格式：<temp_output>.<lang>.srt
                # 例如：temp_original.zh.zh.srt（如果 temp_output = "temp_original.zh", lang_code = "zh"）
                expected_temp_name = temp_output.name  # 例如 "temp_original.zh"
                actual_paths = list(output_dir.glob(f"{expected_temp_name}.{lang_code}.srt"))
                if not actual_paths:
                    # 也检查其他可能的格式（如 .vtt, .ttml）
                    actual_paths = list(output_dir.glob(f"{expected_temp_name}.{lang_code}.*"))
                if not actual_paths:
                    # 更宽泛的搜索：temp_*.<lang>.srt
                    actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.srt"))
                if not actual_paths:
                    # 最宽泛的搜索：temp_*.<lang>.*
                    actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.*"))
                
                if actual_paths:
                    # 文件已经生成，即使 yt-dlp 报错也继续处理
                    logger.warning(
                        f"yt-dlp 返回错误码 {result.returncode}，但字幕文件已生成，继续处理: {actual_paths[0].name}",
                        error_type=ErrorType.CONTENT.value if is_ffmpeg_error else None
                    )
                    # 直接处理文件，不抛出异常
                    actual_path = actual_paths[0]
                    expected_path = output_path
                    # 处理文件（移动到目标位置）
                    try:
                        if actual_path != expected_path:
                            content = actual_path.read_text(encoding="utf-8")
                            if _atomic_write(expected_path, content, mode="w"):
                                try:
                                    actual_path.unlink()
                                except Exception:
                                    pass
                                return expected_path
                            else:
                                logger.warning(f"原子写字幕文件失败，保留临时文件: {actual_path}")
                                return actual_path
                        else:
                            return expected_path
                    except (OSError, IOError, PermissionError) as e:
                        app_error = AppException(
                            message=f"读取/写入字幕文件失败: {e}",
                            error_type=ErrorType.FILE_IO,
                            cause=e
                        )
                        logger.error(
                            f"读取/写入字幕文件失败: {app_error}",
                            error_type=app_error.error_type.value
                        )
                        raise app_error
                else:
                    # 文件未生成，检查是否是 ffmpeg 错误
                    if is_ffmpeg_error:
                        # ffmpeg 错误：尝试不使用转换，直接下载原始格式
                        logger.warning("检测到 ffmpeg 错误，尝试不使用格式转换下载字幕")
                        # 重新调用，但不使用 --convert-subs
                        return self._download_subtitle_no_convert(
                            url, lang_code, output_dir, output_filename, is_auto, proxy
                        )
                    
                    # 映射为 AppException
                    app_error = _map_ytdlp_error_to_app_error(
                        result.returncode,
                        error_msg
                    )
                    logger.error(
                        f"yt-dlp 下载字幕失败: {app_error}",
                        error_type=app_error.error_type.value
                    )
                    
                    # 如果使用了代理，标记代理失败
                    if proxy and self.proxy_manager:
                        self.proxy_manager.mark_failure(proxy, error_msg[:200])
                    
                    # 抛出 AppException（由调用方处理）
                    raise app_error
            
            # 如果使用了代理且成功，标记代理成功
            if proxy and self.proxy_manager:
                self.proxy_manager.mark_success(proxy)
            
            # yt-dlp 下载的字幕文件名格式：<temp_output>.<lang>.srt
            # 查找下载的文件
            expected_path = output_path
            actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.srt"))
            
            if actual_paths:
                # 找到下载的文件，使用原子写机制移动到目标位置
                actual_path = actual_paths[0]
                if actual_path != expected_path:
                    # 读取文件内容
                    try:
                        content = actual_path.read_text(encoding="utf-8")
                        # 使用原子写写入目标文件
                        if _atomic_write(expected_path, content, mode="w"):
                            # 删除临时文件
                            try:
                                actual_path.unlink()
                            except Exception:
                                pass
                        else:
                            # 原子写失败，保留临时文件
                            logger.warning(
                                f"原子写字幕文件失败，保留临时文件: {actual_path}",
                                error_type=ErrorType.FILE_IO.value
                            )
                            return actual_path
                    except (OSError, IOError, PermissionError) as e:
                        # 文件IO错误
                        app_error = AppException(
                            message=f"读取/写入字幕文件失败: {e}",
                            error_type=ErrorType.FILE_IO,
                            cause=e
                        )
                        logger.error(
                            f"读取/写入字幕文件失败: {app_error}",
                            error_type=app_error.error_type.value
                        )
                        raise app_error
                
                # 清理其他可能的临时文件
                for temp_file in output_dir.glob("temp_*"):
                    if temp_file != actual_path and temp_file != expected_path:
                        try:
                            temp_file.unlink()
                        except Exception:
                            pass
                return expected_path
            else:
                # 检查是否已经存在目标文件
                if expected_path.exists():
                    return expected_path
                logger.warning(f"未找到下载的字幕文件: {output_filename}")
                return None
            
        except subprocess.TimeoutExpired:
            app_error = AppException(
                message=f"下载字幕超时: {lang_code}",
                error_type=ErrorType.TIMEOUT
            )
            logger.error(
                f"下载字幕超时: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"下载字幕时文件IO错误: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"下载字幕时文件IO错误: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"下载字幕时出错: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"下载字幕时出错: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
    
    def _download_subtitle_no_convert(
        self,
        url: str,
        lang_code: str,
        output_dir: Path,
        output_filename: str,
        is_auto: bool = False,
        proxy: Optional[str] = None
    ) -> Optional[Path]:
        """不使用格式转换下载字幕（用于 ffmpeg 不可用时）
        
        Args:
            url: 视频 URL
            lang_code: 语言代码
            output_dir: 输出目录
            output_filename: 输出文件名
            is_auto: 是否为自动字幕
            proxy: 代理地址（可选）
        
        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        try:
            output_path = output_dir / output_filename
            temp_output = output_dir / f"temp_{output_path.stem}"
            
            cmd = [
                self.yt_dlp_path,
                "--skip-download",
                "--no-warnings",
                "--output", str(temp_output),
            ]
            
            if proxy:
                cmd.extend(["--proxy", proxy])
            
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
            
            cmd.append(url)
            
            if is_auto:
                cmd.extend(["--write-auto-subs", "--sub-langs", lang_code])
            else:
                cmd.extend(["--write-subs", "--sub-langs", lang_code])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"yt-dlp 下载字幕失败（无转换模式）: {result.stderr}")
                return None
            
            # 查找下载的文件（可能是 .vtt, .ttml 等格式）
            expected_temp_name = temp_output.name
            actual_paths = list(output_dir.glob(f"{expected_temp_name}.{lang_code}.*"))
            
            if actual_paths:
                actual_path = actual_paths[0]
                # 如果是非 srt 格式，尝试转换为 srt（如果可能）
                if actual_path.suffix != ".srt":
                    logger.warning(f"下载的字幕格式为 {actual_path.suffix}，可能需要手动转换")
                    # 直接使用原始格式
                    if actual_path != output_path:
                        try:
                            content = actual_path.read_text(encoding="utf-8")
                            if _atomic_write(output_path, content, mode="w"):
                                try:
                                    actual_path.unlink()
                                except Exception:
                                    pass
                                return output_path
                        except Exception as e:
                            logger.error(f"复制字幕文件失败: {e}")
                return actual_path
            
            return None
            
        except Exception as e:
            logger.error(f"下载字幕失败（无转换模式）: {e}")
            return None
    
    def _verify_subtitle_language(self, subtitle_path: Path, expected_lang: str) -> Optional[str]:
        """验证字幕文件的语言
        
        通过检查字幕内容的前几行，尝试识别语言
        
        Args:
            subtitle_path: 字幕文件路径
            expected_lang: 期望的语言代码
        
        Returns:
            检测到的语言代码，如果无法检测则返回 None
        """
        try:
            # 读取前几行字幕内容
            content = subtitle_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split('\n')
            
            # 提取前10条字幕的文本
            text_samples = []
            for i, line in enumerate(lines):
                if i > 50:  # 只检查前50行
                    break
                # 跳过序号和时间码行
                if line.strip() and not line.strip().isdigit() and '-->' not in line:
                    text_samples.append(line.strip())
            
            if not text_samples:
                return None
            
            # 简单的语言检测：检查是否包含阿拉伯文字符
            sample_text = ' '.join(text_samples[:5])
            if any('\u0600' <= char <= '\u06FF' for char in sample_text):
                return "ar"  # 阿拉伯语
            # 可以添加更多语言检测逻辑
            
            # 如果无法确定，返回 None
            return None
        except Exception as e:
            logger.debug(f"语言验证失败: {e}")
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
