# 无字幕视频处理方案指南

> 本文档详细说明在视频没有任何字幕时，如何通过音频转文字（ASR）技术提取内容。

## 目录

1. [方案概述](#方案概述)
2. [方案 A：本地运行 faster-whisper](#方案-a本地运行-faster-whisper)
3. [方案 B：Whisper API](#方案-bwhisper-api)
4. [方案 C：Deepgram API](#方案-cdeeepgram-api)
5. [场景决策树](#场景决策树)
6. [常见问题与解决方案](#常见问题与解决方案)

---

## 方案概述

### 三种方案对比

| 方案 | 费用 | 需要 GPU | 质量 | 速度 | 适合场景 |
|------|------|----------|------|------|----------|
| **本地 faster-whisper** | 免费 | ✅ 需要 | ⭐⭐⭐⭐⭐ | 取决于 GPU | 有 GPU、批量处理 |
| **Whisper API** | $0.006/分钟 | ❌ | ⭐⭐⭐⭐⭐ | 快 | 质量优先、无 GPU |
| **Deepgram API** | $0.0043/分钟 | ❌ | ⭐⭐⭐⭐ | 很快 | 成本优先、大量视频 |

### 费用预估

| 视频量 | 本地 | Whisper API | Deepgram |
|--------|------|-------------|----------|
| 1 小时 | $0 | $0.36 | $0.26 |
| 10 小时 | $0 | $3.6 | $2.6 |
| 100 小时 | $0 | $36 | $26 |
| 300 视频 × 10 分钟 | $0 | ~$18 | ~$13 |

---

## 方案 A：本地运行 faster-whisper

### 什么是 faster-whisper？

- **类型**：开源项目（完全免费）
- **原理**：使用 CTranslate2 重新实现 Whisper，速度提升 2-4 倍
- **地址**：https://github.com/SYSTRAN/faster-whisper

### 模型选择指南

| 模型 | 参数量 | 显存需求 | 质量 | 1 小时视频耗时 |
|------|--------|----------|------|----------------|
| tiny | 39M | ~1GB | ⭐⭐ | ~2 分钟 |
| base | 74M | ~1GB | ⭐⭐⭐ | ~3 分钟 |
| small | 244M | ~2GB | ⭐⭐⭐⭐ | ~4 分钟 |
| medium | 769M | ~5GB | ⭐⭐⭐⭐⭐ | ~6 分钟 |
| large-v3 | 1550M | ~10GB | ⭐⭐⭐⭐⭐ | ~12 分钟 |

### 根据显卡配置选择模型

| 显存 | 推荐模型 | 质量 | 备注 |
|------|----------|------|------|
| ≥10GB | large-v3 | ⭐⭐⭐⭐⭐ | RTX 3080/4080/4090 |
| 6-8GB | **medium** | ⭐⭐⭐⭐⭐ | RTX 3060 Ti/3070/4060 **推荐** |
| 4-6GB | small | ⭐⭐⭐⭐ | RTX 3050/GTX 1660 |
| 2-4GB | base | ⭐⭐⭐ | GTX 1050/1650 |
| <2GB / 无 GPU | tiny (CPU) | ⭐⭐ | 速度慢，建议用 API |

### 安装方法

```bash
# 安装 faster-whisper
pip install faster-whisper

# 或使用 CUDA 加速版（推荐）
pip install faster-whisper[cuda]
```

### 使用示例

```python
from faster_whisper import WhisperModel

# 加载模型（根据显存自动选择）
model = WhisperModel("medium", device="cuda")

# 转录音频
segments, info = model.transcribe("audio.mp3")

# 输出结果
for segment in segments:
    print(f"[{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")
```

### 自动选择模型逻辑

```python
import torch

def auto_select_model():
    """根据显存自动选择最佳模型"""
    if not torch.cuda.is_available():
        return "tiny"  # 无 GPU 用最小模型
    
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    
    if vram_gb >= 10:
        return "large-v3"
    elif vram_gb >= 6:
        return "medium"
    elif vram_gb >= 4:
        return "small"
    elif vram_gb >= 2:
        return "base"
    else:
        return "tiny"
```

### 优缺点

| 优点 | 缺点 |
|------|------|
| ✅ 完全免费 | ❌ 需要 GPU |
| ✅ 隐私安全（本地处理） | ❌ 首次下载模型较慢 |
| ✅ 无网络依赖 | ❌ 低配电脑速度慢 |
| ✅ 质量最好 | ❌ 需要安装依赖 |

---

## 方案 B：Whisper API

### 基本信息

| 项目 | 说明 |
|------|------|
| 提供商 | OpenAI |
| 价格 | $0.006/分钟 |
| 最低消费 | 无 |
| 免费额度 | 无 |
| 质量 | ⭐⭐⭐⭐⭐（最好） |

### 使用方法

```python
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

with open("audio.mp3", "rb") as audio_file:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="srt"  # 直接输出 SRT 格式
    )

print(result)
```

### 文件限制

| 限制 | 值 |
|------|------|
| 单文件最大 | 25MB |
| 支持格式 | mp3, mp4, wav, webm, m4a, 等 |
| 最长时长 | 无限制（按时长计费） |

### 超过 25MB 的处理方法

```python
# 使用 pydub 分割音频
from pydub import AudioSegment

audio = AudioSegment.from_file("long_audio.mp3")
chunk_length_ms = 10 * 60 * 1000  # 10 分钟

for i, chunk in enumerate(audio[::chunk_length_ms]):
    chunk.export(f"chunk_{i}.mp3", format="mp3")
```

### 优缺点

| 优点 | 缺点 |
|------|------|
| ✅ 质量最好 | ❌ 需要付费 |
| ✅ 无需 GPU | ❌ 需要网络 |
| ✅ 简单易用 | ❌ 有文件大小限制 |
| ✅ 速度快 | ❌ 隐私问题（上传音频） |

---

## 方案 C：Deepgram API

### 基本信息

| 项目 | 说明 |
|------|------|
| 提供商 | Deepgram |
| 价格 | $0.0043/分钟 (Nova-2) |
| 最低消费 | 无 |
| 免费额度 | ✅ **$200（新用户）** |
| 质量 | ⭐⭐⭐⭐ |

### 免费额度说明

- 新注册用户获得 **$200 免费额度**
- 相当于 **~46,000 分钟**（约 770 小时）
- 用完后按量计费

### 使用方法

```python
from deepgram import Deepgram
import asyncio

async def transcribe():
    dg = Deepgram("your-api-key")
    
    with open("audio.mp3", "rb") as audio:
        source = {"buffer": audio, "mimetype": "audio/mp3"}
        options = {"model": "nova-2", "language": "en"}
        
        result = await dg.transcription.prerecorded(source, options)
        return result["results"]["channels"][0]["alternatives"][0]["transcript"]

transcript = asyncio.run(transcribe())
```

### 优缺点

| 优点 | 缺点 |
|------|------|
| ✅ 最便宜 | ❌ 质量略低于 Whisper |
| ✅ $200 免费额度 | ❌ 需要网络 |
| ✅ 无需 GPU | ❌ 隐私问题 |
| ✅ 速度非常快 | |

---

## 场景决策树

### 决策流程图

```
开始
 │
 ├─ 有 NVIDIA GPU？
 │   │
 │   ├─ 是 → 显存 ≥ 6GB？
 │   │       │
 │   │       ├─ 是 → 使用本地 faster-whisper (medium)
 │   │       │
 │   │       └─ 否 → 使用本地 faster-whisper (small/base)
 │   │
 │   └─ 否 → 质量优先 or 成本优先？
 │           │
 │           ├─ 质量优先 → Whisper API
 │           │
 │           └─ 成本优先 → Deepgram API
 │
 └─ 视频量大 (>100 小时)？
     │
     ├─ 是 → 有 GPU？
     │       │
     │       ├─ 是 → 本地 faster-whisper
     │       │
     │       └─ 否 → Deepgram API（$200 免费额度）
     │
     └─ 否 → 任选（推荐 Whisper API）
```

### 快速决策表

| 用户情况 | 推荐方案 | 理由 |
|----------|----------|------|
| 有 GPU (≥6GB) | 本地 faster-whisper | 免费、质量好 |
| 有 GPU (<6GB) | 本地 + small 模型 | 免费、速度还行 |
| 无 GPU，质量优先 | Whisper API | 质量最好 |
| 无 GPU，成本优先 | Deepgram | 最便宜，有免费额度 |
| 大量视频，有 GPU | 本地 faster-whisper | 批量处理成本为 0 |
| 大量视频，无 GPU | Deepgram | $200 免费 → ~770 小时 |
| 偶尔使用 | Whisper API | 简单，无需配置 |

---

## 常见问题与解决方案

### 问题 1：没有 GPU 怎么办？

| 方案 | 说明 |
|------|------|
| ✅ 使用 API | Whisper API 或 Deepgram |
| ⚠️ CPU 模式 | faster-whisper 可用 CPU，但很慢 |
| ⚠️ 云 GPU | 租用云服务器（Google Colab 免费） |

### 问题 2：GPU 显存不够怎么办？

| 解决方案 | 说明 |
|----------|------|
| 换小模型 | medium → small → base |
| 使用 API | 无显存限制 |
| 分块处理 | 长音频分成短段 |

### 问题 3：音频文件太大怎么办？

| 场景 | 解决方案 |
|------|----------|
| Whisper API 限制 25MB | 使用 pydub 分割成小段 |
| 本地内存不够 | 使用 VAD 自动分段 |

```python
# faster-whisper 自带 VAD（语音活动检测）
segments, _ = model.transcribe("audio.mp3", vad_filter=True)
```

### 问题 4：转录质量不好怎么办？

| 原因 | 解决方案 |
|------|----------|
| 模型太小 | 换更大的模型 |
| 音频噪音大 | 先做降噪处理 |
| 语言识别错误 | 手动指定语言 |

```python
# 指定语言
segments, _ = model.transcribe("audio.mp3", language="zh")
```

### 问题 5：多语言混合音频怎么办？

| 方案 | 说明 |
|------|------|
| 自动检测 | Whisper 自动检测语言（默认） |
| 分段处理 | 不同语言段落分别指定 |

### 问题 6：费用超出预算怎么办？

| 方案 | 说明 |
|------|------|
| 用 Deepgram | 比 Whisper API 便宜 28% |
| 用免费额度 | Deepgram 新用户 $200 |
| 切换本地 | 有 GPU 就免费 |

### 问题 7：没有网络怎么办？

| 方案 | 说明 |
|------|------|
| 本地 faster-whisper | 下载模型后离线可用 |
| 预下载模型 | 提前下载好模型文件 |

```python
# 模型会缓存到本地，离线可用
model = WhisperModel("medium")  # 首次需要网络下载
```

---

## 配置建议

### 推荐配置

```json
{
  "asr": {
    "provider": "auto",          // auto | local | whisper_api | deepgram
    "local": {
      "model": "auto",           // auto | tiny | base | small | medium | large
      "device": "auto",          // auto | cuda | cpu
      "vad_filter": true         // 启用语音活动检测
    },
    "whisper_api": {
      "api_key": "",
      "response_format": "srt"
    },
    "deepgram": {
      "api_key": "",
      "model": "nova-2"
    }
  }
}
```

### UI 配置选项

```
ASR 设置
├── 提供商: [自动选择 ▼]
│   ├── 自动选择（推荐）
│   ├── 本地运行
│   ├── Whisper API
│   └── Deepgram API
│
├── 本地模型: [自动 ▼]
│   ├── 自动（根据显存）
│   ├── tiny（最快）
│   ├── base
│   ├── small
│   ├── medium（推荐）
│   └── large（最好）
│
└── 偏好: [质量优先 ▼]
    ├── 质量优先
    ├── 速度优先
    └── 成本优先
```

---

## 总结

| 场景 | 推荐 | 费用 |
|------|------|------|
| 有 6GB+ GPU | 本地 faster-whisper (medium) | 免费 |
| 有 4-6GB GPU | 本地 faster-whisper (small) | 免费 |
| 无 GPU，质量优先 | Whisper API | $0.006/分钟 |
| 无 GPU，成本优先 | Deepgram | $0.0043/分钟 |
| 新用户，大量视频 | Deepgram（$200 免费） | 免费 |
