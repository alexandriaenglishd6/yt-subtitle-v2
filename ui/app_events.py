"""
事件总线
用于组件间解耦通信，支持事件发布和订阅
"""
from typing import Callable, Dict, List, Any, Optional
from threading import Lock


class EventBus:
    """事件总线
    
    提供发布-订阅模式的事件系统，用于组件间解耦通信
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = Lock()
    
    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """订阅事件
        
        Args:
            event_type: 事件类型（如 "theme_changed", "language_changed"）
            callback: 回调函数，接收事件数据作为参数
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        """取消订阅事件
        
        Args:
            event_type: 事件类型
            callback: 要移除的回调函数
        """
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass
    
    def publish(self, event_type: str, data: Any = None) -> None:
        """发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据（可选）
        """
        with self._lock:
            subscribers = self._subscribers.get(event_type, [])
        
        # 在锁外调用回调，避免死锁
        for callback in subscribers:
            try:
                callback(data)
            except Exception:
                # 忽略回调错误，避免影响其他订阅者
                pass
    
    def clear(self) -> None:
        """清空所有订阅者"""
        with self._lock:
            self._subscribers.clear()


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例（单例模式）"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# 事件类型常量
class EventType:
    """事件类型常量"""
    THEME_CHANGED = "theme_changed"
    LANGUAGE_CHANGED = "language_changed"
    PAGE_CHANGED = "page_changed"
    STATUS_CHANGED = "status_changed"
    LOG_MESSAGE = "log_message"
    STATS_UPDATED = "stats_updated"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_STOPPED = "processing_stopped"

