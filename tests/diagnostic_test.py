"""
快速诊断脚本 - 检查 CLI 和模块导入
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("诊断测试：检查模块导入和基本功能")
print("=" * 60)

# 测试 1: 基本导入
print("\n1. 测试基本模块导入...")
try:
    from config.manager import ConfigManager
    print("  [OK] ConfigManager 导入成功")
except Exception as e:
    print(f"  [FAIL] ConfigManager 导入失败: {e}")
    sys.exit(1)

try:
    from core.logger import get_logger
    print("  [OK] get_logger 导入成功")
except Exception as e:
    print(f"  [FAIL] get_logger 导入失败: {e}")
    sys.exit(1)

try:
    from core.fetcher import VideoFetcher
    print("  [OK] VideoFetcher 导入成功")
except Exception as e:
    print(f"  [FAIL] VideoFetcher 导入失败: {e}")
    sys.exit(1)

try:
    from core.detector import SubtitleDetector
    print("  [OK] SubtitleDetector 导入成功")
except Exception as e:
    print(f"  [FAIL] SubtitleDetector 导入失败: {e}")
    sys.exit(1)

# 测试 2: CLI 模块导入
print("\n2. 测试 CLI 模块导入...")
try:
    from cli.main import main as cli_main
    print("  [OK] CLI main 导入成功")
except Exception as e:
    print(f"  [FAIL] CLI main 导入失败: {e}")
    sys.exit(1)

try:
    from cli.channel import channel_command
    print("  [OK] channel_command 导入成功")
except Exception as e:
    print(f"  [FAIL] channel_command 导入失败: {e}")
    sys.exit(1)

try:
    from cli.urls import urls_command
    print("  [OK] urls_command 导入成功")
except Exception as e:
    print(f"  [FAIL] urls_command 导入失败: {e}")
    sys.exit(1)

# 测试 3: 配置加载
print("\n3. 测试配置加载...")
try:
    config_manager = ConfigManager()
    app_config = config_manager.load()
    print("  [OK] 配置加载成功")
    print(f"    输出目录: {app_config.output_dir}")
    print(f"    并发数: {app_config.concurrency}")
except Exception as e:
    print(f"  [FAIL] 配置加载失败: {e}")
    sys.exit(1)

# 测试 4: Logger 初始化
print("\n4. 测试 Logger 初始化...")
try:
    logger = get_logger()
    logger.info("测试日志消息")
    print("  [OK] Logger 初始化成功")
except Exception as e:
    print(f"  [FAIL] Logger 初始化失败: {e}")
    sys.exit(1)

# 测试 5: VideoFetcher 初始化
print("\n5. 测试 VideoFetcher 初始化...")
try:
    fetcher = VideoFetcher()
    print("  [OK] VideoFetcher 初始化成功")
except Exception as e:
    print(f"  [FAIL] VideoFetcher 初始化失败: {e}")
    sys.exit(1)

# 测试 6: SubtitleDetector 初始化
print("\n6. 测试 SubtitleDetector 初始化...")
try:
    detector = SubtitleDetector()
    print("  [OK] SubtitleDetector 初始化成功")
except Exception as e:
    print(f"  [FAIL] SubtitleDetector 初始化失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] 所有诊断测试通过！")
print("=" * 60)

