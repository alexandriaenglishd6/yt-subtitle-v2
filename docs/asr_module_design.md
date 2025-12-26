# ASR 独立模块设计方案

> 纯 API 版本，包含 API 费用统计功能

## 模块概述

| 项目 | 说明 |
|------|------|
| 名称 | Audio Transcriber |
| 类型 | 独立命令行工具 |
| 功能 | 音频/视频 → 字幕文件 |
| 后续 | 可选翻译、摘要 |

---

## 目录结构

```
tools/audio_transcriber/
├── __init__.py
├── main.py                 # CLI 入口
├── config.py               # 配置管理
├── cost_tracker.py         # 费用统计
│
├── providers/              # ASR 供应商
│   ├── __init__.py
│   ├── base.py             # 基类
│   ├── whisper_api.py      # OpenAI Whisper
│   └── deepgram.py         # Deepgram
│
├── processors/             # 后处理（可选）
│   ├── __init__.py
│   ├── translator.py       # 翻译
│   └── summarizer.py       # 摘要
│
└── utils/
    ├── __init__.py
    ├── audio_extractor.py  # 音频提取
    └── rate_limiter.py     # API 限速器
```

---

## 核心组件设计

### 1️⃣ ASR 供应商基类

```python
# providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class TranscribeResult:
    text: str
    segments: list  # 带时间戳的分段
    language: str
    duration_minutes: float

class ASRProvider(ABC):
    """ASR 供应商基类"""
    
    name: str = "base"
    price_per_minute: float = 0.0
    
    @abstractmethod
    def transcribe(self, audio_path: str, language: str = None) -> TranscribeResult:
        pass
    
    def get_cost(self, duration_minutes: float) -> float:
        return duration_minutes * self.price_per_minute
```

### 2️⃣ Whisper API 实现

```python
# providers/whisper_api.py
from openai import OpenAI
from .base import ASRProvider, TranscribeResult

class WhisperAPIProvider(ASRProvider):
    name = "whisper_api"
    price_per_minute = 0.006  # $0.006/分钟
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def transcribe(self, audio_path: str, language: str = None) -> TranscribeResult:
        with open(audio_path, "rb") as f:
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                language=language
            )
        
        return TranscribeResult(
            text=response.text,
            segments=response.segments,
            language=response.language,
            duration_minutes=response.duration / 60
        )
```

### 3️⃣ Deepgram 实现

```python
# providers/deepgram.py
from deepgram import Deepgram
from .base import ASRProvider, TranscribeResult

class DeepgramProvider(ASRProvider):
    name = "deepgram"
    price_per_minute = 0.0043  # $0.0043/分钟 (Nova-2)
    
    def __init__(self, api_key: str):
        self.client = Deepgram(api_key)
    
    async def transcribe(self, audio_path: str, language: str = None) -> TranscribeResult:
        with open(audio_path, "rb") as f:
            source = {"buffer": f.read(), "mimetype": "audio/mp3"}
            options = {"model": "nova-2", "language": language or "en"}
            
            response = await self.client.transcription.prerecorded(source, options)
        
        result = response["results"]["channels"][0]["alternatives"][0]
        return TranscribeResult(
            text=result["transcript"],
            segments=result.get("words", []),
            language=language or "en",
            duration_minutes=response["metadata"]["duration"] / 60
        )
```

---

### 4️⃣ 费用统计器

> **价格支持用户自定义**：默认内置价格，用户可通过配置文件覆盖

