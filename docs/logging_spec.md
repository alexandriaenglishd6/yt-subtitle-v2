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
文件日志：按大小（20MB）轮转，保留 5 份（可配置）

过期清理：启动时清理超过 N 天（默认 14 天）的日志（可选）

日志目录不可写时：回退到控制台，输出 CRITICAL 警告

8. UI 日志面板（LogPanel）行为
仅展示 INFO+（开发者可切换到 DEBUG）

自动滚动到底；提供“暂停滚动/清空”按钮

不在 UI 线程长时间格式化字符串（handler 内部应轻量，必要时异步）

9. 初始化示例（伪代码）
python
复制代码
# core/logger.py
def init_logging(level="INFO", log_dir="logs"):
    logger = logging.getLogger("app")
    logger.setLevel(level)

    fmt = "[%(asctime)s] [%(levelname)5s] [run:%(run_id)s] [task:%(task)s] [video:%(video_id)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S.%f"

    # console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(fmt, datefmt))

    # file with rotation
    fh = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=20*1024*1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt, datefmt))

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger
规范：通过 LoggerAdapter 或自定义 filter 注入 run_id/task/video_id，避免每条日志手填。

10. 与失败记录的关系（重要）
失败记录文件不是日志轮转的一部分，位置固定在 out/ 根目录。

仅在“视频级最终失败”时写入（详见 error_handling.md）。

日志中可有“失败事件”，但不替代失败记录文件的职责。

11. 验收清单
 CLI 与 GUI 同时运行时，日志无重复（确保 handler 仅绑定一次）

 关键路径日志包含 run/task/video 字段

 JSON 事件（若开启）字段规范一致，不夹杂换行/无效 JSON

 敏感数据从不出现在日志

 日志目录写满或不可写时，程序不会崩溃（回退控制台）

 与 error_handling.md 的失败记录文件行为一致