# UI 模块化重构规范（ui_modular_refactor.md）

> 目的：将现有 1,300+ 行的 `ui/main_window.py` 拆分为**清晰、可维护、可扩展**的模块化结构；确保后续改动不再牵一发动全身，同时**不改变已验收的业务行为**。  
> 范围：仅限 UI 层的结构性重构与接线调整；**不修改**业务逻辑语义（Dry Run / 增量 / 输出结构 / 失败记录等保持一致）。  
> 关联任务：`P0-24-fix`（UI 模块化重构，不改行为）

---

## 1. 目标结构（落地后的样子）

ui/
├─ main_window.py # 仅负责布局拼装、页面切换与事件接线（< 300 行）
├─ app_events.py # 事件总线（on/emit），集中管理 UI 内部事件
├─ state.py # 轻量 UI 状态（成功/失败计数、当前模式、只读配置快照）
├─ themes.py # 4 套主题与应用函数（幂等、全量覆盖）
├─ i18n_manager.py # 国际化文案绑定与刷新（不重建控件）
├─ components/
│ ├─ toolbar.py # 顶部工具栏（触发事件，不包含业务流程）
│ ├─ sidebar.py # 左侧导航（触发“切页”事件）
│ ├─ log_panel.py # 底部日志面板（提供 logging.Handler）
│ └─ progress_strip.py # 可选：成功/失败/总数/ETA 简条
└─ pages/
├─ channel_page.py # 频道模式（URL 输入、检查、开始）
├─ url_list_page.py # P1：多行 URL 列表模式
├─ run_params_page.py # 并发、重试、强制重跑等运行参数
├─ network_ai_page.py # 代理、Cookie、AI 供应商与模型设置
├─ appearance_page.py # 语言与主题切换（事件驱动）
└─ system_page.py # 打开目录、版本信息、重置（危险操作二次确认）

markdown
复制代码

**边界约束（强制）：**
- `main_window.py` 只负责**拼装布局 + 绑定/转发事件**，不写页面内部表单逻辑或业务流程。
- `pages/*.py` 互不 `import`；页面/组件**不直接调用 core 层**，统一通过事件或单一 UI 控制器门面接入。
- 主题仅在 `themes.py` 统一应用；文案仅经 `i18n_manager.py` 刷新；**禁止**在页面/组件内写死颜色/文案。
- `components/log_panel.py` 暴露 `LogPanel` 和 `LogHandler`；全局 logger **只绑定一次**。

---

## 2. 重构步骤（5 小步，可回滚）

> 每步都是可独立合并的小 PR；每步后保证可启动且功能可用。

### Step 1：抽离底部日志面板（components/log_panel.py）
- 从 `main_window.py` 提取 `LogPanel` 为独立控件，提供：
  - `append(line: str)`  
  - `get_logging_handler() -> logging.Handler`（线程安全，追加到 UI）
- 全局日志：在主窗初始化时绑定一次 `logger.addHandler(LogPanelHandler)`。
- ✅ 验收：主窗可见、实时日志刷新；主窗内部**不再直接**操作日志文本。

### Step 2：抽离顶部工具栏与左侧侧边栏（components/toolbar.py, sidebar.py）
- `toolbar.py`：按钮仅**emit 事件**（如 `"theme:change"`, `"i18n:change"`, `"open:output_dir"`）。
- `sidebar.py`：仅 **emit** `"nav:<page_key>"` 切页事件。
- `main_window.py` 订阅事件，切换中心 `StackedWidget` 当前页。
- ✅ 验收：切页正常；切主题/切语言时页面文字能刷新（与 Step 4 配合）。

### Step 3：抽离“频道模式页 / 运行参数页”（pages/channel_page.py, run_params_page.py）
- `channel_page.py`：提供 URL 输入、[检查]、[开始] 按钮，仅发事件：
  - `"task:dry_run", payload={url, config_snapshot}`
  - `"task:start", payload={url, force, config_snapshot}`
- `run_params_page.py`：并发、重试、强制重跑，更新 ConfigManager 或 emit `"config:changed"`.
- ✅ 验收：Dry Run 仅日志、不写文件；Start 可跑完整流程；切换页面不影响日志与进度。

