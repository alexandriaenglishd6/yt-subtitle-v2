"""
Smoke Test - 自动化验证 CLI 完整流水线
测试小频道或 URL 列表，验证输出目录结构、文件数量、基本内容
"""
import sys
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.manager import ConfigManager, get_user_data_dir
from core.logger import get_logger

logger = get_logger()


# 测试配置
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 一个公开的测试视频（Rick Astley - Never Gonna Give You Up）
TEST_CHANNEL_URL = None  # 可以设置为一个小频道 URL，例如：https://www.youtube.com/@testchannel
TEST_URLS_FILE = None  # 可以设置为一个包含少量 URL 的文件路径


def run_cli_command(cmd: List[str], timeout: int = 300) -> Dict[str, any]:
    """运行 CLI 命令
    
    Args:
        cmd: 命令列表
        timeout: 超时时间（秒）
    
    Returns:
        结果字典：{"success": bool, "returncode": int, "stdout": str, "stderr": str}
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令执行超时（{timeout}秒）"
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }


def check_output_structure(output_dir: Path, video_id: str, expect_channel: bool = False) -> Dict[str, bool]:
    """检查输出目录结构
    
    Args:
        output_dir: 输出目录路径
        video_id: 视频 ID
        expect_channel: 是否期望频道模式（有频道子目录）
    
    Returns:
        检查结果字典
    """
    results = {
        "output_dir_exists": output_dir.exists(),
        "video_dir_exists": False,
        "original_subtitle_exists": False,
        "translated_subtitle_exists": False,
        "summary_exists": False,
        "metadata_exists": False,
        "metadata_valid": False
    }
    
    if not results["output_dir_exists"]:
        return results
    
    # 查找视频目录
    video_dir = None
    if expect_channel:
        # 频道模式：out/频道名称 [UCxxxxxx]/video_id .../
        for item in output_dir.iterdir():
            if item.is_dir() and "[" in item.name:
                # 这是频道目录
                for sub_item in item.iterdir():
                    if sub_item.is_dir() and video_id in sub_item.name:
                        video_dir = sub_item
                        break
                if video_dir:
                    break
    else:
        # 单视频或 URL 列表模式：out/video_id .../
        for item in output_dir.iterdir():
            if item.is_dir() and video_id in item.name:
                video_dir = item
                break
    
    if video_dir and video_dir.exists():
        results["video_dir_exists"] = True
        
        # 检查文件
        for file in video_dir.iterdir():
            if file.is_file():
                name = file.name
                if name.startswith("original.") and name.endswith(".srt"):
                    results["original_subtitle_exists"] = True
                elif name.startswith("translated.") and name.endswith(".srt"):
                    results["translated_subtitle_exists"] = True
                elif name.startswith("summary.") and name.endswith(".md"):
                    results["summary_exists"] = True
                elif name == "metadata.json":
                    results["metadata_exists"] = True
                    # 验证 metadata.json 内容
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            if isinstance(metadata, dict) and "video_id" in metadata:
                                results["metadata_valid"] = True
                    except Exception:
                        pass
    
    return results


def check_failure_logs(output_dir: Path) -> Dict[str, bool]:
    """检查失败记录文件
    
    Args:
        output_dir: 输出目录路径
    
    Returns:
        检查结果字典
    """
    results = {
        "failed_detail_log_exists": False,
        "failed_urls_txt_exists": False
    }
    
    failed_detail = output_dir / "failed_detail.log"
    failed_urls = output_dir / "failed_urls.txt"
    
    results["failed_detail_log_exists"] = failed_detail.exists()
    results["failed_urls_txt_exists"] = failed_urls.exists()
    
    return results


def test_single_video():
    """测试单视频处理
    
    Returns:
        测试结果
    """
    print("\n" + "=" * 60)
    print("测试场景 1: 单视频处理")
    print("=" * 60)
    
    if not TEST_VIDEO_URL:
        print("⚠️  未配置测试视频 URL，跳过此测试")
        return {"success": False, "skipped": True}
    
    # 加载配置获取输出目录
    config_manager = ConfigManager()
    config = config_manager.load()
    output_dir = Path(config.output_dir)
    
    # 清理之前的输出（可选）
    # 注意：实际测试中可能不想清理，以便验证增量功能
    
    # 运行 CLI 命令
    print(f"\n执行命令: python cli.py channel --url {TEST_VIDEO_URL} --run")
    cmd = ["python", "cli.py", "channel", "--url", TEST_VIDEO_URL, "--run"]
    result = run_cli_command(cmd, timeout=180)
    
    if not result["success"]:
        print(f"❌ CLI 命令执行失败")
        print(f"返回码: {result['returncode']}")
        print(f"错误输出: {result['stderr'][:500]}")
        return {"success": False, "error": result["stderr"]}
    
    print("✅ CLI 命令执行成功")
    
    # 提取视频 ID
    video_id = "jNQXAC9IVRw"  # 从 URL 提取
    
    # 检查输出目录结构
    print(f"\n检查输出目录: {output_dir}")
    structure_results = check_output_structure(output_dir, video_id, expect_channel=False)
    
    print("\n输出结构检查结果:")
    print(f"  - 输出目录存在: {'✅' if structure_results['output_dir_exists'] else '❌'}")
    print(f"  - 视频目录存在: {'✅' if structure_results['video_dir_exists'] else '❌'}")
    print(f"  - 原始字幕存在: {'✅' if structure_results['original_subtitle_exists'] else '❌'}")
    print(f"  - 翻译字幕存在: {'✅' if structure_results['translated_subtitle_exists'] else '❌'}")
    print(f"  - 摘要文件存在: {'✅' if structure_results['summary_exists'] else '❌'}")
    print(f"  - 元数据存在: {'✅' if structure_results['metadata_exists'] else '❌'}")
    print(f"  - 元数据有效: {'✅' if structure_results['metadata_valid'] else '❌'}")
    
    # 检查失败记录
    failure_results = check_failure_logs(output_dir)
    print(f"\n失败记录检查:")
    print(f"  - failed_detail.log 存在: {'✅' if failure_results['failed_detail_log_exists'] else '⚠️  (可选)'}")
    print(f"  - failed_urls.txt 存在: {'✅' if failure_results['failed_urls_txt_exists'] else '⚠️  (可选)'}")
    
    # 判断测试是否通过
    required_checks = [
        structure_results['output_dir_exists'],
        structure_results['video_dir_exists'],
        structure_results['original_subtitle_exists'],
        structure_results['metadata_exists'],
        structure_results['metadata_valid']
    ]
    
    success = all(required_checks)
    
    if success:
        print("\n✅ 单视频处理测试通过")
    else:
        print("\n❌ 单视频处理测试失败")
    
    return {
        "success": success,
        "structure_results": structure_results,
        "failure_results": failure_results
    }


def test_dry_run():
    """测试 Dry Run 模式
    
    Returns:
        测试结果
    """
    print("\n" + "=" * 60)
    print("测试场景 2: Dry Run 模式（仅检测）")
    print("=" * 60)
    
    if not TEST_VIDEO_URL:
        print("⚠️  未配置测试视频 URL，跳过此测试")
        return {"success": False, "skipped": True}
    
    # 运行 Dry Run 命令
    print(f"\n执行命令: python cli.py channel --url {TEST_VIDEO_URL} --dry-run")
    cmd = ["python", "cli.py", "channel", "--url", TEST_VIDEO_URL, "--dry-run"]
    result = run_cli_command(cmd, timeout=60)
    
    if not result["success"]:
        print(f"❌ Dry Run 命令执行失败")
        print(f"返回码: {result['returncode']}")
        print(f"错误输出: {result['stderr'][:500]}")
        return {"success": False, "error": result["stderr"]}
    
    print("✅ Dry Run 命令执行成功")
    
    # 检查日志输出中是否包含检测信息
    stdout = result["stdout"]
    has_detection_info = "检测" in stdout or "字幕" in stdout or "subtitle" in stdout.lower()
    
    print(f"\n日志检查:")
    print(f"  - 包含检测信息: {'✅' if has_detection_info else '⚠️'}")
    
    # Dry Run 不应该生成输出文件（但可能有失败记录）
    config_manager = ConfigManager()
    config = config_manager.load()
    output_dir = Path(config.output_dir)
    
    # 检查是否有新生成的视频目录（Dry Run 不应该生成）
    video_id = "jNQXAC9IVRw"
    structure_results = check_output_structure(output_dir, video_id, expect_channel=False)
    
    # Dry Run 模式下，如果之前没有运行过完整流程，不应该有输出
    # 这里只检查命令执行成功和日志输出
    
    success = result["success"] and has_detection_info
    
    if success:
        print("\n✅ Dry Run 测试通过")
    else:
        print("\n❌ Dry Run 测试失败")
    
    return {
        "success": success,
        "has_detection_info": has_detection_info
    }


def test_urls_list():
    """测试 URL 列表模式
    
    Returns:
        测试结果
    """
    print("\n" + "=" * 60)
    print("测试场景 3: URL 列表模式")
    print("=" * 60)
    
    if not TEST_URLS_FILE or not Path(TEST_URLS_FILE).exists():
        print("⚠️  未配置测试 URL 列表文件，跳过此测试")
        return {"success": False, "skipped": True}
    
    # 运行 URL 列表命令
    print(f"\n执行命令: python cli.py urls --file {TEST_URLS_FILE} --run")
    cmd = ["python", "cli.py", "urls", "--file", TEST_URLS_FILE, "--run"]
    result = run_cli_command(cmd, timeout=300)
    
    if not result["success"]:
        print(f"❌ URL 列表命令执行失败")
        print(f"返回码: {result['returncode']}")
        print(f"错误输出: {result['stderr'][:500]}")
        return {"success": False, "error": result["stderr"]}
    
    print("✅ URL 列表命令执行成功")
    
    # 检查输出目录
    config_manager = ConfigManager()
    config = config_manager.load()
    output_dir = Path(config.output_dir)
    
    # 读取 URL 列表文件，提取视频 ID
    video_ids = []
    try:
        with open(TEST_URLS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and "youtube.com" in line:
                    # 简单提取视频 ID（实际应该用更可靠的方法）
                    if "watch?v=" in line:
                        video_id = line.split("watch?v=")[1].split("&")[0]
                        if len(video_id) == 11:
                            video_ids.append(video_id)
    except Exception as e:
        print(f"⚠️  读取 URL 列表文件失败: {e}")
        return {"success": False, "error": str(e)}
    
    print(f"\n检查 {len(video_ids)} 个视频的输出...")
    
    success_count = 0
    for video_id in video_ids:
        structure_results = check_output_structure(output_dir, video_id, expect_channel=False)
        if structure_results['video_dir_exists'] and structure_results['original_subtitle_exists']:
            success_count += 1
    
    print(f"\n输出检查结果: {success_count}/{len(video_ids)} 个视频有完整输出")
    
    success = success_count > 0  # 至少有一个视频成功
    
    if success:
        print("\n✅ URL 列表模式测试通过")
    else:
        print("\n❌ URL 列表模式测试失败")
    
    return {
        "success": success,
        "success_count": success_count,
        "total_count": len(video_ids)
    }


def main():
    """主测试函数"""
    print("=" * 60)
    print("YouTube 字幕工具 v2 - Smoke Test")
    print("=" * 60)
    print("\n本测试将验证 CLI 完整流水线的功能：")
    print("  - 单视频处理")
    print("  - Dry Run 模式")
    print("  - URL 列表模式（如果配置）")
    print("  - 输出目录结构")
    print("  - 文件存在性")
    print("\n注意：")
    print("  - 测试需要网络连接和 yt-dlp")
    print("  - 测试可能需要几分钟时间")
    print("  - 某些测试可能因为网络问题失败，这是正常的")
    
    results = []
    
    # 测试 1: 单视频处理
    try:
        result1 = test_single_video()
        results.append(("单视频处理", result1))
    except Exception as e:
        print(f"\n❌ 单视频处理测试异常: {e}")
        results.append(("单视频处理", {"success": False, "error": str(e)}))
    
    # 测试 2: Dry Run
    try:
        result2 = test_dry_run()
        results.append(("Dry Run", result2))
    except Exception as e:
        print(f"\n❌ Dry Run 测试异常: {e}")
        results.append(("Dry Run", {"success": False, "error": str(e)}))
    
    # 测试 3: URL 列表模式（如果配置）
    if TEST_URLS_FILE and Path(TEST_URLS_FILE).exists():
        try:
            result3 = test_urls_list()
            results.append(("URL 列表模式", result3))
        except Exception as e:
            print(f"\n❌ URL 列表模式测试异常: {e}")
            results.append(("URL 列表模式", {"success": False, "error": str(e)}))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, result in results:
        if result.get("skipped"):
            status = "⏭️  跳过"
            skipped += 1
        elif result.get("success"):
            status = "✅ 通过"
            passed += 1
        else:
            status = "❌ 失败"
            failed += 1
        
        print(f"{test_name}: {status}")
        if "error" in result:
            print(f"  错误: {result['error'][:100]}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败, {skipped} 跳过")
    
    if failed == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
