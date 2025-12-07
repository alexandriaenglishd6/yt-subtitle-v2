"""
快速诊断脚本 - 检查 CLI 和模块导入
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("诊断测试：检查模块导入和基本功能")
print("=" * 60)

# 测试 1: 基本导入
print("\n1. 测试基本模块导入...")
try:
    from config.manager import ConfigManager
    print("  ✅ ConfigManager 导入成功")
except Exception as e:
    print(f"  ❌ ConfigManager 导入失败: {e}")
    sys.exit(1)

try:
    from core.logger import get_logger
    print("  ✅ get_logger 导入成功")
except Exception as e:
    print(f"  ❌ get_logger 导入失败: {e}")
    sys.exit(1)

try:
    from core.fetcher import VideoFetcher
    print("  ✅ VideoFetcher 导入成功")
except Exception as e:
    print(f"  ❌ VideoFetcher 导入失败: {e}")
    sys.exit(1)

try:
    from core.pipeline import process_single_video, process_video_list
    print("  ✅ pipeline 模块导入成功")
except Exception as e:
    print(f"  ❌ pipeline 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 2: CLI 函数导入
print("\n2. 测试 CLI 函数导入...")
try:
    import cli
    print("  ✅ cli 模块导入成功")
    
    if hasattr(cli, '_run_full_pipeline'):
        print("  ✅ _run_full_pipeline 函数存在")
    else:
        print("  ❌ _run_full_pipeline 函数不存在")
    
    if hasattr(cli, '_run_full_pipeline_for_urls'):
        print("  ✅ _run_full_pipeline_for_urls 函数存在")
    else:
        print("  ❌ _run_full_pipeline_for_urls 函数不存在")
        
except Exception as e:
    print(f"  ❌ cli 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 配置加载
print("\n3. 测试配置加载...")
try:
    config_manager = ConfigManager()
    config = config_manager.load()
    print(f"  ✅ 配置加载成功")
    print(f"     输出目录: {config.output_dir}")
    print(f"     UI 语言: {config.language.ui_language}")
    print(f"     目标语言: {config.language.subtitle_target_languages}")
except Exception as e:
    print(f"  ❌ 配置加载失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 4: CLI 命令解析
print("\n4. 测试 CLI 命令解析...")
try:
    import subprocess
    result = subprocess.run(
        ["python", "cli.py", "--help"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=10
    )
    if result.returncode == 0:
        print("  ✅ CLI --help 命令执行成功")
        print(f"     输出长度: {len(result.stdout)} 字符")
    else:
        print(f"  ❌ CLI --help 命令失败，退出码: {result.returncode}")
        if result.stderr:
            print(f"     错误: {result.stderr[:500]}")
except Exception as e:
    print(f"  ❌ CLI 命令测试异常: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 简单命令执行
print("\n5. 测试简单命令执行...")
try:
    import subprocess
    # 测试一个简单的命令（应该失败，因为没有提供 URL）
    result = subprocess.run(
        ["python", "cli.py", "channel", "--url", "https://www.youtube.com/watch?v=test", "--dry-run"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30
    )
    print(f"  ✅ 命令执行完成，退出码: {result.returncode}")
    if result.stdout:
        print(f"     标准输出长度: {len(result.stdout)} 字符")
        # 显示最后几行
        lines = result.stdout.strip().split('\n')
        if lines:
            print(f"     最后一行: {lines[-1][:100]}")
    if result.stderr:
        print(f"     错误输出长度: {len(result.stderr)} 字符")
        if "Error" in result.stderr or "error" in result.stderr:
            print(f"     错误信息: {result.stderr[:500]}")
except Exception as e:
    print(f"  ❌ 命令执行异常: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)

