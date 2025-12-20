# 错误处理与日志规范实施计划

> 基于 `error_handling.md` 和 `logging_spec.md` 的代码改进计划

## 一、当前状态分析

### 1.1 错误处理现状
- ✅ 已有 `LLMException` 和 `LLMErrorType`（仅用于 AI 调用）
- ❌ 缺少统一的 `AppException` 类（适用于所有模块）
- ❌ 错误类型不完整（缺少 TIMEOUT, FILE_IO, PARSE, INVALID_INPUT, CANCELLED, EXTERNAL_SERVICE）
- ❌ 各模块使用通用 `Exception`，未统一映射
- ✅ `FailureLogger` 已实现，但格式不符合新规范（缺少 error_type 和 batch_id）

### 1.2 日志系统现状
- ✅ 基础日志系统已实现（文件+控制台）
- ✅ 支持日志轮转（但配置为 10MB，需改为 20MB）
- ❌ 日志格式缺少 `run:<batch_id>`, `task:<stage>` 字段
- ❌ 缺少敏感信息脱敏机制
- ❌ 缺少统一字段支持（provider, model, latency_ms, tokens, proxy_id, retries, error_type）
- ❌ 缺少可选的 JSON 事件输出

## 二、实施步骤

### 阶段 1：创建统一错误处理基础设施

1. **创建 `core/exceptions.py`**
   - 定义 `ErrorType` 枚举（包含所有错误类型）
   - 定义 `AppException` 类（包含 error_type 和 cause）
   - 提供错误类型映射辅助函数

2. **创建 `core/cancel_token.py`**
   - 实现 `CancelToken` 类（用于用户取消操作）

### 阶段 2：更新日志系统

1. **更新 `core/logger.py`**
   - 修改日志格式以包含 `run:<batch_id>`, `task:<stage>`, `video:<id>` 字段
   - 实现敏感信息脱敏（API Key、Cookie等）
   - 添加统一字段支持（通过 LoggerAdapter 或自定义 Formatter）
   - 更新日志轮转配置（20MB x 5份）
   - 实现日志目录不可写时的回退策略
   - 添加可选的 JSON 事件输出

2. **创建批次ID生成机制**
   - 在 pipeline 入口生成 `run_id`（格式：`YYYYMMDD_HHMMSS`）
   - 在日志记录时自动注入 `run_id` 和 `task`

### 阶段 3：更新失败记录

1. **更新 `core/failure_logger.py`**
   - 修改 `log_failure` 方法以接受 `error_type` 和 `batch_id`
   - 更新失败记录格式以符合 `error_handling.md` 要求
   - 实现原子写文件机制（先写.tmp，成功后rename）

### 阶段 4：更新各模块错误处理

1. **更新 `core/fetcher.py`**
   - 将 yt-dlp 错误映射为 `AppException`
   - 使用统一的错误类型

2. **更新 `core/downloader.py`**
   - 将下载错误映射为 `AppException`
   - 文件IO错误使用 `FILE_IO` 类型

3. **更新 `core/translator.py` 和 `core/summarizer.py`**
   - 将 `LLMException` 适配为 `AppException`
   - 保持错误类型映射一致

4. **更新 `core/output.py`**
   - 文件操作异常使用 `FILE_IO`
   - 命名不合法使用 `INVALID_INPUT`
   - 实现原子写文件

5. **更新 `core/pipeline.py`**
   - 生成 `run_id` 并传递给所有子模块
   - 统一错误处理和失败记录

### 阶段 5：测试与验证

1. **按照 `error_handling.md` 验收清单测试**
   - 故意断网 → NETWORK 重试后失败
   - 错误 API Key → AUTH 立即失败
   - 429 限流 → RATE_LIMIT 退避重试
   - 磁盘写满 → FILE_IO 立即失败
   - 用户点击停止 → CANCELLED 生效

2. **按照 `logging_spec.md` 验收清单测试**
   - 日志包含 run/task/video 字段
   - 敏感数据从不出现在日志
   - 日志目录写满时程序不崩溃
   - 与失败记录文件行为一致

## 三、文件清单

### 新增文件
- `core/exceptions.py` - 统一异常定义
- `core/cancel_token.py` - 取消令牌实现

### 修改文件
- `core/logger.py` - 日志格式和功能增强
- `core/failure_logger.py` - 失败记录格式更新
- `core/pipeline.py` - 批次ID生成和错误处理
- `core/fetcher.py` - 错误映射
- `core/downloader.py` - 错误映射和原子写
- `core/translator.py` - 错误适配
- `core/summarizer.py` - 错误适配
- `core/output.py` - 错误映射和原子写
- `core/proxy_manager.py` - 错误映射
- `core/cookie_manager.py` - 错误映射

## 四、注意事项

1. **向后兼容**：确保现有代码在更新后仍能正常工作
2. **渐进式更新**：先完成基础设施，再逐步更新各模块
3. **测试覆盖**：每个阶段完成后进行测试
4. **文档同步**：确保代码实现与规范文档一致

