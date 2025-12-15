"""
轻量级状态存储
用于在 UI 组件间共享状态，避免深层传递
"""
from typing import Any, Dict, Optional, Callable
from threading import Lock
from dataclasses import dataclass


@dataclass
class AppState:
    """应用状态
    
    存储全局 UI 状态，避免在组件间深层传递
    """
    # 运行状态
    is_processing: bool = False
    running_status: str = "Idle"  # 使用英文作为默认值，实际显示时会通过 t() 函数翻译
    
    # 当前页面
    current_page: str = "channel"
    current_mode: str = "频道模式"
    
    # 统计信息
    stats: Dict[str, int] = None
    
    # 当前主题和语言
    current_theme: str = "light"
    current_language: str = "zh-CN"
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "current": 0
            }


class StateManager:
    """状态管理器
    
    提供线程安全的状态存储和访问
    """
    
    def __init__(self):
        self._state = AppState()
        self._lock = Lock()
        self._listeners: Dict[str, list] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取状态值
        
        Args:
            key: 状态键（支持点号分隔的嵌套键，如 "stats.total"）
            default: 默认值
        
        Returns:
            状态值
        """
        with self._lock:
            keys = key.split(".")
            value = self._state
            for k in keys:
                if isinstance(value, dict):
                    if k in value:
                        value = value[k]
                    else:
                        return default
                elif hasattr(value, k):
                    value = getattr(value, k)
                else:
                    return default
            return value
    
    def set(self, key: str, value: Any) -> None:
        """设置状态值
        
        Args:
            key: 状态键（支持点号分隔的嵌套键，如 "stats.total"）
            value: 状态值
        """
        with self._lock:
            keys = key.split(".")
            target = self._state
            
            # 导航到目标对象（最后一个键除外）
            for k in keys[:-1]:
                if hasattr(target, k):
                    target = getattr(target, k)
                elif isinstance(target, dict) and k in target:
                    target = target[k]
                else:
                    # 如果路径不存在，创建字典
                    if not isinstance(target, dict):
                        return
                    if k not in target:
                        target[k] = {}
                    target = target[k]
            
            # 设置值
            final_key = keys[-1]
            if isinstance(target, dict):
                target[final_key] = value
            else:
                # 对于对象，使用 setattr（即使是动态属性也可以设置）
                setattr(target, final_key, value)
            
            # 通知监听者
            self._notify_listeners(key, value)
    
    def update(self, **kwargs) -> None:
        """批量更新状态
        
        Args:
            **kwargs: 要更新的键值对
        """
        with self._lock:
            for key, value in kwargs.items():
                self.set(key, value)
    
    def subscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        """订阅状态变化
        
        Args:
            key: 状态键
            callback: 回调函数，接收新值作为参数
        """
        with self._lock:
            if key not in self._listeners:
                self._listeners[key] = []
            if callback not in self._listeners[key]:
                self._listeners[key].append(callback)
    
    def unsubscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        """取消订阅状态变化
        
        Args:
            key: 状态键
            callback: 要移除的回调函数
        """
        with self._lock:
            if key in self._listeners:
                try:
                    self._listeners[key].remove(callback)
                except ValueError:
                    pass
    
    def _notify_listeners(self, key: str, value: Any) -> None:
        """通知监听者状态变化"""
        # 在锁外调用回调，避免死锁
        listeners = self._listeners.get(key, [])
        for callback in listeners:
            try:
                callback(value)
            except Exception:
                pass
    
    def get_state(self) -> AppState:
        """获取完整状态对象（只读）"""
        with self._lock:
            return self._state


# 全局状态管理器实例
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """获取全局状态管理器实例（单例模式）"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager

