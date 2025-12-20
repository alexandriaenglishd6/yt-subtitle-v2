# 日志与可观测性规范（logging_spec.md）

> 目标：让调试、审计和复现变得简单；确保日志有用、可读、不过度泄露隐私。  
> 适用范围：所有模块（UI/CLI/Core/AI/网络/输出）。

---

## 1. 日志去向（Sinks）

- **控制台（stdout）**：简洁 info 流（CLI 与开发环境）
- **文件日志**：`logs/app.log`（文本）；按大小或日期**滚动**保留（建议 20MB x 5 份）
- **UI 日志面板**（LogPanel）：订阅记录器 handler（只展示必要等级）
- **失败记录文件**（不等同于日志）：`out/failed_detail.log` / `out/failed_urls.txt`（见 `error_handling.md`）

> 注意：失败记录文件不是通用日志，它用于**业务失败复跑**场景，不混杂其他信息。

---

## 2. 日志等级与用途

- `DEBUG`：开发排查用，包含函数入参关键摘要、决策分支、重试次数等
- `INFO`：阶段进度、开始/结束、关键成功事件（下载完成、写文件完成）
- `WARNING`：可恢复问题（单次重试失败、代理不可用被跳过）
- `ERROR`：视频级失败或模块失败（但系统仍可继续）
- `CRITICAL`：系统级故障（配置缺失、无法初始化、日志系统不可用）

默认运行等级：`INFO`；开发时可设 `DEBUG`。

---

## 3. 基本日志格式

文本行（控制台/文件）：
[2025-12-09 14:33:21.456] [INFO ] [run:20251209_140000] [task:download] [video:dQw4w9WgXcQ] message...

pgsql
复制代码

字段说明：
- 时间戳：ISO-like 到毫秒
- 级别：固定宽度（便于扫描）
- 关联 ID：
  - `run:<batch_id>`：本次运行批次 ID
  - `task:<stage>`：download / translate / summarize / output / dryrun …
  - `video:<id>`：YouTube 视频 ID（如有）
- 消息：简明扼要，避免长文本

> 规范：同一“视频处理链”中，必须保持 `run` 与 `video` 贯穿全流程。

---

## 4. JSON 事件（可选增强）

对关键事件（开始/成功/失败）追加一行 JSON（方便统计脚本）：

```json
{"ts":"2025-12-09T14:33:21.456Z","level":"INFO","event":"download_succeeded","run":"20251209_140000","video":"dQw4w9WgXcQ","duration_ms":8123,"proxy_id":"p3"}
建议事件名：

download_started/succeeded/failed

translate_started/succeeded/failed

summarize_started/succeeded/failed

output_written

retry_scheduled

rate_limited

task_cancelled

5. 敏感信息与脱敏
严禁出现在任何日志中的内容：

API Key、Cookie 原文、Authorization 头、账号密码

完整字幕原文（允许截断预览，≤ 200 字符）

私人路径或真实人名（如无必要）

必须脱敏/截断：

URL 中的查询参数（保留 video_id 即可）

Prompt/返回文本：最多前 200 字符 + ...

6. 统一字段规范（建议）
provider / model：AI 供应商与模型（若涉及）

latency_ms：一次调用耗时

tokens_in / tokens_out / tokens_total（若可获得）

proxy_id：当前使用代理的标识（如 p1/p2/p3）

retries：已重试次数

error_type：与 error_handling.md 对齐

示例：

ini
复制代码
[2025-12-09 14:39:02.110] [ERROR] [run:20251209_140000] [task:translate] [video:AbCdEfGh] error=RATE_LIMIT retries=3 provider=openai model=gpt-4.1-mini msg=429 Too Many Requests
7. 轮转与保留

### 7.1 文件大小轮转
- **实现方式**：使用 Python `RotatingFileHandler`
- **单文件大小上限**：20MB
- **备份数量**：5 份（`app.log`, `app.log.1`, `app.log.2`, `app.log.3`, `app.log.4`, `app.log.5`）
- **轮转策略**：当日志文件达到 20MB 时，自动轮转

### 7.2 过期清理
- **实现方式**：启动时自动清理（`core/logger.py` 中的 `cleanup_old_logs()` 函数）
- **默认保留天数**：14 天
- **清理时机**：Logger 初始化时（如果 `cleanup_old_logs=True`）
- **清理范围**：所有匹配 `app.log*` 模式的日志文件

### 7.3 回退策略
- **日志目录不可写时**：自动回退到控制台输出
- **错误处理**：输出 CRITICAL 级别警告，程序继续运行

### 7.4 日志文件位置
- **默认路径**：`<用户数据目录>/logs/app.log`
  - Windows: `%APPDATA%\yt-subtitle-v2\logs\app.log`
  - Linux/Mac: `~/.config/yt-subtitle-v2/logs/app.log`

8. UI 日志面板（LogPanel）行为
仅展示 INFO+（开发者可切换到 DEBUG）

自动滚动到底；提供“暂停滚动/清空”按钮

不在 UI 线程长时间格式化字符串（handler 内部应轻量，必要时异步）

9. 实现细节

### 9.1 初始化方式
```python
from core.logger import get_logger, set_log_context

# 获取全局 logger 实例（单例模式）
logger = get_logger(
    name="yt-subtitle-v2",
    level="INFO",
    console_output=True,
    file_output=True,
    cleanup_old_logs=True,      # 启动时清理过期日志
    max_log_age_days=14,        # 日志最大保留天数
)

# 设置日志上下文（线程本地）
set_log_context(
    run_id="20251209_140000",
    task="download",
    video_id="dQw4w9WgXcQ",
    provider="openai",
    model="gpt-4",
)

# 记录日志（自动包含上下文信息）
logger.info("开始下载字幕")
```

### 9.2 上下文管理
- **线程本地存储**：使用 `threading.local()` 实现线程安全的上下文存储
- **上下文字段**：`run_id`, `task`, `video_id`, `extra_fields`
- **上下文设置**：通过 `set_log_context()` 函数设置
- **上下文清除**：通过 `clear_log_context()` 函数清除

### 9.3 格式化器
- **实现类**：`ContextFormatter`（继承自 `logging.Formatter`）
- **功能**：自动脱敏、注入上下文字段、格式化时间戳

### 9.4 敏感信息脱敏
- **脱敏规则**（`_sanitize_message()` 函数）：
  - API Key（`sk-` 开头）：替换为 `sk-***REDACTED***`
  - Cookie 头、Authorization 头：自动脱敏
  - 过长消息（>500 字符）：截断并添加 `... [truncated]`

10. 与失败记录的关系（重要）
失败记录文件不是日志轮转的一部分，位置固定在 out/ 根目录。

仅在“视频级最终失败”时写入（详见 error_handling.md）。

日志中可有“失败事件”，但不替代失败记录文件的职责。

11. 验收清单

- [x] CLI 与 GUI 同时运行时，日志无重复（确保 handler 仅绑定一次）
- [x] 关键路径日志包含 run/task/video 字段
- [x] 日志格式统一，符合规范
- [x] 敏感数据从不出现在日志（自动脱敏）
- [x] 日志目录写满或不可写时，程序不会崩溃（回退控制台）
- [x] 日志轮转功能正常（20MB x 5份）
- [x] 过期日志自动清理（默认 14 天）
- [x] 与 `error_handling.md` 的失败记录文件行为一致

---

## 12. 实现状态（2025-12-14）

### 12.1 已实现功能
- ✅ 统一日志格式（包含 run_id/task/video_id 字段）
- ✅ 日志轮转（20MB x 5份）
- ✅ 过期日志清理（默认 14 天）
- ✅ 敏感信息脱敏
- ✅ 线程本地上下文管理
- ✅ 回退策略（目录不可写时回退到控制台）
- ✅ UI 回调支持

### 12.2 实现位置
- **核心实现**：`core/logger.py`
- **上下文管理**：`set_log_context()`, `clear_log_context()`
- **过期清理**：`cleanup_old_logs()` 函数
- **格式化器**：`ContextFormatter` 类
- **日志管理器**：`Logger` 类

### 12.3 使用示例
所有模块应通过 `get_logger()` 获取 logger 实例，并通过 `set_log_context()` 设置上下文：

```python
from core.logger import get_logger, set_log_context

logger = get_logger()

# 在流水线开始时设置上下文
set_log_context(run_id="20251209_140000", task="pipeline")

# 在处理单个视频时更新上下文
set_log_context(run_id="20251209_140000", task="download", video_id="dQw4w9WgXcQ")

# 记录日志（自动包含上下文）
logger.info("开始下载字幕")
```