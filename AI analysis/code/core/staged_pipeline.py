"""
分阶段队列化 Pipeline 模块
实现多阶段队列处理，支持不同阶段配置不同并发数
"""
import queue
import threading
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from core.models import VideoInfo, DetectionResult
from core.logger import get_logger, set_log_context, clear_log_context
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.failure_logger import FailureLogger
from core.detector import SubtitleDetector
from core.downloader import SubtitleDownloader
from core.translator import SubtitleTranslator
from core.summarizer import Summarizer

logger = get_logger()

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


@dataclass
class StageData:
    """阶段数据容器
    
    用于在阶段之间传递视频处理数据
    """
    video_info: VideoInfo
    detection_result: Optional[DetectionResult] = None
    download_result: Optional[Dict[str, Any]] = None
    translation_result: Optional[Dict[str, Path]] = None
    summary_result: Optional[Path] = None  # 摘要文件路径
    temp_dir: Optional[Path] = None  # 临时目录（在 DOWNLOAD 阶段创建）
    temp_dir_created: bool = False  # 临时目录是否已创建
    error: Optional[Exception] = None  # 错误异常对象
    error_stage: Optional[str] = None  # 发生错误的阶段名称
    error_type: Optional[ErrorType] = None  # 错误类型（ErrorType 枚举）
    skip_reason: Optional[str] = None  # 跳过原因（如"无可用字幕"）
    is_processed: bool = False  # 是否已处理（用于增量管理）
    processing_failed: bool = False  # 处理是否失败（用于资源清理）
    run_id: Optional[str] = None  # 批次ID（run_id），用于日志和失败记录


