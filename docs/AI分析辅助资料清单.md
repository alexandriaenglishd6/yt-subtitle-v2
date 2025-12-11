# AI 分析辅助资料清单

> 当需要将项目代码发送给其他 AI 进行分析时，除了 GitHub 上的代码，还需要提供以下辅助资料。

---

## 📋 必须提供的核心文档（按优先级）

### 🔴 最高优先级（必须提供）

这些文档是理解项目架构、设计意图和当前状态的关键：

1. **`docs/v2_final_plan.md`** ⭐⭐⭐
   - **行为规范文档（最高优先级）**
   - 定义所有核心功能的实现规范
   - 包含：Dry Run、增量处理、目录结构、配置路径等硬规则
   - **重要性**：所有代码实现必须以此为准，AI 分析时必须参考

2. **`docs/ide_任务表.md`**
   - 开发任务清单，包含 P0/P1 所有任务
   - 任务依赖关系、工作量估算
   - **当前进度**：P0 已完成，P1-1 到 P1-6 已完成
   - **重要性**：了解项目开发历史和当前状态

3. **`README.md`**
   - 项目简介和快速开始指南
   - 功能概览、安装说明、配置说明
   - **重要性**：快速了解项目整体情况

4. **`docs/新会话上下文恢复指南.md`**
   - 上下文恢复指南
   - 项目结构概览
   - **重要性**：帮助 AI 快速理解项目结构

### 🟡 高优先级（强烈建议提供）

5. **`docs/project_blueprint.md`**
   - 项目蓝图，说明工具目标、使用场景、整体架构
   - **重要性**：理解项目的设计理念和架构思路

6. **`docs/acceptance_criteria.md`**
   - 验收标准，用于验证功能是否正确实现
   - **重要性**：了解功能验收标准

7. **`requirements.txt`**
   - 项目依赖列表
   - **重要性**：了解项目技术栈和依赖关系

### 🟢 中优先级（按需提供）

8. **`docs/测试执行文档.md`**
   - 测试执行指南和测试用例
   - **重要性**：了解测试方法和测试覆盖

9. **`docs/AI_PROVIDER_EXTENSION.md`**
   - AI 供应商扩展指南
   - **重要性**：如果分析涉及 AI 功能扩展

10. **`docs/cookie_setup_guide.md`**
    - Cookie 设置指南
    - **重要性**：如果分析涉及网络功能

---

## 📁 项目结构说明

### 核心目录结构

```
yt-subtitle-v2/
├── core/              # 核心业务逻辑
│   ├── pipeline.py    # 主流水线（process_video_list, process_single_video）
│   ├── detector.py    # 字幕检测
│   ├── downloader.py  # 字幕下载
│   ├── translator.py  # 翻译
│   ├── summarizer.py  # 摘要
│   ├── output.py      # 输出处理
│   ├── llm_client.py  # AI 接口抽象
│   ├── ai_providers.py # AI 供应商实现
│   ├── models.py      # 数据模型
│   ├── language.py    # 语言配置
│   ├── fetcher.py     # 视频信息获取
│   ├── incremental.py # 增量处理
│   ├── failure_logger.py # 失败记录
│   └── ...
├── ui/                # GUI 界面
│   ├── main_window.py # 主窗口
│   ├── business_logic.py # GUI 业务逻辑
│   ├── components/    # UI 组件
│   ├── pages/         # 页面组件
│   └── i18n/          # 国际化资源
├── cli/               # CLI 命令行接口
│   ├── main.py        # CLI 入口
│   ├── channel.py     # 频道模式
│   ├── urls.py        # URL 列表模式
│   └── ...
├── config/            # 配置管理
│   └── manager.py     # 配置管理器
└── docs/              # 文档
```

### 关键设计模式

1. **模块化设计**：核心逻辑与 UI/CLI 分离
2. **配置驱动**：所有配置通过 `ConfigManager` 统一管理
3. **错误处理**：统一的 `AppException` 和错误分类
4. **国际化**：使用 `i18n_manager.py` 管理多语言
5. **原子写文件**：使用 `_atomic_write` 确保文件写入安全

