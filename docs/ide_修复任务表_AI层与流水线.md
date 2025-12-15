
# YouTube 字幕工具 – 架构审计修复任务表（R 系列 · AI 层与流水线）

> 版本：2025-12-11（v2.1 最终修订版）  
> 适用范围：  
> - 只针对「AI 层与处理流水线」的修复任务，不包含 UI 视觉、文案等  
> - 基于多家 AI 审计（GPT / Claude / Grok / Gemini）综合结论整理  
>
> 所有任务必须遵守以下优先级顺序与行为规范：
> 1. `docs/v2_final_plan.md` – 行为规范（**最高优先级**，Dry Run / 增量 / 输出结构等）
> 2. `docs/project_blueprint.md` – 项目蓝图
> 3. `docs/acceptance_criteria.md` – 验收标准
> 4. `docs/AI_PROVIDER_EXTENSION.md` – AI 层设计（OpenAI 兼容 + Gemini 架构）
> 5. `docs/ide_任务表.md` – 原 P0 / P1 功能任务表

---

## 1. 优先级分组说明

- **R0 – 红线级（必须优先完成）**  
  - 会直接导致：增量失效、Dry Run 行为错误、数据/文件损坏、架构未来无法演进。  

- **R1 – 高优先级（稳定性 & 维护成本）**  
  - 不立刻炸，但会显著影响长期使用体验与调试效率。  

- **R2 – 中期优化（可观测性 & 用户体验）**  
  - 主要提升排错能力、使用流畅度，对功能行为没有根本改变。  

- **R3 – 长期优化（性能 & 进阶能力）**  
  - 不影响当前使用，可在一个月后逐步实现。

---

## 2. R0 红线级任务总表（最终修订版）

> 这一组是 Grok 的“8 项必改”里最关键的部分 + Gemini 对 R0 的增强版：  
> - 既解决增量/并发/行为规范的硬问题  
> - 又一口气铺好新的 AI LLMClient 架构（基于 `LLMClient` Protocol，三大实现：`OpenAICompatibleClient`、`GeminiClient`、`AnthropicClient`）  
>
> 建议执行顺序：**R0-1 → R0-2 → R0-3 → R0-4 → R0-5**

