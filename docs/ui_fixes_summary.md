# UI 问题修复总结

> 修复时间：2025-12-09

## 🔧 修复的问题

### 1. ✅ 语言切换始终显示英文

**问题原因**：
- 在 `_on_language_changed` 中，使用 `t("language_zh")` 来比较，但 `t()` 函数会根据当前语言返回不同的文本
- 当用户选择"中文"时，`value` 是"中文"，但 `t("language_zh")` 在英文状态下返回的也是"中文"（因为翻译文件中 `language_zh` 的值是固定的"中文"），导致比较失败

**修复方案**：
- 直接比较 `value` 与固定的文本（"中文" 或 "English"），不依赖 `t()` 函数
- 更新 `toolbar.py` 的 `refresh_language()` 方法，使用固定文本设置下拉框值
- 完善 `channel_page.py` 的 `refresh_language()` 方法，确保所有文本都能正确更新

**修改文件**：
- `ui/main_window.py` - 修复语言切换判断逻辑
- `ui/components/toolbar.py` - 修复语言下拉框刷新逻辑
- `ui/pages/channel_page.py` - 完善语言刷新方法

### 2. ✅ 下载字幕失败（Cookie 未传递）

**问题原因**：
- `SubtitleDetector`（字幕检测器）不支持 Cookie，导致检测字幕时失败
- 虽然 `VideoFetcher` 和 `SubtitleDownloader` 支持 Cookie，但 `SubtitleDetector` 在 Dry Run 时也需要 Cookie

**修复方案**：
- 为 `SubtitleDetector` 添加 `cookie_manager` 参数支持
- 在 `_get_subtitle_info_ytdlp` 方法中添加 Cookie 参数传递
- 在 `business_logic.py` 中创建 `SubtitleDetector` 时传递 `cookie_manager`

**修改文件**：
- `core/detector.py` - 添加 Cookie 支持
- `ui/business_logic.py` - 传递 Cookie 给 SubtitleDetector

### 3. ✅ 主题切换正常（已确认）

**状态**：主题切换功能正常工作 ✅

## 📝 修改详情

### `ui/main_window.py`
- 修复 `_on_language_changed`：直接比较固定文本（"中文"、"English"）
- 修复窗口标题初始化顺序：先设置默认标题，i18n 初始化后再更新

### `ui/components/toolbar.py`
- 修复 `refresh_language`：使用固定文本设置下拉框值，避免翻译问题

### `ui/pages/channel_page.py`
- 完善 `refresh_language`：添加标题和 URL 标签的刷新
- 保存标题和 URL 标签的引用，便于刷新

### `core/detector.py`
- 添加 `cookie_manager` 参数到 `__init__`
- 在 `_get_subtitle_info_ytdlp` 中添加 Cookie 参数传递

### `ui/business_logic.py`
- 创建 `SubtitleDetector` 时传递 `cookie_manager`

## ✅ 验证

- ✅ 无语法错误
- ✅ 无 linter 错误
- ✅ 所有修改已应用

## 🧪 测试建议

1. **语言切换测试**：
   - 启动 GUI
   - 切换语言（中文 ↔ English）
   - 验证所有 UI 文本正确更新（标题、按钮、标签等）

2. **Cookie 测试**：
   - 确保配置中有有效的 Cookie
   - 执行 Dry Run 检测字幕
   - 验证不再出现 "Sign in to confirm you're not a bot" 错误
   - 执行 Start 处理，验证字幕下载成功

3. **主题切换测试**：
   - 切换不同主题
   - 验证颜色正确更新，无残留

## 📋 注意事项

1. **Cookie 配置**：确保在配置文件中正确设置了 Cookie，格式为浏览器复制的 Cookie 字符串
2. **语言切换**：语言切换后，所有组件文本会自动刷新，但可能需要重新打开某些页面才能看到完整效果
3. **错误处理**：如果 Cookie 无效或过期，YouTube 仍可能要求登录，此时需要更新 Cookie

