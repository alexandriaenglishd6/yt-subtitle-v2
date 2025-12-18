# YouTube 字幕工具 v3.1

> 一个只为「我要把整个 YouTube 频道的字幕变成**我需要的语言摘要和双语字幕**」而生的极简、极快、尽量不翻车的个人神器。  
> 一条频道链接，一键到底，1000+ 视频也不怕，重构后的模块化架构更稳定、更强大。

## 项目简介

YouTube 自动字幕工具 v3.1 - 专注于频道级批量字幕处理、翻译和摘要生成。本项目经过全面重构（v3.1），采用了分阶段流水线（Staged Pipeline）架构，支持大规模并发处理，具备完善的国际化（i18n）支持。

## 核心功能

### 批量处理
- ✅ **频道模式**：输入频道 URL，自动获取所有视频。
- ✅ **URL 列表模式**：支持粘贴多行 URL 或从文本文件导入链接。
- ✅ **分阶段流水线**：检测、下载、翻译、摘要、输出五个阶段独立运行，互不阻塞。
- ✅ **智能并发**：支持普通任务与 AI 请求独立并发控制，避免 API 限流。

### 字幕处理
- ✅ **智能检测**：自动区分人工字幕和自动生成字幕。
- ✅ **多格式输出**：支持 SRT 和 TXT 格式，支持双语字幕对照。
- ✅ **增量处理**：只处理新视频，跳过已处理视频，支持强制重跑模式。
- ✅ **Dry Run 模式**：仅检测字幕，不消耗 AI 额度。

### AI 功能
- ✅ **多供应商支持**：原生支持 OpenAI, Anthropic, Gemini, DeepSeek, Kimi, 智谱 GLM 等。
- ✅ **OpenAI 兼容性**：支持任何兼容 OpenAI 接口的第三方中转站。
- ✅ **本地模型支持**：支持 Ollama 和 LM Studio 本地部署模型。
- ✅ **Google 翻译**：内置免费的 Google 翻译支持（无需 API Key）。
- ✅ **独立配置**：翻译和摘要可配置不同的供应商、模型和并发限制。

### 网络与安全
- ✅ **多代理轮询**：支持 HTTP/SOCKS5 代理，自动健康检查。
- ✅ **Cookie 管理**：内置 Netscape 格式 Cookie 支持，规避 YouTube 访问限制。
- ✅ **信息脱敏**：日志中自动脱敏 API Key、Cookie 等敏感信息。

### 用户界面
- ✅ **现代化 GUI**：基于 CustomTkinter 的深色/浅色现代化界面。
- ✅ **完全国际化**：中英文界面一键切换，日志输出同步国际化。
- ✅ **增强型日志**：带时间戳的实时日志面板，支持级别过滤。

## 快速开始

### 安装依赖

```bash
# 核心依赖
pip install yt-dlp customtkinter>=5.2.0 deep-translator

# AI 功能可选依赖
pip install openai anthropic google-generativeai
pip install pysocks  # 如果使用 SOCKS 代理
```

### 运行程序

```bash
# 启动 GUI (推荐)
python main.py

# 启动 CLI (开发/自动化)
python cli.py channel --url "https://www.youtube.com/@channel" --run
```

## 目录结构 (v3.1 模块化)

```
.
├── core/                # 核心业务逻辑
│   ├── ai_providers/    # AI 客户端实现 (OpenAI, Anthropic, Gemini等)
│   ├── staged_pipeline/ # 分阶段流水线调度引擎
│   ├── output/          # 格式化输出模块
│   └── pipeline/        # 业务流程编排
├── ui/                  # 现代化 GUI 实现
│   ├── main_window/     # 主窗口与页面管理
│   ├── pages/           # 各功能配置页面
│   └── i18n/            # 国际化语言包 (zh_CN, en_US)
├── config/              # 配置管理
├── cli/                 # 命令行接口实现
└── out/                 # 默认输出目录
```

## 更新日志

### v3.1.0 (2025-12-18)
- ✨ **重大重构**：全面完成模块化包结构拆分，提升系统可维护性。
- ✨ **AI 并发分离**：新增 AI 独立并发线程设置，防止大规模处理时触发 API 限流。
- ✨ **Google 翻译集成**：支持通过 `deep-translator` 使用免费的 Google 翻译。
- ✨ **日志增强**：GUI 日志面板增加时间戳，全流程日志信息（含报错）实现 100% 国际化。
- 💄 **UI 优化**：统一全站字体规格，优化 AI 供应商配置交互，增加预填示例。
- 🔒 **安全性与易用性**：实现 API Key 掩码显示、清除功能，日志自动脱敏，保护用户隐私。