| 编号 | 任务名称 | 简要说明 | 依赖 | 预估工作量 | 状态 |
|------|----------|----------|------|------------|------|
| **R0-1** | **重构 AI 架构 + 修复流水线 LLM 参数** | ① 修复 `pipeline.process_video_list()` 内部误用 `translation_llm` / `summary_llm` 但只传了单一 `llm` 导致的 NameError / 逻辑错配。② 同步落地新的 AI 架构：基于 `LLMClient` Protocol，重构为三大实现类：`OpenAICompatibleClient`（覆盖 OpenAI + 所有兼容服务）、`GeminiClient`（Google Gemini 专用）、`AnthropicClient`（Claude/Anthropic）。所有实现类必须提供 4 个必需属性（`supports_vision`、`max_input_tokens`、`max_output_tokens`、`max_concurrency`），并在 `generate()` 中使用 `Semaphore` 进行并发限流。③ 更新 `AIConfig` 添加 `max_concurrency` 字段，更新注册表支持 `"openai"` 和 `"openai_compatible"` 都指向 `OpenAICompatibleClient`。④ 更新文档 `docs/AI_PROVIDER_EXTENSION.md` 为 v2.1 草案版内容。 | P0-14（完整流水线已跑通） | M | ✅ 已完成 |
| **R0-2** | **调整 archive 存储位置 + 迁移旧数据** | ① 修复 Grok 指出的"不同频道共用 `out/archive.txt` 导致增量互相污染"问题：将 archive 改为按来源隔离的结构，统一使用用户数据目录下的 `archives/` 文件夹（通过 `ConfigManager.get_archives_dir()` 获取），例如 `archives/<channel_id>.txt` / `archives/batch_<batch_id>.txt` / `archives/playlist_<playlist_id>.txt`。② 增加迁移逻辑：在 `IncrementalManager` 初始化时，如果检测到旧位置（如 `out/archive.txt`）存在历史 `archive.txt`，自动迁移/合并到新位置（`archives/migrated_archive.txt`），并备份旧文件，避免老用户重复全量处理和扣费。 | P0-6（增量基础逻辑） | S | ✅ 已完成 |
| **R0-3** | **Dry Run 模式彻底只读** | 严格执行 `v2_final_plan.md` 中对 Dry Run 的定义：Dry Run 不允许任何写入，包括：output 目录、archives、`with_subtitle.txt` / `without_subtitle.txt` / `failed_urls.txt` 等文件。实现方案：① 在调用 `incremental_manager.mark_as_processed()` 前增加 `if not dry_run:` 判断。② 对所有底层写入函数增加 `dry_run` 检查（必要时加断言），确保 Dry Run 调用路径中不会落盘。 | P0-8（Dry Run 行为） | S | ✅ 已完成 |
| **R0-4** | **文件写入：加锁 + 原子写入** | 解决并发和异常中断导致的文件错乱问题。① 对所有"追加写入"的文本文件（`with_subtitle.txt` / `without_subtitle.txt` / `failed_urls.txt` / `mark_as_processed()` 中的 archive 写入等），在 `core/failure_logger.py` 中添加 `_append_line_safe(path: Path, line: str)` 函数，使用 `dict[Path, Lock]` 实现"每个文件一把锁"，所有追加写入统一调用此函数。② 对"覆盖写入"的文件（如字幕文件、摘要文件、`metadata.json` 等），继续使用现有的原子写策略（`_atomic_write`）：先写入 `*.tmp` 临时文件，再使用 `os.replace(tmp, target)` 原子替换，防止写入过程中异常导致文件损坏或内容截断。 | P0-16（TaskRunner 并发）、P0-14（输出结构） | S | ✅ 已完成 |
| **R0-5** | **临时目录清理逻辑补完** | 规范 `temp/` 目录生命周期：在 `process_single_video()` 中，将临时目录清理逻辑移入 `finally` 块，只要在本次任务中创建过 `temp_dir`，任务结束（无论成功/失败/被取消）都尝试清理。如果需要保留失败现场，可通过配置项（如 `keep_temp_on_error`）控制仅在失败时保留。 | P0-14（完整流水线） | S | ✅ 已完成 |

---

## 3. R1 高优先级任务（稳定性 & 维护成本）

> R1 可以在 R0 全部完成后立即进行。  
> 这一层主要来自：GPT 原任务表 + Grok 的“高优”三项 + Gemini 的补充意见。

| 编号 | 任务名称 | 简要说明 | 依赖 | 预估工作量 | 状态 |
|------|----------|----------|------|------------|------|
| **R1-1** | 统一 LLMException → AppException → failure_logger | 在新 AI 架构下，所有 LLMClient 实现（`OpenAICompatibleClient` / `GeminiClient` / `AnthropicClient`）都必须将各自 SDK 的错误统一包装为 `LLMException(LLMErrorType.XXX)`，再由 pipeline 通过 `map_llm_error_to_app_error()` 映射为 `AppException` 并传给 `failure_logger`。确保 RATE_LIMIT / NETWORK / AUTH / CONTENT 等分类在日志和失败记录中可见，而不是一堆 UNKNOWN。 | R0-1（AI 架构已重构） | S | ✅ 已完成 |
| **R1-2** | 任务取消机制（CancelToken） | 引入 `CancelToken` + `TaskCancelledError`：① 在耗时循环（批量处理视频、下载/翻译/摘要循环）中，每 ~0.5s 检查一次 `cancel_token.is_cancelled()`。② GUI 的"停止处理"按钮和 CLI 的中断逻辑统一调用 `cancel_token.cancel()`。③ 捕获 `TaskCancelledError` 时，记录"任务已取消"日志，并按约定清理临时资源。 | P0-16（并发）、UI 业务逻辑 | M | ✅ 已完成 |
| **R1-3** | 代理健康管理与自动降级 | 扩展网络/代理层：为每个代理记录成功/失败次数与最后失败时间，简单策略：① 同一代理连续失败 ≥5 次时标记为 unhealthy，并在后续 10 分钟内避免继续使用。② 定时对 unhealthy 代理做轻量探测，请求成功则恢复为 healthy。③ 所有代理都 unhealthy 时，可尝试直连或失败最少的代理。目标：避免坏代理卡死整个任务，又能自动恢复。 | P0-18（代理配置）、R1-1（错误分类） | M | ✅ 已完成 |
| **R1-4** | 下载并发与 AI 并发解耦 / 限速 | 当前 TaskRunner 对"每个视频任务"的并发控制较粗。实现：① 在 LLMClient 实现类内部使用 `threading.Semaphore` 对 AI 调用进行限流（已在 R0-1 中完成，每个实现类的 `generate()` 方法中使用 `with self._semaphore:` 包装 API 调用）。② 更新并发默认值：下载并发从 3 调整为 10，AI 并发（`max_concurrency`）默认 5。目标：在多供应商/本地模型场景下保持稳定，不因 AI 并发过高导致崩溃。 | P0-16（并发）、R0-1（AI 架构） | XS | ✅ 已完成 |

