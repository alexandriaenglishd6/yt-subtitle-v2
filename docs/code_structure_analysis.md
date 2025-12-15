# 代码结构详细分析

本文档提供了每个大文件的详细结构分析，供 AI 进行拆分规划。

---

## 1. core/ai_providers.py (1391 行)

### 文件结构

```python
# 导入和初始化 (1-16 行)
# OpenAICompatibleClient 类 (18-322 行)
# GeminiClient 类 (323-489 行)
# AnthropicClient 类 (490-682 行)
# GoogleTranslateClient 类 (683-1365 行)
# 注册表和工厂函数 (1367-1409 行)
```

### 详细类分析

#### OpenAICompatibleClient (~300 行)
- `__init__()`: 初始化，包含本地模型预热逻辑
- `_is_local_base_url()`: 检测本地模型
- `_warmup_in_background()`: 后台预热
- `_warmup()`: 预热实现
- `generate()`: 主要生成方法（包含重试逻辑）
- 属性：`supports_vision`, `max_input_tokens`, `max_output_tokens`, `max_concurrency`

#### GeminiClient (~160 行)
- `__init__()`: 初始化
- `_check_dependencies()`: 检查依赖
- `generate()`: 主要生成方法（包含重试逻辑）
- 属性：同上

#### AnthropicClient (~190 行)
- `__init__()`: 初始化
- `_check_dependencies()`: 检查依赖
- `generate()`: 主要生成方法（包含重试逻辑）
- 属性：同上

#### GoogleTranslateClient (~680 行)
- `__init__()`: 初始化
- `generate()`: 主要生成方法（实际是翻译）
- `_translate_subtitle_block()`: 翻译字幕块（核心逻辑）
- 包含大量翻译相关的辅助方法

#### 工厂函数和注册表 (~40 行)
- `_LLM_REGISTRY`: 注册表字典
- `create_llm_client()`: 工厂函数

### 拆分建议

**方案 A：按提供商拆分（推荐）**
```
core/ai_providers/
  __init__.py              # 导出所有类和工厂函数
  base.py                  # 基础接口/抽象类（如果需要）
  openai_compatible.py    # OpenAICompatibleClient + 预热逻辑
  gemini.py                # GeminiClient
  anthropic.py             # AnthropicClient
  google_translate.py       # GoogleTranslateClient
  factory.py                # create_llm_client + _LLM_REGISTRY
```

**优势：**
- 每个提供商独立文件，职责清晰
- 便于单独测试和维护
- 符合单一职责原则

**迁移步骤：**
1. 创建 `core/ai_providers/` 目录
2. 逐个移动类到独立文件
3. 在 `__init__.py` 中导出，保持向后兼容
4. 更新所有导入语句

---

## 2. core/staged_pipeline.py (1345 行)

### 文件结构

```python
# 导入和常量 (1-27 行)
# StageData dataclass (29-49 行)
# StageQueue 类 (51-336 行)
# StagedPipeline 类 (337-1345 行)
```

### 详细类分析

#### StageData (dataclass, ~20 行)
- 数据容器，包含所有阶段需要的数据
- 字段：video_info, detection_result, download_result, translation_result, summary_result, temp_dir, error, error_stage, error_type, skip_reason, is_processed, processing_failed, run_id

#### StageQueue (~280 行)
- `__init__()`: 初始化队列和执行器
- `enqueue()`: 加入队列
- `start()`: 启动工作线程
- `stop()`: 停止工作线程
- `_worker_loop()`: 工作线程主循环
- `_log_failure()`: 记录失败
- 统计方法：`get_stats()`, `is_done()`

#### StagedPipeline (~1000 行)
- `__init__()`: 初始化所有阶段队列
- `process_videos()`: 主入口，处理视频列表
- `_create_detect_processor()`: DETECT 阶段处理器 (~150 行)
- `_create_download_processor()`: DOWNLOAD 阶段处理器 (~150 行)
- `_create_translate_processor()`: TRANSLATE 阶段处理器 (~250 行)
- `_create_summarize_processor()`: SUMMARIZE 阶段处理器 (~100 行)
- `_create_output_processor()`: OUTPUT 阶段处理器 (~150 行)
- `_cleanup_temp_dir()`: 清理临时目录

