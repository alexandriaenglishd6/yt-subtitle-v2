# AI Profile 使用指南

## 概述

AI Profile 系统允许你通过配置文件定义多个 AI 配置组合，然后根据任务类型（翻译、摘要）选择不同的配置。这样可以在不改代码的前提下灵活调整模型策略。

## 快速开始

### 1. 创建配置文件

将 `config/ai_profiles.json.example` 复制到用户数据目录，并重命名为 `ai_profiles.json`：

**Windows:**
```powershell
Copy-Item config\ai_profiles.json.example "$env:APPDATA\yt-subtitle-v2\ai_profiles.json"
```

**Linux/macOS:**
```bash
cp config/ai_profiles.json.example ~/.config/yt-subtitle-v2/ai_profiles.json
```

### 2. 编辑配置

打开 `ai_profiles.json`，根据需要修改：

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "api_keys": {
        "openai": "env:OPENAI_API_KEY"
      },
      "enabled": true
    },
    "subtitle_summarize_default": {
      "provider": "openai",
      "model": "gpt-4o",
      "api_keys": {
        "openai": "env:OPENAI_API_KEY"
      },
      "enabled": true
    }
  },
  "task_mapping": {
    "subtitle_translate": "subtitle_translate_default",
    "subtitle_summarize": "subtitle_summarize_default"
  }
}
```

### 3. 使用

配置文件会自动加载，无需重启应用。下次运行翻译或摘要任务时，系统会使用 Profile 中配置的模型。

## 配置说明

### Profile 配置项

每个 Profile 包含以下字段：

- `provider`: AI 提供商（`openai`, `gemini`, `anthropic`, `google_translate` 等）
- `model`: 模型名称（如 `gpt-4o-mini`, `gpt-4o`, `gemini-2.5-flash` 等）
- `base_url`: API 基础 URL（可选，用于本地模型或自定义网关）
- `timeout_seconds`: 超时时间（秒）
- `max_retries`: 最大重试次数
- `max_concurrency`: 最大并发数
- `api_keys`: API Key 配置（格式：`{"provider": "env:ENV_VAR_NAME"}` 或 `{"provider": "实际key"}`）
- `enabled`: 是否启用此 Profile

### 任务映射

`task_mapping` 定义了任务类型到 Profile 的映射：

- `subtitle_translate`: 字幕翻译任务
- `subtitle_summarize`: 字幕摘要任务

## 使用场景

### 场景 1: 快速翻译 + 高质量摘要

```json
{
  "task_mapping": {
    "subtitle_translate": "subtitle_translate_fast",
    "subtitle_summarize": "subtitle_summarize_quality"
  }
}
```

### 场景 2: 使用不同供应商

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "provider": "google_translate",
      "model": "google_translate_free"
    },
    "subtitle_summarize_default": {
      "provider": "openai",
      "model": "gpt-4o-mini"
    }
  }
}
```

### 场景 3: 本地模型 + 云端模型

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "provider": "openai",
      "model": "qwen2.5:7b",
      "base_url": "http://localhost:11434/v1"
    },
    "subtitle_summarize_default": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "base_url": null
    }
  }
}
```

### 场景 4: 临时禁用某个 Profile

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "enabled": false
    }
  }
}
```

禁用后，系统会回退到 `config.json` 中的 `translation_ai` 配置。

## 向后兼容

- 如果 `ai_profiles.json` 不存在，系统会使用 `config.json` 中的 `translation_ai` 和 `summary_ai` 配置
- 如果 Profile 未配置或禁用，也会回退到 `config.json` 中的配置
- 现有的配置方式仍然有效

## 调试

### 查看当前使用的 Profile

在日志中会显示当前使用的 Profile 名称：

```
[INFO] 翻译 AI 客户端已创建: openai/gpt-4o-mini (Profile: subtitle_translate_default)
[INFO] 摘要 AI 客户端已创建: openai/gpt-4o (Profile: subtitle_summarize_quality)
```

### 验证配置

可以通过 Python 脚本验证配置：

```python
from core.ai_profile_manager import get_profile_manager

manager = get_profile_manager()
manager.load()

# 列出所有 Profiles
profiles = manager.list_profiles()
for name, profile in profiles.items():
    print(f"{name}: {profile.ai_config.provider}/{profile.ai_config.model}")

# 查看任务映射
mappings = manager.list_task_mappings()
print(f"任务映射: {mappings}")
```

## 常见问题

### Q: 配置文件在哪里？

配置文件位于用户数据目录：
- Windows: `%APPDATA%\yt-subtitle-v2\ai_profiles.json`
- Linux: `~/.config/yt-subtitle-v2/ai_profiles.json`
- macOS: `~/Library/Application Support/yt-subtitle-v2/ai_profiles.json`

### Q: 如何知道当前使用的是哪个 Profile？

查看日志输出，会显示 Profile 名称。

### Q: 配置文件格式错误怎么办？

系统会记录错误日志，并回退到 `config.json` 中的配置。检查日志文件查看具体错误。

### Q: 可以同时使用多个 Profile 吗？

每个任务类型只能映射到一个 Profile，但可以为不同任务类型配置不同的 Profile。

### Q: 如何临时禁用 Profile？

将 Profile 的 `enabled` 字段设置为 `false`。

