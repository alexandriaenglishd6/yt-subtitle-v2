# YouTube Subtitle Tool / YouTube 字幕工具 v1.0.0

**[English](#english)** | **[中文](#chinese)**

---

<a name="english"></a>
## 🇬🇧 English

> A minimalist, fast, and reliable tool for batch downloading YouTube subtitles, translating them, and generating AI summaries.  
> One channel URL, one click - handles 1000+ videos with ease.

### Features

#### Batch Processing
- ✅ **Channel Mode**: Input a channel URL, automatically fetch all videos
- ✅ **URL List Mode**: Paste multiple URLs or import from file
- ✅ **Staged Pipeline**: Detect, Download, Translate, Summarize, Output - each stage runs independently
- ✅ **Smart Concurrency**: Separate concurrency control for tasks and AI requests

#### Subtitle Processing
- ✅ **Smart Detection**: Distinguish between manual and auto-generated subtitles
- ✅ **Multiple Formats**: SRT and TXT output, bilingual subtitle support
- ✅ **Incremental Processing**: Only process new videos, skip processed ones
- ✅ **Dry Run Mode**: Detect subtitles only, no AI quota consumed

#### AI Features
- ✅ **Multi-Provider**: OpenAI, Anthropic, Gemini, DeepSeek, Kimi, GLM, etc.
- ✅ **OpenAI Compatible**: Any OpenAI-compatible API endpoint
- ✅ **Local Models**: Ollama and LM Studio support
- ✅ **Google Translate**: Free translation without API key
- ✅ **Separate Config**: Different providers for translation and summarization

#### Network & Security
- ✅ **Proxy Support**: HTTP/SOCKS5 with health check
- ✅ **Cookie Management**: Netscape format cookie support
- ✅ **Data Masking**: Auto-mask API keys and cookies in logs

#### User Interface
- ✅ **Modern GUI**: Dark/Light theme with CustomTkinter
- ✅ **Internationalization**: Chinese/English interface switch
- ✅ **Enhanced Logging**: Real-time log panel with level filtering

### Quick Start

```bash
# Install dependencies
pip install yt-dlp customtkinter>=5.2.0 deep-translator

# Optional AI dependencies
pip install openai anthropic google-generativeai

# Run GUI
python main.py

# Run CLI
python cli.py channel --url "https://www.youtube.com/@channel" --run
```

### Portable Version

Download the pre-built portable version from [Releases](https://github.com/alexandriaenglishd6/yt-subtitle-v2/releases), extract and run `YT-Subtitle-Tool.exe`.

---

<a name="chinese"></a>
## 🇨🇳 中文

> 一个只为「把整个 YouTube 频道的字幕变成**我需要的语言摘要和双语字幕**」而生的极简、极快、尽量不翻车的个人神器。  
> 一条频道链接，一键到底，1000+ 视频也不怕。

### 核心功能

#### 批量处理
- ✅ **频道模式**：输入频道 URL，自动获取所有视频
- ✅ **URL 列表模式**：支持粘贴多行 URL 或从文本文件导入链接
- ✅ **分阶段流水线**：检测、下载、翻译、摘要、输出五个阶段独立运行
- ✅ **智能并发**：支持普通任务与 AI 请求独立并发控制

#### 字幕处理
- ✅ **智能检测**：自动区分人工字幕和自动生成字幕
- ✅ **多格式输出**：支持 SRT 和 TXT 格式，支持双语字幕对照
- ✅ **增量处理**：只处理新视频，跳过已处理视频
- ✅ **Dry Run 模式**：仅检测字幕，不消耗 AI 额度

#### AI 功能
- ✅ **多供应商支持**：原生支持 OpenAI, Anthropic, Gemini, DeepSeek, Kimi, 智谱 GLM 等
- ✅ **OpenAI 兼容性**：支持任何兼容 OpenAI 接口的第三方中转站
- ✅ **本地模型支持**：支持 Ollama 和 LM Studio 本地部署模型
- ✅ **Google 翻译**：内置免费的 Google 翻译支持（无需 API Key）
- ✅ **独立配置**：翻译和摘要可配置不同的供应商、模型和并发限制

#### 网络与安全
- ✅ **多代理轮询**：支持 HTTP/SOCKS5 代理，自动健康检查
- ✅ **Cookie 管理**：内置 Netscape 格式 Cookie 支持
- ✅ **信息脱敏**：日志中自动脱敏 API Key、Cookie 等敏感信息

#### 用户界面
- ✅ **现代化 GUI**：基于 CustomTkinter 的深色/浅色现代化界面
- ✅ **完全国际化**：中英文界面一键切换，日志输出同步国际化
- ✅ **增强型日志**：带时间戳的实时日志面板，支持级别过滤

### 快速开始

```bash
# 安装核心依赖
pip install yt-dlp customtkinter>=5.2.0 deep-translator

# AI 功能可选依赖
pip install openai anthropic google-generativeai

# 启动 GUI (推荐)
python main.py

# 启动 CLI (开发/自动化)
python cli.py channel --url "https://www.youtube.com/@channel" --run
```

### 便携版

从 [Releases](https://github.com/alexandriaenglishd6/yt-subtitle-v2/releases) 下载预编译便携版，解压后运行 `YT-Subtitle-Tool.exe` 即可。

---

## 目录结构 / Project Structure

```
.
├── core/                # 核心业务逻辑 / Core business logic
│   ├── ai_providers/    # AI 客户端实现 / AI client implementations
│   ├── staged_pipeline/ # 分阶段流水线 / Staged pipeline engine
│   ├── translator/      # 翻译器模块 / Translator module
│   └── output/          # 格式化输出 / Output formatting
├── ui/                  # GUI 实现 / GUI implementation
│   ├── main_window/     # 主窗口 / Main window
│   ├── pages/           # 功能页面 / Feature pages
│   └── components/      # UI 组件 / UI components
├── config/              # 配置管理 / Configuration
├── cli/                 # 命令行接口 / CLI
└── out/                 # 默认输出目录 / Default output directory
```

---

## 更新日志 / Changelog

### v1.0.0 (2025-12-24) - 重构稳定版 / Refactored Stable Release
- ✨ **双语字幕优化**：选择双语模式自动启用翻译
- ✨ **分块翻译进度**：每 25% 输出进度汇总，日志更清晰
- ✨ **便携版打包**：支持 PyInstaller 打包为便携版
- ✨ **AI 摘要优化**：提示词增加内容筛选规则（跳过广告等）
- ✨ **UI 优化**：页面标题居中，顶部添加 GitHub 开源地址按钮
- 🐛 **Bug 修复**：修复翻译状态检查、国际化翻译键缺失等问题

### v3.1.1 (2025-12-23)
- ✨ 代码拆分重构：将大文件拆分为可复用模块
- 🔒 API Key 安全性：始终显示脱敏格式
- 🐛 语言文件清理：清理 50+ 个重复键

### v3.1.0 (2025-12-18)
- ✨ 重大重构：全面完成模块化包结构拆分
- ✨ AI 并发分离：新增 AI 独立并发线程设置
- ✨ Google 翻译集成：支持免费的 Google 翻译

---

## License

MIT License
