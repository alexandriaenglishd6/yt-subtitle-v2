"""
Pipeline 监控脚本

实时监控 Pipeline 的运行状态，包括：
- 各阶段的队列大小
- 各阶段的处理进度
- 资源使用情况
- 错误统计
"""
import sys
import time
import os
import threading
from pathlib import Path
from typing import Optional

# 可选依赖：psutil（用于资源监控）
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("警告: psutil 未安装，将跳过资源监控。安装命令: pip install psutil")

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger
from config.manager import ConfigManager

logger = get_logger()


def monitor_staged_pipeline(pipeline, interval: float = 1.0, duration: Optional[float] = None):
    """监控分阶段 Pipeline 的运行状态
    
    Args:
        pipeline: StagedPipeline 实例
        interval: 监控间隔（秒）
        duration: 监控持续时间（秒），如果为 None 则持续监控直到 Pipeline 完成
    """
    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
    else:
        process = None
    
    start_time = time.time()
    
    print("\n开始监控 Pipeline...")
    print("=" * 80)
    
    try:
        while True:
            # 检查是否超时
            if duration and (time.time() - start_time) > duration:
                break
            
            # 获取各阶段统计
            detect_stats = pipeline.detect_queue.get_stats()
            download_stats = pipeline.download_queue.get_stats()
            translate_stats = pipeline.translate_queue.get_stats()
            summarize_stats = pipeline.summarize_queue.get_stats()
            output_stats = pipeline.output_queue.get_stats()
            
            # 获取队列大小
            detect_queue_size = pipeline.detect_queue.input_queue.qsize()
            download_queue_size = pipeline.download_queue.input_queue.qsize()
            translate_queue_size = pipeline.translate_queue.input_queue.qsize()
            summarize_queue_size = pipeline.summarize_queue.input_queue.qsize()
            output_queue_size = pipeline.output_queue.input_queue.qsize()
            
            # 获取资源使用
            if process:
                memory_mb = process.memory_info().rss / 1024 / 1024
                thread_count = len(process.threads())
            else:
                memory_mb = 0
                thread_count = threading.active_count()
            
            # 计算总进度
            total_processed = (
                detect_stats["processed"] + detect_stats["failed"] +
                download_stats["processed"] + download_stats["failed"] +
                translate_stats["processed"] + translate_stats["failed"] +
                summarize_stats["processed"] + summarize_stats["failed"] +
                output_stats["processed"] + output_stats["failed"]
            )
            
            # 清屏并显示状态
            print("\033[2J\033[H", end="")  # 清屏（Unix/Linux/Mac）
            print("Pipeline 监控面板")
            print("=" * 80)
            print(f"运行时间: {time.time() - start_time:.1f} 秒")
            print(f"内存使用: {memory_mb:.1f} MB")
            print(f"线程数量: {thread_count}")
            print()
            
            print("各阶段状态:")
            print(f"  DETECT:    处理 {detect_stats['processed']:3d}, 失败 {detect_stats['failed']:3d}, 队列 {detect_queue_size:3d}")
            print(f"  DOWNLOAD:  处理 {download_stats['processed']:3d}, 失败 {download_stats['failed']:3d}, 队列 {download_queue_size:3d}")
            print(f"  TRANSLATE: 处理 {translate_stats['processed']:3d}, 失败 {translate_stats['failed']:3d}, 队列 {translate_queue_size:3d}")
            print(f"  SUMMARIZE: 处理 {summarize_stats['processed']:3d}, 失败 {summarize_stats['failed']:3d}, 队列 {summarize_queue_size:3d}")
            print(f"  OUTPUT:    处理 {output_stats['processed']:3d}, 失败 {output_stats['failed']:3d}, 队列 {output_queue_size:3d}")
            print()
            
            # 检查是否完成
            if (pipeline.detect_queue.is_empty() and
                pipeline.download_queue.is_empty() and
                pipeline.translate_queue.is_empty() and
                pipeline.summarize_queue.is_empty() and
                pipeline.output_queue.is_empty()):
                print("✅ 所有阶段已完成")
                break
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"\n监控出错: {e}")
        import traceback
        traceback.print_exc()


def monitor_from_logs(log_file: Path, interval: float = 1.0):
    """从日志文件监控 Pipeline 状态
    
    Args:
        log_file: 日志文件路径
        interval: 检查间隔（秒）
    """
    if not log_file.exists():
        print(f"错误: 日志文件不存在: {log_file}")
        return
    
    print(f"监控日志文件: {log_file}")
    print("=" * 80)
    
    # 统计信息
    stage_counts = {
        "detect": {"processed": 0, "failed": 0},
        "download": {"processed": 0, "failed": 0},
        "translate": {"processed": 0, "failed": 0},
        "summarize": {"processed": 0, "failed": 0},
        "output": {"processed": 0, "failed": 0},
    }
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            # 读取到文件末尾
            f.seek(0, 2)  # 移动到文件末尾
            
            while True:
                line = f.readline()
                if not line:
                    time.sleep(interval)
                    continue
                
                # 解析日志行，提取阶段和状态信息
                # 这里需要根据实际日志格式进行解析
                # 示例：检测 "处理完成"、"失败" 等关键词
                
                # 更新统计
                # ...
                
                # 显示当前状态
                print("\033[2J\033[H", end="")
                print("Pipeline 日志监控")
                print("=" * 80)
                for stage, counts in stage_counts.items():
                    print(f"  {stage.upper()}: 处理 {counts['processed']}, 失败 {counts['failed']}")
                
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"\n监控出错: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline 监控工具")
    parser.add_argument("--log-file", type=Path, help="监控日志文件（而不是实时 Pipeline）")
    parser.add_argument("--interval", type=float, default=1.0, help="监控间隔（秒，默认 1.0）")
    
    args = parser.parse_args()
    
    if args.log_file:
        monitor_from_logs(args.log_file, args.interval)
    else:
        print("实时监控需要传入 Pipeline 实例")
        print("请使用 test_performance_comparison.py 进行测试，或修改此脚本以支持实时监控")

