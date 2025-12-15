# 编码问题检查报告

> 检查时间：2025-12-15

## 问题描述

在执行 git commit 命令时，使用多行中文提交信息（多个 `-m` 参数）时出现乱码，git 将提交信息的一部分误认为是文件路径（pathspec）。

## 检查结果

### ✅ 代码文件编码正常

所有关键文件都是 **UTF-8 编码**，且可读性正常：

| 文件 | 编码 | 置信度 | 中文字符数 | 状态 |
|------|------|--------|------------|------|
| `core/output.py` | UTF-8 | 0.99 | 2675 | ✅ 正常 |
| `core/pipeline.py` | UTF-8 | 0.99 | 2472 | ✅ 正常 |
| `core/prompts.py` | UTF-8 | 0.99 | 517 | ✅ 正常 |
| `ui/i18n/zh_CN.json` | UTF-8 | 0.99 | 1865 | ✅ 正常 |
| `ui/i18n/en_US.json` | UTF-8 | 0.99 | 2 | ✅ 正常 |
| `docs/dev_log.md` | UTF-8 | 0.99 | 6418 | ✅ 正常 |
| `docs/ide_修复任务表_AI层与流水线.md` | UTF-8 | 0.99 | 2717 | ✅ 正常 |

### ✅ Git 配置已优化

已设置以下 Git 配置以支持 UTF-8：

```bash
git config --global core.quotepath false
git config --global i18n.commitencoding utf-8
git config --global i18n.logoutputencoding utf-8
```

### ⚠️ 问题根源

**问题不在代码文件，而在终端环境：**

1. **PowerShell 默认编码**：Windows PowerShell 默认使用 **GBK 编码**（代码页 936）
2. **命令解析问题**：当使用多个 `-m` 参数时，PowerShell 在解析包含中文的命令行参数时可能出现编码转换问题
3. **Git 误解析**：由于编码问题，git 将提交信息的一部分误认为是文件路径

## 解决方案

### 方案 1：使用单行提交信息（推荐）

避免使用多个 `-m` 参数，改用单行提交信息：

```bash
# ❌ 不推荐（可能出现乱码）
git commit -m "feat: UI 模块功能增强" -m "- 频道模式优化" -m "- 国际化完善"

# ✅ 推荐（单行）
git commit -m "feat: UI 模块功能增强 - 频道模式优化、国际化完善"
```

### 方案 2：使用英文提交信息

对于重要的提交，使用英文提交信息可以避免编码问题：

```bash
git commit -m "feat: enhance UI module and internationalization"
```

### 方案 3：使用 Git 编辑器

使用 Git 的默认编辑器编写多行提交信息：

```bash
git commit  # 会打开编辑器，可以写多行中文
```

### 方案 4：设置 PowerShell UTF-8 编码（临时）

在 PowerShell 中临时设置 UTF-8 编码：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001  # 设置代码页为 UTF-8
```

### 方案 5：使用 Git Bash 或 WSL

使用 Git Bash 或 WSL（Windows Subsystem for Linux）可以避免 PowerShell 的编码问题。

## 验证

运行以下命令验证编码检查：

```bash
python check_encoding.py
```

## 总结

- ✅ **代码文件本身没有问题**：所有文件都是正确的 UTF-8 编码
- ✅ **Git 配置已优化**：已设置 UTF-8 编码支持
- ⚠️ **问题在终端环境**：PowerShell 的 GBK 编码导致命令行参数解析问题
- 💡 **建议**：使用单行提交信息或英文提交信息，避免在 PowerShell 中使用多行中文提交信息

## 相关文件

- `check_encoding.py` - 编码检查工具

