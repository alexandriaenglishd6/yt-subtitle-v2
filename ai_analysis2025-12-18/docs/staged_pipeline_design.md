# 分阶段队列化 Pipeline 设计文档

## 1. 概述

将当前单一 pipeline 拆分为多个阶段队列，实现更好的并行处理和资源利用。

### 1.1 当前架构

- **单一 pipeline**：每个视频作为一个完整任务，按顺序执行所有步骤
- **并发控制**：使用 `TaskRunner` 在视频级别进行并发
- **问题**：
  - I/O 密集阶段（下载）和 AI 计算阶段（翻译、摘要）混在一起
  - 无法针对不同阶段优化并发数
  - 资源利用不均衡

### 1.2 目标架构

- **分阶段队列**：将流程拆分为多个阶段，每个阶段有独立的队列和执行器
- **阶段间传递**：视频数据在阶段之间通过队列传递
- **独立并发控制**：每个阶段可以配置不同的并发数
- **保持兼容性**：与现有规范（错误处理、日志、失败记录）完全一致

## 2. 阶段定义

### 2.1 处理阶段

**注意**：DISCOVER 阶段已移除，因为视频列表已经在 `process_video_list` 中传入，无需额外发现阶段。

1. **DETECT**（检测字幕）
   - 输入：VideoInfo
   - 输出：VideoInfo + DetectionResult
   - 类型：I/O 密集（网络请求）
   - 并发数：默认 10
   - **特殊处理**：
     - 检查增量记录（如果 `force=False`，跳过已处理视频）
     - 如果没有字幕，设置 `skip_reason` 并记录失败

2. **DOWNLOAD**（下载字幕）
   - 输入：VideoInfo + DetectionResult
   - 输出：VideoInfo + DetectionResult + DownloadResult
   - 类型：I/O 密集（网络下载）
   - 并发数：默认 10
   - **特殊处理**：
     - 创建临时目录（`temp_dir`）
     - 如果下载失败，清理临时目录并记录失败

3. **TRANSLATE**（翻译字幕）
   - 输入：VideoInfo + DetectionResult + DownloadResult
   - 输出：VideoInfo + DetectionResult + DownloadResult + TranslationResult
   - 类型：AI 计算密集
   - 并发数：默认 5（受 AI 并发限制）
   - **特殊处理**：
     - 检查是否需要翻译（官方字幕 vs AI 翻译）
     - 部分语言翻译失败不视为整体失败
     - 翻译策略：OFFICIAL_ONLY / OFFICIAL_AUTO_THEN_AI / AI_ONLY

4. **SUMMARIZE**（生成摘要）
   - 输入：VideoInfo + DetectionResult + DownloadResult + TranslationResult
   - 输出：VideoInfo + DetectionResult + DownloadResult + TranslationResult + SummaryResult
   - 类型：AI 计算密集
   - 并发数：默认 5（受 AI 并发限制）
   - **特殊处理**：
     - 检查是否需要生成摘要（`summary_llm` 是否可用）
     - 摘要失败不视为整体失败

5. **OUTPUT**（输出文件）
   - 输入：完整的处理结果
   - 输出：无（文件已写入）
   - 类型：I/O 密集（文件写入）
   - 并发数：默认 10
   - **特殊处理**：
     - 写入输出文件（Dry Run 模式下跳过）
     - 更新增量记录（如果成功）
     - 清理临时目录（无论成功/失败）
     - 记录最终统计信息

### 2.2 阶段数据模型

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

@dataclass
class StageData:
    """阶段数据容器
    
    用于在阶段之间传递视频处理数据
    """
    video_info: VideoInfo
    detection_result: Optional[DetectionResult] = None
    download_result: Optional[Dict[str, Any]] = None
    translation_result: Optional[Dict[str, Path]] = None
    summary_result: Optional[str] = None
    temp_dir: Optional[Path] = None  # 临时目录（在 DOWNLOAD 阶段创建）
    temp_dir_created: bool = False  # 临时目录是否已创建
    error: Optional[Exception] = None  # 错误异常对象
    error_stage: Optional[str] = None  # 发生错误的阶段名称
    error_type: Optional[ErrorType] = None  # 错误类型（ErrorType 枚举）
    skip_reason: Optional[str] = None  # 跳过原因（如"无可用字幕"）
    is_processed: bool = False  # 是否已处理（用于增量管理）
    processing_failed: bool = False  # 处理是否失败（用于资源清理）