```python
# cost_tracker.py
from dataclasses import dataclass, field
from typing import Dict, Optional
import json
from pathlib import Path

@dataclass
class CostTracker:
    """API 费用追踪（支持自定义价格）"""
    
    costs: Dict[str, float] = field(default_factory=lambda: {
        'asr': 0.0,
        'translation': 0.0,
        'summary': 0.0
    })
    usage: Dict[str, float] = field(default_factory=lambda: {
        'asr_minutes': 0.0,
        'translation_chars': 0,
        'summary_tokens': 0
    })
    
    # 默认价格（内置，用户可覆盖）
    DEFAULT_PRICES = {
        'asr': {
            'whisper_api': 0.006,      # $/分钟
            'deepgram': 0.0043,        # $/分钟
            'local_whisper': 0.0,      # 本地免费
        },
        'translation': {
            'deepl': 0.00002,          # $/字符
            'baidu': 0.00005,          # $/字符
            'google_free': 0.0,        # 免费
        },
        'summary': {
            'deepseek': 0.0005,        # $/千token
            'kimi': 0.012,             # $/千token
            'gpt4o_mini': 0.15,        # $/千token
        }
    }
    
    # 用户自定义价格
    custom_prices: Dict = field(default_factory=dict)
    
    def set_custom_prices(self, pricing_config: dict):
        """设置用户自定义价格"""
        self.custom_prices = pricing_config
    
    def get_price(self, category: str, provider: str) -> float:
        """获取价格，优先用户配置，其次默认"""
        # 先查用户配置
        if category in self.custom_prices:
            if provider in self.custom_prices[category]:
                return self.custom_prices[category][provider]
        
        # 再查默认
        return self.DEFAULT_PRICES.get(category, {}).get(provider, 0)
    
    def add_asr(self, provider: str, minutes: float):
        price = self.get_price('asr', provider)
        cost = minutes * price
        self.usage['asr_minutes'] += minutes
        self.costs['asr'] += cost
        return cost
    
    def add_translation(self, provider: str, chars: int):
        price = self.get_price('translation', provider)
        cost = chars * price
        self.usage['translation_chars'] += chars
        self.costs['translation'] += cost
        return cost
    
    def add_summary(self, provider: str, tokens: int):
        price = self.get_price('summary', provider) / 1000  # 转换为每 token
        cost = tokens * price
        self.usage['summary_tokens'] += tokens
        self.costs['summary'] += cost
        return cost
    
    @property
    def total(self) -> float:
        return sum(self.costs.values())
    
    def get_report(self) -> str:
        return f"""
╔══════════════════════════════════════════╗
║            API 费用统计报告              ║
╠══════════════════════════════════════════╣
║  ASR 转文字                              ║
║    用量: {self.usage['asr_minutes']:.1f} 分钟
║    费用: ${self.costs['asr']:.4f}
╠══════════════════════════════════════════╣
║  翻译                                    ║
║    用量: {self.usage['translation_chars']:,} 字符
║    费用: ${self.costs['translation']:.4f}
╠══════════════════════════════════════════╣
║  摘要                                    ║
║    用量: {self.usage['summary_tokens']:,} tokens
║    费用: ${self.costs['summary']:.4f}
╠══════════════════════════════════════════╣
║  总计: ${self.total:.4f}
╚══════════════════════════════════════════╝
"""
    
    def save(self, path: Path):
        data = {
            'costs': self.costs,
            'usage': self.usage,
            'total': self.total,
            'custom_prices': self.custom_prices
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: Path, pricing_config: dict = None) -> 'CostTracker':
        tracker = cls()
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            tracker.costs = data.get('costs', tracker.costs)
            tracker.usage = data.get('usage', tracker.usage)
        
        # 加载用户自定义价格
        if pricing_config:
            tracker.set_custom_prices(pricing_config)
        
        return tracker
```

### 价格配置文件

> 用户可在配置文件中自定义价格，覆盖默认值

```json
{
  "pricing": {
    "asr": {
      "whisper_api": 0.006,
      "deepgram": 0.0043,
      "local_whisper": 0
    },
    "translation": {
      "deepl": 0.00002,
      "baidu": 0.00005,
      "google_free": 0
    },
    "summary": {
      "deepseek": 0.5,
      "kimi": 12,
      "gpt4o_mini": 0.15
    }
  }
}
```

### 使用示例

```python
# 加载配置文件中的自定义价格
with open('config.json') as f:
    config = json.load(f)

cost_tracker = CostTracker.load(
    Path('./cost_history.json'),
    pricing_config=config.get('pricing')
)

# 添加费用记录
cost_tracker.add_asr('whisper_api', 10.5)  # 10.5 分钟
cost_tracker.add_translation('deepl', 5000)  # 5000 字符
cost_tracker.add_summary('deepseek', 10000)  # 10000 tokens

# 输出报告
print(cost_tracker.get_report())
```

---

### 5️⃣ API 限速器

```python
# utils/rate_limiter.py
import time
import threading

class RateLimiter:
    """API 限速器"""
    
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.interval = 60.0 / rpm
        self.lock = threading.Lock()
        self.last_call = 0
    
    def wait(self):
        with self.lock:
            now = time.time()
            wait_time = self.interval - (now - self.last_call)
            if wait_time > 0:
                time.sleep(wait_time)
            self.last_call = time.time()

# 预设限速器
RATE_LIMITERS = {
    'whisper_api': RateLimiter(rpm=50),
    'deepgram': RateLimiter(rpm=100),  # 无官方限制，设置合理值
    'deepl': RateLimiter(rpm=100),
    'deepseek': RateLimiter(rpm=60),
}
```