---

## 4. R2 中期优化任务（可观测性 & 用户体验）

> R2 任务主要提升调试能力、失败可追溯性与使用舒适度。  
> Grok 提的「Cookie 地区缓存 / 并发默认值调高」也归入此层级。

| 编号 | 任务名称 | 简要说明 | 依赖 | 预估工作量 | 状态 |
|------|----------|----------|------|------------|------|
| **R2-1** | 结构化失败记录 `failed_records.json` | 在现有 `failed_urls.txt` / `failed_detail.log` 基础上，新增一个 JSON 失败记录文件，每条记录包含 `video_id` / `url` / `stage`（detect/download/translate/summarize/output）/ `error_type` / `timestamp` / `run_id`。为将来"一键重试某类失败"或简单错误统计做准备。 | R1-1（错误类型已统一） | S | ✅ 已完成 |
| **R2-2** | 扩展 `metadata.json` 中的 AI 与运行信息 | 为每个视频输出目录中的 `metadata.json` 增加：工具版本、生成时间、run_id、翻译/摘要的 provider / model / prompt_version / 语言设置等信息，以便后续判断是否需要重新生成、以及排查问题。 | P0-14（OutputWriter）、LanguageConfig | S | ⬜ 未开始 |
| **R2-3** | 日志规范与日志滚动（轮转） | 根据 logging 计划文档（如无则新建 `docs/logging_spec.md`）：统一日志字段（run_id / task / video_id）与级别。实现文件日志的滚动策略（单文件大小上限 + 备份数），避免长时间运行日志无限增长。 | P0-3（日志系统）、R0-5 | M | ⬜ 未开始 |
| **R2-4** | GUI 线程安全与事件流文档化 | 在 `docs/` 下补充/更新 GUI 线程与事件流说明：规定“所有 UI 更新必须在主线程（`after()`）执行；业务逻辑只在后台线程；UI 与 core 通过事件/回调交互”。对 `ui/business_logic.py` 等实现做一次自查，确保符合文档。 | 《新会话上下文恢复指南》 | S | ⬜ 未开始 |
| **R2-5** | Cookie 地区测试结果缓存 | 根据 Grok 建议：在 Cookie 测试成功后，将检测到的地区/语言信息写入 config（如 `network_region` 字段），下次启动时直接显示“当前地区：XX（已缓存）”，并允许用户一键重新测试。减少每次重启都手动重测的麻烦。 | `docs/cookie_setup_guide.md` | S | ⬜ 未开始 |
| **R2-6** | 并发默认值与 UI 控制优化 | 默认并发值从 3 调整为 10，并在 GUI 中提供滑块或输入框控制范围（如 1~50），同时在文档中说明高并发可能带来的风险（限流/本地模型压力）。与 R1-4 的 AI 并发限速配合使用。 | P0-16（TaskRunner）、R1-4 | XS | ⬜ 未开始 |

---

## 5. R3 长期优化任务（性能 & 进阶能力）

> 这些任务不会影响当前稳定性，属于“有时间可以慢慢做”的增强项。

