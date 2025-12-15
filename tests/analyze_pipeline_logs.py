"""
Pipeline 日志分析工具

分析 Pipeline 运行日志，提取：
- 各阶段耗时统计
- 错误类型分布
- 性能瓶颈识别
- 资源使用趋势
"""
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def parse_log_line(line: str) -> Optional[Dict]:
    """解析日志行
    
    Returns:
        解析后的日志信息，如果无法解析则返回 None
    """
    # 日志格式示例：
    # [2025-12-15 18:56:13.147] [INFO ] [run:20251215_185613] [task:detect] [video:jNQXAC9IVRw] 检测字幕: ...
    
    pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] \[(\w+)\s*\] \[run:([^\]]+)\] \[task:([^\]]+)\] \[video:([^\]]+)\] (.+)'
    match = re.match(pattern, line)
    
    if not match:
        return None
    
    timestamp_str, level, run_id, task, video_id, message = match.groups()
    
    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None
    
    return {
        "timestamp": timestamp,
        "level": level,
        "run_id": run_id,
        "task": task,
        "video_id": video_id,
        "message": message
    }


def analyze_log_file(log_file: Path) -> Dict:
    """分析日志文件
    
    Returns:
        分析结果字典
    """
    if not log_file.exists():
        print(f"错误: 日志文件不存在: {log_file}")
        return {}
    
    print(f"分析日志文件: {log_file}")
    print("=" * 80)
    
    # 统计数据
    stage_times = defaultdict(list)  # 各阶段的耗时
    stage_counts = defaultdict(lambda: {"processed": 0, "failed": 0})  # 各阶段的处理数
    error_types = defaultdict(int)  # 错误类型统计
    video_timeline = defaultdict(list)  # 每个视频的时间线
    
    current_video = None
    video_start_time = None
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            log_entry = parse_log_line(line.strip())
            if not log_entry:
                continue
            
            task = log_entry["task"]
            video_id = log_entry["video_id"]
            message = log_entry["message"]
            timestamp = log_entry["timestamp"]
            
            # 跟踪每个视频的时间线
            if video_id != current_video:
                if current_video and video_start_time:
                    # 计算上一个视频的总耗时
                    total_time = (timestamp - video_start_time).total_seconds()
                    video_timeline[current_video].append(("total", total_time))
                current_video = video_id
                video_start_time = timestamp
            
            # 检测阶段开始/结束
            if "检测字幕:" in message or "开始检测字幕:" in message:
                video_timeline[video_id].append(("detect_start", timestamp))
            elif "检测到字幕:" in message or "检测字幕完成:" in message:
                if video_timeline[video_id] and video_timeline[video_id][-1][0] == "detect_start":
                    detect_time = (timestamp - video_timeline[video_id][-1][1]).total_seconds()
                    stage_times["detect"].append(detect_time)
                    video_timeline[video_id].append(("detect_end", timestamp))
            
            # 下载阶段
            if "下载字幕:" in message:
                video_timeline[video_id].append(("download_start", timestamp))
            elif "字幕下载完成:" in message:
                if video_timeline[video_id] and video_timeline[video_id][-1][0] == "download_start":
                    download_time = (timestamp - video_timeline[video_id][-1][1]).total_seconds()
                    stage_times["download"].append(download_time)
                    video_timeline[video_id].append(("download_end", timestamp))
            
            # 翻译阶段
            if "翻译字幕:" in message:
                video_timeline[video_id].append(("translate_start", timestamp))
            elif "翻译完成:" in message:
                if video_timeline[video_id] and video_timeline[video_id][-1][0] == "translate_start":
                    translate_time = (timestamp - video_timeline[video_id][-1][1]).total_seconds()
                    stage_times["translate"].append(translate_time)
                    video_timeline[video_id].append(("translate_end", timestamp))
            
            # 摘要阶段
            if "生成摘要:" in message:
                video_timeline[video_id].append(("summarize_start", timestamp))
            elif "摘要生成完成:" in message:
                if video_timeline[video_id] and video_timeline[video_id][-1][0] == "summarize_start":
                    summarize_time = (timestamp - video_timeline[video_id][-1][1]).total_seconds()
                    stage_times["summarize"].append(summarize_time)
                    video_timeline[video_id].append(("summarize_end", timestamp))
            
            # 输出阶段
            if "写入输出文件:" in message:
                video_timeline[video_id].append(("output_start", timestamp))
            elif "输出文件写入完成:" in message or "处理完成:" in message:
                if video_timeline[video_id] and video_timeline[video_id][-1][0] == "output_start":
                    output_time = (timestamp - video_timeline[video_id][-1][1]).total_seconds()
                    stage_times["output"].append(output_time)
                    video_timeline[video_id].append(("output_end", timestamp))
            
            # 统计处理数
            if "处理完成:" in message and "失败" not in message.lower():
                stage_counts[task]["processed"] += 1
            elif "失败" in message.lower() or log_entry["level"] == "ERROR":
                stage_counts[task]["failed"] += 1
                # 提取错误类型
                if "error_type=" in message:
                    error_match = re.search(r'error_type=(\w+)', message)
                    if error_match:
                        error_types[error_match.group(1)] += 1
    
    # 打印分析结果
    print("\n各阶段耗时统计:")
    print("-" * 80)
    for stage, times in stage_times.items():
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            print(f"  {stage.upper():10s}: 平均 {avg_time:6.2f}s, 最小 {min_time:6.2f}s, 最大 {max_time:6.2f}s, 样本数 {len(times)}")
    
    print("\n各阶段处理统计:")
    print("-" * 80)
    for stage, counts in stage_counts.items():
        total = counts["processed"] + counts["failed"]
        if total > 0:
            success_rate = counts["processed"] / total * 100
            print(f"  {stage.upper():10s}: 处理 {counts['processed']:3d}, 失败 {counts['failed']:3d}, 成功率 {success_rate:5.1f}%")
    
    if error_types:
        print("\n错误类型分布:")
        print("-" * 80)
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_type:20s}: {count:3d}")
    
    # 识别性能瓶颈
    print("\n性能瓶颈分析:")
    print("-" * 80)
    if stage_times:
        avg_times = {stage: sum(times) / len(times) for stage, times in stage_times.items() if times}
        if avg_times:
            max_stage = max(avg_times.items(), key=lambda x: x[1])
            print(f"  最耗时阶段: {max_stage[0].upper()} (平均 {max_stage[1]:.2f} 秒)")
            
            # 计算各阶段占比
            total_avg = sum(avg_times.values())
            if total_avg > 0:
                print(f"  各阶段占比:")
                for stage, avg_time in sorted(avg_times.items(), key=lambda x: x[1], reverse=True):
                    percentage = avg_time / total_avg * 100
                    print(f"    {stage.upper():10s}: {percentage:5.1f}%")
    
    return {
        "stage_times": dict(stage_times),
        "stage_counts": dict(stage_counts),
        "error_types": dict(error_types),
        "video_timeline": dict(video_timeline)
    }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline 日志分析工具")
    parser.add_argument("log_file", type=Path, help="日志文件路径")
    parser.add_argument("--output", type=Path, help="输出分析结果到 JSON 文件")
    
    args = parser.parse_args()
    
    result = analyze_log_file(args.log_file)
    
    if args.output:
        import json
        
        # 转换不可序列化的对象
        serializable_result = {
            "stage_times": {k: v for k, v in result["stage_times"].items()},
            "stage_counts": result["stage_counts"],
            "error_types": result["error_types"],
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(serializable_result, f, indent=2, ensure_ascii=False)
        
        print(f"\n分析结果已保存到: {args.output}")


if __name__ == "__main__":
    main()