### 拆分建议

**方案 A：按阶段拆分处理器（推荐）**
```
core/staged_pipeline/
  __init__.py              # 导出主要类
  stage_data.py            # StageData dataclass
  stage_queue.py           # StageQueue 类
  pipeline.py              # StagedPipeline 主类（简化版，只负责编排）
  processors/
    __init__.py
    detect.py              # _create_detect_processor
    download.py            # _create_download_processor
    translate.py           # _create_translate_processor
    summarize.py           # _create_summarize_processor
    output.py              # _create_output_processor
  utils.py                 # _cleanup_temp_dir 等工具函数
```

**优势：**
- 每个阶段处理器独立，便于维护
- `StagedPipeline` 只负责编排，逻辑更清晰
- 便于单独测试和优化某个阶段

**迁移步骤：**
1. 创建 `core/staged_pipeline/` 目录结构
2. 移动 `StageData` 和 `StageQueue` 到独立文件
3. 将每个处理器函数提取到独立文件
4. 重构 `StagedPipeline` 使用导入的处理器
5. 更新所有导入语句

---

## 3. core/output.py (1155 行)

### 文件结构

```python
# 导入和初始化 (1-21 行)
# OutputWriter 类 (23-1155 行)
```

### 详细类分析

#### OutputWriter (单个大类)
需要进一步分析内部方法结构。可能的职责：
- 目录结构管理
- 字幕文件写入
- 摘要文件写入
- metadata.json 写入
- archive 文件写入
- 各种格式的文件处理

### 拆分建议

**需要先分析内部方法，可能的拆分方向：**
```
core/output/
  __init__.py              # 导出 OutputWriter
  writer.py                # OutputWriter 主类（协调器）
  directory.py             # 目录结构管理
  formats/
    __init__.py
    subtitle.py            # 字幕文件写入逻辑
    summary.py             # 摘要文件写入逻辑
    metadata.py            # metadata.json 写入逻辑
    archive.py             # archive 文件写入逻辑
  utils.py                 # 文件操作工具函数
```

---

## 4. core/pipeline.py (1045 行)

### 文件结构

```python
# 导入 (1-31 行)
# _safe_log() 辅助函数 (32-52 行)
# process_single_video() 主函数 (53-524 行)
# _cleanup_temp_dir() 辅助函数 (525-534 行)
# _handle_processing_error() 辅助函数 (535-578 行)
# _get_error_type_display_name() 辅助函数 (579-603 行)
# process_video_list() 主函数 (604-883 行)
# _process_video_list_staged() 内部函数 (884-1045 行)
```

### 详细函数分析

#### process_single_video() (~470 行)
- 旧版单视频处理逻辑
- 包含完整的处理流程：检测、下载、翻译、摘要、输出

#### process_video_list() (~280 行)
- 主入口函数
- 分发到新版或旧版处理逻辑

#### _process_video_list_staged() (~160 行)
- 新版分阶段处理逻辑
- 使用 StagedPipeline

### 拆分建议

**方案 A：新旧版本分离（推荐）**
```
core/pipeline/
  __init__.py              # 导出主要函数
  single_video.py          # process_single_video + 辅助函数
  video_list.py            # process_video_list（分发器）
  legacy/
    __init__.py
    runner.py              # 旧版 TaskRunner 逻辑（如果存在）
  staged/
    __init__.py
    handler.py             # _process_video_list_staged
  utils.py                 # _safe_log, _cleanup_temp_dir 等工具函数
```

**优势：**
- 新旧版本逻辑清晰分离
- 便于逐步迁移和测试
- 保持向后兼容

---

## 5. ui/main_window.py (977 行)

### 文件结构

```python
# 导入 (1-32 行)
# MainWindow 类 (33-977 行)
```

### 详细类分析

