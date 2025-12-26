# UI 优化方案

> CustomTkinter 界面优化详细计划

## 目录

1. [方案对比](#方案对比)
2. [方案 A：轻量优化](#方案-a轻量优化3-天)
3. [方案 B：中等优化](#方案-b中等优化5-6-天)
4. [潜在问题与修复](#潜在问题与修复)
5. [注意事项](#注意事项)

---

## 方案对比

| 对比项 | A. 轻量优化 | B. 中等优化 |
|--------|-------------|-------------|
| **工作量** | 3 天 | 5-6 天 |
| 主题色 | 单色 | 渐变色 |
| 图标 | ❌ | ✅ |
| 动画 | ❌ | ✅ 悬停/进度 |
| 卡片样式 | 简单边框 | 毛玻璃+阴影 |
| 状态标签 | ❌ | ✅ 彩色标签 |
| **修复难度** | 🟢 简单 | 🟡 中等 |
| **推荐版本** | v2.0 | v2.1+ |

> 效果演示：[ui_comparison_demo.html](./ui_comparison_demo.html)

### 相关文件

| 文件 | 说明 |
|------|------|
| [ui_comparison_demo.html](./ui_comparison_demo.html) | UI 组件效果对比 |
| [v2_layout_demo.html](./v2_layout_demo.html) | 4 种布局方案对比 |
| [v2_layout_v1based.html](./v2_layout_v1based.html) | ✅ v2.0 推荐布局（基于 v1.0 改进） |

---

## 方案 A：轻量优化（3 天）

### 实施内容

| 任务 | 时间 | 说明 |
|------|------|------|
| 1. 创建自定义主题文件 | 0.5 天 | `custom_theme.json` |
| 2. 统一组件样式 | 1 天 | 按钮、输入框、进度条 |
| 3. 统一布局间距 | 0.5 天 | 全局 padding/gap |
| 4. 主题切换测试 | 1 天 | 明/暗主题切换 |

### 自定义主题文件

```json
// ui/themes/custom_theme.json
{
  "CTk": {
    "fg_color": ["#F5F5F7", "#1E1E2E"]
  },
  "CTkButton": {
    "fg_color": ["#6366F1", "#6366F1"],
    "hover_color": ["#4F46E5", "#4F46E5"],
    "text_color": ["white", "white"],
    "corner_radius": 8
  },
  "CTkFrame": {
    "fg_color": ["#FFFFFF", "#2D2D3F"],
    "corner_radius": 12
  },
  "CTkEntry": {
    "fg_color": ["#F0F0F0", "#1E1E2E"],
    "border_color": ["#CCCCCC", "#4D4D5F"],
    "corner_radius": 8
  },
  "CTkProgressBar": {
    "fg_color": ["#E5E5E5", "#3D3D4F"],
    "progress_color": ["#6366F1", "#6366F1"],
    "corner_radius": 4
  }
}
```

### 样式管理器

```python
# ui/styles.py
import customtkinter as ctk
from pathlib import Path

COLORS = {
    "primary": "#6366F1",
    "secondary": "#8B5CF6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
}

SPACING = {
    "xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32,
}

def apply_theme():
    theme_path = Path(__file__).parent / "themes" / "custom_theme.json"
    ctk.set_default_color_theme(str(theme_path))
```

---

## 方案 B：中等优化（5-6 天）

### 实施内容

| 任务 | 时间 | 说明 |
|------|------|------|
| 1. 方案 A 全部内容 | 2 天 | 基础样式 |
| 2. 图标集成 | 1 天 | CTkImage |
| 3. 渐变效果 | 0.5 天 | Canvas 实现 |
| 4. 状态标签 | 0.5 天 | Badge 组件 |
| 5. 悬停动画 | 0.5 天 | hover 效果 |
| 6. 主题切换完整测试 | 0.5 天 | 多组件测试 |

### 图标管理器

```python
# ui/icons.py
from PIL import Image
import customtkinter as ctk
from pathlib import Path

ICON_DIR = Path(__file__).parent / "assets" / "icons"

class IconManager:
    _cache = {}
    
    @classmethod
    def get(cls, name: str, size: tuple = (20, 20)) -> ctk.CTkImage:
        key = f"{name}_{size}"
        if key not in cls._cache:
            cls._cache[key] = ctk.CTkImage(
                light_image=Image.open(ICON_DIR / f"{name}_light.png"),
                dark_image=Image.open(ICON_DIR / f"{name}_dark.png"),
                size=size
            )
        return cls._cache[key]
```

### 状态标签

```python
# ui/components/badge.py
import customtkinter as ctk

class Badge(ctk.CTkLabel):
    STYLES = {
        "success": {"fg": "#10B981", "bg": "#10B98133"},
        "warning": {"fg": "#F59E0B", "bg": "#F59E0B33"},
        "error": {"fg": "#EF4444", "bg": "#EF444433"},
    }
    
    def __init__(self, master, text, style="success", **kwargs):
        colors = self.STYLES.get(style)
        super().__init__(master, text=text, fg_color=colors["bg"],
                         text_color=colors["fg"], corner_radius=12)
```

### 主题切换刷新器

```python
# ui/theme_manager.py
class ThemeManager:
    def __init__(self, root):
        self.root = root
    
    def switch_theme(self, mode: str):
        ctk.set_appearance_mode(mode)
        self._refresh_all(self.root)
    
    def _refresh_all(self, widget):
        for child in widget.winfo_children():
            if hasattr(child, 'configure'):
                try: child.configure()
                except: pass
            self._refresh_all(child)
        widget.update_idletasks()
```

---

## 潜在问题与修复

### 问题 1：颜色残留

| 项目 | 说明 |
|------|------|
| 场景 | 主题切换后部分组件保持旧颜色 |
| 概率 | 🟡 中等 |
| 难度 | 🟢 简单 |
| 方案 | 使用 `ThemeManager._refresh_all()` |

### 问题 2：按钮文字模糊

| 项目 | 说明 |
|------|------|
| 场景 | 使用自定义字体或缩放后 |
| 概率 | 🟢 低 |
| 难度 | 🟢 简单 |
| 方案 | 统一字体 `("Microsoft YaHei UI", 14)` |

### 问题 3：渐变背景闪烁

| 项目 | 说明 |
|------|------|
| 场景 | 窗口调整大小时 |
| 概率 | 🟡 中等 |
| 难度 | 🟡 中等 |
| 方案 | 添加防抖 + 缓存 |

---

## 注意事项

| 类别 | 注意事项 |
|------|----------|
| 🔴 高危 | 不要在渐变绘制中做复杂计算 |
| 🔴 高危 | 主题切换后必须调用 `update_idletasks()` |
| 🟡 中危 | 图标必须提供 light/dark 两版本 |
| 🟡 中危 | 字体统一使用系统字体 |
| 🟢 建议 | 渐变只用于静态背景 |
| 🟢 建议 | 先在小范围测试再全局应用 |

---

## 推荐

| 版本 | 推荐方案 |
|------|----------|
| v2.0 | 方案 A（轻量优化） |
| v2.1+ | 方案 B（中等优化） |

---

## 日志输出配色

### 配色方案

| 类型 | 颜色 | 色码 | 说明 |
|------|------|------|------|
| 常规 | 白/黑 | 跟随主题 | 浅色主题黑字，深色主题白字 |
| 警告/提示 | 蓝色 | `#3B82F6` | 避免橙/黄色模糊 |
| 成功 | 绿色 | `#10B981` | 操作成功 |
| 错误 | 红色 | `#EF4444` | 错误信息 |

### 实现示例

```python
# ui/log_colors.py
import customtkinter as ctk

LOG_COLORS = {
    "info": None,  # 跟随主题
    "warning": "#3B82F6",  # 蓝色
    "success": "#10B981",  # 绿色
    "error": "#EF4444",    # 红色
}

def get_log_color(level: str, mode: str) -> str:
    if level == "info":
        return "#000000" if mode == "light" else "#FFFFFF"
    return LOG_COLORS.get(level, "#FFFFFF")
```

---

## 容易出错的地方

| 问题 | 概率 | 修复难度 | 说明 |
|------|------|----------|------|
| 状态未同步刷新 | 🟡 中 | 🟢 简单 | 组件状态改变后未调用 configure() |
| 颜色定义分散 | 🟡 中 | 🟢 简单 | 颜色硬编码在多个文件中 |
| 图标路径错误 | 🟢 低 | 🟢 简单 | 路径拼写错误或文件缺失 |
| 主题切换残留 | 🟡 中 | 🟡 中等 | 切换后部分组件未刷新 |
| 字体渲染异常 | 🟢 低 | 🟢 简单 | 自定义字体缺失或不兼容 |

---

## 降低维护难度的方法

### 1️⃣ 集中管理颜色

```python
# ui/colors.py
# 所有颜色定义在一个文件中

COLORS = {
    "primary": "#6366F1",
    "success": "#10B981",
    "warning": "#3B82F6",  # 使用蓝色替代橙色
    "error": "#EF4444",
}

LOG_COLORS = {
    "info": {"light": "#000000", "dark": "#FFFFFF"},
    "warning": "#3B82F6",
    "success": "#10B981",
    "error": "#EF4444",
}
```

### 2️⃣ 避免硬编码

```python
# ❌ 错误做法
label.configure(text_color="#EF4444")

# ✅ 正确做法
from ui.colors import COLORS
label.configure(text_color=COLORS["error"])
```

### 3️⃣ 状态变化时打日志

```python
def set_status(self, status: str):
    logger.debug(f"状态变化: {self.current} -> {status}")
    self.current = status
    self._update_ui()
```

### 4️⃣ 组件命名规范

| 组件类型 | 命名规范 | 示例 |
|----------|----------|------|
| 按钮 | `btn_动作` | `btn_download` |
| 标签 | `lbl_内容` | `lbl_status` |
| 输入框 | `entry_字段` | `entry_url` |
| 进度条 | `progress_名称` | `progress_main` |

### 5️⃣ 主题切换测试清单

| 测试项 | 验证 |
|--------|------|
| 背景色 | ✅ 切换后正确 |
| 文字色 | ✅ 切换后正确 |
| 按钮色 | ✅ 切换后正确 |
| 日志色 | ✅ 切换后正确 |
| 图标色 | ✅ 跟随主题 |