---

## 🔑 关键概念和术语

### 核心概念

1. **Dry Run 模式**：仅检测字幕，不下载不处理
2. **增量处理**：使用 `--download-archive` 记录已处理视频，避免重复
3. **翻译策略**：
   - `OFFICIAL_ONLY`：只用官方多语言字幕
   - `OFFICIAL_FIRST`：优先官方字幕/自动翻译，无则用 AI
   - `AI_ONLY`：只用 AI 翻译
4. **双语字幕**：源语言 + 目标语言对照输出
5. **输出目录结构**：使用语言代码命名（如 `original.en.srt`）

### 配置项说明

- **语言配置**：`LanguageConfig`（UI语言、目标语言、摘要语言等）
- **AI 配置**：`AIConfig`（翻译和摘要独立配置）
- **网络配置**：代理列表、Cookie、并发数
- **输出配置**：输出目录、增量存档路径

---

## 🚨 重要注意事项

### 代码规范

1. **错误处理**：所有错误必须使用 `AppException`，并指定 `ErrorType`
2. **日志记录**：使用 `get_logger()` 获取 logger，支持上下文（run_id, task, video_id）
3. **文件操作**：使用 `_atomic_write` 进行原子写文件
4. **线程安全**：GUI 更新必须使用 `self.after(0, ...)` 切换到主线程

### 实现约束

1. **行为规范**：所有实现必须符合 `v2_final_plan.md` 的规定
2. **目录结构**：输出目录结构必须严格按照规范
3. **配置路径**：配置保存在用户数据目录（如 `%APPDATA%/yt-subtitle-v2/`）
4. **国际化**：所有 UI 文本必须使用 `t()` 函数进行翻译

---

## 📝 分析建议

### 给 AI 的提示词模板

```
我正在开发 YouTube 字幕工具 v2，请先阅读以下核心文档以恢复上下文：

1. 行为规范：docs/v2_final_plan.md（最高优先级，所有实现必须以此为准）
2. 任务表：docs/ide_任务表.md（了解开发历史和当前进度）
3. 项目蓝图：docs/project_blueprint.md（理解设计理念）
4. README.md（快速了解项目）

当前状态：
- P0 已完成
- P1-1 到 P1-6 已完成
- 最新功能：有字幕/无字幕视频链接保存（追加模式，带分隔符）

请先阅读这些文档，然后告诉我下一步应该做什么。
```

### 分析重点

1. **架构理解**：先理解整体架构和模块划分
2. **数据流**：理解从输入到输出的完整数据流
3. **配置系统**：理解配置如何加载、保存和使用
4. **错误处理**：理解错误分类和处理机制
5. **并发处理**：理解 `TaskRunner` 如何实现并发

---

## 📦 完整资料包清单

如果要完整分析项目，建议按以下顺序提供：

### 第一阶段（必须）
- [ ] `docs/v2_final_plan.md`
- [ ] `docs/ide_任务表.md`
- [ ] `README.md`
- [ ] `requirements.txt`
- [ ] `docs/新会话上下文恢复指南.md`

### 第二阶段（强烈建议）
- [ ] `docs/project_blueprint.md`
- [ ] `docs/acceptance_criteria.md`
- [ ] `docs/测试执行文档.md`

### 第三阶段（按需）
- [ ] `docs/AI_PROVIDER_EXTENSION.md`（如果涉及 AI 扩展）
- [ ] `docs/cookie_setup_guide.md`（如果涉及网络功能）
- [ ] 其他相关技术文档

---

## 💡 快速检查清单

在发送给 AI 之前，请确认：

- [ ] 已提供 `v2_final_plan.md`（行为规范）
- [ ] 已提供 `ide_任务表.md`（任务清单）
- [ ] 已提供 `README.md`（项目简介）
- [ ] 已提供 `requirements.txt`（依赖列表）
- [ ] 已说明当前开发进度
- [ ] 已说明需要分析的具体问题或目标

---

**最后更新**：2025-12-11

