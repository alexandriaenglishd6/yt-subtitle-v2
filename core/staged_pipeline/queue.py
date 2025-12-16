"""
阶段队列管理
"""
import queue
import threading
from typing import Optional, Dict, List, Callable
from concurrent.futures import ThreadPoolExecutor

from core.logger import get_logger
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.failure_logger import FailureLogger
from .data_types import StageData

logger = get_logger()


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

