# Cookie 配置指南

## 为什么需要 Cookie？

YouTube 对未登录用户或频繁请求的 IP 有访问限制。配置 Cookie 可以：
- 提高视频和字幕的下载成功率
- 访问需要登录才能查看的内容
- 减少被 YouTube 限制的风险

## 如何获取 Cookie

### 方法一：使用浏览器开发者工具（推荐）

1. **打开浏览器**，访问 [YouTube](https://www.youtube.com)
2. **登录你的 YouTube 账号**（如果需要）
3. **按 F12** 打开开发者工具
4. **切换到 Network（网络）标签**
5. **刷新页面**（F5 或 Ctrl+R）
6. **在请求列表中找到任意一个请求**（如 `watch`、`browse` 等）
7. **点击该请求**，在右侧找到 **Headers（请求头）**
8. **找到 `Cookie:` 字段**，复制整个 Cookie 字符串
   - Cookie 字符串格式类似：`VISITOR_INFO1_LIVE=xxx; YSC=yyy; PREF=zzz; ...`
9. **粘贴到工具的 Cookie 配置页面**

### 方法二：使用浏览器扩展

某些浏览器扩展（如 "Get cookies.txt LOCALLY"）可以导出 Cookie 文件，但本工具需要的是 Cookie 字符串格式。

## 如何在工具中配置 Cookie

1. **打开工具**，点击左侧边栏的 **"运行设置" → "网络 & AI"**
2. **在 Cookie 配置区域**：
   - 可以直接在文本框中粘贴 Cookie 字符串
   - 或点击 **"从剪贴板粘贴"** 按钮自动粘贴
3. **（可选）点击 "测试 Cookie"** 验证 Cookie 是否有效
4. **点击 "保存 Cookie"** 保存配置
5. **重新启动工具** 或重新加载配置以使 Cookie 生效

## Cookie 格式要求

- Cookie 字符串格式：`key1=value1; key2=value2; key3=value3; ...`
- 每个 Cookie 项用分号（`;`）分隔
- 不要包含 `Cookie:` 前缀，只复制值部分
- 确保 Cookie 完整（不要截断）

## 常见问题

### Q: Cookie 测试失败怎么办？

A: 可能的原因：
- Cookie 已过期（需要重新获取）
- Cookie 格式不正确（检查是否包含 `Cookie:` 前缀）
- 网络连接问题
- YouTube 检测到异常请求

**解决方法**：
1. 重新获取 Cookie（确保浏览器已登录）
2. 检查 Cookie 格式是否正确
3. 尝试使用代理

### Q: Cookie 保存后仍然下载失败？

A: 确保：
1. Cookie 已正确保存（查看日志确认）
2. 已重新初始化核心组件（保存 Cookie 后会自动重新加载）
3. Cookie 未过期（如果失败，尝试重新获取）

### Q: Cookie 会过期吗？

A: 是的，Cookie 有有效期。如果发现下载失败，可能需要：
1. 重新获取 Cookie
2. 重新保存到工具中

## 安全提示

⚠️ **重要**：Cookie 包含你的登录凭证，请妥善保管：
- 不要将 Cookie 分享给他人
- 不要在公共场合展示 Cookie
- 如果怀疑 Cookie 泄露，请立即更改 YouTube 密码

## 配置文件位置

Cookie 保存在用户数据目录的 `config.json` 文件中：
- **Windows**: `%APPDATA%\yt-subtitle-v2\config.json`
- **Linux**: `~/.config/yt-subtitle-v2/config.json`
- **macOS**: `~/Library/Application Support/yt-subtitle-v2/config.json`

你可以直接编辑该文件，但建议通过工具界面配置，以避免格式错误。