```

## 3. 架构设计

### 3.1 阶段队列系统

```python
class StageQueue:
    """阶段队列
    
    管理单个阶段的队列和执行器，支持并发处理和错误处理
    """
    def __init__(
        self,
        stage_name: str,
        executor: ThreadPoolExecutor,
        processor: Callable[[StageData], StageData],
        next_stage_queue: Optional['StageQueue'] = None,
        max_queue_size: int = 100,  # 最大队列大小，防止内存溢出
        failure_logger: Optional[FailureLogger] = None,  # 失败记录器
        cancel_token: Optional[CancelToken] = None,  # 取消令牌
    ):
        self.stage_name = stage_name
        self.executor = executor
        self.processor = processor
        self.next_stage_queue = next_stage_queue
        self.failure_logger = failure_logger
        self.cancel_token = cancel_token
        self.input_queue = queue.Queue(maxsize=max_queue_size)  # 限制队列大小
        self.running = False
        self.workers = []
        self._lock = threading.Lock()
        self._processed_count = 0
        self._failed_count = 0
    
    def enqueue(self, data: StageData):
        """将数据加入队列
        
        如果队列已满，会阻塞直到有空间
        """
        self.input_queue.put(data)
    
    def start(self, num_workers: int = None):
        """启动阶段处理
        
        Args:
            num_workers: worker 线程数量，如果为 None 则使用 executor 的 max_workers
        """
        if self.running:
            return
        
        self.running = True
        num_workers = num_workers or self.executor._max_workers
        
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"{self.stage_name}-worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def stop(self, timeout: float = 30.0):
        """停止阶段处理
        
        Args:
            timeout: 等待 worker 线程停止的超时时间（秒）
        """
        if not self.running:
            return
        
        self.running = False
        
        # 向队列中放入停止信号
        for _ in range(len(self.workers)):
            self.input_queue.put(None)  # None 作为停止信号
        
        # 等待所有 worker 线程停止
        for worker in self.workers:
            worker.join(timeout=timeout)
        
        self.workers.clear()
    
    def _worker_loop(self):
        """Worker 线程主循环"""
        while self.running:
            try:
                # 检查取消状态
                if self.cancel_token and self.cancel_token.is_cancelled():
                    break
                
                # 从队列中获取数据（带超时，以便定期检查取消状态）
                try:
                    data = self.input_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # None 作为停止信号
                if data is None:
                    break
                
                # 处理数据
                try:
                    result = self.processor(data)
                    
                    # 如果处理失败，记录失败信息
                    if result.error and self.failure_logger:
                        self._log_failure(result)
                    
                    # 如果处理成功且没有跳过，传递给下一阶段
                    if not result.error and not result.skip_reason and self.next_stage_queue:
                        self.next_stage_queue.enqueue(result)
                    
                    # 更新统计
                    with self._lock:
                        if result.error:
                            self._failed_count += 1
                        else:
                            self._processed_count += 1
                
                except Exception as e:
                    logger.error(f"阶段 {self.stage_name} 处理异常: {e}")
                    if data:
                        data.error = e
                        data.error_stage = self.stage_name
                        if self.failure_logger:
                            self._log_failure(data)
                
                finally:
                    self.input_queue.task_done()
            
            except Exception as e:
                logger.error(f"Worker 线程异常: {e}")
    
    def _log_failure(self, data: StageData):
        """记录失败信息
        
        根据阶段调用相应的失败记录方法
        """
        # 根据阶段和错误类型调用相应的失败记录方法
        # 例如：log_download_failure, log_translation_failure, log_summary_failure
        # ...
```

### 3.2 Pipeline 编排器

```python
class StagedPipeline:
    """分阶段 Pipeline 编排器"""
    
    def __init__(
        self,
        language_config: LanguageConfig,
        translation_llm: Optional[LLMClient],
        summary_llm: Optional[LLMClient],
        output_writer: OutputWriter,
        failure_logger: FailureLogger,
        incremental_manager: IncrementalManager,
        archive_path: Optional[Path],
        force: bool = False,
        dry_run: bool = False,
        cancel_token: Optional[CancelToken] = None,
        proxy_manager=None,
        cookie_manager=None,
        run_id: Optional[str] = None,
        on_log: Optional[Callable] = None,
        # 阶段并发配置（注意：已移除 discover_concurrency）
        detect_concurrency: int = 10,
        download_concurrency: int = 10,
        translate_concurrency: int = 5,
        summarize_concurrency: int = 5,
        output_concurrency: int = 10,
    ):
        # 初始化各个阶段队列
        pass
    
    def process_videos(self, videos: List[VideoInfo]) -> Dict[str, int]:
        """处理视频列表
        
        Returns:
            统计信息：{"total": 总数, "success": 成功数, "failed": 失败数}
        """
        # 1. 将视频加入 DETECT 阶段（第一个阶段）
        # 2. 启动所有阶段
        # 3. 等待所有阶段完成
        # 4. 返回统计信息
        pass
