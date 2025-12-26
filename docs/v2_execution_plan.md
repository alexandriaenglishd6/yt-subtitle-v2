# v2.0 详细执行计划

> 开发执行顺序与注意事项

## 总览

| 阶段 | 时间 | 关键点 |
|------|------|--------|
| 1. 骨架搭建 | 2-2.5 天 | 加锁、接口定义 |
| 2. UI 布局 | 1.5-2 天 | 固定宽度、线程安全 |
| 3. 后端功能 | 3-4 天 | 容错、轮询 |
| 4. 联调测试 | 1 天 | 端到端 |
| **总计** | **~7-9 天** | |

---

## 阶段 1：骨架搭建（2-2.5 天）

### 1.1 目录结构（0.5 天）

**具体工作**：

| 任务 | 说明 |
|------|------|
| 创建 `core/scheduler/` | 调度器模块 |
| 创建 `core/pools/` | 资源池模块 |
| 创建 `core/providers/` | AI 供应商模块 |
| 移动现有代码 | 从 v1.0 迁移 |

**目录结构**：

```
core/
├── pools/
│   ├── __init__.py
│   ├── base_pool.py      # 基类
│   ├── key_pool.py       # API Key 池
│   ├── proxy_pool.py     # 代理池
│   └── cookie_pool.py    # Cookie 池
├── scheduler/
│   ├── __init__.py
│   └── task_scheduler.py # 任务调度器
└── providers/
    ├── __init__.py
    └── provider_manager.py
```

**容易出错**：

| 问题 | 解决方案 |
|------|----------|
| 循环导入 | 使用绝对导入 |
| 路径问题 | 统一用绝对导入 |

---

### 1.2 核心数据结构（1 天）

**具体工作**：

| 类 | 功能 | 核心方法 |
|----|------|----------|
| `BasePool` | 资源池基类 | `get()`, `release()`, `mark_failed()` |
| `KeyPool` | API Key 管理 | `get_available()`, `record_usage()` |
| `ProxyPool` | 代理管理 | `get_healthy()`, `health_check()` |
| `CookiePool` | Cookie 管理 | `get_valid()`, `mark_expired()` |

**代码骨架**：

```python
# core/pools/base_pool.py
from abc import ABC, abstractmethod
from threading import Lock

class BasePool(ABC):
    def __init__(self):
        self.lock = Lock()
        self.items = []
    
    @abstractmethod
    def get(self) -> any:
        pass
    
    @abstractmethod
    def release(self, item) -> None:
        pass
```

**容易出错**：

| 问题 | 解决方案 |
|------|----------|
| 忘记加锁 | 所有操作 `with self.lock:` |
| 资源未释放 | 用完必须 `release()` |
| 状态不同步 | 添加日志记录 |

---

### 1.3 调度器骨架（0.5-1 天）

**具体工作**：

| 任务 | 说明 |
|------|------|
| `TaskScheduler` 类 | 任务分发 |
| 任务队列 | 待处理/进行中/完成 |
| 状态回调 | 通知 UI 更新 |

**接口定义**：

```python
class TaskScheduler:
    def submit(self, urls: list) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def cancel(self) -> None: ...
    
    # 状态回调
    def on_progress(self, callback): ...
    def on_status_change(self, callback): ...
```

**容易出错**：

| 问题 | 解决方案 |
|------|----------|
| 回调在错误线程 | 用 `after()` 切换主线程 |
| 取消时状态未清理 | 等待线程结束 |

---

## 阶段 2：UI 布局（1.5-2 天）

### 2.1 右侧状态栏框架（0.5 天）

**具体工作**：

| 任务 | 说明 |
|------|------|
| 修改主窗口布局 | 添加右侧区域 |
| 创建 `StatusPanel` | 状态栏容器 |
| 占位数据 | 先用假数据 |

**代码示例**：

```python
class StatusPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, width=160)
        self._create_widgets()
    
    def update_progress(self, data: dict):
        self.lbl_progress.configure(...)
```

**容易出错**：

| 问题 | 解决方案 |
|------|----------|
| 宽度被挤压 | 固定 `width=160` |
| 主题切换颜色不对 | 从 `colors.py` 引用 |

---

### 2.2 语言配置精简（0.5 天）

**具体工作**：

| 任务 | 说明 |
|------|------|
| 精简主界面配置 | 只留 2 行 |
| 移动到运行参数 | 详细配置 |
| 按钮紧凑排列 | 减少间距 |

**注意事项**：
- ✅ 先列清单：哪些保留、哪些移动
- ✅ 配置绑定要同步修改

---

### 2.3 状态数据绑定（0.5-1 天）

**数据结构**：

```python
@dataclass
class StatusData:
    progress: float
    eta_minutes: float
    proxy_status: tuple  # (available, total)
    cookie_status: tuple
    api_status: tuple
    cost_asr: float
    cost_translate: float
    cost_summary: float
```

**容易出错**：

| 问题 | 解决方案 |
|------|----------|
| 刷新太频繁 | 间隔 >= 500ms |
| 刷新在错误线程 | 用 `after()` |

---

## 阶段 3：后端功能（3-4 天）

### 3.1 多 Key 轮询（1 天）

| 任务 | 说明 |
|------|------|
| `KeySelector` | 轮询选择器 |
| 使用量记录 | 每个 Key 用了多少 |
| 失败标记 | Key 失效处理 |

---

### 3.2 代理池健康监控（1 天）

| 任务 | 说明 |
|------|------|
| 健康检查 | 定期测试 |
| 失败计数 | 连续失败禁用 |
| 恢复检测 | 冷却后重试 |

---

### 3.3 三级容错（1 天）

| 级别 | 策略 |
|------|------|
| L1 | 换 Key 重试 |
| L2 | 换 Provider 重试 |
| L3 | 拆分请求重试 |

---

## 阶段 4：联调测试（1 天）

| 任务 | 说明 |
|------|------|
| 端到端测试 | 完整流程 |
| 压力测试 | 50 并发 |
| UI 状态验证 | 数据正确 |

---

## 执行检查清单

### 骨架阶段

- [ ] 创建目录结构
- [ ] 实现 BasePool
- [ ] 实现 KeyPool
- [ ] 实现 ProxyPool
- [ ] 实现 CookiePool
- [ ] 实现 TaskScheduler 骨架

### UI 阶段

- [ ] 添加右侧状态栏
- [ ] 创建 StatusPanel 组件
- [ ] 精简语言配置
- [ ] 状态数据绑定
- [ ] 主题切换测试

### 后端阶段

- [ ] 多 Key 轮询
- [ ] 代理池健康监控
- [ ] 三级容错
- [ ] 费用统计

### 联调阶段

- [ ] 端到端测试
- [ ] 压力测试
- [ ] Bug 修复
