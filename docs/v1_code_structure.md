# v1.0 代码结构与统计

> 统计日期：2025-12-25

## 项目概览

| 统计项 | 数量 |
|--------|------|
| **Python 文件总数** | 139 个 |
| **预估代码总行数** | ~12,000-15,000 行 |

---

## 目录结构

```
yt-subtitle-v2/
├── main.py                    # 程序入口
├── cli.py                     # 命令行入口
│
├── core/                      # 核心业务层（~8000 行）
│   ├── ai_providers/          # AI 供应商（9 个文件）
│   ├── staged_pipeline/       # 分阶段流水线（6 个文件）
│   ├── translator/            # 翻译模块（3 个文件）
│   ├── output/                # 输出模块（8 个文件）
│   ├── i18n/                  # 国际化（5 个文件）
│   └── ...                    # 其他核心模块（25 个文件）
│
├── ui/                        # UI 层（~4000 行）
│   ├── main_window/           # 主窗口（5 个文件）
│   ├── pages/                 # 页面（13 个文件）
│   ├── components/            # 组件（6 个文件）
│   └── business_logic/        # 业务逻辑（6 个文件）
│
├── config/                    # 配置层（3 个文件）
├── cli/                       # 命令行接口（7 个文件）
└── docs/                      # 文档
```

---

## 核心模块详解（core/）

### 主要文件

| 文件 | 行数估算 | 作用 |
|------|----------|------|
| `downloader.py` | ~1400 | YouTube 字幕下载，yt-dlp 封装 |
| `translator/translator.py` | ~1100 | 翻译核心逻辑，分块翻译 |
| `output/writer.py` | ~900 | 输出文件写入（SRT/TXT/MD）|
| `fetcher.py` | ~800 | 频道/播放列表视频列表获取 |
| `ai_providers/google_translate.py` | ~800 | Google 免费翻译 API |
| `logger.py` | ~750 | 日志系统，多级别输出 |
| `summarizer.py` | ~550 | 摘要生成（Map-Reduce）|
| `proxy_manager.py` | ~450 | 代理管理 |
| `staged_pipeline/scheduler.py` | ~400 | 分阶段调度器 |
| `staged_pipeline/queue.py` | ~350 | 任务队列 |
| `cookie_manager.py` | ~350 | Cookie 管理 |
| `failure_logger.py` | ~350 | 失败记录和报告 |
| `detector.py` | ~280 | 链接类型检测 |
| `incremental.py` | ~280 | 增量检查（跳过已处理）|

### AI 供应商（ai_providers/）

| 文件 | 作用 |
|------|------|
| `openai_compatible.py` | OpenAI 兼容 API（DeepSeek/Kimi/通义等）|
| `gemini.py` | Google Gemini |
| `anthropic.py` | Claude |
| `google_translate.py` | Google 翻译（免费）|
| `local_model.py` | 本地 Ollama 模型 |
| `base.py` | 供应商基类 |
| `factory.py` | 工厂模式创建供应商 |
| `registry.py` | 供应商注册表 |

### 分阶段流水线（staged_pipeline/）

| 文件 | 作用 |
|------|------|
| `scheduler.py` | 调度器，管理 5 个线程池 |
| `queue.py` | 任务队列实现 |
| `data_types.py` | 数据类型定义 |
| `processors/` | 各阶段处理器目录 |

### 输出模块（output/）

| 文件 | 作用 |
|------|------|
| `writer.py` | 输出写入主逻辑 |
| `formats/subtitle.py` | SRT/VTT 格式 |
| `formats/summary.py` | 摘要格式 |
| `formats/metadata.py` | 元数据格式 |
| `formats/chapter.py` | 章节格式 |

---

## UI 模块详解（ui/）

### 主窗口（main_window/）

| 文件 | 行数估算 | 作用 |
|------|----------|------|
| `window.py` | ~210 | 主窗口布局 |
| `event_handlers.py` | ~600 | 事件处理 |
| `task_handlers.py` | ~420 | 任务处理 |
| `page_manager.py` | ~220 | 页面管理 |

### 页面（pages/）

| 文件 | 行数估算 | 作用 |
|------|----------|------|
| `url_list_page.py` | ~700 | URL 列表页面 |
| `run_params_page.py` | ~420 | 运行参数页面 |
| `translation_summary_page.py` | ~230 | 翻译摘要设置 |
| `ai_config/` | ~300 | AI 配置页面 |
| `network_settings/` | ~400 | 网络设置页面 |

### 组件（components/）

| 文件 | 行数估算 | 作用 |
|------|----------|------|
| `log_panel.py` | ~550 | 日志面板 |
| `language_config.py` | ~520 | 语言配置 |
| `toolbar.py` | ~270 | 顶部工具栏 |
| `sidebar.py` | ~120 | 侧边栏 |
| `collapsible_frame.py` | ~60 | 可折叠框架 |

---

## 配置模块（config/）

| 文件 | 作用 |
|------|------|
| `manager.py` | 配置管理器，加载/保存配置 |

---

## 命令行接口（cli/）

| 文件 | 作用 |
|------|------|
| `main.py` | CLI 入口 |
| `channel.py` | 频道处理命令 |
| `urls.py` | URL 批量处理命令 |
| `cookie.py` | Cookie 管理命令 |
| `ai_smoke_test.py` | AI 连接测试 |

---

## 功能亮点

| 功能 | 状态 | 说明 |
|------|------|------|
| 分阶段并行 | ✅ | 5 个独立线程池 |
| 国际化 | ✅ | 中英双语 UI/日志 |
| 多 AI 供应商 | ✅ | 6+ 供应商 |
| 增量检查 | ✅ | 跳过已处理视频 |
| 失败重试 | ✅ | 自动重试 |
| 主题系统 | ✅ | 明暗主题 |
| 代理支持 | ✅ | HTTP/SOCKS5 |
| Cookie 管理 | ✅ | 登录态保持 |

---

## 技术栈

| 项目 | 技术 |
|------|------|
| UI 框架 | customtkinter |
| 下载工具 | yt-dlp |
| AI 调用 | requests / openai SDK |
| 翻译 | Google Translate API |
| 打包 | PyInstaller |