```

## 4. 实现细节

### 4.1 阶段处理器

每个阶段需要实现一个处理器函数：

```python
def process_detect_stage(
    data: StageData,
    cookie_manager,
    run_id: str,
    on_log: Optional[Callable],
    cancel_token: Optional[CancelToken]
) -> StageData:
    """处理检测阶段"""
    try:
        # 设置日志上下文
        set_log_context(run_id=run_id, task="detect", video_id=data.video_info.video_id)
        
        # 执行检测
        detector = SubtitleDetector(cookie_manager=cookie_manager)
        detection_result = detector.detect(data.video_info)
        
        # 更新数据
        data.detection_result = detection_result
        
        if not detection_result.has_subtitles:
            data.skip_reason = "无可用字幕"
            # 记录失败
            # ...
        
        return data
    except Exception as e:
        data.error = e
        data.error_stage = "detect"
        return data
```

### 4.2 错误处理

- **各阶段失败时立即记录**：
  - DETECT 阶段失败：调用 `failure_logger.log_failure(stage="detect")`
  - DOWNLOAD 阶段失败：调用 `failure_logger.log_download_failure()`
  - TRANSLATE 阶段失败：调用 `failure_logger.log_translation_failure()`
  - SUMMARIZE 阶段失败：调用 `failure_logger.log_summary_failure()`
  - OUTPUT 阶段失败：调用 `failure_logger.log_failure()`

- **部分失败处理**：
  - 翻译部分语言失败：不视为整体失败，继续处理其他语言
  - 摘要失败：不视为整体失败，继续输出其他内容

- **失败视频处理**：
  - 失败的视频不会进入下一阶段
  - 错误信息记录到 `StageData.error` 和 `StageData.error_stage`
  - 最终在 OUTPUT 阶段统计失败数量

### 4.3 日志记录

- 每个阶段设置相应的日志上下文（task="detect"/"download"/"translate"/"summarize"/"output"）
- 保持与现有日志格式一致

### 4.4 取消支持

- **取消检查**：
  - 每个 worker 线程在处理前检查 `cancel_token.is_cancelled()`
  - 如果取消，立即停止从队列中取数据
  - 使用 `queue.get(timeout=1.0)` 定期检查取消状态

- **取消传播**：
  - 当检测到取消时，向所有阶段的队列发送停止信号（None）
  - 等待正在处理的任务完成（或超时）
  - 清理临时文件和资源

- **取消记录**：
  - 取消的任务不记录到 `failure_logger`（取消不是失败）
  - 记录日志："任务已取消: {reason}"

### 4.5 资源管理

- **临时目录管理**：
  - 在 DOWNLOAD 阶段创建临时目录（`temp_dir`）
  - 在 OUTPUT 阶段完成后清理临时目录
  - 如果某个阶段失败，也应该清理临时目录
  - 使用 `try-finally` 确保清理

- **内存管理**：
  - 为每个阶段的队列设置最大大小（`max_queue_size=100`）
  - 使用 `queue.Queue(maxsize=...)` 限制队列大小
  - 当队列满时，阻塞生产者线程（防止内存溢出）

- **增量管理集成**：
  - 在 DETECT 阶段之前检查增量记录（`incremental_manager.is_processed()`）
  - 如果已处理且 `force=False`，设置 `skip_reason="已处理"` 并跳过
  - 在 OUTPUT 阶段成功后更新增量记录（`incremental_manager.mark_as_processed()`）

- **Dry Run 模式支持**：
  - DOWNLOAD 阶段：正常执行（需要下载字幕文件）
  - TRANSLATE 阶段：正常执行（需要翻译字幕）
  - SUMMARIZE 阶段：正常执行（需要生成摘要）
  - OUTPUT 阶段：跳过文件写入和增量更新

### 4.6 统计信息收集

- **进度回调**：
  - 每个阶段完成后更新统计信息
  - 使用线程安全的方式更新统计（`threading.Lock`）
  - 定期调用 `on_stats` 回调（如每完成一个视频）

- **阶段级统计**：
  - 每个 `StageQueue` 维护自己的统计（`_processed_count`, `_failed_count`）
  - 最终在 `StagedPipeline` 中汇总所有阶段的统计

## 5. 兼容性保证

### 5.1 API 兼容性

- 保持 `process_video_list` 函数签名不变
- 内部实现改为使用 `StagedPipeline`
- 返回格式保持一致

### 5.2 行为兼容性

- 错误处理逻辑保持一致
- 失败记录格式保持一致
- 日志格式保持一致
- 增量管理逻辑保持一致

### 5.3 配置兼容性

- 支持通过参数配置各阶段并发数
- 默认值与当前实现保持一致（总体并发 10）
- 保持 `process_video_list` 函数的 `concurrency` 参数，内部映射到各阶段并发数

## 6. 实施计划

### 阶段 1：基础架构
1. 实现 `StageData` 数据模型（包含所有必要字段）
2. 实现 `StageQueue` 基础类（包含 worker 线程、错误处理、取消支持）
3. 实现 `StagedPipeline` 框架（阶段编排、统计收集）

### 阶段 2：阶段实现
1. 实现 DETECT 阶段（增量检查、字幕检测、失败记录）
2. 实现 DOWNLOAD 阶段（临时目录创建、字幕下载、失败记录）
3. 实现 TRANSLATE 阶段（翻译逻辑、部分失败处理、失败记录）
4. 实现 SUMMARIZE 阶段（摘要生成、失败记录）
5. 实现 OUTPUT 阶段（文件写入、增量更新、临时目录清理、统计汇总）

### 阶段 3：集成与测试
1. 集成到 `process_video_list`
2. 确保错误处理正确
3. 确保日志记录正确
4. 确保失败记录正确
5. 性能测试和优化

### 阶段 4：文档与清理
1. 更新相关文档
2. 代码清理和优化
3. 添加注释和文档字符串

## 7. 注意事项

1. **线程安全**：
   - 使用 `queue.Queue` 确保阶段间数据传递的线程安全
   - 使用 `threading.Lock` 保护共享状态（统计信息等）
   - 避免在 `StageData` 中共享可变状态

2. **资源清理**：
   - 使用 `try-finally` 确保临时文件正确清理
   - 在 OUTPUT 阶段完成后清理临时目录
   - 如果某个阶段失败，也应该清理临时目录

3. **内存管理**：
   - 为每个阶段的队列设置最大大小（`max_queue_size=100`）
   - 监控队列大小，防止内存溢出
   - 考虑使用流式处理（如果视频数量很大）

4. **错误恢复**：
   - 确保部分失败不影响整体流程
   - 翻译部分语言失败不视为整体失败
   - 摘要失败不视为整体失败

5. **性能监控**：
   - 添加各阶段的性能监控（处理时间、成功率等）
   - 记录队列大小、等待时间等指标
   - 提供性能报告和优化建议

6. **取消支持**：
   - 确保取消能够快速传播到所有阶段
   - 清理正在处理的任务和资源
   - 不将取消记录为失败

7. **增量管理**：
   - 在 DETECT 阶段之前检查增量记录
   - 在 OUTPUT 阶段成功后更新增量记录
   - 支持 `force` 参数强制重跑

## 8. 预期收益

1. **更好的资源利用**：
   - I/O 密集阶段（下载）和 AI 计算阶段（翻译、摘要）可以并行
   - 不同阶段可以使用不同的并发数，优化资源利用

2. **更灵活的并发控制**：
   - 不同阶段可以配置不同并发数
   - I/O 密集阶段可以使用更高的并发数（10）
   - AI 计算阶段可以使用较低的并发数（5，受 AI 并发限制）

3. **更好的可扩展性**：
   - 易于添加新阶段或修改现有阶段
   - 阶段之间解耦，修改一个阶段不影响其他阶段

4. **更好的可观测性**：
   - 可以监控各阶段的性能（处理时间、成功率等）
   - 可以识别瓶颈阶段并优化

5. **更好的错误处理**：
   - 各阶段失败时立即记录，便于排查问题
   - 部分失败不影响整体流程

## 9. 风险评估与缓解措施

### 高风险

1. **线程安全问题**：
   - **风险**：多阶段并发可能导致数据竞争
   - **缓解措施**：使用线程安全的数据结构（`queue.Queue`），避免共享可变状态

2. **资源泄漏**：
   - **风险**：临时文件可能没有正确清理
   - **缓解措施**：使用 `try-finally` 确保清理，添加资源监控

3. **错误处理不一致**：
   - **风险**：新架构可能改变错误处理行为
   - **缓解措施**：详细测试，确保与现有行为一致

### 中风险

1. **性能问题**：
   - **风险**：队列传递可能增加开销
   - **缓解措施**：性能测试，必要时优化

2. **内存占用**：
   - **风险**：队列中可能堆积大量数据
   - **缓解措施**：限制队列大小，监控内存使用

## 10. 测试策略

### 单元测试
- 测试每个阶段的处理器
- 测试错误处理逻辑
- 测试资源清理

### 集成测试
- 测试完整流程
- 测试错误场景（各阶段失败）
- 测试取消场景
- 测试 Dry Run 模式
- 测试增量管理

### 性能测试
- 对比新旧架构的性能
- 测试不同并发配置下的表现
- 测试内存使用情况
- 测试队列大小限制的影响

