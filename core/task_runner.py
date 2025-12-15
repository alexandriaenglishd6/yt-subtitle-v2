"""
并发执行器模块
实现队列 + worker 池并发执行，支持配置并发数
"""
import queue
import threading
from typing import Callable, Optional, Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from core.logger import get_logger

logger = get_logger()


class TaskRunner:
    """并发任务执行器
    
    使用队列 + worker 池实现并发执行，支持配置并发数。
    默认并发数 10（用于下载任务），不在代码中硬锁死上限，对过高配置只做日志警告。
    """
    
    def __init__(self, concurrency: int = 10):
        """初始化任务执行器
        
        Args:
            concurrency: 并发数，默认 10（用于下载任务）
        """
        # 验证并发数
        if concurrency <= 0:
            logger.warning(f"并发数无效（{concurrency}），重置为 1")
            concurrency = 1
        
        self.concurrency = concurrency
        
        # 对过高并发数做警告（但不阻止）
        if concurrency > 10:
            logger.warning(
                f"并发数设置较高（{concurrency}），可能导致 IP 封锁或 429 错误，请谨慎使用"
            )
        elif concurrency > 5:
            logger.info(
                f"并发数设置为 {concurrency}，建议监控网络请求频率，避免触发限流"
            )
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._task_queue: queue.Queue = queue.Queue()
        self._results: List[Any] = []
        self._errors: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._completed_count = 0
        self._total_count = 0
        self._running_tasks: Dict[Future, str] = {}  # 跟踪正在运行的任务
    
    def run_tasks(
        self,
        tasks: List[Callable[[], Any]],
        task_names: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, List[str]], None]] = None
    ) -> Dict[str, Any]:
        """并发执行任务列表
        
        Args:
            tasks: 任务函数列表（每个函数不接受参数，返回任务结果）
            task_names: 任务名称列表（用于日志），如果为 None 则使用索引
            progress_callback: 进度回调函数 (completed, total, running_tasks) -> None
        
        Returns:
            执行结果字典：
            {
                "total": 总任务数,
                "success": 成功数,
                "failed": 失败数,
                "results": 成功结果列表,
                "errors": 错误信息列表
            }
        """
        if not tasks:
            logger.warning("任务列表为空")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "results": [],
                "errors": []
            }
        
        self._total_count = len(tasks)
        self._completed_count = 0
        self._results = []
        self._errors = []
        self._running_tasks = {}
        
        # 如果没有提供任务名称，使用索引
        if task_names is None:
            task_names = [f"任务-{i+1}" for i in range(len(tasks))]
        elif len(task_names) != len(tasks):
            logger.warning(f"任务名称数量（{len(task_names)}）与任务数量（{len(tasks)}）不匹配，使用默认名称")
            task_names = [f"任务-{i+1}" for i in range(len(tasks))]
        
        logger.info(f"开始并发执行 {self._total_count} 个任务，并发数: {self.concurrency}")
        
        # 创建线程池
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            self._executor = executor
            
            # 提交所有任务
            future_to_task = {}
            for i, (task, task_name) in enumerate(zip(tasks, task_names)):
                future = executor.submit(self._execute_task, task, task_name, i)
                future_to_task[future] = (task_name, i)
                # 记录正在运行的任务
                with self._lock:
                    self._running_tasks[future] = task_name
            
            # 等待所有任务完成
            for future in as_completed(future_to_task):
                task_name, task_index = future_to_task[future]
                try:
                    result = future.result()
                    with self._lock:
                        if result is not None:
                            self._results.append(result)
                        self._completed_count += 1
                        # 从运行列表中移除
                        self._running_tasks.pop(future, None)
                        
                        # 调用进度回调
                        if progress_callback:
                            try:
                                running_list = list(self._running_tasks.values())
                                progress_callback(self._completed_count, self._total_count, running_list)
                            except Exception as e:
                                logger.warning(f"进度回调执行失败: {e}")
                except Exception as e:
                    # 提取错误类型（如果是 AppException）
                    error_type = "unknown"
                    if hasattr(e, 'error_type'):
                        error_type = e.error_type.value
                    
                    with self._lock:
                        self._errors.append({
                            "task_name": task_name,
                            "task_index": task_index,
                            "error": str(e),
                            "error_type": error_type
                        })
                        self._completed_count += 1
                        # 从运行列表中移除
                        self._running_tasks.pop(future, None)
                        
                        # 调用进度回调
                        if progress_callback:
                            try:
                                running_list = list(self._running_tasks.values())
                                progress_callback(self._completed_count, self._total_count, running_list)
                            except Exception as e:
                                logger.warning(f"进度回调执行失败: {e}")
                    
                    logger.error(f"任务执行失败 [{task_name}]: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
        
        # 统计成功数：只有 True 才算成功，False 和 None 都算失败
        success_count = sum(1 for r in self._results if r is True)
        failed_count = len(self._errors) + sum(1 for r in self._results if r is not True)
        
        logger.info(f"任务执行完成: 总计 {self._total_count}, 成功 {success_count}, 失败 {failed_count}")
        
        return {
            "total": self._total_count,
            "success": success_count,
            "failed": failed_count,
            "results": self._results,
            "errors": self._errors
        }
    
    def _execute_task(self, task: Callable[[], Any], task_name: str, task_index: int) -> Any:
        """执行单个任务（包装函数）
        
        Args:
            task: 任务函数
            task_name: 任务名称
            task_index: 任务索引
        
        Returns:
            任务执行结果
        """
        try:
            logger.debug(f"开始执行任务 [{task_name}] ({task_index + 1}/{self._total_count})")
            result = task()
            logger.debug(f"任务完成 [{task_name}]")
            return result
        except Exception as e:
            logger.error(f"任务执行异常 [{task_name}]: {e}")
            raise
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前执行进度
        
        Returns:
            进度信息字典：{"completed": 已完成数, "total": 总数, "running": 正在运行的任务列表}
        """
        with self._lock:
            return {
                "completed": self._completed_count,
                "total": self._total_count,
                "running": list(self._running_tasks.values())
            }

