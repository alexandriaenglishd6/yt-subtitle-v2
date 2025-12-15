# 修复提交信息乱码

## 问题说明

以下提交信息存在编码问题（乱码）：

1. `dfabafd` - 当前：`feat: R2-2 鎵╁睍 metadata.json 涓殑 AI 涓庤繍琛屼俊鎭?- 娣诲姞宸ュ叿鐗堟湰鍙枫€乺un_id銆乼ranslation_ai銆乻ummary_ai 瀛楁`
   - 应该为：`feat: R2-2 扩展 metadata.json 中的 AI 与运行信息 - 添加工具版本号、run_id、translation_ai、summary_ai 字段`

2. `924ea56` - 当前：`docs: 鏇存柊 AI 鎻愪緵鍟嗘墿灞曟枃妗ｅ拰娴嬭瘯鏂囨。`
   - 应该为：`docs: 更新 AI 提供商扩展文档和测试文档`

3. `0bdf0cc` - 当前：`feat: UI 妯″潡鍔熻兘澧炲己鍜屽浗闄呭寲瀹屽杽`
   - 应该为：`feat: UI 模块功能增强和国际化完善`

## 修复方法

### 方法 1：使用 git rebase -i（推荐）

```bash
# 1. 开始交互式 rebase
git rebase -i dfabafd^

# 2. 在编辑器中，将以下三行的 "pick" 改为 "reword"：
#    pick dfabafd feat: R2-2 鎵╁睍...
#    pick 924ea56 docs: 鏇存柊...
#    pick 0bdf0cc feat: UI 妯″潡...

# 3. 保存并关闭编辑器，Git 会逐个提示你修改提交信息

# 4. 修改每个提交信息为正确的版本

# 5. 完成后，强制推送到远程（注意：这会重写历史）
git push --force origin main
```

### 方法 2：使用 git filter-branch

```bash
# 创建修复脚本
cat > fix_msg.sh << 'EOF'
#!/bin/sh
case "$GIT_COMMIT" in
    dfabafdbcce6613635e0c82ea14756df8b2a1236)
        echo "feat: R2-2 扩展 metadata.json 中的 AI 与运行信息 - 添加工具版本号、run_id、translation_ai、summary_ai 字段"
        ;;
    924ea563afa15412e4acb78fd0d3c0855a92d21b)
        echo "docs: 更新 AI 提供商扩展文档和测试文档"
        ;;
    0bdf0ccc74466d19f951b85f2a9fc2b38bcf5cfe)
        echo "feat: UI 模块功能增强和国际化完善"
        ;;
    *)
        cat
        ;;
esac
EOF

chmod +x fix_msg.sh

# 执行修复
export FILTER_BRANCH_SQUELCH_WARNING=1
git filter-branch --force --msg-filter ./fix_msg.sh dfabafd^..HEAD

# 强制推送
git push --force origin main
```

### 方法 3：接受现状（如果不想修改历史）

如果这些乱码不影响功能，也可以选择不修复。乱码只在 Git 历史记录中显示，不影响代码功能。

## 注意事项

⚠️ **重要**：修改已推送的提交历史需要 `--force` 推送，这会影响所有使用该仓库的人。如果其他人已经基于这些提交工作，需要协调。

## 正确的提交信息

- `dfabafd`: `feat: R2-2 扩展 metadata.json 中的 AI 与运行信息 - 添加工具版本号、run_id、translation_ai、summary_ai 字段`
- `924ea56`: `docs: 更新 AI 提供商扩展文档和测试文档`
- `0bdf0cc`: `feat: UI 模块功能增强和国际化完善`

