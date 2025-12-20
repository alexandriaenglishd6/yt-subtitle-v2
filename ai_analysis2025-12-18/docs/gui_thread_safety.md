# GUI 线程安全与事件流规范

> **版本**：2025-12-14  
> **适用范围**：所有 GUI 相关代码（`ui/` 目录下的所有模块）  
> **优先级**：必须严格遵守，违反可能导致 UI 卡死、崩溃或数据不一致

---

## 1. 核心原则

### 1.1 线程分离原则

**所有 UI 更新必须在主线程执行，业务逻辑只在后台线程执行。**

- **主线程（UI 线程）**：负责所有 UI 控件的创建、更新、事件处理
- **后台线程（工作线程）**：负责耗时操作（网络请求、文件 I/O、AI 调用等）

### 1.2 通信机制

**UI 与 Core 通过回调函数（callbacks）进行通信。**

- 后台线程通过回调函数通知主线程更新 UI
- 所有回调函数必须使用 `self.after(0, ...)` 包装，确保在主线程执行

---

## 2. 实现规范

### 2.1 后台任务执行

**使用 `VideoProcessor._run_task_in_thread()` 方法在后台线程执行任务。**

```python
# ui/business_logic.py
def _run_task_in_thread(
    self,
    task_fn: Callable[[], None],
    on_status: Callable[[str], None],
    on_complete: Optional[Callable[[], None]] = None
) -> threading.Thread:
    """在后台线程中执行任务"""
    def wrapper():
        try:
            task_fn()  # 业务逻辑在后台线程执行
        except Exception as e:
            logger.error(f"Task failed: {e}")
        finally:
            on_status(t("status_idle"))  # 回调函数会通过 after() 在主线程执行
            if on_complete:
                on_complete()
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread
```

**关键点**：
- 任务函数 `task_fn` 在后台线程执行
- 回调函数 `on_status`、`on_complete` 通过 `self.after(0, ...)` 在主线程执行
- 使用 `daemon=True` 确保程序退出时线程自动终止

### 2.2 线程安全的回调函数

**所有从后台线程调用 UI 更新的回调函数必须使用 `self.after(0, ...)` 包装。**

```python
# ui/main_window.py
def _create_safe_callbacks(self):
    """创建线程安全的回调函数集"""
    def safe_on_log(level: str, message: str, video_id: Optional[str] = None):
        """线程安全的日志回调"""
        self.after(0, lambda: self._on_log(level, message, video_id))
    
    def safe_on_status(status: str):
        """线程安全的状态更新回调"""
        self.after(0, lambda: self._on_status(status))
    
    def safe_on_stats(stats: dict):
        """线程安全的统计信息更新回调"""
        self.after(0, lambda: self._on_stats(stats))
    
    def safe_on_complete():
        """线程安全的完成回调"""
        self.after(0, lambda: setattr(self, 'is_processing', False))
        self.after(0, self._restore_processing_buttons)
    
    return safe_on_log, safe_on_status, safe_on_stats, safe_on_complete
```

**关键点**：
- `self.after(0, callback)` 将回调函数调度到主线程的事件循环中执行
- `after(0, ...)` 表示"在下一个事件循环迭代时执行"，确保在主线程执行
- 所有 UI 更新操作（设置文本、更新按钮状态、添加日志等）都必须通过 `after()` 执行

### 2.3 禁止的操作

**以下操作严禁在后台线程中直接执行：**

1. ❌ **直接操作 UI 控件**
   ```python
   # 错误示例
   def task():
       self.log_panel.append_log("INFO", "消息")  # ❌ 在后台线程直接操作 UI
   ```

2. ❌ **直接访问 UI 状态**
   ```python
   # 错误示例
   def task():
       if self.is_processing:  # ❌ 在后台线程直接读取 UI 状态
           return
   ```

3. ❌ **直接调用 UI 方法**
   ```python
   # 错误示例
   def task():
       self._update_stats_display()  # ❌ 在后台线程直接调用 UI 方法
   ```

**正确做法**：
```python
# 正确示例
def task():
    # 业务逻辑在后台线程执行
    result = process_data()
    # 通过回调函数更新 UI（回调函数内部使用 after()）
    self.after(0, lambda: self._update_ui(result))
```

---

## 3. 事件流示例

### 3.1 完整处理流程

```
用户点击"开始处理"按钮
    ↓
主线程：调用 VideoProcessor.process_videos()
    ↓
主线程：创建线程安全的回调函数（使用 after()）
    ↓
主线程：调用 _run_task_in_thread() 启动后台线程
    ↓
后台线程：执行业务逻辑（获取视频列表、处理视频等）
    ↓
后台线程：通过回调函数通知主线程（on_log, on_status, on_stats）
    ↓
主线程：回调函数通过 after(0, ...) 调度到主线程执行
    ↓
主线程：更新 UI（日志面板、状态栏、统计信息等）
    ↓
后台线程：任务完成，调用 on_complete 回调
    ↓
主线程：恢复按钮状态，更新处理标志
```

### 3.2 代码示例