| 编号 | 任务名称 | 简要说明 | 依赖 | 预估工作量 | 状态 |
|------|----------|----------|------|------------|------|
| **R3-1** | 流水线分阶段队列化 | 将当前单一 pipeline 拆分为多个阶段队列，如：“发现视频 → 检测字幕 → 下载 → 翻译 → 摘要 → 输出”。可选地为不同阶段使用不同 executor，使 I/O 密集和 AI 计算阶段更好地并行。需要保证行为与现有规范完全一致。 | P0-14、R1-4 | L | ⬜ 未开始 |
| **R3-2** | AI Profile 配置与多供应商路由 | 引入 `ai_profiles.json`（或等效配置），将“任务类型 → 模型/供应商组合”的映射配置化，例如 `subtitle_translate_default` / `subtitle_summarize_fast` 等，由 `OpenAICompatibleClient` / `GeminiClient` / `AnthropicClient` 根据 profile 选择模型。便于在不改代码的前提下调整模型策略。 | `AI_PROVIDER_EXTENSION.md`、R0-1 | M | ⬜ 未开始 |
| **R3-3** | 本地模型资源限制与预热 | 针对本地大模型 LLMClient（通过 `OpenAICompatibleClient` 的 `base_url` 配置接入，如 `http://localhost:11434/v1`），增加预热逻辑（启动时做一次轻量调用）等，避免初次调用冷启动太慢或并发过高导致机器卡死。与 R1-4 的并发限速（`Semaphore`）协同。 | R1-4（AI 并发控制） | M | ⬜ 未开始 |
| **R3-4** | AI 供应商健康自检脚本 `ai_smoke_test` | 新增一个简单 CLI 命令或脚本，遍历当前配置中启用的所有 LLMClient（`OpenAICompatibleClient` / `GeminiClient` / `AnthropicClient` 等），分别发起一个极小请求，以验证 API Key / 代理 / 网络是否可用，并输出“健康报告”。建议在重大改版或用户首次配置时使用。 | R0-1、R1-3 | S | ⬜ 未开始 |

---

## 6. IDE 执行规范（针对 R 系列任务）

当 IDE / 代码助手执行本任务表中的任意任务时，必须遵守以下流程（在原 `ide_任务表.md` 的 5.x 基础上扩展）：

### 6.1 开始执行某个 R 任务前

1. **声明当前任务编号与名称**  
   - 例如：「现在执行 `R0-2 调整 archive 存储位置与数据迁移`」。

2. **引用相关约束文档**  
   - 至少包括：  
     - `docs/v2_final_plan.md` 中相关小节（Dry Run / 增量 / 输出结构等）  
     - `docs/project_blueprint.md`（如本任务涉及架构分层）  
     - `docs/AI_PROVIDER_EXTENSION.md`（如任务涉及 AI 架构/LLMClient）  

3. **用中文简要复述任务理解**  
   - 要说清楚：  
     - 要修复/优化的行为是什么；  
     - 将修改/新增哪些模块；  
     - 明确不会动哪些稳定模块（防止误伤）。

4. **给出执行步骤（简要列表）**  
   - 步骤 1：阅读相关代码与文档  
   - 步骤 2：按任务说明修改实现  
   - 步骤 3：更新必要的文档/注释  
   - 步骤 4：执行必要的自测（见下条）

### 6.2 完成某个 R 任务后

1. **列出修改的文件与主要改动点**  
2. **描述测试步骤与结果**  
   - 至少包含：  
     - 正常场景测试（小规模频道/URL 列表）  
     - 与本任务直接相关的异常/边界场景（如 Dry Run、取消任务、代理失效、多线程写入等）  

3. **显式对齐行为规范**  
   - 说明当前实现是否完全符合 `v2_final_plan.md` 与本任务表的要求；  
   - 如发现规范本身存在灰色地带或冲突，需在提交中备注，并建议如何更新对应文档。

---

> ✅ 小结：  
> - R0 部分已按 Grok 的“真正致命问题”收敛，并吸收 Gemini 的三点修正（AI 架构重构 + archive 迁移 + 原子写入）。  
> - R1/R2/R3 保留了 GPT/Claude 的系统性规划，结合 Grok 的使用体验优化建议，形成一个既**不爆炸**又**可长期演进**的修复路线图。  
> - 你可以直接把本文件交给 IDE，按 R0 → R1 → R2 → R3 的顺序逐步落地。
```
