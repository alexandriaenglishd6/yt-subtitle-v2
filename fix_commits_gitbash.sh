#!/bin/bash
# Script to fix commit messages with encoding issues
# Run this in Git Bash: bash fix_commits_gitbash.sh

set -e

echo "Fixing commit messages with encoding issues..."
echo ""

# Create message filter script
cat > /tmp/fix_msg_filter.sh << 'EOF'
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

chmod +x /tmp/fix_msg_filter.sh

# Set environment variable
export FILTER_BRANCH_SQUELCH_WARNING=1

# Run git filter-branch
echo "Running git filter-branch..."
git filter-branch --force --msg-filter /tmp/fix_msg_filter.sh dfabafd^..HEAD

# Check result
echo ""
echo "Checking results..."
git log --format="%h %s" dfabafd^..HEAD

echo ""
echo "Done! Please review the changes above."
echo ""
echo "If the commit messages look correct, force push to remote:"
echo "  git push --force origin main"
echo ""
echo "WARNING: Force push will rewrite history. Make sure no one else is working on this branch."

# Clean up
rm -f /tmp/fix_msg_filter.sh