### Step 4：抽离“网络&AI / 外观&系统”（pages/network_ai_page.py, appearance_page.py, system_page.py）
- `network_ai_page.py`：代理多行、Cookie 测试、AI 供应商与模型选择，发：
  - `"network:proxy_set"`, `"cookie:test"`, `"ai:config_changed"`.
- `appearance_page.py`：下拉切换语言/主题，发：
  - `"i18n:change"`, `"theme:change"`.
- `system_page.py`：打开输出目录、版本信息、重置（危险操作二次确认）。
- ✅ 验收：修改配置后新任务生效；[测试 AI 设置] 有清晰结果日志；外观切换无闪烁/异常。

### Step 5：事件总线 + 轻量状态（app_events.py, state.py）
- `app_events.py`：提供极简事件总线：
  ```python
  class EventBus:
      def on(self, topic: str, handler: Callable): ...
      def emit(self, topic: str, **payload): ...
  bus = EventBus()
state.py：维护只读 UI 状态（成功/失败/总数/当前模式），事件触发时更新并广播。

流水线回调（进度/完成）→ 统一 emit "task:progress", "task:done"，由主窗刷新 UI。

✅ 验收：全局计数在任意页面可见且同步；无循环依赖；关闭/重开窗口不丢日志句柄。

3. 主题与国际化的幂等规则
问题根因（常见）：

切语言时重建控件树 → 主题失效或重复叠加；

主题应用函数非幂等，多次调用样式叠加；

语言切换与主题切换并发/顺序不定。

统一修复准则：

i18n_manager.set_language(lang)：仅更新文案，不重建控件，不触碰样式；通过已注册控件/回调刷新 text。

themes.apply(theme, root_widget)：幂等、全量覆盖；禁止在页面/组件中 setStyleSheet 写死颜色。

切换流程顺序固定：

暂停 UI 重绘（可选：setUpdatesEnabled(False)）

刷新 i18n 文案

应用主题

恢复重绘并一次刷新

提供 ThemeGuard：上下文管理器保证同一时刻仅一次主题应用。

4. 事件与依赖边界（防“再次长成大文件”）
仅允许的依赖方向：

perl
复制代码
components/*  →  app_events.py
pages/*       →  app_events.py
main_window   →  pages/*, components/*, app_events, state, i18n_manager, themes
（UI 层）     →  （core 层入口，仅 1~2 个控制器/门面）
禁止：

页面彼此 import

页面/组件直接 import core/* 深层实现（统一通过主窗/单一 UiController 门面）

在页面里写死颜色或样式；在页面里硬编码文案

在多个地方重复绑定 logger handler（只绑定一次）

5. 交付与验收
5.1 交付物
新增文件：ui/app_events.py, ui/state.py, ui/components/{toolbar.py, sidebar.py, log_panel.py}, ui/pages/{channel_page.py, run_params_page.py, network_ai_page.py, appearance_page.py, system_page.py}

压缩后的 ui/main_window.py（< 300 行）

文件/类关系图（md/plantuml/mermaid 任选）

自测说明（如何验证切页、Dry Run、Start、切语言/切主题、日志与进度同步）

在 docs/dev_log.md 追加“P0-24-fix UI 模块化重构”事件摘要与改动链接

5.2 验收标准（必须全部通过）
结构：

main_window.py < 300 行；单个 page/comp 文件 < 300 行；无页面间 import。

事件：

所有交互通过 app_events.py；主流程接线集中，无分散直连 core 的调用。

主题/i18n：

主题应用幂等；切语言不重建控件、不破坏主题；无闪烁/残留样式。

功能回归：

上一轮整体验收（Dry Run / 增量 / 输出 / 失败记录）全部仍然通过。

日志：

LogPanel 独立；全局 logger 仅绑定一次 handler；任务期间日志实时刷新。

文档：

交付文件与自测说明齐全；dev_log.md 已记录。

6. 回滚与风险控制
每个 Step 单独提交，每步可回滚；任何一步未通过验收禁止继续下一步。

若出现页面功能回退/崩溃：优先回滚最近一步，再修复后重试。

遇到必须动业务逻辑的情况：停止重构，先更新文档并确认（不得擅自修改业务语义）。