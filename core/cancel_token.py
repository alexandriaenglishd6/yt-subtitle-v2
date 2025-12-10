"""
取消令牌（CancelToken）
用于支持用户主动取消操作，各环节必须周期性检查并及时终止
"""
import threading
from typing import Optional


class CancelToken:
    """取消令牌
    
    用于在长时间运行的任务中支持取消操作。
    各环节必须周期性检查 `is_cancelled()` 并及时终止。
    
    Example:
        token = CancelToken()
        
        def long_running_task(token: CancelToken):
            for i in range(1000):
                if token.is_cancelled():
                    return  # 及时终止
                # 执行任务...
        
        # 在另一个线程中取消
        token.cancel()
    """
    
    def __init__(self):
        """初始化取消令牌"""
        self._cancelled = False
        self._lock = threading.Lock()
        self._reason: Optional[str] = None
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """取消操作
        
        Args:
            reason: 取消原因（可选）
        """
        with self._lock:
            self._cancelled = True
            self._reason = reason
    
    def is_cancelled(self) -> bool:
        """检查是否已取消
        
        Returns:
            如果已取消返回 True，否则返回 False
        """
        with self._lock:
            return self._cancelled
    
    def get_reason(self) -> Optional[str]:
        """获取取消原因
        
        Returns:
            取消原因，如果未取消或未提供原因则返回 None
        """
        with self._lock:
            return self._reason
    
    def reset(self) -> None:
        """重置取消状态（谨慎使用，主要用于测试）"""
        with self._lock:
            self._cancelled = False
            self._reason = None