#### MainWindow (单个大类)
需要进一步分析内部方法，可能包含：
- 窗口初始化
- 页面管理（切换页面）
- 事件处理
- 组件初始化
- 配置管理

### 拆分建议

**方案 A：按职责拆分（推荐）**
```
ui/main_window/
  __init__.py              # 导出 MainWindow
  window.py                # MainWindow 主类（简化版）
  page_manager.py          # 页面管理和切换逻辑
  event_handlers.py        # 事件处理函数
  initialization.py         # 初始化相关代码
  components.py            # 组件创建和配置
```

---

## 6. ui/business_logic.py (881 行)

### 文件结构

```python
# 导入 (1-31 行)
# VideoProcessor 类 (32-881 行)
```

### 详细类分析

#### VideoProcessor (单个大类)
需要进一步分析内部方法，可能包含：
- 组件初始化
- 视频检测处理
- 下载处理
- 翻译处理
- 摘要处理
- 状态管理
- 回调处理

### 拆分建议

**方案 A：按功能模块拆分（推荐）**
```
ui/business_logic/
  __init__.py              # 导出 VideoProcessor
  processor.py             # VideoProcessor 主类（协调器）
  handlers/
    __init__.py
    detection.py           # 检测相关处理
    download.py            # 下载相关处理
    translation.py         # 翻译相关处理
    summarization.py       # 摘要相关处理
  state.py                 # 状态管理
  callbacks.py             # 回调处理
```

---

## 7. ui/pages/network_settings_page.py (913 行)

### 文件结构

```python
# 导入 (1-15 行)
# NetworkSettingsPage 类 (16-913 行)
```

### 详细类分析

#### NetworkSettingsPage (单个大类)
可能包含多个功能区域：
- Cookie 配置区域
- 代理配置区域
- 网络设置区域
- 各种事件处理

### 拆分建议

**方案 A：按功能区域拆分（推荐）**
```
ui/pages/network_settings/
  __init__.py              # 导出 NetworkSettingsPage
  page.py                  # 主页面类（协调器）
  cookie_section.py        # Cookie 配置区域
  proxy_section.py         # 代理配置区域
  network_section.py        # 网络设置区域
  components.py            # 共享组件
```

---

## 拆分优先级和顺序

### 第一阶段（高优先级）
1. **core/ai_providers.py** - 收益最大，风险最小
2. **core/staged_pipeline.py** - 类过大，需要拆分

### 第二阶段（中优先级）
3. **core/output.py** - 需要先分析内部结构
4. **core/pipeline.py** - 新旧版本分离
5. **ui/main_window.py** - GUI 重构
6. **ui/business_logic.py** - 业务逻辑模块化

### 第三阶段（低优先级）
7. **ui/pages/network_settings_page.py** - 页面类，影响较小

---

## 拆分注意事项

1. **保持向后兼容**：通过 `__init__.py` 导出，保持原有导入路径
2. **测试覆盖**：拆分前确保有足够的测试
3. **Git 历史**：使用 `git mv` 保留文件历史
4. **文档更新**：更新相关文档和注释
5. **渐进式重构**：一次拆分一个文件，确保功能正常

---

## 依赖关系分析

### 核心依赖
- `core/ai_providers.py` 被多个模块导入
- `core/staged_pipeline.py` 被 `core/pipeline.py` 导入
- `core/output.py` 被多个模块导入

### 拆分影响
- 拆分 `ai_providers.py` 需要更新所有导入语句
- 拆分 `staged_pipeline.py` 需要更新 `pipeline.py`
- 其他文件的拆分影响相对较小

---

## 建议的拆分顺序

1. **core/ai_providers.py** - 最独立，影响范围可控
2. **core/staged_pipeline.py** - 相对独立，但被 pipeline 使用
3. **core/output.py** - 需要先分析内部结构
4. **core/pipeline.py** - 依赖 staged_pipeline 拆分完成
5. **ui/main_window.py** - GUI 层，影响相对独立
6. **ui/business_logic.py** - 业务逻辑层
7. **ui/pages/network_settings_page.py** - 页面层，影响最小