class StageQueue:
    """阶段队列
    
    管理单个阶段的队列和执行器，支持并发处理和错误处理
    """
    
    def __init__(
        self,
        stage_name: str,
        executor: ThreadPoolExecutor,
        processor: Callable[[StageData], StageData],
        next_stage_queue: Optional['StageQueue'] = None,
        max_queue_size: int = 100,  # 最大队列大小，防止内存溢出
        failure_logger: Optional[FailureLogger] = None,  # 失败记录器
        cancel_token: Optional[CancelToken] = None,  # 取消令牌
    ):
        """初始化阶段队列
        
        Args:
            stage_name: 阶段名称（如 "detect", "download" 等）
            executor: 线程池执行器
            processor: 阶段处理函数 (StageData) -> StageData
            next_stage_queue: 下一阶段的队列（如果为 None 则表示这是最后一个阶段）
            max_queue_size: 最大队列大小
            failure_logger: 失败记录器
            cancel_token: 取消令牌
        """
        self.stage_name = stage_name
        self.executor = executor
        self.processor = processor
        self.next_stage_queue = next_stage_queue
        self.failure_logger = failure_logger
        self.cancel_token = cancel_token
        self.input_queue = queue.Queue(maxsize=max_queue_size)  # 限制队列大小
        self.running = False
        self.workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._processed_count = 0
        self._failed_count = 0
        self._total_count = 0
    
    def enqueue(self, data: StageData):
        """将数据加入队列
        
        如果队列已满，会阻塞直到有空间
        
        Args:
            data: 阶段数据
        """
        try:
            self.input_queue.put(data, block=True, timeout=None)
            with self._lock:
                self._total_count += 1
        except Exception as e:
            logger.error(f"阶段 {self.stage_name} 入队失败: {e}")
            raise
    
    def start(self, num_workers: int = None):
        """启动阶段处理
        
        Args:
            num_workers: worker 线程数量，如果为 None 则使用 executor 的 max_workers
        """
        if self.running:
            logger.warning(f"阶段 {self.stage_name} 已经在运行")
            return
        
        self.running = True
        num_workers = num_workers or self.executor._max_workers
        
        logger.info(f"启动阶段 {self.stage_name}，worker 数量: {num_workers}")
        
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"{self.stage_name}-worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def stop(self, timeout: float = 30.0):
        """停止阶段处理
        
        Args:
            timeout: 等待 worker 线程停止的超时时间（秒）
        """
        if not self.running:
            return
        
        logger.info(f"停止阶段 {self.stage_name}...")
        self.running = False
        
        # 向队列中放入停止信号
        for _ in range(len(self.workers)):
            try:
                self.input_queue.put(None, block=False)  # None 作为停止信号
            except queue.Full:
                # 队列已满，等待一下再试
                pass
        
        # 等待所有 worker 线程停止
        for worker in self.workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                logger.warning(f"Worker 线程 {worker.name} 在超时后仍未停止")
        
        self.workers.clear()
        logger.info(f"阶段 {self.stage_name} 已停止")
    
    def _worker_loop(self):
        """Worker 线程主循环"""
        while self.running:
            try:
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    logger.info(f"阶段 {self.stage_name} worker 检测到取消信号")
                    break
                
                # 从队列中获取数据（带超时，以便定期检查取消状态）
                try:
                    data = self.input_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # None 作为停止信号
                if data is None:
                    break
                
                # 处理数据
                try:
                    result = self.processor(data)
                    
                    # 如果处理失败，记录失败信息
                    if result.error and self.failure_logger:
                        self._log_failure(result)
                    
                    # 如果处理成功且没有跳过，传递给下一阶段
                    if not result.error and not result.skip_reason and self.next_stage_queue:
                        self.next_stage_queue.enqueue(result)
                    
                    # 更新统计
                    with self._lock:
                        if result.error or result.processing_failed:
                            self._failed_count += 1
                        else:
                            self._processed_count += 1
                
                except Exception as e:
                    logger.error(f"阶段 {self.stage_name} 处理异常: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    if data:
                        data.error = e
                        data.error_stage = self.stage_name
                        # 尝试提取错误类型
                        if isinstance(e, AppException):
                            data.error_type = e.error_type
                        else:
                            data.error_type = ErrorType.UNKNOWN
                        if self.failure_logger:
                            self._log_failure(data)
                    
                    with self._lock:
                        self._failed_count += 1
                
                finally:
                    self.input_queue.task_done()
            
            except Exception as e:
                logger.error(f"Worker 线程异常: {e}")
                import traceback
                logger.debug(traceback.format_exc())
    
    def _log_failure(self, data: StageData):
        """记录失败信息
        
        根据阶段调用相应的失败记录方法
        
        Args:
            data: 包含错误信息的阶段数据
        """
        if not self.failure_logger or not data.error:
            return
        
        try:
            video_id = data.video_info.video_id
            url = data.video_info.url
            error_type = data.error_type or ErrorType.UNKNOWN
            
            # 根据错误类型提取失败原因
            if isinstance(data.error, AppException):
                reason = str(data.error)
            elif isinstance(data.error, TaskCancelledError):
                # 取消不记录为失败
                return
            else:
                reason = str(data.error)
            
            # 根据阶段调用相应的失败记录方法
            if self.stage_name == "detect":
                self.failure_logger.log_failure(
                    video_id=video_id,
                    url=url,
                    reason=reason or data.skip_reason or "检测失败",
                    error_type=error_type,
                    batch_id=data.run_id,
                    channel_id=data.video_info.channel_id,
                    channel_name=data.video_info.channel_name,
                    stage="detect"
                )
            elif self.stage_name == "download":
                self.failure_logger.log_download_failure(
                    video_id=video_id,
                    url=url,
                    reason=reason or "下载失败",
                    error_type=error_type,
                    batch_id=data.run_id,
                    channel_id=data.video_info.channel_id,
                    channel_name=data.video_info.channel_name
                )
            elif self.stage_name == "translate":
                self.failure_logger.log_translation_failure(
                    video_id=video_id,
                    url=url,
                    reason=reason or "翻译失败",
                    error_type=error_type,
                    batch_id=data.run_id,
                    channel_id=data.video_info.channel_id,
                    channel_name=data.video_info.channel_name
                )
            elif self.stage_name == "summarize":
                self.failure_logger.log_summary_failure(
                    video_id=video_id,
                    url=url,
                    reason=reason or "摘要失败",
                    error_type=error_type,
                    batch_id=data.run_id,
                    channel_id=data.video_info.channel_id,
                    channel_name=data.video_info.channel_name
                )
            else:
                # 其他阶段使用通用失败记录
                self.failure_logger.log_failure(
                    video_id=video_id,
                    url=url,
                    reason=reason or "处理失败",
                    error_type=error_type,
                    batch_id=data.run_id,
                    channel_id=data.video_info.channel_id,
                    channel_name=data.video_info.channel_name,
                    stage=self.stage_name
                )
        except Exception as e:
            logger.error(f"记录失败信息时出错: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """获取阶段统计信息
        
        Returns:
            统计信息字典：{"processed": 已处理数, "failed": 失败数, "total": 总数}
        """
        with self._lock:
            return {
                "processed": self._processed_count,
                "failed": self._failed_count,
                "total": self._total_count
            }
    
    def wait_for_completion(self, timeout: Optional[float] = None):
        """等待队列中的所有任务完成
        
        Args:
            timeout: 超时时间（秒），如果为 None 则无限等待
        """
        self.input_queue.join()
    
    def is_empty(self) -> bool:
        """检查队列是否为空
        
        Returns:
            如果队列为空且没有正在处理的任务，返回 True
        """
        return self.input_queue.empty() and self._processed_count + self._failed_count >= self._total_count


class StagedPipeline:
    """分阶段 Pipeline 编排器
    
    将视频处理流程拆分为多个阶段，每个阶段有独立的队列和执行器
    """
    
    def __init__(
        self,
        language_config,
        translation_llm: Optional[Any],
        summary_llm: Optional[Any],
        output_writer: Any,
        failure_logger: FailureLogger,
        incremental_manager: Any,
        archive_path: Optional[Path],
        force: bool = False,
        dry_run: bool = False,
        cancel_token: Optional[CancelToken] = None,
        proxy_manager=None,
        cookie_manager=None,
        run_id: Optional[str] = None,
        on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
        # 阶段并发配置
        detect_concurrency: int = 10,
        download_concurrency: int = 10,
        translate_concurrency: int = 5,
        summarize_concurrency: int = 5,
        output_concurrency: int = 10,
        translation_llm_init_error_type: Optional[ErrorType] = None,
        translation_llm_init_error: Optional[str] = None,
    ):
        """初始化分阶段 Pipeline
        
        Args:
            language_config: 语言配置
            translation_llm: 翻译 LLM 客户端（可选）
            summary_llm: 摘要 LLM 客户端（可选）
            output_writer: 输出写入器
            failure_logger: 失败记录器
            incremental_manager: 增量管理器
            archive_path: archive 文件路径
            force: 是否强制重跑
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
            proxy_manager: 代理管理器
            cookie_manager: Cookie 管理器
            run_id: 批次ID（run_id）
            on_log: 日志回调
            detect_concurrency: DETECT 阶段并发数
            download_concurrency: DOWNLOAD 阶段并发数
            translate_concurrency: TRANSLATE 阶段并发数
            summarize_concurrency: SUMMARIZE 阶段并发数
            output_concurrency: OUTPUT 阶段并发数
            translation_llm_init_error_type: 翻译 LLM 初始化错误类型
            translation_llm_init_error: 翻译 LLM 初始化错误信息
        """
        self.language_config = language_config
        self.translation_llm = translation_llm
        self.summary_llm = summary_llm
        self.output_writer = output_writer
        self.failure_logger = failure_logger
        self.incremental_manager = incremental_manager
        self.archive_path = archive_path
        self.force = force
        self.dry_run = dry_run
        self.cancel_token = cancel_token
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
        self.run_id = run_id
        self.on_log = on_log
        self.translation_llm_init_error_type = translation_llm_init_error_type
        self.translation_llm_init_error = translation_llm_init_error
        
        # 创建各阶段的执行器
        self.detect_executor = ThreadPoolExecutor(max_workers=detect_concurrency, thread_name_prefix="detect")
        self.download_executor = ThreadPoolExecutor(max_workers=download_concurrency, thread_name_prefix="download")
        self.translate_executor = ThreadPoolExecutor(max_workers=translate_concurrency, thread_name_prefix="translate")
        self.summarize_executor = ThreadPoolExecutor(max_workers=summarize_concurrency, thread_name_prefix="summarize")
        self.output_executor = ThreadPoolExecutor(max_workers=output_concurrency, thread_name_prefix="output")
        
        # 创建各阶段的队列（从后往前创建，以便设置 next_stage_queue）
        # OUTPUT 阶段（最后一个阶段）
        self.output_queue = StageQueue(
            stage_name="output",
            executor=self.output_executor,
            processor=self._create_output_processor(),
            next_stage_queue=None,  # 最后一个阶段
            failure_logger=failure_logger,
            cancel_token=cancel_token
        )
        
        # SUMMARIZE 阶段
        self.summarize_queue = StageQueue(
            stage_name="summarize",
            executor=self.summarize_executor,
            processor=self._create_summarize_processor(),
            next_stage_queue=self.output_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token
        )
        
        # TRANSLATE 阶段
        self.translate_queue = StageQueue(
            stage_name="translate",
            executor=self.translate_executor,
            processor=self._create_translate_processor(),
            next_stage_queue=self.summarize_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token
        )
        
        # DOWNLOAD 阶段
        self.download_queue = StageQueue(
            stage_name="download",
            executor=self.download_executor,
            processor=self._create_download_processor(),
            next_stage_queue=self.translate_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token
        )
        
        # DETECT 阶段（第一个阶段）
        self.detect_queue = StageQueue(
            stage_name="detect",
            executor=self.detect_executor,
            processor=self._create_detect_processor(),
            next_stage_queue=self.download_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token
        )
        
        # 统计信息
        self._lock = threading.Lock()
        self._total_count = 0
        self._success_count = 0
        self._failed_count = 0
    
    def _create_detect_processor(self) -> Callable[[StageData], StageData]:
        """创建 DETECT 阶段处理器
        
        Returns:
            处理器函数
        """
        def processor(data: StageData) -> StageData:
            """处理 DETECT 阶段
            
            1. 检查增量记录（如果 force=False，跳过已处理视频）
            2. 执行字幕检测
            3. 如果没有字幕，设置 skip_reason 并记录失败
            """
            vid = data.video_info.video_id
            title_preview = data.video_info.title[:MAX_TITLE_DISPLAY_LENGTH]
            
            try:
                # 设置日志上下文
                if data.run_id:
                    set_log_context(run_id=data.run_id, task="detect", video_id=vid)
                
                logger.info(f"检测字幕: {vid} - {title_preview}...", video_id=vid)
                
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    raise TaskCancelledError(reason)
                
                # 检查增量记录（如果 force=False）
                if not self.force and self.archive_path:
                    if self.incremental_manager.is_processed(vid, self.archive_path):
                        data.is_processed = True
                        data.skip_reason = "已处理（增量模式）"
                        logger.info(f"视频已处理，跳过: {vid}", video_id=vid)
                        if self.on_log:
                            try:
                                self.on_log("INFO", f"视频已处理，跳过: {vid}", vid)
                            except Exception:
                                pass
                        return data
                
                # 执行字幕检测
                detector = SubtitleDetector(cookie_manager=self.cookie_manager)
                detection_result = detector.detect(data.video_info)
                data.detection_result = detection_result
                
                # 检查是否有字幕
                if not detection_result.has_subtitles:
                    error_msg = "视频无可用字幕，跳过处理"
                    logger.warning(error_msg, video_id=vid)
                    if self.on_log:
                        try:
                            self.on_log("WARN", error_msg, vid)
                        except Exception:
                            pass
                    
                    if not self.dry_run:
                        # 失败记录会在 StageQueue._log_failure 中处理
                        data.skip_reason = "无可用字幕"
                        data.error_type = ErrorType.CONTENT
                        data.processing_failed = True
                    else:
                        data.skip_reason = "无可用字幕（Dry Run）"
                    
                    return data
                
                logger.info(f"检测到字幕: {vid}", video_id=vid)
                return data
                
            except TaskCancelledError as e:
                # 任务已取消
                reason = e.reason or "用户取消"
                logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
                data.error = e
                data.error_type = ErrorType.CANCELLED
                data.error_stage = "detect"
                return data
            except AppException as e:
                # 应用异常
                data.error = e
                data.error_type = e.error_type
                data.error_stage = "detect"
                data.processing_failed = True
                logger.error(f"检测字幕失败: {vid} - {e}", video_id=vid)
                return data
            except Exception as e:
                # 未知异常
                app_error = AppException(
                    message=f"检测字幕失败: {str(e)}",
                    error_type=ErrorType.UNKNOWN,
                    cause=e
                )
                data.error = app_error
                data.error_type = ErrorType.UNKNOWN
                data.error_stage = "detect"
                data.processing_failed = True
                logger.error(f"检测字幕异常: {vid} - {e}", video_id=vid)
                import traceback
                logger.debug(traceback.format_exc(), video_id=vid)
                return data
            finally:
                # 清理日志上下文
                clear_log_context()
        
        return processor
    
    def _create_download_processor(self) -> Callable[[StageData], StageData]:
        """创建 DOWNLOAD 阶段处理器
        
        Returns:
            处理器函数
        """
        def processor(data: StageData) -> StageData:
            """处理 DOWNLOAD 阶段
            
            1. 创建临时目录
            2. 下载原始字幕和官方翻译字幕
            3. 检查下载结果，如果没有原始字幕则失败
            """
            vid = data.video_info.video_id
            title_preview = data.video_info.title[:MAX_TITLE_DISPLAY_LENGTH]
            
            try:
                # 设置日志上下文
                if data.run_id:
                    set_log_context(run_id=data.run_id, task="download", video_id=vid)
                
                logger.info(f"下载字幕: {vid} - {title_preview}...", video_id=vid)
                
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    raise TaskCancelledError(reason)
                
                # 检查是否有检测结果
                if not data.detection_result:
                    raise AppException(
                        message="缺少检测结果",
                        error_type=ErrorType.INVALID_INPUT
                    )
                
                # 创建临时目录
                data.temp_dir = Path("temp") / vid
                data.temp_dir.mkdir(parents=True, exist_ok=True)
                data.temp_dir_created = True
                
                # 下载字幕
                downloader = SubtitleDownloader(
                    proxy_manager=self.proxy_manager,
                    cookie_manager=self.cookie_manager
                )
                download_result = downloader.download(
                    data.video_info,
                    data.detection_result,
                    self.language_config,
                    data.temp_dir,
                    cancel_token=self.cancel_token
                )
                
                # 检查下载结果
                if not download_result.get("original"):
                    error_msg = "下载原始字幕失败"
                    logger.error(error_msg, video_id=vid)
                    if self.on_log:
                        try:
                            self.on_log("ERROR", error_msg, vid)
                        except Exception:
                            pass
                    
                    if not self.dry_run:
                        # 失败记录会在 StageQueue._log_failure 中处理
                        data.error_type = ErrorType.NETWORK
                        data.processing_failed = True
                    else:
                        data.skip_reason = "下载原始字幕失败（Dry Run）"
                    
                    return data
                
                # 保存下载结果
                data.download_result = download_result
                
                logger.info(f"字幕下载完成: {vid}", video_id=vid)
                return data
                
            except TaskCancelledError as e:
                # 任务已取消
                reason = e.reason or "用户取消"
                logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
                data.error = e
                data.error_type = ErrorType.CANCELLED
                data.error_stage = "download"
                return data
            except AppException as e:
                # 应用异常
                data.error = e
                data.error_type = e.error_type
                data.error_stage = "download"
                data.processing_failed = True
                logger.error(f"下载字幕失败: {vid} - {e}", video_id=vid)
                return data
            except Exception as e:
                # 未知异常
                app_error = AppException(
                    message=f"下载字幕失败: {str(e)}",
                    error_type=ErrorType.UNKNOWN,
                    cause=e
                )
                data.error = app_error
                data.error_type = ErrorType.UNKNOWN
                data.error_stage = "download"
                data.processing_failed = True
                logger.error(f"下载字幕异常: {vid} - {e}", video_id=vid)
                import traceback
                logger.debug(traceback.format_exc(), video_id=vid)
                return data
            finally:
                # 清理日志上下文
                clear_log_context()
        
        return processor
    
    def _create_translate_processor(self) -> Callable[[StageData], StageData]:
        """创建 TRANSLATE 阶段处理器
        
        Returns:
            处理器函数
        """
        def processor(data: StageData) -> StageData:
            """处理 TRANSLATE 阶段
            
            1. 检查哪些语言有官方字幕，哪些需要翻译
            2. 如果有需要翻译的语言，调用翻译器
            3. 合并翻译结果和官方字幕
            4. 检查是否所有目标语言都有翻译结果
            """
            vid = data.video_info.video_id
            
            try:
                # 设置日志上下文
                if data.run_id:
                    set_log_context(run_id=data.run_id, task="translate", video_id=vid)
                
                logger.info(f"翻译字幕: {vid}", video_id=vid)
                
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    raise TaskCancelledError(reason)
                
                # 检查是否有必要的输入数据
                if not data.detection_result:
                    raise AppException(
                        message="缺少检测结果",
                        error_type=ErrorType.INVALID_INPUT
                    )
                if not data.download_result:
                    raise AppException(
                        message="缺少下载结果",
                        error_type=ErrorType.INVALID_INPUT
                    )
                
                # 优化：先检查哪些语言有官方字幕，哪些需要翻译
                translation_result = {}
                official_translations = data.download_result.get("official_translations", {})
                needs_translation = []  # 需要翻译的语言列表
                
                # 详细日志：记录下载到的所有官方字幕
                logger.info(
                    f"翻译决策：已下载的官方字幕: {list(official_translations.keys())}, 目标语言: {self.language_config.subtitle_target_languages}, 策略: {self.language_config.translation_strategy}",
                    video_id=vid
                )
                
                # AI_ONLY 策略特殊处理：即使有官方字幕也要调用 AI 翻译
                if self.language_config.translation_strategy == "AI_ONLY" or self.force:
                    # AI_ONLY 模式或强制重译：所有语言都需要翻译（忽略官方字幕）
                    needs_translation = self.language_config.subtitle_target_languages.copy()
                    if self.language_config.translation_strategy == "AI_ONLY":
                        logger.info(
                            f"翻译策略为 AI_ONLY，所有目标语言都需要 AI 翻译（忽略官方字幕）。需要翻译的语言: {needs_translation}",
                            video_id=vid
                        )
                    else:
                        logger.info(
                            f"强制重译模式，所有目标语言都需要重新翻译。需要翻译的语言: {needs_translation}",
                            video_id=vid
                        )
                else:
                    # OFFICIAL_ONLY 或 OFFICIAL_AUTO_THEN_AI 策略：优先使用官方字幕
                    # 辅助函数：检查语言代码是否匹配（处理 en vs en-US 的情况）
                    def lang_matches(lang1: str, lang2: str) -> bool:
                        """检查两个语言代码是否匹配（考虑主语言代码）"""
                        if lang1 == lang2:
                            return True
                        
                        # 特殊处理：zh-CN 和 zh-TW 不互相匹配
                        lang1_lower = lang1.lower()
                        lang2_lower = lang2.lower()
                        if (lang1_lower in ["zh-cn", "zh_cn"] and lang2_lower in ["zh-tw", "zh_tw"]) or \
                           (lang1_lower in ["zh-tw", "zh_tw"] and lang2_lower in ["zh-cn", "zh_cn"]):
                            return False
                        
                        # 其他语言：提取主语言代码进行匹配
                        main1 = lang1.split("-")[0].split("_")[0].lower()
                        main2 = lang2.split("-")[0].split("_")[0].lower()
                        return main1 == main2
                    
                    for target_lang in self.language_config.subtitle_target_languages:
                        # 先尝试精确匹配
                        official_path = official_translations.get(target_lang)
                        
                        # 如果精确匹配失败，尝试模糊匹配（如 en-US 匹配 en）
                        if not official_path or not official_path.exists():
                            for detected_lang, path in official_translations.items():
                                if lang_matches(detected_lang, target_lang) and path and path.exists():
                                    official_path = path
                                    logger.debug(
                                        f"目标语言 {target_lang} 通过模糊匹配找到官方字幕（检测到的语言: {detected_lang}）",
                                        video_id=vid
                                    )
                                    break
                        
                        # 检查是否有官方字幕
                        if official_path and official_path.exists():
                            # 有官方字幕，直接使用
                            translation_result[target_lang] = official_path
                            logger.info(
                                f"目标语言 {target_lang} 使用官方字幕: {official_path.name}",
                                video_id=vid
                            )
                        else:
                            # 没有官方字幕，需要翻译
                            needs_translation.append(target_lang)
                            logger.info(
                                f"目标语言 {target_lang} 无官方字幕，需要 AI 翻译",
                                video_id=vid
                            )
                    
                    # 如果所有语言都有官方字幕，且策略允许，可以完全跳过翻译步骤
                    if not needs_translation:
                        logger.info(
                            f"所有目标语言都有官方字幕，跳过翻译步骤（策略: {self.language_config.translation_strategy}）",
                            video_id=vid
                        )
                
                # 如果有语言需要翻译，进入翻译步骤
                if needs_translation:
                    logger.info(
                        f"开始翻译步骤，需要翻译的语言: {needs_translation}",
                        video_id=vid
                    )
                    if not self.translation_llm:
                        # LLM 不可用
                        needs_ai = (
                            self.language_config.translation_strategy in ["AI_ONLY", "OFFICIAL_AUTO_THEN_AI"]
                        )
                        
                        if needs_ai:
                            # 需要翻译但 LLM 不可用
                            if self.translation_llm_init_error:
                                if self.translation_llm_init_error_type == ErrorType.AUTH:
                                    warning_msg = f"翻译 AI 初始化失败（API Key 无效或权限不足）：{self.translation_llm_init_error}，以下语言无法翻译：{', '.join(needs_translation)}"
                                else:
                                    warning_msg = f"翻译 AI 初始化失败：{self.translation_llm_init_error}，以下语言无法翻译：{', '.join(needs_translation)}"
                            else:
                                warning_msg = f"翻译 AI 不可用（可能是 API Key 无效或未启用），以下语言无法翻译：{', '.join(needs_translation)}"
                            logger.warning(warning_msg, video_id=vid)
                            if self.on_log:
                                try:
                                    self.on_log("WARN", warning_msg, vid)
                                except Exception:
                                    pass
                        else:
                            # OFFICIAL_ONLY 策略，但部分语言没有官方字幕
                            logger.warning(f"翻译策略为 OFFICIAL_ONLY，但以下语言无官方字幕：{', '.join(needs_translation)}", video_id=vid)
                    else:
                        # LLM 可用，调用翻译
                        logger.info(
                            f"调用翻译器，翻译目标语言: {needs_translation}",
                            video_id=vid
                        )
                        translator = SubtitleTranslator(llm=self.translation_llm, language_config=self.language_config)
                        # 只翻译需要的语言
                        partial_result = translator.translate(
                            data.video_info,
                            data.detection_result,
                            self.language_config,
                            data.download_result,
                            data.temp_dir,
                            force_retranslate=self.force,
                            target_languages=needs_translation,
                            cancel_token=self.cancel_token
                        )
                        logger.info(
                            f"翻译器返回结果: {list(partial_result.keys())}",
                            video_id=vid
                        )
                        # 合并翻译结果（已有官方字幕的保持不变）
                        translation_result.update(partial_result)
                        logger.info(
                            f"合并后的翻译结果: {list(translation_result.keys())}",
                            video_id=vid
                        )
                else:
                    logger.info(
                        f"无需翻译，直接使用官方字幕。翻译结果: {list(translation_result.keys())}",
                        video_id=vid
                    )
                
                # 检查是否有翻译结果
                has_translation = any(
                    path and path.exists()
                    for path in translation_result.values()
                )
                
                # 检查是否所有目标语言都有翻译结果
                missing_languages = [
                    target_lang
                    for target_lang in self.language_config.subtitle_target_languages
                    if not translation_result.get(target_lang) or not translation_result[target_lang].exists()
                ]
                
                if missing_languages:
                    missing_str = ', '.join(missing_languages)
                    if self.language_config.translation_strategy == "OFFICIAL_ONLY":
                        # 如果翻译策略是 OFFICIAL_ONLY 且没有可用翻译，应该停止任务
                        error_msg = (
                            f"翻译策略为'只用官方多语言字幕'，但以下目标语言无可用官方字幕：{missing_str}。\n"
                            f"请修改翻译策略为'优先官方字幕/自动翻译，无则用 AI'，或确保视频有对应的官方字幕。"
                        )
                        logger.error(error_msg, video_id=vid)
                        if self.on_log:
                            try:
                                self.on_log("ERROR", error_msg, vid)
                            except Exception:
                                pass
                        if not self.dry_run:
                            # 失败记录会在 StageQueue._log_failure 中处理
                            data.error_type = ErrorType.CONTENT
                            data.processing_failed = True
                        else:
                            data.skip_reason = f"翻译策略为 OFFICIAL_ONLY，但以下语言无可用官方字幕：{missing_str}（Dry Run）"
                        
                        # 创建异常对象用于失败记录
                        data.error = AppException(message=error_msg, error_type=ErrorType.CONTENT)
                        return data
                    else:
                        # 其他策略下，翻译失败不视为整体失败，继续处理
                        logger.warning(f"以下目标语言翻译失败或无可用翻译：{missing_str}", video_id=vid)
                        if not self.dry_run:
                            # 如果有初始化失败的错误类型，使用它；否则使用 UNKNOWN
                            error_type = self.translation_llm_init_error_type if self.translation_llm_init_error_type else ErrorType.UNKNOWN
                            # 构建失败原因
                            if self.translation_llm_init_error:
                                if error_type == ErrorType.AUTH:
                                    reason = f"翻译 AI 初始化失败（API Key 无效或权限不足）：{self.translation_llm_init_error}，目标语言翻译失败：{missing_str}"
                                else:
                                    reason = f"翻译 AI 初始化失败：{self.translation_llm_init_error}，目标语言翻译失败：{missing_str}"
                            else:
                                reason = f"翻译失败或无可用翻译：{missing_str}"
                            
                            # 失败记录会在 StageQueue._log_failure 中处理
                            # 但这里需要设置错误信息以便记录
                            data.error = AppException(message=reason, error_type=error_type)
                            data.error_type = error_type
                            # 注意：这里不设置 processing_failed = True，因为翻译失败不视为整体失败
                
                # 保存翻译结果
                data.translation_result = translation_result
                
                logger.info(f"翻译完成: {vid}", video_id=vid)
                return data
                
            except TaskCancelledError as e:
                # 任务已取消
                reason = e.reason or "用户取消"
                logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
                data.error = e
                data.error_type = ErrorType.CANCELLED
                data.error_stage = "translate"
                return data
            except AppException as e:
                # 应用异常
                data.error = e
                data.error_type = e.error_type
                data.error_stage = "translate"
                data.processing_failed = True
                logger.error(f"翻译字幕失败: {vid} - {e}", video_id=vid)
                return data
            except Exception as e:
                # 未知异常
                app_error = AppException(
                    message=f"翻译字幕失败: {str(e)}",
                    error_type=ErrorType.UNKNOWN,
                    cause=e
                )
                data.error = app_error
                data.error_type = ErrorType.UNKNOWN
                data.error_stage = "translate"
                data.processing_failed = True
                logger.error(f"翻译字幕异常: {vid} - {e}", video_id=vid)
                import traceback
                logger.debug(traceback.format_exc(), video_id=vid)
                return data
            finally:
                # 清理日志上下文
                clear_log_context()
        
        return processor
    
    def _create_summarize_processor(self) -> Callable[[StageData], StageData]:
        """创建 SUMMARIZE 阶段处理器
        
        Returns:
            处理器函数
        """
        def processor(data: StageData) -> StageData:
            """处理 SUMMARIZE 阶段
            
            1. 检查是否有翻译结果或原始字幕，以及是否有 summary_llm
            2. 如果有，调用摘要生成器
            3. 摘要失败不视为整体失败
            """
            vid = data.video_info.video_id
            
            try:
                # 设置日志上下文
                if data.run_id:
                    set_log_context(run_id=data.run_id, task="summarize", video_id=vid)
                
                # 检查是否有必要的输入数据和 summary_llm
                if not self.summary_llm:
                    logger.debug(f"摘要 LLM 不可用，跳过摘要生成: {vid}", video_id=vid)
                    data.summary_result = None
                    return data
                
                # 检查是否有翻译结果或原始字幕
                has_translation = False
                if data.translation_result:
                    has_translation = any(
                        path and path.exists()
                        for path in data.translation_result.values()
                    )
                
                has_original = False
                if data.download_result and data.download_result.get("original"):
                    has_original = data.download_result["original"].exists()
                
                if not (has_translation or has_original):
                    logger.debug(f"无可用字幕，跳过摘要生成: {vid}", video_id=vid)
                    data.summary_result = None
                    return data
                
                logger.info(f"生成摘要: {vid}", video_id=vid)
                
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    raise TaskCancelledError(reason)
                
                # 生成摘要
                summarizer = Summarizer(llm=self.summary_llm, language_config=self.language_config)
                summary_path = summarizer.summarize(
                    data.video_info,
                    self.language_config,
                    data.translation_result or {},
                    data.download_result or {},
                    data.temp_dir,
                    force_regenerate=self.force
                )
                
                if not summary_path:
                    logger.warning("摘要生成失败", video_id=vid)
                    if not self.dry_run:
                        # 尝试从 summarizer 获取错误类型
                        summary_error = summarizer.get_summary_error()
                        error_type = ErrorType.UNKNOWN
                        if summary_error:
                            error_type = summary_error.error_type
                        
                        # 失败记录会在 StageQueue._log_failure 中处理
                        # 但这里需要设置错误信息以便记录
                        data.error = AppException(
                            message="摘要生成失败",
                            error_type=error_type
                        )
                        data.error_type = error_type
                        # 注意：不设置 processing_failed = True，因为摘要失败不视为整体失败
                    else:
                        logger.debug("[Dry Run] 摘要生成失败（Dry Run）", video_id=vid)
                else:
                    # 保存摘要结果（已经是 Path 类型）
                    data.summary_result = summary_path
                    logger.info(f"摘要生成完成: {vid}", video_id=vid)
                
                return data
                
            except TaskCancelledError as e:
                # 任务已取消
                reason = e.reason or "用户取消"
                logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
                data.error = e
                data.error_type = ErrorType.CANCELLED
                data.error_stage = "summarize"
                # 取消不视为失败，但需要清理资源
                return data
            except AppException as e:
                # 应用异常
                data.error = e
                data.error_type = e.error_type
                data.error_stage = "summarize"
                # 摘要失败不视为整体失败
                logger.error(f"生成摘要失败: {vid} - {e}", video_id=vid)
                return data
            except Exception as e:
                # 未知异常
                app_error = AppException(
                    message=f"生成摘要失败: {str(e)}",
                    error_type=ErrorType.UNKNOWN,
                    cause=e
                )
                data.error = app_error
                data.error_type = ErrorType.UNKNOWN
                data.error_stage = "summarize"
                # 摘要失败不视为整体失败
                logger.error(f"生成摘要异常: {vid} - {e}", video_id=vid)
                import traceback
                logger.debug(traceback.format_exc(), video_id=vid)
                return data
            finally:
                # 清理日志上下文
                clear_log_context()
        
        return processor
    
    def _create_output_processor(self) -> Callable[[StageData], StageData]:
        """创建 OUTPUT 阶段处理器
        
        Returns:
            处理器函数
        """
        def processor(data: StageData) -> StageData:
            """处理 OUTPUT 阶段
            
            1. 写入输出文件（Dry Run 模式下跳过）
            2. 更新增量记录（如果成功）
            3. 清理临时目录（无论成功/失败）
            """
            vid = data.video_info.video_id
            
            try:
                # 设置日志上下文
                if data.run_id:
                    set_log_context(run_id=data.run_id, task="output", video_id=vid)
                
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    raise TaskCancelledError(reason)
                
                # 检查是否有必要的输入数据
                if not data.detection_result:
                    raise AppException(
                        message="缺少检测结果",
                        error_type=ErrorType.INVALID_INPUT
                    )
                if not data.download_result:
                    raise AppException(
                        message="缺少下载结果",
                        error_type=ErrorType.INVALID_INPUT
                    )
                
                # 步骤 1: 写入输出文件（Dry Run 模式下跳过）
                if not self.dry_run:
                    logger.info(f"写入输出文件: {vid}", video_id=vid)
                    
                    # 确保 translation_result 中包含所有需要的语言（包括官方字幕）
                    # 如果有官方字幕但没有在 translation_result 中，从 download_result 中补充
                    translation_result = data.translation_result or {}
                    official_translations = data.download_result.get("official_translations", {})
                    
                    for target_lang in self.language_config.subtitle_target_languages:
                        if target_lang not in translation_result and target_lang in official_translations:
                            official_path = official_translations[target_lang]
                            if official_path and official_path.exists():
                                translation_result[target_lang] = official_path
                                logger.debug(
                                    f"补充官方字幕到翻译结果: {target_lang} <- {official_path}",
                                    video_id=vid
                                )
                    
                    # 写入所有输出文件
                    self.output_writer.write_all(
                        data.video_info,
                        data.detection_result,
                        self.language_config,
                        data.download_result,
                        translation_result,
                        data.summary_result,  # summary_result 已经是 Path 类型
                        channel_name=data.video_info.channel_name,
                        channel_id=data.video_info.channel_id,
                        run_id=data.run_id,
                        translation_llm=self.translation_llm,
                        summary_llm=self.summary_llm
                    )
                    
                    logger.info(f"输出文件写入完成: {vid}", video_id=vid)
                else:
                    logger.debug(f"[Dry Run] 跳过写入输出文件: {vid}", video_id=vid)
                
                # 步骤 2: 更新增量记录（仅在成功时，Dry Run 模式下跳过）
                if self.archive_path and not self.dry_run:
                    self.incremental_manager.mark_as_processed(vid, self.archive_path)
                    logger.debug(f"已更新增量记录: {vid}", video_id=vid)
                elif self.archive_path and self.dry_run:
                    logger.debug(f"[Dry Run] 跳过更新增量记录: {vid}", video_id=vid)
                
                logger.info(f"处理完成: {vid}", video_id=vid)
                return data
                
            except TaskCancelledError as e:
                # 任务已取消
                reason = e.reason or "用户取消"
                logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
                data.error = e
                data.error_type = ErrorType.CANCELLED
                data.error_stage = "output"
                # 取消不视为失败，但需要清理资源
                return data
            except AppException as e:
                # 应用异常
                data.error = e
                data.error_type = e.error_type
                data.error_stage = "output"
                data.processing_failed = True
                logger.error(f"输出文件失败: {vid} - {e}", video_id=vid)
                return data
            except Exception as e:
                # 未知异常
                app_error = AppException(
                    message=f"输出文件失败: {str(e)}",
                    error_type=ErrorType.UNKNOWN,
                    cause=e
                )
                data.error = app_error
                data.error_type = ErrorType.UNKNOWN
                data.error_stage = "output"
                data.processing_failed = True
                logger.error(f"输出文件异常: {vid} - {e}", video_id=vid)
                import traceback
                logger.debug(traceback.format_exc(), video_id=vid)
                return data
            finally:
                # 步骤 3: 清理临时目录（无论成功/失败/被取消都尝试清理）
                if data.temp_dir_created and data.temp_dir and data.temp_dir.exists():
                    try:
                        shutil.rmtree(data.temp_dir)
                        logger.debug(f"已清理临时目录: {data.temp_dir}", video_id=vid)
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {e}", video_id=vid)
                
                # 清理日志上下文
                clear_log_context()
        
        return processor
    
    def process_videos(self, videos: List[VideoInfo]) -> Dict[str, int]:
        """处理视频列表
        
        Args:
            videos: 视频列表
        
        Returns:
            统计信息：{"total": 总数, "success": 成功数, "failed": 失败数}
        """
        if not videos:
            logger.warning("视频列表为空")
            return {
                "total": 0,
                "success": 0,
                "failed": 0
            }
        
        self._total_count = len(videos)
        self._success_count = 0
        self._failed_count = 0
        
        logger.info(f"开始处理 {self._total_count} 个视频（分阶段队列模式）", run_id=self.run_id)
        
        try:
            # 1. 启动所有阶段
            self.detect_queue.start()
            self.download_queue.start()
            self.translate_queue.start()
            self.summarize_queue.start()
            self.output_queue.start()
            
            # 2. 将视频加入 DETECT 阶段（第一个阶段）
            for video in videos:
                data = StageData(
                    video_info=video,
                    run_id=self.run_id  # 添加 run_id 到 data（用于失败记录）
                )
                self.detect_queue.enqueue(data)
            
            # 3. 等待所有阶段完成
            # 等待所有队列为空且所有任务完成
            import time
            while True:
                if self.cancel_token and self.cancel_token.is_cancelled():
                    logger.info("检测到取消信号，停止处理")
                    break
                
                # 检查所有阶段是否完成
                if (self.detect_queue.is_empty() and
                    self.download_queue.is_empty() and
                    self.translate_queue.is_empty() and
                    self.summarize_queue.is_empty() and
                    self.output_queue.is_empty()):
                    break
                
                time.sleep(0.5)  # 等待 0.5 秒后再次检查
            
            # 4. 汇总统计信息
            detect_stats = self.detect_queue.get_stats()
            download_stats = self.download_queue.get_stats()
            translate_stats = self.translate_queue.get_stats()
            summarize_stats = self.summarize_queue.get_stats()
            output_stats = self.output_queue.get_stats()
            
            # 成功数：OUTPUT 阶段成功处理的数量
            self._success_count = output_stats["processed"]
            # 失败数：所有阶段的失败数之和
            self._failed_count = (
                detect_stats["failed"] +
                download_stats["failed"] +
                translate_stats["failed"] +
                summarize_stats["failed"] +
                output_stats["failed"]
            )
            
            logger.info(
                f"处理完成: 总计 {self._total_count}, 成功 {self._success_count}, 失败 {self._failed_count}",
                run_id=self.run_id
            )
            
            return {
                "total": self._total_count,
                "success": self._success_count,
                "failed": self._failed_count
            }
        
        finally:
            # 5. 停止所有阶段
            self.output_queue.stop()
            self.summarize_queue.stop()
            self.translate_queue.stop()
            self.download_queue.stop()
            self.detect_queue.stop()
            
            # 关闭所有执行器
            self.output_executor.shutdown(wait=True)
            self.summarize_executor.shutdown(wait=True)
            self.translate_executor.shutdown(wait=True)
            self.download_executor.shutdown(wait=True)
            self.detect_executor.shutdown(wait=True)
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            if hasattr(self, 'output_executor'):
                self.output_executor.shutdown(wait=False)
            if hasattr(self, 'summarize_executor'):
                self.summarize_executor.shutdown(wait=False)
            if hasattr(self, 'translate_executor'):
                self.translate_executor.shutdown(wait=False)
            if hasattr(self, 'download_executor'):
                self.download_executor.shutdown(wait=False)
            if hasattr(self, 'detect_executor'):
                self.detect_executor.shutdown(wait=False)
        except Exception:
            pass

