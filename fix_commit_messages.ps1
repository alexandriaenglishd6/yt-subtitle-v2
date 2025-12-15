# PowerShell script to fix commit messages with encoding issues
# This script uses git filter-branch to fix the commit messages

Write-Host "Fixing commit messages with encoding issues..."
Write-Host ""

# Set encoding
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Create a temporary script file for the message filter
$filterScript = @'
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
'@

# Write the script to a temporary file
$filterScript | Out-File -FilePath "temp_msg_filter.sh" -Encoding UTF8 -NoNewline

# Make it executable (if on Unix-like system)
if (Get-Command chmod -ErrorAction SilentlyContinue) {
    chmod +x temp_msg_filter.sh
}

# Set environment variable to suppress warning
$env:FILTER_BRANCH_SQUELCH_WARNING = "1"

# Run git filter-branch
Write-Host "Running git filter-branch..."
& git filter-branch --force --msg-filter "bash temp_msg_filter.sh" dfabafd^..HEAD

# Check if it worked
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Success! Commit messages have been fixed."
    Write-Host ""
    Write-Host "Please review the changes:"
    Write-Host "  git log --oneline dfabafd^..HEAD"
    Write-Host ""
    Write-Host "If satisfied, force push to remote:"
    Write-Host "  git push --force origin main"
    Write-Host ""
    Write-Host "WARNING: Force push will rewrite history. Make sure no one else is working on this branch."
} else {
    Write-Host ""
    Write-Host "Error: git filter-branch failed. Please check the error messages above."
    Write-Host "You may need to run this script in Git Bash instead of PowerShell."
}

# Clean up
if (Test-Path "temp_msg_filter.sh") {
    Remove-Item "temp_msg_filter.sh"
}

