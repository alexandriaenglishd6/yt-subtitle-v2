# StagedPipeline DETECT 和 OUTPUT 阶段测试

## 概述

`test_staged_pipeline_detect_output.py` 是一个测试脚本，用于验证 `StagedPipeline` 的 DETECT 和 OUTPUT 阶段的实现。

## 测试模式

测试脚本创建了一个**测试模式**的 `StagedPipeline`，其中：

- **DETECT 阶段**：正常执行字幕检测（使用真实的 `SubtitleDetector`）
- **DOWNLOAD 阶段**：直通模式，创建模拟的原始字幕文件
- **TRANSLATE 阶段**：直通模式，创建模拟的翻译字幕文件
- **SUMMARIZE 阶段**：直通模式，不生成摘要
- **OUTPUT 阶段**：正常执行输出写入（使用真实的 `OutputWriter`）

## 测试场景

### 测试 1: DETECT + OUTPUT（有字幕）

- 使用一个已知有字幕的测试视频
- 验证 DETECT 阶段能正确检测字幕
- 验证 OUTPUT 阶段能正确写入输出文件

### 测试 2: DETECT only（无字幕）

- 使用一个无字幕的测试视频（或无效视频 ID）
- 验证 DETECT 阶段能正确处理无字幕情况
- 验证失败记录是否正确

## 使用方法

```bash
# 运行测试
python tests/test_staged_pipeline_detect_output.py
```

## 注意事项

1. **测试视频 URL**：脚本中使用了示例视频 URL，实际测试时应该使用真实的视频 URL
2. **临时目录**：测试会创建临时目录，测试完成后会自动清理
3. **日志输出**：测试会输出详细的日志信息，包括处理过程和结果

## 预期结果

- 测试 1 应该成功处理视频并生成输出文件
- 测试 2 应该正确处理无字幕情况并记录失败

## 下一步

完成 DETECT 和 OUTPUT 阶段的验证后，可以继续实现中间阶段（DOWNLOAD、TRANSLATE、SUMMARIZE）的处理器函数。

