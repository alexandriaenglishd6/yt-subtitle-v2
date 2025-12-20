# 错误处理规范（error_handling.md）

> 目标：以统一、可预测的方式处理错误，让流水线可恢复、可重试、可审计。  
> 适用范围：下载/检测/翻译/摘要/输出/网络与代理/配置/CLI 与 UI。

---

## 1. 错误分类（标准枚举）

所有模块抛错必须映射到以下类型（统一对齐 AI 调用层的 `LLMErrorType` 思想）：

- `NETWORK`：网络不可达、DNS 失败、连接重置、超时等
- `TIMEOUT`：显式超时（与 NETWORK 可合并，但建议保留独立可视化）
- `RATE_LIMIT`：对方限流（429）、配额耗尽、频率限制
- `AUTH`：无效/缺失凭证（API Key、Cookie）
- `CONTENT`：违规/不可处理内容（YouTube 限制、模型安全策略拦截）
- `FILE_IO`：文件系统异常（权限不足、磁盘满、路径非法、原子重命名失败）
- `PARSE`：数据结构/字幕解析失败、JSON 解析失败
- `INVALID_INPUT`：URL 非法、参数不完整、配置错误
- `CANCELLED`：用户主动取消（CancelToken）
- `EXTERNAL_SERVICE`：第三方服务异常但非网络问题（例如 yt-dlp 返回码）
- `UNKNOWN`：无法归类的其他错误

> 规范：模块内部捕获原始异常 → 映射为上述类型 → 抛出统一异常（自定义 `AppException`，含 `error_type` 与 `message`）。

---

## 2. 统一异常结构

```python
class AppException(Exception):
    def __init__(self, message: str, *, error_type: str, cause: Exception | None = None):
        super().__init__(message)
        self.error_type = error_type  # 取自上述枚举
        self.cause = cause            # 原始异常（可选）
上层看到 AppException 即可决定：是否重试；是否记录失败；如何反馈 UI。

禁止使用 None/False 表示失败，必须抛异常。

3. 重试与退避策略（默认）
通用重试器（在 core/task_runner.py 暴露 retry(fn, max_retries, backoff, jitter)），默认配置来自 config.ai.max_retries 或模块内默认：

错误类型	是否重试	备注
NETWORK	✅	指数退避（1s, 2s, 4s…）+ 随机抖动
TIMEOUT	✅	同 NETWORK
RATE_LIMIT	✅	退避时间可读响应头（Retry-After），否则指数退避
AUTH	❌	立即失败（提示检查 Key/Cookie）
CONTENT	❌	立即失败（记录原因）
FILE_IO	❌/✅	路径/权限错误 ❌；磁盘临时繁忙 ✅（小次数重试）
PARSE	❌	通常为逻辑/数据问题
INVALID_INPUT	❌	立即失败
EXTERNAL_SERVICE	✅	小次数重试（1~2次），持续失败则失败
CANCELLED	❌	立即停止链路、清理现场
UNKNOWN	✅	小次数尝试后失败

规范：重试由调用处控制，底层模块不做内部无限重试；每次重试必须可被 CancelToken 打断。

4. 取消与幂等
在 task_runner 引入 CancelToken，各环节必须周期性检查并及时终止。

落盘采用“原子写”：

先写 .tmp；成功后 atomic rename；失败清理 .tmp；

任何中途失败不得污染最终产物与增量状态。

成功准线：仅当所有必需产物（原文字幕/翻译/摘要/metadata）落盘成功，才将视频标记为“成功”并写入增量档案。

5. 失败记录规则（与日志区分）
**仅当“视频级任务最终失败”**时，写失败记录文件：

out/failed_detail.log：富信息行（时间戳、video_id/url、可选频道/批次、error_type、简要原因）

out/failed_urls.txt：纯 URL，一行一个（便于粘贴重跑）

子步骤失败但后续重试成功 → 不写失败记录。

写入采用静默追加，不弹窗，不阻塞主流程。

示例（failed_detail.log）：

less
复制代码
[2025-12-09 14:32:10] [batch:20251209_140000] [video:dQw4w9WgXcQ] https://www.youtube.com/watch?v=dQw4w9WgXcQ  error=NETWORK  msg=连接超时(3次重试失败)
failed_urls.txt 示例：

arduino
复制代码
https://www.youtube.com/watch?v=dQw4w9WgXcQ
6. 各子系统约定
Fetcher/Detector/Downloader：将 yt-dlp 退出码与常见 stderr 文案映射为 NETWORK / RATE_LIMIT / CONTENT / EXTERNAL_SERVICE。

Translator/Summarizer（AI）：统一抛 LLMException → 适配为 AppException（error_type 映射保持一致）。

Output：所有文件操作异常 → FILE_IO；命名不合法 → INVALID_INPUT。

Proxy/Cookie：认证失败 → AUTH；代理不可用 → NETWORK；黑名单/禁用 → 不当作失败记录，仅日志提示（可配置）。

Incremental：读取/写入异常 → FILE_IO；断电/中断后必须不破坏现有成功记录。

7. UI/CLI 反馈
UI 状态栏与日志框仅显示“简短可操作信息”（别贴栈追踪）。

提示用户如何自查：检查网络/代理/Key；重试建议。

CLI 退出码：全局成功 0；部分失败 2；致命配置错误 3；用户取消 130。

8. 验收清单（必须全部通过）
 故意断网 → NETWORK 重试后失败，记录到失败文件，程序不崩。

 错误 API Key → AUTH 立即失败，提示检查配置，不重试。

 429 限流 → RATE_LIMIT 退避重试；仍失败则记录失败文件。

 磁盘写满 → FILE_IO 立即失败；不产生半截文件；不污染增量。

 用户点击停止 → CANCELLED 生效，清理临时文件，不写失败记录。

 任何情况下，archives/ 仅在成功后更新。