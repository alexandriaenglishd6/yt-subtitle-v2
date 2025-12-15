"""
性能对比测试脚本

对比新旧架构的处理性能，包括：
- 总处理时间
- 各阶段耗时
- 资源使用（内存、线程）
- 成功率
"""
import sys
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

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

from core.models import VideoInfo
from core.pipeline import process_video_list
from core.language import LanguageConfig
from core.output import OutputWriter
from core.failure_logger import FailureLogger
from core.incremental import IncrementalManager
from core.cancel_token import CancelToken
from config.manager import ConfigManager
from cli.utils import create_llm_clients
import tempfile
import shutil
import threading


@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_time: float  # 总处理时间（秒）
    avg_time_per_video: float  # 平均每个视频的处理时间（秒）
    peak_memory_mb: float  # 峰值内存使用（MB）
    avg_memory_mb: float  # 平均内存使用（MB）
    success_count: int  # 成功数
    failed_count: int  # 失败数
    stage_times: Dict[str, float]  # 各阶段耗时（如果可获取）


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self):
        if HAS_PSUTIL:
            self.process = psutil.Process(os.getpid())
        else:
            self.process = None
        self.memory_samples = []
        self.thread_samples = []
        self.monitoring = False
        self.monitor_thread = None
    
    def start(self):
        """开始监控"""
        self.monitoring = True
        self.memory_samples = []
        self.thread_samples = []
        
        def monitor_loop():
            while self.monitoring:
                try:
                    if self.process:
                        # 内存使用（MB）
                        memory_mb = self.process.memory_info().rss / 1024 / 1024
                        self.memory_samples.append(memory_mb)
                    
                    # 线程数量
                    thread_count = threading.active_count()
                    self.thread_samples.append(thread_count)
                    
                    time.sleep(0.5)  # 每 0.5 秒采样一次
                except Exception:
                    break
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
    
    def get_metrics(self) -> Dict[str, float]:
        """获取监控指标"""
        if not self.memory_samples:
            return {
                "peak_memory_mb": 0,
                "avg_memory_mb": 0,
                "peak_threads": 0,
                "avg_threads": 0
            }
        
        return {
            "peak_memory_mb": max(self.memory_samples),
            "avg_memory_mb": sum(self.memory_samples) / len(self.memory_samples),
            "peak_threads": max(self.thread_samples) if self.thread_samples else 0,
            "avg_threads": sum(self.thread_samples) / len(self.thread_samples) if self.thread_samples else 0
        }


def test_architecture(
    videos: List[VideoInfo],
    use_staged: bool,
    concurrency: int = 10,
    test_name: str = ""
) -> PerformanceMetrics:
    """测试指定架构的性能
    
    Args:
        videos: 视频列表
        use_staged: 是否使用分阶段 Pipeline
        concurrency: 并发数
        test_name: 测试名称（用于日志）
    
    Returns:
        性能指标
    """
    print(f"\n{'=' * 60}")
    print(f"测试: {test_name}")
    print(f"架构: {'分阶段 Pipeline' if use_staged else '旧架构 (TaskRunner)'}")
    print(f"视频数量: {len(videos)}")
    print(f"并发数: {concurrency}")
    print(f"{'=' * 60}")
    
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.load()
    
    # 创建临时输出目录
    temp_output_dir = Path(tempfile.mkdtemp(prefix=f"perf_test_{test_name}_"))
    
    try:
        # 创建必要的组件
        language_config = config.language
        output_writer = OutputWriter(temp_output_dir)
        failure_logger = FailureLogger(temp_output_dir)
        incremental_manager = IncrementalManager()
        archive_path = temp_output_dir / "archive.txt"
        
        # 创建 LLM 客户端
        from core.logger import get_logger
        logger = get_logger()
        translation_llm, summary_llm = create_llm_clients(config, logger)
        
        # 创建资源监控器
        monitor = ResourceMonitor()
        monitor.start()
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行处理
        result = process_video_list(
            videos=videos,
            language_config=language_config,
            translation_llm=translation_llm,
            summary_llm=summary_llm,
            output_writer=output_writer,
            failure_logger=failure_logger,
            incremental_manager=incremental_manager,
            archive_path=archive_path,
            force=True,  # 强制重跑，避免增量影响
            dry_run=False,
            cancel_token=None,
            concurrency=concurrency,
            proxy_manager=None,
            cookie_manager=None,
            on_stats=None,
            on_log=None,
            use_staged_pipeline=use_staged,  # 关键参数
        )
        
        # 记录结束时间
        end_time = time.time()
        
        # 停止监控
        monitor.stop()
        resource_metrics = monitor.get_metrics()
        
        # 计算性能指标
        total_time = end_time - start_time
        avg_time_per_video = total_time / len(videos) if videos else 0
        
        metrics = PerformanceMetrics(
            total_time=total_time,
            avg_time_per_video=avg_time_per_video,
            peak_memory_mb=resource_metrics["peak_memory_mb"],
            avg_memory_mb=resource_metrics["avg_memory_mb"],
            success_count=result.get("success", 0),
            failed_count=result.get("failed", 0),
            stage_times={}  # 分阶段 Pipeline 的详细耗时需要从日志中提取
        )
        
        # 打印结果
        print(f"\n处理完成！")
        print(f"总处理时间: {metrics.total_time:.2f} 秒")
        print(f"平均每个视频: {metrics.avg_time_per_video:.2f} 秒")
        print(f"成功率: {metrics.success_count}/{len(videos)} ({metrics.success_count * 100 // len(videos) if videos else 0}%)")
        print(f"峰值内存: {metrics.peak_memory_mb:.2f} MB")
        print(f"平均内存: {metrics.avg_memory_mb:.2f} MB")
        print(f"峰值线程数: {resource_metrics['peak_threads']}")
        print(f"平均线程数: {resource_metrics['avg_threads']:.1f}")
        
        return metrics
        
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_output_dir)
        except Exception as e:
            print(f"清理临时目录失败: {e}")