```python
# ui/main_window.py
def _on_start_processing(self):
    """开始处理按钮点击事件（主线程）"""
    # 创建线程安全的回调函数
    safe_on_log, safe_on_status, safe_on_stats, safe_on_complete = \
        self._create_safe_callbacks()
    
    # 启动后台任务
    self.is_processing = True
    self.video_processor.process_videos(
        url=self.current_page.get_url(),
        on_log=safe_on_log,      # 线程安全的回调
        on_status=safe_on_status,
        on_stats=safe_on_stats,
        on_complete=safe_on_complete
    )

# ui/business_logic.py
def process_videos(self, url, on_log, on_status, on_stats, on_complete):
    """处理视频（在后台线程执行）"""
    def task():
        # 业务逻辑在后台线程执行
        videos = self._fetch_videos(url, on_log, on_status)
        # on_log 回调会通过 after() 在主线程执行
        on_log("INFO", f"找到 {len(videos)} 个视频")
        # ... 更多业务逻辑
    
    return self._run_task_in_thread(task, on_status, on_complete)
```

---

## 4. 常见场景

### 4.1 日志输出

```python
# 后台线程中
def task():
    # 业务逻辑
    result = do_something()
    # 通过回调函数输出日志（回调函数内部使用 after()）
    on_log("INFO", f"处理完成: {result}")

# 回调函数（在主线程执行）
def safe_on_log(level: str, message: str, video_id: Optional[str] = None):
    self.after(0, lambda: self._on_log(level, message, video_id))

def _on_log(self, level: str, message: str, video_id: Optional[str] = None):
    # 在主线程中更新 UI
    self.log_panel.append_log(level, message, video_id)
```

### 4.2 状态更新

```python
# 后台线程中
def task():
    on_status("处理中...")
    # 业务逻辑
    on_status("完成")

# 回调函数（在主线程执行）
def safe_on_status(status: str):
    self.after(0, lambda: self._on_status(status))

def _on_status(self, status: str):
    # 在主线程中更新状态栏
    self.toolbar.set_status(status)
```

### 4.3 统计信息更新

```python
# 后台线程中
def task():
    stats = {"total": 10, "success": 5, "failed": 0}
    on_stats(stats)

# 回调函数（在主线程执行）
def safe_on_stats(stats: dict):
    self.after(0, lambda: self._on_stats(stats))

def _on_stats(self, stats: dict):
    # 在主线程中更新统计信息显示
    self.log_panel.update_stats(stats)
```

---

## 5. 检查清单

在实现或修改 GUI 代码时，请确保：

- [ ] 所有耗时操作（网络请求、文件 I/O、AI 调用）都在后台线程执行
- [ ] 所有 UI 更新操作都通过 `self.after(0, ...)` 在主线程执行
- [ ] 所有回调函数都使用 `_create_safe_callbacks()` 创建的线程安全版本
- [ ] 后台线程中不直接操作 UI 控件
- [ ] 后台线程中不直接访问 UI 状态变量
- [ ] 使用 `threading.Thread` 时设置 `daemon=True`
- [ ] 任务完成时正确调用 `on_complete` 回调

---

## 6. 相关文件

### 6.1 核心实现文件

- **`ui/business_logic.py`**：业务逻辑封装，包含 `_run_task_in_thread()` 方法
- **`ui/main_window.py`**：主窗口，包含 `_create_safe_callbacks()` 方法
- **`ui/pages/*.py`**：各个页面，使用线程安全的回调函数

### 6.2 关键方法

- **`VideoProcessor._run_task_in_thread()`**：在后台线程执行任务
- **`MainWindow._create_safe_callbacks()`**：创建线程安全的回调函数
- **`MainWindow.after()`**：调度回调函数到主线程执行

---

## 7. 故障排查

### 7.1 UI 卡死

**症状**：UI 界面无响应，按钮点击无反应

**可能原因**：
- 在后台线程中执行了耗时操作，但没有使用 `after()` 更新 UI
- 在主线程中执行了耗时操作（网络请求、文件 I/O 等）

**解决方法**：
- 确保所有耗时操作都在后台线程执行
- 确保所有 UI 更新都通过 `after()` 在主线程执行

### 7.2 数据不一致

**症状**：UI 显示的数据与实际数据不一致

**可能原因**：
- 在后台线程中直接修改 UI 状态变量
- 多个线程同时访问共享状态

**解决方法**：
- 所有状态更新都通过回调函数在主线程执行
- 使用 `after()` 确保状态更新在主线程执行

### 7.3 程序崩溃

**症状**：程序运行时崩溃，出现线程相关错误

**可能原因**：
- 在后台线程中直接操作 UI 控件
- 回调函数没有使用 `after()` 包装

**解决方法**：
- 检查所有 UI 操作是否都在主线程执行
- 确保所有回调函数都使用 `after()` 包装

---

## 8. 最佳实践

1. **统一使用回调函数**：所有后台线程与主线程的通信都通过回调函数
2. **使用线程安全的回调**：使用 `_create_safe_callbacks()` 创建的回调函数
3. **明确线程边界**：在代码注释中明确标注哪些代码在主线程执行，哪些在后台线程执行
4. **错误处理**：在回调函数中添加异常处理，避免回调函数异常导致程序崩溃
5. **资源清理**：任务完成时正确清理资源，调用 `on_complete` 回调

---

**文档结束**

> **提示**：在修改 GUI 代码时，请始终遵循本规范。如有疑问，请参考 `ui/business_logic.py` 和 `ui/main_window.py` 中的实现示例。