---

### 6️⃣ 主程序

```python
# main.py
import argparse
from pathlib import Path
from providers.whisper_api import WhisperAPIProvider
from providers.deepgram import DeepgramProvider
from cost_tracker import CostTracker
from utils.audio_extractor import extract_audio

def main():
    parser = argparse.ArgumentParser(description="Audio Transcriber - 音频转文字工具")
    parser.add_argument("input", help="输入文件或目录")
    parser.add_argument("-o", "--output", default="./output", help="输出目录")
    parser.add_argument("-p", "--provider", default="whisper_api", 
                        choices=["whisper_api", "deepgram"])
    parser.add_argument("-l", "--language", help="语言代码 (如 en, zh)")
    parser.add_argument("--translate", action="store_true", help="翻译字幕")
    parser.add_argument("--summarize", action="store_true", help="生成摘要")
    parser.add_argument("--show-cost", action="store_true", help="显示费用统计")
    
    args = parser.parse_args()
    
    # 初始化费用追踪器
    cost_tracker = CostTracker.load(Path(args.output) / "cost_history.json")
    
    # 选择 ASR 供应商
    if args.provider == "whisper_api":
        provider = WhisperAPIProvider(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        provider = DeepgramProvider(api_key=os.getenv("DEEPGRAM_API_KEY"))
    
    # 处理文件
    input_path = Path(args.input)
    files = list(input_path.glob("*.mp4")) if input_path.is_dir() else [input_path]
    
    for file in files:
        print(f"处理: {file.name}")
        
        # 提取音频
        audio_path = extract_audio(file)
        
        # ASR 转文字
        result = provider.transcribe(audio_path, args.language)
        cost = cost_tracker.add_asr(args.provider, result.duration_minutes)
        print(f"  ASR 完成: {result.duration_minutes:.1f} 分钟, 费用: ${cost:.4f}")
        
        # 保存字幕
        output_path = Path(args.output) / f"{file.stem}.srt"
        save_as_srt(result.segments, output_path)
        
        # 可选：翻译
        if args.translate:
            # ... 翻译逻辑
            pass
        
        # 可选：摘要
        if args.summarize:
            # ... 摘要逻辑
            pass
    
    # 显示费用统计
    if args.show_cost:
        print(cost_tracker.get_report())
    
    # 保存费用历史
    cost_tracker.save(Path(args.output) / "cost_history.json")

if __name__ == "__main__":
    main()
```

---

## 使用示例

```bash
# 基本使用
python -m tools.audio_transcriber video.mp4

# 指定 Deepgram（更便宜）
python -m tools.audio_transcriber video.mp4 -p deepgram

# 批量处理 + 翻译 + 摘要
python -m tools.audio_transcriber ./videos/ --translate --summarize

# 显示费用统计
python -m tools.audio_transcriber --show-cost
```

---

## 配置文件

```json
{
  "asr": {
    "provider": "whisper_api",
    "language": "auto"
  },
  "translation": {
    "enabled": false,
    "provider": "deepl",
    "target_language": "zh"
  },
  "summary": {
    "enabled": false,
    "provider": "deepseek"
  },
  "api_keys": {
    "openai": "${OPENAI_API_KEY}",
    "deepgram": "${DEEPGRAM_API_KEY}",
    "deepl": "${DEEPL_API_KEY}",
    "deepseek": "${DEEPSEEK_API_KEY}"
  }
}
```

---

## 费用统计输出示例

```
╔══════════════════════════════════════════╗
║            API 费用统计报告              ║
╠══════════════════════════════════════════╣
║  ASR 转文字                              ║
║    用量: 120.5 分钟                      ║
║    费用: $0.7230                         ║
╠══════════════════════════════════════════╣
║  翻译                                    ║
║    用量: 48,000 字符                     ║
║    费用: $0.9600                         ║
╠══════════════════════════════════════════╣
║  摘要                                    ║
║    用量: 96,000 tokens                   ║
║    费用: $0.0480                         ║
╠══════════════════════════════════════════╣
║  总计: $1.7310                           ║
╚══════════════════════════════════════════╝
```

---

## 开发计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | ASR 核心 + 费用统计 | 2 天 |
| Phase 2 | 翻译 + 摘要集成 | 1 天 |
| Phase 3 | 批量处理 + 并发 | 1 天 |
| **总计** | | **4 天** |

