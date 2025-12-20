# 性能测试快速开始

## 最简单的测试方法

### 1. 性能对比测试（推荐）

```bash
# 使用频道 URL，测试 10 个视频，并发数 10
python tests/test_performance_comparison.py --url "https://www.youtube.com/@频道名" --count 10 --concurrency 10
```

**示例**：
```bash
python tests/test_performance_comparison.py --url "https://www.youtube.com/@JasonEfficiencyLab" --count 10 --concurrency 10
```

### 2. 只测试新架构

```bash
python tests/test_performance_comparison.py --url "频道URL" --count 10 --only-staged
```

### 3. 只测试旧架构

```bash
python tests/test_performance_comparison.py --url "频道URL" --count 10 --only-old
```

---

## 支持的 URL 类型

- **频道 URL**：`https://www.youtube.com/@频道名` 或 `https://www.youtube.com/c/频道名`
- **播放列表 URL**：`https://www.youtube.com/playlist?list=播放列表ID`
- **单个视频 URL**：`https://www.youtube.com/watch?v=视频ID`

---

## 测试结果解读

测试完成后会显示：

1. **总处理时间**：新旧架构的对比
2. **平均每个视频**：处理速度对比
3. **内存使用**：峰值和平均内存对比
4. **成功率**：功能一致性验证

**预期结果**：
- ✅ 新架构的处理时间应该与旧架构相当或更快
- ✅ 成功率应该完全相同（功能一致性）
- ✅ 内存使用不应该显著增加

---

## 常见问题

### Q: 提示需要 Cookie？

如果测试视频需要 Cookie 才能访问，请先在配置中设置 Cookie（通过 GUI 或直接编辑配置文件）。

### Q: 测试时间太长？

可以先用更少的视频测试：
```bash
python tests/test_performance_comparison.py --url "频道URL" --count 5 --concurrency 5
```

### Q: 想查看详细日志？

测试过程中的日志会输出到控制台，也可以查看 `logs/` 目录下的日志文件。

---

## 下一步

测试通过后，可以：

1. **在实际使用中验证**：使用 GUI 或 CLI 处理真实任务
2. **监控性能**：关注处理速度和资源使用
3. **收集反馈**：记录遇到的问题和改进建议

