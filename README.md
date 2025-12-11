# YouTube 字幕工具 v2

> 一个只为「我要把整个 YouTube 频道的字幕变成**我需要的语言摘要和双语字幕**」而生的极简、极快、尽量不翻车的个人神器。  
> 一条频道链接，一键到底，1000+ 视频也不怕，从此告别臃肿老项目。

## 项目简介

YouTube 自动字幕工具 v2 - 专注于频道级批量字幕处理、翻译和摘要生成。支持 GUI 和 CLI 两种使用方式，提供完整的字幕处理流程。

## 核心功能

### 批量处理
- ✅ **频道模式**：输入频道 URL，自动获取所有视频
- ✅ **URL 列表模式**：支持粘贴多行 URL 或从文本文件导入链接
- ✅ **播放列表支持**：自动识别并处理播放列表
- ✅ **单视频处理**：支持单个视频 URL

### 字幕处理
- ✅ **智能检测**：自动区分人工字幕和自动生成字幕
- ✅ **字幕下载**：支持下载原始字幕和官方翻译字幕
- ✅ **增量处理**：只处理新视频，避免重复下载
- ✅ **Dry Run 模式**：仅检测字幕，不下载不处理

### AI 功能
- ✅ **AI 翻译**：支持 OpenAI、Anthropic 等供应商
- ✅ **AI 摘要**：自动生成视频摘要
- ✅ **独立配置**：翻译和摘要可配置不同的 AI 供应商和模型
- ✅ **翻译策略**：支持"只用官方"、"优先官方后 AI"、"只用 AI" 三种策略
- ✅ **双语字幕**：支持生成源语言+目标语言双语字幕

### 网络支持
- ✅ **多代理支持**：支持 HTTP/HTTPS/SOCKS5 代理，自动轮询和健康检查
- ✅ **代理测试**：提供代理连通性测试功能
- ✅ **Cookie 支持**：支持 YouTube Cookie，可测试 Cookie 有效性
- ✅ **并发控制**：可配置并发数，提高处理效率

### 用户界面
- ✅ **现代化 GUI**：基于 CustomTkinter 的现代化界面
- ✅ **多语言支持**：支持中文和英文界面
- ✅ **主题系统**：提供 4 套主题（亮色白、亮色灰、深色灰、Claude 暖色）
- ✅ **实时日志**：实时显示处理进度和日志信息
- ✅ **统计信息**：显示计划处理数、成功/失败数、当前状态
- ✅ **日志过滤**：支持按级别过滤日志（全部/INFO/WARN/ERROR）

### 其他功能
- ✅ **失败记录**：自动记录失败视频到 `failed_urls.txt` 和 `failed_detail.log`
- ✅ **URL 去重**：URL 列表模式支持链接去重
- ✅ **配置管理**：所有配置保存在用户数据目录，支持持久化
- ✅ **错误处理**：完善的错误分类和重试机制

## 快速开始

### 安装依赖

```bash
# 核心依赖
pip install yt-dlp customtkinter>=5.2.0

# AI 功能（可选，根据需要选择）
pip install openai>=1.0.0          # OpenAI 支持
pip install anthropic>=0.18.0      # Anthropic 支持
pip install pysocks                # SOCKS 代理支持（如使用 SOCKS 代理）
```

### 运行 GUI

```bash
python main.py
```

### 运行 CLI

```bash
# 频道模式
python cli.py channel --url "https://www.youtube.com/@channel"

# URL 列表模式
python cli.py urls --file urls.txt

# Dry Run 模式（仅检测，不下载）
python cli.py channel --url "https://www.youtube.com/@channel" --dry-run
```

## 配置说明

### 配置文件位置

配置文件保存在用户数据目录：
- **Windows**: `%APPDATA%/yt-subtitle-v2/config.json`
- **Linux**: `~/.config/yt-subtitle-v2/config.json`
- **macOS**: `~/Library/Application Support/yt-subtitle-v2/config.json`

### 主要配置项

- **语言配置**：目标语言、摘要语言、双语模式、翻译策略
- **AI 配置**：翻译 AI 和摘要 AI 可独立配置供应商、模型、API 地址
- **网络配置**：代理列表、Cookie
- **运行参数**：并发数、重试次数、输出目录
- **UI 配置**：界面语言、主题

## 输出目录结构

```
out/
├── {video_id}/
│   ├── original.{lang}.srt          # 原始字幕
│   ├── translated.{lang}.srt       # 翻译字幕
│   ├── bilingual.{source}-{target}.srt  # 双语字幕
│   ├── summary.{lang}.txt           # 摘要
│   └── metadata.json                # 元数据
├── with_subtitle.txt                # 有字幕的视频链接（追加模式，带分隔符）
├── without_subtitle.txt             # 无字幕的视频链接（追加模式，带分隔符）
├── failed_urls.txt                  # 失败视频列表
└── failed_detail.log                # 失败详情日志
```

## 支持的 AI 供应商

- **OpenAI**：支持 GPT-4、GPT-4o、GPT-3.5 等模型
- **Anthropic**：支持 Claude 3.5 Sonnet、Claude 3 Opus 等模型

> 注意：更多供应商（如 Gemini、Groq）正在规划中。

## 开发状态

### ✅ 已完成（P0 MVP）

- [x] 项目骨架和基础架构
- [x] 配置管理系统
- [x] 日志系统
- [x] CLI 入口和命令结构
- [x] 视频解析（频道/播放列表/URL 列表）
- [x] 增量管理
- [x] 字幕检测
- [x] Dry Run 模式
- [x] 字幕下载
- [x] AI 翻译模块
- [x] AI 摘要模块
- [x] 输出模块
- [x] 失败记录
- [x] 并发执行
- [x] 代理支持
- [x] Cookie 支持
- [x] CLI 完整流水线
- [x] GUI 骨架
- [x] GUI 核心功能接入
- [x] UI 国际化
- [x] 主题系统
- [x] 配置与 GUI 绑定

### ✅ 已完成（P1 增强功能）

- [x] 双语字幕输出
- [x] URL 列表模式（CLI + GUI）
- [x] 增量高级选项
- [x] 错误分类和重试策略
- [x] 详细进度展示
- [x] 高级日志视图

### 🔄 进行中

- 功能优化和 Bug 修复
- 代码模块化重构

## 文档

详细设计文档位于 `docs/` 目录：

- `project_blueprint.md` - 项目蓝图
- `v2_final_plan.md` - 行为规范（**最高优先级**）
- `ide_任务表.md` - 开发任务清单
- `ui_plan.md` - UI 布局规划
- `acceptance_criteria.md` - 验收标准
- `ide_integration.md` - IDE 行为约束
- `测试执行文档.md` - 测试执行指南

## 技术栈

- **Python 3.8+**
- **yt-dlp** - YouTube 视频信息获取
- **CustomTkinter** - 现代化 GUI 框架
- **OpenAI / Anthropic** - AI 翻译和摘要

## 许可证

（待补充）

## 贡献

（待补充）

## 更新日志

### v2.0.0（开发中）

- ✅ 完成 P0 MVP 所有功能
- ✅ 完成 P1 增强功能（除配置导入/导出）
- ✅ AI 翻译和摘要功能拆分，支持独立配置
- ✅ UI 页面重组，优化用户体验
- ✅ 添加代理和 Cookie 测试功能
- ✅ 优化窗口大小和布局
- ✅ 完善错误处理和日志系统