---

## 依赖

```
openai>=1.0.0
deepgram-sdk>=2.0.0
pydub>=0.25.1
yt-dlp>=2024.1.0
```

---

## 代理 IP 和 Cookie 支持

> 下载 YouTube 音频时需要代理和 Cookie 支持，复用主程序模块

### 目录结构更新

```
tools/audio_transcriber/
├── __init__.py
├── main.py
├── config.py
├── cost_tracker.py
│
├── providers/              # ASR 供应商
│   └── ...
│
├── extractors/             # 新增：音频提取
│   ├── __init__.py
│   └── youtube.py          # 支持代理+Cookie
│
├── processors/             # 后处理
│   └── ...
│
└── utils/
    ├── rate_limiter.py
    └── concurrent.py       # 新增：并发处理
```

### YouTube 音频提取器

```python
# extractors/youtube.py
import yt_dlp
from pathlib import Path
from typing import Optional

class YouTubeAudioExtractor:
    """YouTube 音频提取器，支持代理和 Cookie"""
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        cookie_file: Optional[str] = None,
        output_dir: str = "./temp"
    ):
        self.proxy = proxy
        self.cookie_file = cookie_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def extract(self, url: str) -> Path:
        """下载 YouTube 视频的音频"""
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.output_dir / '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
        
        # 添加代理
        if self.proxy:
            ydl_opts['proxy'] = self.proxy
        
        # 添加 Cookie
        if self.cookie_file:
            ydl_opts['cookiefile'] = self.cookie_file
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info['id']
            audio_path = self.output_dir / f"{video_id}.mp3"
            return audio_path
    
    def cleanup(self, audio_path: Path):
        """清理临时音频文件"""
        if audio_path.exists():
            audio_path.unlink()
```

---

## 并发处理

### 并发管理器

```python
# utils/concurrent.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable
from dataclasses import dataclass

@dataclass
class TaskResult:
    video_url: str
    success: bool
    result: any
    error: str = None

class ConcurrentProcessor:
    """并发处理器"""
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.pool = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_batch(
        self,
        items: List[str],
        process_func: Callable,
        rate_limiter = None
    ) -> List[TaskResult]:
        """批量并发处理"""
        
        results = []
        futures = {}
        
        for item in items:
            if rate_limiter:
                rate_limiter.wait()
            
            future = self.pool.submit(process_func, item)
            futures[future] = item
        
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
                results.append(TaskResult(
                    video_url=item,
                    success=True,
                    result=result
                ))
            except Exception as e:
                results.append(TaskResult(
                    video_url=item,
                    success=False,
                    result=None,
                    error=str(e)
                ))
        
        return results
    
    def shutdown(self):
        self.pool.shutdown(wait=True)
```

### 主程序更新（支持并发）

