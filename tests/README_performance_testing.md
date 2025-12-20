# 性能与稳定性测试快速指南

## 快速开始

### 1. 安装可选依赖（用于资源监控）

```bash
pip install psutil
```

> 注意：`psutil` 是可选的，如果不安装，测试脚本仍可运行，只是会跳过资源监控部分。

### 2. 运行性能对比测试

```bash
# 对比新旧架构的性能（使用 10 个视频，并发数 10）
python tests/test_performance_comparison.py --url "https://www.youtube.com/@频道名" --count 10 --concurrency 10

# 只测试新架构
python tests/test_performance_comparison.py --url "https://www.youtube.com/@频道名" --count 10 --only-staged

# 只测试旧架构
python tests/test_performance_comparison.py --url "https://www.youtube.com/@频道名" --count 10 --only-old
```

### 3. 分析日志

```bash
# 分析最新的日志文件
python tests/analyze_pipeline_logs.py logs/最新日志文件.log

# 输出分析结果到 JSON
python tests/analyze_pipeline_logs.py logs/最新日志文件.log --output analysis_result.json
```

---

## 测试场景建议

### 场景 1: 小规模快速验证（5-10 个视频）

```bash
python tests/test_performance_comparison.py --url "频道URL" --count 5 --concurrency 5
```

**目的**：快速验证基本功能是否正常

### 场景 2: 中等规模性能测试（50-100 个视频）

```bash
# 测试不同并发数
python tests/test_performance_comparison.py --url "频道URL" --count 50 --concurrency 10
python tests/test_performance_comparison.py --url "频道URL" --count 50 --concurrency 20
python tests/test_performance_comparison.py --url "频道URL" --count 50 --concurrency 30
```

**目的**：找到最佳并发配置，验证性能提升

### 场景 3: 长时间稳定性测试（500+ 个视频）

```bash
# 使用 GUI 或 CLI 处理大量视频，然后分析日志
python tests/analyze_pipeline_logs.py logs/最新日志文件.log
```

**目的**：验证长时间运行的稳定性，检查内存泄漏

---

## 关键指标解读

### 性能指标

- **总处理时间**：应该与旧架构相当或更快
- **平均每个视频**：应该与旧架构相当
- **吞吐量**：单位时间内处理的视频数，新架构应该更高

### 资源指标

- **峰值内存**：不应该显著高于旧架构
- **平均内存**：应该保持稳定，不应该持续增长（内存泄漏）
- **线程数量**：应该符合配置的并发数

### 稳定性指标

- **成功率**：应该与旧架构相同
- **失败率**：应该与旧架构相同
- **错误类型分布**：应该合理，不应该出现大量 UNKNOWN 错误

---

## 常见问题

### Q: 新架构性能比旧架构慢？

**可能原因**：
1. 并发配置不合理（各阶段并发数设置不当）
2. 某个阶段成为瓶颈
3. 队列大小限制了并行度

**解决方案**：
1. 调整各阶段的并发配置
2. 检查日志，找出瓶颈阶段
3. 增加队列大小

### Q: 内存使用持续增长？

**可能原因**：
1. 临时文件未正确清理
2. 队列中积累了太多数据
3. 线程泄漏

**解决方案**：
1. 检查临时目录清理逻辑
2. 检查队列大小限制
3. 检查线程管理

### Q: 成功率下降？

**可能原因**：
1. 错误处理逻辑不一致
2. 数据流转问题
3. 资源竞争问题

**解决方案**：
1. 对比新旧架构的日志
2. 检查各阶段的错误处理
3. 验证数据流转逻辑

---

## 持续监控建议

在实际使用中，建议：

1. **定期运行性能测试**：每周或每月运行一次性能对比测试
2. **监控日志**：定期分析日志，关注错误率和异常模式
3. **收集用户反馈**：关注实际使用中的问题
4. **性能基准**：建立性能基准，跟踪性能变化趋势

---

## 回退方案

如果新架构出现问题，可以：

1. **临时回退**：在代码中设置 `use_staged_pipeline=False`
2. **配置回退**：在配置文件中添加开关（未来实现）
3. **版本回退**：如果问题严重，回退到之前的版本

