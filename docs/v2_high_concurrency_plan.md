# v2.0 高并发优化实施计划

## 目录

1. [项目简介](#项目简介)
2. [概述](#概述)
3. [架构设计](#架构设计)
4. [阶段 1：链接识别优化](#阶段-1链接识别优化)
5. [阶段 2：字幕下载优化](#阶段-2字幕下载优化)
6. [阶段 3：字幕清洗与预处理](#阶段-3字幕清洗与预处理) → 📄 [详细文档](./subtitle_processing_plan.md)
7. [阶段 4：翻译优化](#阶段-4翻译优化)
8. [阶段 5：摘要优化](#阶段-5摘要优化)
9. [阶段 6：输出优化](#阶段-6输出优化)
10. [通用架构：多 Key 与多供应商](#通用架构多-key-与多供应商)
11. [状态显示与日志优化](#状态显示与日志优化)
12. [容错与恢复机制](#容错与恢复机制)
13. [独立辅助工具](#独立辅助工具) → 📄 [详细文档](./auxiliary_tools_plan.md)
14. [UI 优化](#ui-优化) → 📄 [详细文档](./ui_optimization_plan.md)
15. [性能优化](#性能优化)
16. [降级模式](#降级模式)
17. [阶段状态记录](#阶段状态记录)
18. [实施路线图](#实施路线图)
19. [详细执行计划](#详细执行计划) → 📄 [详细文档](./v2_execution_plan.md)
20. [注意事项](#注意事项) → 📄 [详细文档](./development_guidelines.md)
21. [运维指南](#运维指南)
22. [版本兼容](#版本兼容)

---

## 项目简介

> 本章节帮助未参与项目的人快速了解项目背景

### 产品定位

**YouTube Tools** 是一个 YouTube 字幕下载、翻译和摘要工具，帮助用户快速提取视频内容。

### v1.0 已实现功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 视频链接处理 | 单视频、频道、播放列表 | ✅ |
| 字幕下载 | 官方字幕、自动字幕 | ✅ |
| 多语言翻译 | 多供应商支持 | ✅ |
| AI 摘要 | 内容提炼 | ✅ |
| 代理支持 | HTTP/SOCKS5 | ✅ |
| Cookie 支持 | 登录态保持 | ✅ |
| 国际化 | 中英双语 UI/日志 | ✅ |
| 主题切换 | 明/暗主题 | ✅ |
| 增量检查 | 跳过已处理视频 | ✅ |

### 技术栈

| 项目 | 技术 | 说明 |
|------|------|------|
| UI 框架 | CustomTkinter | Python 原生 GUI |
| 下载工具 | yt-dlp | YouTube 数据获取 |
| AI 集成 | OpenAI/DeepSeek/Kimi | 翻译+摘要 |
| 翻译 | Google 免费/DeepL | 专属翻译 API |
| 国际化 | 自研 i18n | JSON 语言文件 |
| 打包 | PyInstaller | 可执行文件 |

### 代码规模

| 统计项 | 数量 |
|--------|------|
| Python 文件 | 139 个 |
| 代码行数 | ~12,000-15,000 |

> 详细代码结构见 [docs/v1_code_structure.md](./v1_code_structure.md)

### 相关文档

| 文档 | 说明 |
|------|------|
| [README.md](../README.md) | 项目概述 |
| [PROJECT_CONTEXT.md](./PROJECT_CONTEXT.md) | 项目上下文（恢复开发用） |
| [dev_log.md](./dev_log.md) | 开发日志 |
| [v1_code_structure.md](./v1_code_structure.md) | v1.0 代码结构 |
| [dev_workflow_guide.md](./dev_workflow_guide.md) | 开发工作流指南 |
| [asr_module_design.md](./asr_module_design.md) | ASR 模块设计 |
| [asr_guide.md](./asr_guide.md) | ASR 技术指南 |

---

## 概述

### 设计目标

| 目标 | 说明 |
|------|------|
| **高性能** | 50 线程并发，快速处理任务 |
| **高稳定** | 1000+ 视频，运行数小时不崩溃 |
| **无瓶颈** | 全流程每个阶段都支持高并发 |

### 各阶段耗时

| 阶段 | 单视频耗时 | 瓶颈原因 | 可并行 |
|------|------------|----------|--------|
| 链接识别 | ~1-2s | 网络请求 | ✅ |
| 字幕下载 | ~2-5s | yt-dlp 下载 | ✅ |
| **翻译** | ~30s-2min | **AI API 调用** | ✅ |
| **摘要** | ~20-40s | **AI API 调用** | ⚠️ 部分 |
| 输出 | ~0.5s | 文件 I/O | ✅ |

**结论**：**翻译是最耗时的阶段**，其次是摘要。

### v1.0 vs v2.0 对比

| 功能模块 | v1.0 现状 | v2.0 计划 | 提升 |
|----------|-----------|-----------|------|
| 并发数 | 10 线程 | 50 线程 | ⬆️⬆️⬆️ |
| API Key | 单 Key | 多 Key 轮询 | ⬆️⬆️ |
| 翻译提供商 | 1 个 | 多提供商并行 | ⬆️⬆️⬆️ |
| 字幕预处理 | ❌ 无 | 清洗+智能分段 | ⭐ 新增 |
| 错误恢复 | 基础重试 | 三级容错 | ⬆️⬆️ |
| 状态显示 | 简单 ETA | 聚合日志+智能 ETA | ⬆️ |

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  用户                                                           │
│     ↓ 点击按钮                                                   │
│  UI 层 (前台)           → 负责展示界面、接收用户操作               │
│     ↓ 发送指令                                                    │
│  控制层 (领班)          → 负责协调资源、安排任务优先级              │
│     ↓ 分配任务                                                    │
│  业务层 (厨房)          → 负责具体工作：下载、翻译、摘要            │
│     ↓ 读写数据                                                    │
│  数据层 (仓库)          → 负责存储配置、字幕、结果                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5 个架构原则

| 原则 | 说明 | 示例 |
|------|------|------|
| **单一职责** | 每个模块只做一件事 | ProxyPool 只管代理 |
| **中央调度** | 统一协调各模块 | TaskScheduler 分配任务 |
| **资源池化** | 共享资源统一管理 | 代理池、Key 池、Cookie 池 |
| **错误隔离** | 一个失败不影响全局 | try-except 包装 |
| **状态可观测** | 能看到发生了什么 | 进度追踪、日志汇总 |

### 中央调度器

```python
class TaskScheduler:
    """中央调度器 - 统一协调各资源池"""
    
    def __init__(self):
        # 资源池
        self.proxy_pool = ProxyPool()
        self.cookie_pool = CookieRotator()
        self.key_pool = KeySelector()
        
        # 处理器
        self.translator = Translator()
        self.summarizer = Summarizer()
    
    def process_video(self, url):
        # 1. 获取资源
        proxy = self.proxy_pool.get_healthy_proxy()
        cookie = self.cookie_pool.get_healthy_cookie()
        key = self.key_pool.get_next_key()
        
        # 2. 执行任务
        try:
            subtitle = download(url, proxy=proxy, cookie=cookie)
            result = self.translator.translate(subtitle, api_key=key)
            return result
        except Exception as e:
            # 3. 错误处理（不影响其他任务）
            logger.error(f"失败: {e}")
            return None
```

### 资源池模式

```python
class Pool:
    """通用资源池模式"""
    
    def __init__(self, items: list):
        self.items = {item: {"status": "active", "fails": 0} for item in items}
        self.lock = threading.Lock()  # 防止并发冲突
    
    def get_healthy(self):
        """获取健康的资源"""
        with self.lock:
            active = [k for k, v in self.items.items() if v["status"] == "active"]
            return min(active, key=lambda x: self.items[x]["fails"])
    
    def mark_failed(self, item):
        """标记失败"""
        with self.lock:
            self.items[item]["fails"] += 1
            if self.items[item]["fails"] >= 3:
                self.items[item]["status"] = "disabled"
    
    def mark_success(self, item):
        """标记成功"""
        with self.lock:
            self.items[item]["fails"] = 0
```

### 推荐目录结构

```
yt-subtitle-v2/
├── core/                      # 业务层
│   ├── pools/                 # 资源池
│   │   ├── proxy_pool.py
│   │   ├── cookie_pool.py
│   │   └── key_pool.py
│   │
│   ├── processors/            # 处理器
│   │   ├── downloader.py
│   │   ├── translator.py
│   │   └── summarizer.py
│   │
│   └── scheduler.py           # 中央调度器
│
├── ui/                        # UI 层
├── config/                    # 配置层
└── main.py                    # 入口
```

### 实施建议

| 步骤 | 说明 |
|------|------|
| 1 | 先实现 `ProxyPool`，测试通过 |
| 2 | 再实现 `CookieRotator`，复用 Pool 模式 |
| 3 | 然后实现 `KeySelector` |
| 4 | 在调度器中集成这些池 |
| 5 | 逐步添加错误处理和状态追踪 |

**核心原则**：一次只改一个地方，改完测试通过再改下一个

---

## 阶段 1：链接识别优化

### 当前状态

- ✅ 已支持多线程并行
- ⚠️ 单代理可能被 YouTube 限流

### 改进方案：代理池（带健康度管理）

```python
class ProxyPool:
    """代理池 - 带健康度管理和失败回退"""
    
    def __init__(self, proxies: list[str]):
        self.proxies = {
            p: {"fails": 0, "success": 0, "last_fail": None, "status": "active"}
            for p in proxies
        }
        self.lock = threading.Lock()
    
    def get_healthy_proxy(self) -> Optional[str]:
        """获取健康的代理（优先选择失败次数最少的）"""
        with self.lock:
            active = [p for p, s in self.proxies.items() if s["status"] == "active"]
            if not active:
                self._try_recover()
                active = [p for p, s in self.proxies.items() if s["status"] == "active"]
            if not active:
                return None
            return min(active, key=lambda p: self.proxies[p]["fails"])
    
    def mark_failed(self, proxy: str):
        """标记代理失败（连续 3 次失败则禁用）"""
        with self.lock:
            self.proxies[proxy]["fails"] += 1
            self.proxies[proxy]["last_fail"] = time.time()
            if self.proxies[proxy]["fails"] >= 3:
                self.proxies[proxy]["status"] = "disabled"
    
    def mark_success(self, proxy: str):
        """标记代理成功（重置失败计数）"""
        with self.lock:
            self.proxies[proxy]["success"] += 1
            self.proxies[proxy]["fails"] = 0
    
    def _try_recover(self):
        """自动恢复：禁用超过 5 分钟的代理尝试恢复"""
        now = time.time()
        for proxy, status in self.proxies.items():
            if status["status"] == "disabled":
                if status["last_fail"] and now - status["last_fail"] > 300:
                    status["status"] = "active"
                    status["fails"] = 0
```

### 使用流程

```python
pool = ProxyPool(["proxy1:8080", "proxy2:8080", "proxy3:8080"])

async def fetch_with_proxy(url: str):
    proxy = pool.get_healthy_proxy()
    if not proxy:
        raise Exception("无可用代理")
    try:
        result = await fetch(url, proxy=proxy)
        pool.mark_success(proxy)
        return result
    except Exception:
        pool.mark_failed(proxy)
        return await fetch_with_proxy(url)  # 自动重试下一个代理
```

**效果**：50 个代理 → 50 倍并发 + 自动故障转移

---

## 阶段 2：字幕下载优化

### 当前状态

- ✅ 已支持多线程并行
- ⚠️ 单 Cookie 可能被限流

### Cookie 快速失效原因

| 原因 | 可能性 | 说明 |
|------|--------|------|
| **请求频率过高** | ⭐⭐⭐ 高 | 短时间大量请求触发风控 |
| **IP 与 Cookie 不匹配** | ⭐⭐⭐ 高 | Cookie 登录地区与请求 IP 不一致 |
| **并发请求异常** | ⭐⭐ 中 | 同一 Cookie 同时发起太多请求 |

### 改进方案：Cookie 轮换（带健康度管理）

```python
class CookieRotator:
    """Cookie 轮换器 - 带健康度管理和来源标识"""
    
    def __init__(self, cookie_files: list[Path]):
        self.cookies = {}
        for path in cookie_files:
            account_id = path.stem  # 使用文件名作为账户标识
            self.cookies[account_id] = {
                "path": path,
                "fails": 0, "success": 0,
                "last_fail": None, "cooldown_until": 0,
                "status": "active"  # active, rate_limited, expired
            }
        self.lock = threading.Lock()
        self.max_concurrent = 3      # 单 Cookie 最大并发
        self.min_interval = 1.0      # 请求最小间隔（秒）
        self.cooldown_time = 60      # 使用后冷却时间（秒）
    
    def get_healthy_cookie(self) -> Optional[tuple[str, Path]]:
        """获取健康的 Cookie（返回账户ID和路径）"""
        with self.lock:
            now = time.time()
            active = [(k, v) for k, v in self.cookies.items() 
                      if v["status"] == "active" and v["cooldown_until"] < now]
            if not active:
                self._try_recover()
                active = [(k, v) for k, v in self.cookies.items() 
                          if v["status"] == "active" and v["cooldown_until"] < now]
            if not active:
                return None
            # 选择休息时间最长的
            account_id = max(active, key=lambda x: now - x[1]["cooldown_until"])[0]
            return account_id, self.cookies[account_id]["path"]
    
    def mark_rate_limited(self, account_id: str):
        """标记为限流（30 分钟后自动恢复）"""
        with self.lock:
            self.cookies[account_id]["status"] = "rate_limited"
            self.cookies[account_id]["last_fail"] = time.time()
    
    def mark_expired(self, account_id: str, error_msg: str):
        """标记为过期（需人工重新导出）"""
        with self.lock:
            self.cookies[account_id]["status"] = "expired"
            self.cookies[account_id]["error_msg"] = error_msg
    
    def mark_success(self, account_id: str):
        """标记成功并设置冷却期"""
        with self.lock:
            self.cookies[account_id]["success"] += 1
            self.cookies[account_id]["fails"] = 0
            self.cookies[account_id]["cooldown_until"] = time.time() + self.cooldown_time
    
    def _try_recover(self):
        """尝试恢复限流的 Cookie（30 分钟后）"""
        now = time.time()
        for account_id, status in self.cookies.items():
            if status["status"] == "rate_limited":
                if status["last_fail"] and now - status["last_fail"] > 1800:
                    status["status"] = "active"
                    status["fails"] = 0
```

### 防止 Cookie 快速失效的策略

| 策略 | 推荐值 | 说明 |
|------|--------|------|
| 单 Cookie 并发 | 2-3 | 不要太高 |
| 请求间隔 | 1-2 秒 | 模拟人类行为 |
| 使用后冷却 | 30-60 秒 | 给 Cookie "休息" |
| Cookie 数量 | 10-20 个 | 分担压力 |

### Cookie 文件命名规范

```
cookies/
├── account1.txt          # 账户1
├── account2.txt          # 账户2
├── john_gmail.txt        # John 的账户
└── backup.txt            # 备用账户
```

### 状态类型与 UI 显示

| 状态 | 图标 | 说明 | 处理方式 |
|------|------|------|----------|
| `active` | ✅ | 正常可用 | 继续使用 |
| `rate_limited` | ⚠️ | 暂时限流 | 30 分钟后自动恢复 |
| `expired` | ❌ | 永久失效 | 需人工重新导出 |

---

## 阶段 3：字幕清洗与预处理

> 📄 **详细内容已拆分至**：[subtitle_processing_plan.md](./subtitle_processing_plan.md)

### 概述

| 问题 | 解决方案 |
|------|----------|
| 截断不当 | 规则清洗 + 短句合并 |
| 无意义字符 | 噪音清除（`[音乐]`、`♪` 等） |
| 短句过多 | 智能分段（NLP/AI） |

### 输出格式

| 格式 | 说明 |
|------|------|
| `.srt` | 保留时间轴 |
| `.txt` | 去时间轴的纯文本 |
| `.md` | 清洗+分段+格式化 |

---

## 独立辅助工具

> 📄 **详细内容已拆分至**：[auxiliary_tools_plan.md](./auxiliary_tools_plan.md)

### 工具列表

| 工具 | 功能 | 状态 |
|------|------|------|
| 文件合并器 | 多文件合并为单个 MD | 待实现 |
| 音频转文字（ASR） | YouTube 视频音频转文字 | 待实现 |
| 独立翻译/摘要 CLI | 独立使用翻译/摘要功能 | 可选 |

> **注意**：这些工具不集成到 v2.0 主程序中，可独立使用。

---

## 阶段 4：翻译优化


### 供应商分类

| 类型 | 供应商 | 特点 | 用途 |
|------|--------|------|------|
| **通用 AI** | OpenAI, Gemini, DeepSeek | 翻译+摘要 | 全能 |
| **翻译专属** | DeepL, 百度, Google | 仅翻译 | 速度快、成本低 |

### 多 Key 轮询

```python
class KeySelector:
    """多 Key 轮询调度器"""
    
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.index = 0
        self.lock = threading.Lock()
    
    def get_next_key(self) -> str:
        with self.lock:
            key = self.keys[self.index % len(self.keys)]
            self.index += 1
            return key
```

### 并发计算示例

```
翻译专属供应商:
  DeepL:  2 Keys × 5 并发 = 10
  百度:   1 Key  × 10 并发 = 10
  Google: 免费    × 20 并发 = 20
  ────────────────────────────
  小计: 40 并发

通用 AI 供应商 (备用):
  OpenAI: 3 Keys × 3 并发 = 9
  Gemini: 1 Key  × 5 并发 = 5
  ────────────────────────────
  小计: 14 并发

总计: 54 并发翻译任务
```

---

## 阶段 5：摘要优化

### Map-Reduce 并发

```
之前（串行 Map）:
  Chunk 1: [摘要] → Chunk 2: [摘要] → Chunk 3: [摘要] → [合并]
  
之后（并发 Map）:
  Chunk 1: [摘要] ─┐
  Chunk 2: [摘要] ─┼→ [合并]
  Chunk 3: [摘要] ─┘
```

### 供应商选择

| 任务 | 可用供应商 |
|------|------------|
| 翻译 | 通用 AI + 翻译专属 API |
| 摘要 | **仅通用 AI** |
| 字幕整理 | **仅通用 AI** |

### Reduce 阶段瓶颈

如果 Reduce 阶段耗时 ~20s：
- 原因：AI 合并多个子摘要
- 在高并发模式下**不是主要瓶颈**（多视频并行）

---

## 阶段 6：输出优化

### 异步输出

```python
# 改进：异步输出，不阻塞后续处理
result = await generate_summary(subtitle)
asyncio.create_task(write_output_async(result))  # 不阻塞
return result  # 立即返回，继续下一个视频
```

---

## 通用架构：多 Key 与多供应商

### 方案 1：单供应商多 Key

```json
{
  "openai": {
    "api_keys": ["sk-1", "sk-2", "sk-3", "sk-4", "sk-5"],
    "max_concurrency_per_key": 5
  }
}
// 效果：5 × 5 = 25 并发
```

| 优点 | 风险 |
|------|------|
| 简单，质量一致 | 单点故障 |

### 方案 2：多供应商多 Key

```json
{
  "openai": { "api_keys": ["sk-1", "sk-2"], "max_concurrency_per_key": 5 },
  "gemini": { "api_keys": ["gem-1"], "max_concurrency_per_key": 10 },
  "deepseek": { "api_keys": ["ds-1", "ds-2"], "max_concurrency_per_key": 20 }
}
// 效果：2×5 + 1×10 + 2×20 = 60 并发
```

| 优点 | 注意 |
|------|------|
| 容错能力强 | 质量可能不一致 |
| 并发能力更高 | 需处理不同 API |

### 推荐配置

**性价比优先**：找一个便宜好用的供应商，配多个 Key

```json
{
  "translation": { "provider": "deepseek", "api_keys": ["k1", "k2", "k3"] },
  "summary": { "provider": "deepseek", "api_keys": ["k1", "k2"] }
}
```

---

## 状态显示与日志优化

### 方案 A：日志汇总（推荐）

```
[18:05:00] 进度: 62% | 检测 300/500 | 下载 280/500 | 翻译 6400/9600 | ETA: ~12分钟
[18:05:05] 进度: 68% | 检测 340/500 | 下载 320/500 | 翻译 7200/9600 | ETA: ~10分钟
[18:05:10] ⚠️ OpenAI Key-2 限流，已自动切换
```

### ETA 改进

| 改进项 | 说明 |
|--------|------|
| **模糊显示** | `~12分钟` 代替 `12:34` |
| **智能隐藏** | 无法准确计算时显示 `--` |
| **滑动平均** | 使用最近 10 个任务的平均时间 |

### 动态日志频率

| 并发 | 日志模式 |
|------|----------|
| 1-10 | 详细（每个 chunk） |
| 11-30 | 中等（每 25%） |
| 31-50 | 精简（聚合汇总） |

### 方案 B：状态面板组件（可选，Phase 3）

> **注意**：此功能为可选，适合需要专业级监控的高并发场景。

#### UI 设计

```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 总体进度: ████████████░░░░░░░░ 62%   ⏱️ 剩余: ~12分钟       │
├─────────────────────────────────────────────────────────────────┤
│  阶段     活跃    队列    完成       速率        状态           │
├─────────────────────────────────────────────────────────────────┤
│  🔍 检测   48/50   152    300/500   8.5/s       ✅             │
│  📥 下载   50/50   120    280/500   7.2/s       ✅             │
│  🌐 翻译   45/50   1280   6400/9600  85/s       ✅             │
│  📝 摘要   12/20   60     240/310   4.2/s       ⚠️ 限流        │
├─────────────────────────────────────────────────────────────────┤
│ 🔥 CPU 45% | 内存 2.1GB | ⚠️ OpenAI Key-2 限流                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 组件结构

```python
class StatusPanel(ctk.CTkFrame):
    """高并发状态面板"""
    
    def __init__(self, parent):
        self.overall_progress = ProgressBar()   # 总进度条
        self.stage_table = StageTable()         # 阶段统计表
        self.resource_monitor = ResourceBar()   # 资源监控
        self.warning_area = WarningArea()       # 警告区域
        
        # 每秒刷新
        self.after(1000, self.refresh)
    
    def refresh(self):
        stats = GlobalTaskScheduler.get_stats()
        self.overall_progress.update(stats.completed, stats.total)
        self.stage_table.update(stats.stages)
        self.resource_monitor.update(stats.cpu, stats.memory)
```

#### 显示信息

| 组件 | 显示内容 |
|------|----------|
| 总进度条 | 完成百分比 + 剩余时间 |
| 阶段表格 | 各阶段活跃/队列/完成/速率/状态 |
| 资源监控 | CPU/内存使用率 |
| 警告区域 | 限流/错误通知 |

#### 实现难度

| 项目 | 工作量 |
|------|--------|
| UI 组件设计 | 2h |
| 数据收集层 | 2h |
| 实时刷新机制 | 1h |
| 测试优化 | 1h |
| **总计** | **6h** |


## 容错与恢复机制

### 三级容错

| 级别 | 策略 | 说明 |
|------|------|------|
| L1 | Key 轮询 | 同 Provider 换 Key |
| L2 | Provider 切换 | 换其他 Provider |
| L3 | 拆分重试 | 缩小 chunk 重试 |

### 断点续传

| 功能 | 状态 |
|------|------|
| 翻译分块恢复 | ✅ 已实现 |
| 摘要分块恢复 | ⏳ 待实现 |

---

## UI 优化

> 详细方案见 [docs/ui_optimization_plan.md](./ui_optimization_plan.md)

### 方案对比

| 方案 | 工作量 | 内容 | 推荐版本 |
|------|--------|------|----------|
| **A. 轻量优化** | 3 天 | 主题色、圆角、间距 | v2.0 |
| **B. 中等优化** | 5-6 天 | 图标、渐变、动画 | v2.1+ |

### v2.0 推荐：方案 A

| 任务 | 时间 |
|------|------|
| 自定义主题文件 | 0.5 天 |
| 统一组件样式 | 1 天 |
| 统一布局间距 | 0.5 天 |
| 主题切换测试 | 1 天 |

### 相关文件

| 文件 | 说明 |
|------|------|
| [ui_optimization_plan.md](./ui_optimization_plan.md) | 详细方案 |
| [ui_comparison_demo.html](./ui_comparison_demo.html) | 效果演示 |

---

## 性能优化

### 启动速度优化

| 优化项 | 效果 | 工作量 | 说明 |
|--------|------|--------|------|
| **延迟导入** | ⭐⭐⭐ | 1 天 | 使用时才导入非核心模块 |
| **预编译 pyc** | ⭐⭐ | 0.5 天 | 打包时编译字节码 |

#### 延迟导入示例

```python
# ❌ 启动时全部导入
from core.translator import Translator

# ✅ 使用时才导入
def translate():
    from core.translator import Translator
    return Translator()
```

### 运行流畅度优化

| 优化项 | 效果 | 工作量 | 说明 |
|--------|------|--------|------|
| **日志批量刷新** | ⭐⭐ | 0.5 天 | 积累后批量更新 UI |
| **进度条节流** | ⭐⭐ | 0.5 天 | 变化 >1% 才刷新 |
| **减少 UI 重绘** | ⭐⭐ | 1 天 | 合并多次更新 |

#### 日志批量刷新

```python
def log(msg):
    self.buffer.append(msg)
    if len(self.buffer) >= 10 or time.time() - self.last_flush > 0.1:
        self._flush()  # 批量写入
```

#### 进度条节流

```python
def update_progress(value):
    if abs(value - self.last_value) > 0.01:  # 变化 >1% 才更新
        self.progress.set(value)
        self.last_value = value
```

### 工作量汇总

| 方向 | 工作量 |
|------|--------|
| 启动速度 | ~1.5 天 |
| 运行流畅 | ~1 天 |
| **总计** | **~2.5 天** |

---

## 降级模式

> 资源不足时自动降级，保证基本运行

### 降级层级

| 级别 | 条件 | 行为 |
|------|------|------|
| L0 正常 | 资源充足 | 全功能运行 |
| L1 降级 | 代理不可用 | 直连 YouTube |
| L2 降级 | Cookie 不可用 | 跳过需登录内容 |
| L3 降级 | API Key 不可用 | 跳过翻译/摘要，只下载 |
| L4 暂停 | 全部不可用 | 暂停任务，等待恢复 |

### 代理使用范围

| 阶段 | 需要代理 | 原因 |
|------|----------|------|
| 链接识别 | ✅ | 访问 YouTube |
| 字幕下载 | ✅ | 访问 YouTube |
| 翻译 | ❌ | AI API 可直连 |
| 摘要 | ❌ | AI API 可直连 |

### 降级处理代码

```python
class FallbackManager:
    def get_level(self) -> int:
        level = 0
        if not self.proxy_pool.has_available():
            level = max(level, 1)
        if not self.cookie_pool.has_available():
            level = max(level, 2)
        if not self.key_pool.has_available():
            level = max(level, 3)
        return level
    
    def execute(self, task):
        level = self.get_level()
        if level == 0: return self._full_mode(task)
        if level == 1: return self._direct_mode(task)
        if level == 2: return self._no_cookie_mode(task)
        if level == 3: return self._download_only(task)
        return self._pause_and_notify()
```

---

## 阶段状态记录

> L3 降级后支持从本地字幕继续翻译

### 状态数据结构

```python
{
    "video_id": "xxxxx",
    "stages": {
        "download": "completed",
        "translate": "pending",
        "summarize": "pending"
    },
    "files": {
        "subtitle": "output/xxxxx.srt",
        "translated": null,
        "summary": null
    }
}
```

### 恢复逻辑

```python
def resume_task(video_id):
    state = load_state(video_id)
    
    if state["stages"]["download"] == "completed":
        # 从本地字幕继续
        if state["stages"]["translate"] == "pending":
            text = read_file(state["files"]["subtitle"])
            translated = translate(text)
        
        if state["stages"]["summarize"] == "pending":
            summary = summarize(text)
```

### 用户流程

```
1. L3 降级 → 只下载字幕
2. 等待 API Key 恢复
3. 重新运行
4. 检测到字幕已存在 → 跳过下载
5. 直接翻译 + 摘要
```

### 工作量

| 功能 | 工作量 |
|------|--------|
| 降级模式 | 1 天 |
| 阶段状态记录 | 0.5 天 |
| **总计** | **1.5 天** |

---

## 实施路线图

### Phase 1：快速提升（~5h）

| 任务 | 工作量 |
|------|--------|
| 字幕清洗（噪音+短句） | 3h |
| 日志汇总 + ETA 改进 | 2h |

**效果**：摘要质量提升 20-30%，日志可读

### Phase 2：高性能（~10h）

| 任务 | 工作量 |
|------|--------|
| 多 Key 数据结构 | 2h |
| KeySelector 轮询 | 2h |
| 多 Provider 并行 | 4h |
| 三级容错 | 2h |

**效果**：翻译速度提升 10 倍

### Phase 3：专业版（~15h）

| 任务 | 工作量 |
|------|--------|
| 代理池 + Cookie 轮换 | 4h |
| 健康监控 | 2h |
| 翻译专属 API 集成 | 3h |
| 状态面板组件 | 6h |

**效果**：50 并发 + 长时间运行

### 总工作量

#### 核心功能（Phase 1-3）

| 阶段 | 工作量 | 累计 |
|------|--------|------|
| Phase 1（字幕清洗+日志） | 5h | 5h |
| Phase 2（多 Key+多 Provider） | 10h | 15h |
| Phase 3（代理池+Cookie+状态） | 15h | 30h |

#### 必做项汇总

| 模块 | 工时 | 天数（8h/天） | 类型 |
|------|------|--------------|------|
| Phase 1-3 核心功能 | 30h | 3.75 天 | 必做 |
| UI 优化方案 A | 24h | 3 天 | 必做 |
| **必做总计** | **54h** | **~7 天** | |

#### 可选项汇总

| 模块 | 工时 | 天数 | 类型 |
|------|------|------|------|
| UI 优化方案 B（增量） | 16-24h | 2-3 天 | 可选 |
| 性能优化 | 20h | 2.5 天 | 可选 |
| **可选总计** | **36-44h** | **~5 天** | |

#### 独立工具（不计入 v2.0 工期）

| 模块 | 工时 | 说明 |
|------|------|------|
| ASR 音频转文字 | 4 天 | 独立模块 |
| 文件合并器 | 0.5 天 | 独立模块 |

#### 总工期估算

| 范围 | 天数 | 说明 |
|------|------|------|
| **必做项** | **~7 天** | v2.0 最小可发布版本 |
| **必做 + 可选** | **~12 天** | 完整 v2.0 |
| **包含独立工具** | **~16.5 天** | 全部功能 |

---

## 详细执行计划

> 完整执行计划见 [docs/v2_execution_plan.md](./v2_execution_plan.md)

### 执行顺序

| 阶段 | 时间 | 内容 |
|------|------|------|
| 1. 骨架搭建 | 2-2.5 天 | 目录结构、数据结构、调度器 |
| 2. UI 布局 | 1.5-2 天 | 状态栏、配置精简、数据绑定 |
| 3. 后端功能 | 3-4 天 | 多 Key 轮询、代理池、容错 |
| 4. 联调测试 | 1 天 | 端到端测试 |

---

## 注意事项

> 📄 **详细内容已拆分至**：[development_guidelines.md](./development_guidelines.md)

### 快速参考

| 级别 | 关键事项 |
|------|----------|
| 🔴 高危 | 资源池加锁、锁内不做耗时操作、异常必须记录日志 |
| 🟡 中危 | Cookie/代理失效判断、进度统计线程安全 |
| 🟢 低危 | 日志级别区分、优雅停止、单元测试覆盖 |

### 核心规范

| 类别 | 要点 |
|------|------|
| 国际化 | 所有 UI 文本和日志用 `t()` 包装 |
| 代码 | 函数 ≤50 行，文件 ≤300 行 |
| 安全 | 不记录敏感信息，HTTPS 优先 |

---


## 运维指南

### 故障排查

| 问题 | 排查步骤 |
|------|----------|
| **翻译失败** | ① 检查 API Key 是否有效 → ② 检查网络连通性 → ③ 检查配额是否用完 |
| **Cookie 快速失效** | ① 检查并发数是否过高 → ② 检查冷却时间 → ③ 检查 IP 是否匹配 |
| **程序卡死** | ① 检查是否死锁 → ② 查看线程状态 → ③ 查看日志最后输出 |
| **下载失败** | ① 检查代理是否可用 → ② 检查链接格式 → ③ 检查 yt-dlp 版本 |
| **内存占用高** | ① 检查并发数 → ② 检查是否有内存泄漏 → ③ 重启程序 |

### 回滚方案

| 场景 | 操作 |
|------|------|
| **新功能上线后出问题** | Git 回退到上一个稳定版本 |
| **配置改错了** | 删除配置文件，程序自动生成默认配置 |
| **数据迁移失败** | 备份目录恢复，回退到旧版本 |

**回滚命令**：
```bash
# Git 回退到上一个版本
git checkout HEAD~1

# 恢复默认配置
rm config.json  # 下次启动自动生成
```

### 监控指标（可选，Phase 3）

> **注意**：此功能为可选，适合需要详细监控的场景。

| 指标 | 说明 | 采集方式 |
|------|------|----------|
| 成功率 | 各阶段成功/失败比例 | 日志统计 |
| 平均耗时 | 各阶段平均处理时间 | 计时器 |
| 资源使用率 | 代理/Cookie/Key 使用情况 | 资源池统计 |
| 错误分布 | 各类错误出现频率 | 错误日志分类 |

---

## 版本兼容

### v1.0 → v2.0 迁移

| 项目 | 兼容性 | 说明 |
|------|--------|------|
| **配置文件** | ⚠️ 部分兼容 | 新增字段自动填充默认值 |
| **输出文件** | ✅ 完全兼容 | SRT/TXT/MD 格式不变 |
| **API 调用** | ✅ 兼容 | 现有 Provider 继续支持 |

**迁移步骤**：
1. 备份 v1.0 配置文件
2. 安装 v2.0
3. 首次启动自动迁移配置
4. 检查新增配置项

### 功能开关说明

| 功能 | 是否可选 | 默认值 | 说明 |
|------|----------|--------|------|
| 代理池 | ✅ 可选 | 关闭 | 无代理时使用直连 |
| Cookie 轮换 | ✅ 可选 | 关闭 | 无 Cookie 时匿名访问 |
| 多 Key 轮询 | ✅ 可选 | 关闭 | 单 Key 时不轮询 |
| 字幕清洗 | ✅ 可选 | 开启 | 建议开启 |
| AI 字幕整理 | ✅ 可选 | auto | 短文本用 AI |
| MD 格式输出 | ✅ 可选 | 关闭 | 按需开启 |
| 状态面板 | ✅ 可选 | 关闭 | Phase 3 实现 |
| 监控指标 | ✅ 可选 | 关闭 | Phase 3 实现 |

### 配置示例

```json
{
  "features": {
    "proxy_pool": false,
    "cookie_rotation": false,
    "multi_key": true,
    "subtitle_clean": true,
    "ai_restructure": "auto",
    "md_output": false,
    "status_panel": false,
    "metrics": false
  }
}
```