```python
# main.py（更新版）
import argparse
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from extractors.youtube import YouTubeAudioExtractor
from providers.whisper_api import WhisperAPIProvider
from providers.deepgram import DeepgramProvider
from cost_tracker import CostTracker
from utils.rate_limiter import RATE_LIMITERS
from utils.concurrent import ConcurrentProcessor

def main():
    parser = argparse.ArgumentParser(description="Audio Transcriber - 音频转文字工具")
    parser.add_argument("input", nargs='?', help="YouTube URL 或包含 URL 的文件")
    parser.add_argument("-o", "--output", default="./output", help="输出目录")
    parser.add_argument("-p", "--provider", default="whisper_api",
                        choices=["whisper_api", "deepgram"])
    parser.add_argument("-l", "--language", help="语言代码 (如 en, zh)")
    parser.add_argument("-c", "--concurrency", type=int, default=5, help="并发数")
    parser.add_argument("--proxy", help="代理地址 (如 http://127.0.0.1:7890)")
    parser.add_argument("--cookie", help="Cookie 文件路径")
    parser.add_argument("--translate", action="store_true", help="翻译字幕")
    parser.add_argument("--summarize", action="store_true", help="生成摘要")
    parser.add_argument("--show-cost", action="store_true", help="显示费用统计")
    
    args = parser.parse_args()
    
    # 初始化
    cost_tracker = CostTracker.load(Path(args.output) / "cost_history.json")
    
    extractor = YouTubeAudioExtractor(
        proxy=args.proxy,
        cookie_file=args.cookie,
        output_dir=Path(args.output) / "temp"
    )
    
    if args.provider == "whisper_api":
        asr_provider = WhisperAPIProvider(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        asr_provider = DeepgramProvider(api_key=os.getenv("DEEPGRAM_API_KEY"))
    
    rate_limiter = RATE_LIMITERS[args.provider]
    
    # 处理单个视频的函数
    def process_video(url: str):
        # 1. 下载音频
        audio_path = extractor.extract(url)
        
        # 2. ASR 转文字
        rate_limiter.wait()
        result = asr_provider.transcribe(str(audio_path), args.language)
        cost = cost_tracker.add_asr(args.provider, result.duration_minutes)
        
        # 3. 保存字幕
        output_path = Path(args.output) / f"{audio_path.stem}.srt"
        save_as_srt(result.segments, output_path)
        
        # 4. 清理临时文件
        extractor.cleanup(audio_path)
        
        return {
            'url': url,
            'duration': result.duration_minutes,
            'cost': cost,
            'output': str(output_path)
        }
    
    # 获取 URL 列表
    if args.input:
        if Path(args.input).exists():
            # 从文件读取 URL 列表
            with open(args.input) as f:
                urls = [line.strip() for line in f if line.strip()]
        else:
            # 单个 URL
            urls = [args.input]
    else:
        print("请提供 YouTube URL 或 URL 列表文件")
        return
    
    print(f"共 {len(urls)} 个视频，并发数: {args.concurrency}")
    
    # 并发处理
    processor = ConcurrentProcessor(max_workers=args.concurrency)
    results = processor.process_batch(urls, process_video, rate_limiter)
    processor.shutdown()
    
    # 统计结果
    success = sum(1 for r in results if r.success)
    failed = len(results) - success
    
    print(f"\n处理完成: {success} 成功, {failed} 失败")
    
    # 显示费用统计
    if args.show_cost or True:  # 默认显示
        print(cost_tracker.get_report())
    
    # 保存费用历史
    cost_tracker.save(Path(args.output) / "cost_history.json")

if __name__ == "__main__":
    main()
```

---

## 使用示例（更新）

```bash
# 单个视频
python -m tools.audio_transcriber "https://youtube.com/watch?v=xxx"

# 使用代理
python -m tools.audio_transcriber "https://youtube.com/..." --proxy http://127.0.0.1:7890

# 使用 Cookie
python -m tools.audio_transcriber "https://youtube.com/..." --cookie cookies.txt

# 批量处理 + 并发
python -m tools.audio_transcriber urls.txt -c 10

# 完整参数
python -m tools.audio_transcriber urls.txt \
    -p deepgram \
    -c 5 \
    --proxy http://127.0.0.1:7890 \
    --cookie cookies.txt \
    --translate \
    --summarize
```

---

## 配置文件（更新）

```json
{
  "asr": {
    "provider": "whisper_api",
    "language": "auto"
  },
  "network": {
    "proxy": null,
    "cookie_file": null,
    "concurrency": 5
  },
  "translation": {
    "enabled": false,
    "provider": "deepl",
    "target_language": "zh"
  },
  "summary": {
    "enabled": false,
    "provider": "deepseek"
  },
  "api_keys": {
    "openai": "${OPENAI_API_KEY}",
    "deepgram": "${DEEPGRAM_API_KEY}",
    "deepl": "${DEEPL_API_KEY}",
    "deepseek": "${DEEPSEEK_API_KEY}"
  }
}
```

---

## 开发计划（更新）

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | ASR 核心 + 费用统计 | 2 天 |
| Phase 2 | 代理 + Cookie + 并发 | 1 天 |
| Phase 3 | 翻译 + 摘要集成 | 1 天 |
| **总计** | | **4 天** |

---

## 本地 GPU 扩展预留

> 当前设计已预留本地 GPU 接口，后期扩展无需修改现有代码

```python
# providers/base.py（已预留）
class ASRProvider(ABC):
    name: str
    price_per_minute: float
    is_local: bool = False  # 区分本地/API
    
    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscribeResult:
        pass

# 后期添加本地 GPU 支持
# providers/local_whisper.py
class LocalWhisperProvider(ASRProvider):
    name = "local_whisper"
    price_per_minute = 0.0
    is_local = True
    
    def __init__(self, model_size: str = "medium"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_size, device="cuda")
    
    def transcribe(self, audio_path: str) -> TranscribeResult:
        segments, info = self.model.transcribe(audio_path)
        # ... 格式转换
```