def compare_architectures(
    videos: List[VideoInfo],
    concurrency: int = 10
):
    """对比新旧架构的性能
    
    Args:
        videos: 视频列表
        concurrency: 并发数
    """
    print("\n" + "=" * 60)
    print("性能对比测试")
    print("=" * 60)
    print(f"测试视频数量: {len(videos)}")
    print(f"并发数: {concurrency}")
    
    # 测试新架构
    staged_metrics = test_architecture(
        videos=videos,
        use_staged=True,
        concurrency=concurrency,
        test_name="新架构（分阶段 Pipeline）"
    )
    
    # 等待一下，让资源释放
    time.sleep(2)
    
    # 测试旧架构
    old_metrics = test_architecture(
        videos=videos,
        use_staged=False,
        concurrency=concurrency,
        test_name="旧架构（TaskRunner）"
    )
    
    # 对比结果
    print("\n" + "=" * 60)
    print("性能对比结果")
    print("=" * 60)
    
    print(f"\n总处理时间:")
    print(f"  新架构: {staged_metrics.total_time:.2f} 秒")
    print(f"  旧架构: {old_metrics.total_time:.2f} 秒")
    if old_metrics.total_time > 0:
        speedup = (old_metrics.total_time - staged_metrics.total_time) / old_metrics.total_time * 100
        print(f"  性能变化: {speedup:+.1f}%")
    
    print(f"\n平均每个视频:")
    print(f"  新架构: {staged_metrics.avg_time_per_video:.2f} 秒")
    print(f"  旧架构: {old_metrics.avg_time_per_video:.2f} 秒")
    
    print(f"\n内存使用:")
    print(f"  新架构 - 峰值: {staged_metrics.peak_memory_mb:.2f} MB, 平均: {staged_metrics.avg_memory_mb:.2f} MB")
    print(f"  旧架构 - 峰值: {old_metrics.peak_memory_mb:.2f} MB, 平均: {old_metrics.avg_memory_mb:.2f} MB")
    
    print(f"\n成功率:")
    print(f"  新架构: {staged_metrics.success_count}/{len(videos)} ({staged_metrics.success_count * 100 // len(videos) if videos else 0}%)")
    print(f"  旧架构: {old_metrics.success_count}/{len(videos)} ({old_metrics.success_count * 100 // len(videos) if videos else 0}%)")
    
    # 判断结果
    if staged_metrics.success_count == old_metrics.success_count:
        print("\n✅ 功能一致性: 通过（成功率相同）")
    else:
        print(f"\n⚠️  功能一致性: 警告（成功率不同：新架构 {staged_metrics.success_count} vs 旧架构 {old_metrics.success_count}）")
    
    if staged_metrics.total_time <= old_metrics.total_time * 1.1:  # 允许 10% 的性能差异
        print("✅ 性能: 通过（新架构性能相当或更好）")
    else:
        print("⚠️  性能: 警告（新架构性能下降）")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="性能对比测试")
    parser.add_argument("--url", type=str, help="测试视频 URL 或频道 URL")
    parser.add_argument("--count", type=int, default=10, help="测试视频数量（默认 10）")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数（默认 10）")
    parser.add_argument("--only-staged", action="store_true", help="只测试新架构")
    parser.add_argument("--only-old", action="store_true", help="只测试旧架构")
    
    args = parser.parse_args()
    
    if not args.url:
        print("错误: 请提供测试视频 URL 或频道 URL")
        print("用法: python tests/test_performance_comparison.py --url <URL> [--count <数量>] [--concurrency <并发数>]")
        sys.exit(1)
    
    # 获取视频列表
    print("正在获取视频列表...")
    from core.fetcher import VideoFetcher
    from config.manager import ConfigManager
    
    config = ConfigManager().load()
    
    # 创建 Cookie 管理器（如果配置中存在）
    from core.cookie_manager import CookieManager
    cookie_manager = None
    if config.cookie:
        cookie_manager = CookieManager(cookie_string=config.cookie)
    
    fetcher = VideoFetcher(proxy_manager=None, cookie_manager=cookie_manager)
    
    try:
        videos = fetcher.fetch_from_url(args.url)  # 使用正确的方法名
        if not videos:
            print("错误: 无法获取视频列表")
            sys.exit(1)
        
        # 限制视频数量
        if len(videos) > args.count:
            videos = videos[:args.count]
            print(f"限制测试视频数量为 {args.count}")
        
        print(f"获取到 {len(videos)} 个视频")
        
        # 执行测试
        if args.only_staged:
            test_architecture(
                videos=videos,
                use_staged=True,
                concurrency=args.concurrency,
                test_name="新架构（分阶段 Pipeline）"
            )
        elif args.only_old:
            test_architecture(
                videos=videos,
                use_staged=False,
                concurrency=args.concurrency,
                test_name="旧架构（TaskRunner）"
            )
        else:
            compare_architectures(videos=videos, concurrency=args.concurrency)
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

