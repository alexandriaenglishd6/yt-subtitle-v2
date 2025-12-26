# 项目上下文（Project Context）

> 本文件用于项目封存后快速恢复开发，让 AI/IDE 快速了解项目情况。

## 项目简介

| 项目 | 说明 |
|------|------|
| **名称** | YouTube Tools |
| **版本** | v1.0.0（已发布） |
| **功能** | YouTube 字幕下载、翻译、摘要生成 |
| **技术栈** | Python + CustomTkinter + yt-dlp |
| **代码量** | 139 个 Python 文件，~12,000-15,000 行 |

---

## 当前状态

| 状态项 | 值 |
|--------|------|
| 最新版本 | v1.0.0 |
| 发布日期 | 2025-12-24 |
| 下一版本 | v2.0（规划中） |
| 封存日期 | 2025-12-25 |

---

## 快速恢复步骤

1. **导入项目**：将项目文件夹导入 IDE
2. **阅读文档**：
   - `docs/dev_log.md` - 开发历史（重点看里程碑和最近的日志）
   - `docs/v1_code_structure.md` - 代码结构
   - `docs/v2_high_concurrency_plan.md` - v2.0 规划
3. **运行测试**：`python main.py` 验证程序正常
4. **继续开发**：按 v2.0 规划继续

---

## IDE 启动提示词

复制以下内容给 AI/IDE：

```
请帮我恢复开发这个项目。

**项目信息**：
- YouTube 字幕工具 v1.0.0，已发布
- 下一步是 v2.0 高并发优化
- 技术栈：Python + CustomTkinter

**请先阅读以下文档**：
1. `docs/dev_log.md` - 开发历史（重点看里程碑和最近的工作日志）
2. `docs/v1_code_structure.md` - 代码结构
3. `docs/v2_high_concurrency_plan.md` - v2.0 规划

**开发规范**：
- 国际化：所有 UI 文本用 t() 包装
- 日志国际化：日志消息也要用 t() 包装
- 测试：每改 10 行代码就测试
- 工作流：参考 `docs/dev_workflow_guide.md`

**当前待办**：
- Phase 1：字幕清洗 + 日志汇总
- Phase 2：多 Key 轮询 + 多 Provider 支持
```

---

## 关键决策记录

| 决策 | 说明 |
|------|------|
| v1.0.0 完结 | 功能稳定，后续进入 v2.0 |
| 继续用 Python | 不迁移到 Tauri/Qt，等用户量增长再考虑 |
| 高并发优先 | v2.0 重点是性能优化 |
| 国际化规范 | 所有文本和日志都要国际化 |

---

## 核心文档索引

| 文档 | 作用 |
|------|------|
| `docs/dev_log.md` | 完整开发历史、里程碑、每日日志 |
| `docs/v2_high_concurrency_plan.md` | v2.0 功能规划（~1100 行） |
| `docs/v2_execution_plan.md` | 详细执行计划 |
| `docs/ui_optimization_plan.md` | UI 优化方案 |
| `docs/subtitle_processing_plan.md` | 字幕清洗与预处理方案 |
| `docs/auxiliary_tools_plan.md` | 独立辅助工具（ASR、文件合并器） |
| `docs/development_guidelines.md` | 开发规范与注意事项 |
| `docs/asr_module_design.md` | ASR 模块设计 |
| `docs/asr_guide.md` | ASR 技术指南 |
| `docs/v1_code_structure.md` | 代码结构统计 |
| `docs/dev_workflow_guide.md` | 开发工作流指南 |
| `README.md` | 项目概述（中英双语） |


### 演示文件

| 文件 | 说明 |
|------|------|
| `docs/ui_comparison_demo.html` | UI 组件效果对比 |
| `docs/v2_layout_demo.html` | 布局方案对比 |
| `docs/v2_layout_v1based.html` | v2.0 推荐布局 |

---

## 未完成工作

### Phase 1（基础版）
- [ ] 字幕清洗（P0）
- [ ] 日志汇总（P1）

### Phase 2（进阶版）
- [ ] 多 Key 轮询
- [ ] 多 Provider 支持
- [ ] ETA 改进

### Phase 3（专业版，可选）
- [ ] 代理池 + Cookie 轮换
- [ ] 健康监控
- [ ] 状态面板组件

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│  UI 层 (CustomTkinter)     → 负责展示界面、接收用户操作          │
│     ↓                                                           │
│  控制层 (StagedScheduler)  → 负责协调资源、安排任务优先级        │
│     ↓                                                           │
│  业务层 (core/)            → 下载、翻译、摘要                   │
│     ↓                                                           │
│  数据层 (config/)          → 配置、字幕、结果                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 联系方式

- GitHub: https://github.com/alexandriaenglishd6/yt-subtitle-v2
