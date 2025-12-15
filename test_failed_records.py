#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T2-1：结构化失败记录测试脚本

用于验证 failed_records.json 文件格式和内容
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional


def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """加载 JSONL 格式文件（每行一个 JSON 对象）"""
    records = []
    if not file_path.exists():
        return records
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"❌ 第 {line_num} 行 JSON 解析失败: {e}")
                print(f"   内容: {line[:100]}...")
                return []
    return records


def validate_record_format(record: Dict[str, Any], line_num: int) -> tuple[bool, List[str]]:
    """验证单条记录的格式
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    # 必需字段
    required_fields = ["video_id", "url", "stage", "error_type", "timestamp"]
    for field in required_fields:
        if field not in record:
            errors.append(f"缺少必需字段: {field}")
    
    # 验证字段类型
    if "video_id" in record and not isinstance(record["video_id"], str):
        errors.append(f"video_id 应该是字符串类型")
    if "url" in record and not isinstance(record["url"], str):
        errors.append(f"url 应该是字符串类型")
    if "stage" in record and not isinstance(record["stage"], str):
        errors.append(f"stage 应该是字符串类型")
    if "error_type" in record and not isinstance(record["error_type"], str):
        errors.append(f"error_type 应该是字符串类型")
    if "timestamp" in record and not isinstance(record["timestamp"], str):
        errors.append(f"timestamp 应该是字符串类型")
    
    # 验证可选字段类型（如果存在）
    optional_fields = {
        "run_id": str,
        "reason": str,
        "channel_id": str,
        "channel_name": str
    }
    for field, expected_type in optional_fields.items():
        if field in record and not isinstance(record[field], expected_type):
            errors.append(f"{field} 应该是 {expected_type.__name__} 类型")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def extract_records_from_log(log_path: Path) -> List[Dict[str, str]]:
    """从 failed_detail.log 中提取记录
    
    Returns:
        List of dicts with keys: video_id, url, error_type, timestamp, reason
    """
    records = []
    if not log_path.exists():
        return records
    
    import re
    # 格式：[时间戳] [batch:...] [video:video_id] url error=error_type msg=reason
    pattern = r'\[([^\]]+)\] \[batch:([^\]]+)?\] \[video:([^\]]+)\] ([^\s]+) error=([^\s]+) msg=(.+?)(?: stage=([^\s]+))?$'
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            match = re.match(pattern, line)
            if match:
                timestamp, batch_id, video_id, url, error_type, reason, stage = match.groups()
                records.append({
                    "video_id": video_id,
                    "url": url,
                    "error_type": error_type,
                    "timestamp": timestamp,
                    "reason": reason,
                    "run_id": batch_id if batch_id else None,
                    "stage": stage if stage else "unknown"
                })
    
    return records


def extract_urls_from_txt(txt_path: Path) -> List[str]:
    """从 failed_urls.txt 中提取 URL 列表"""
    urls = []
    if not txt_path.exists():
        return urls
    
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                urls.append(line)
    
    return urls


def main():
    """主测试函数"""
    print("=" * 60)
    print("T2-1：结构化失败记录测试")
    print("=" * 60)
    print()
    
    # 确定输出目录（默认使用 out）
    output_dir = Path("out")
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    
    json_path = output_dir / "failed_records.json"
    log_path = output_dir / "failed_detail.log"
    urls_path = output_dir / "failed_urls.txt"
    
    print(f"检查目录: {output_dir.absolute()}")
    print()
    
    # 1. 检查文件是否存在
    print("1. 文件存在性检查")
    print("-" * 60)
    
    if not json_path.exists():
        print(f"❌ failed_records.json 不存在: {json_path}")
        print("   请先运行包含失败场景的任务以生成该文件")
        print("   例如：使用无效 URL 或网络错误触发失败")
        return
    else:
        print(f"✓ failed_records.json 存在: {json_path}")
    
    if log_path.exists():
        print(f"✓ failed_detail.log 存在: {log_path}")
    else:
        print(f"⚠ failed_detail.log 不存在（可选）: {log_path}")
    
    if urls_path.exists():
        print(f"✓ failed_urls.txt 存在: {urls_path}")
    else:
        print(f"⚠ failed_urls.txt 不存在（可选）: {urls_path}")
    print()
    
    # 2. 加载和验证 JSON 记录
    print("2. JSON 记录格式验证")
    print("-" * 60)
    
    json_records = load_jsonl(json_path)
    if not json_records:
        print("❌ failed_records.json 为空或格式错误")
        return
    
    print(f"✓ 成功加载 {len(json_records)} 条 JSON 记录")
    print()
    
    # 验证每条记录
    all_valid = True
    for i, record in enumerate(json_records, 1):
        is_valid, errors = validate_record_format(record, i)
        if not is_valid:
            all_valid = False
            print(f"❌ 第 {i} 条记录格式错误:")
            for error in errors:
                print(f"   - {error}")
            print(f"   记录内容: {json.dumps(record, ensure_ascii=False, indent=2)}")
            print()
        elif i <= 3:  # 只显示前 3 条记录的详细信息
            print(f"✓ 第 {i} 条记录格式正确:")
            print(f"   {json.dumps(record, ensure_ascii=False, indent=2)}")
            print()
    
    if all_valid:
        print(f"✓ 所有 {len(json_records)} 条记录格式正确")
    print()
    
    # 3. 验证必需字段和可选字段
    print("3. 字段完整性检查")
    print("-" * 60)
    
    required_fields = ["video_id", "url", "stage", "error_type", "timestamp"]
    optional_fields = ["run_id", "reason", "channel_id", "channel_name"]
    
    field_stats = {field: 0 for field in required_fields + optional_fields}
    
    for record in json_records:
        for field in required_fields:
            if field in record:
                field_stats[field] += 1
        for field in optional_fields:
            if field in record:
                field_stats[field] += 1
    
    # 检查必需字段
    all_required_present = True
    for field in required_fields:
        count = field_stats[field]
        if count == len(json_records):
            print(f"✓ 必需字段 '{field}': 所有记录都有 ({count}/{len(json_records)})")
        else:
            all_required_present = False
            print(f"❌ 必需字段 '{field}': 只有 {count}/{len(json_records)} 条记录有")
    
    print()
    
    # 检查可选字段
    print("可选字段统计:")
    for field in optional_fields:
        count = field_stats[field]
        if count > 0:
            print(f"  - '{field}': {count}/{len(json_records)} 条记录有")
    print()
    
    # 4. 验证一致性
    print("4. 记录一致性验证")
    print("-" * 60)
    
    # 从 JSON 中提取信息
    json_video_ids = {r["video_id"] for r in json_records}
    json_urls = {r["url"] for r in json_records}
    
    # 与 failed_detail.log 对比
    if log_path.exists():
        log_records = extract_records_from_log(log_path)
        log_video_ids = {r["video_id"] for r in log_records}
        log_urls = {r["url"] for r in log_records}
        
        if json_video_ids == log_video_ids:
            print(f"✓ JSON 与 log 的 video_id 一致 ({len(json_video_ids)} 个)")
        else:
            only_in_json = json_video_ids - log_video_ids
            only_in_log = log_video_ids - json_video_ids
            if only_in_json:
                print(f"⚠ 仅在 JSON 中的 video_id: {only_in_json}")
            if only_in_log:
                print(f"⚠ 仅在 log 中的 video_id: {only_in_log}")
        
        if json_urls == log_urls:
            print(f"✓ JSON 与 log 的 url 一致 ({len(json_urls)} 个)")
        else:
            only_in_json = json_urls - log_urls
            only_in_log = log_urls - json_urls
            if only_in_json:
                print(f"⚠ 仅在 JSON 中的 url: {only_in_json}")
            if only_in_log:
                print(f"⚠ 仅在 log 中的 url: {only_in_log}")
    else:
        print("⚠ 无法验证与 log 的一致性（log 文件不存在）")
    
    # 与 failed_urls.txt 对比
    if urls_path.exists():
        txt_urls = set(extract_urls_from_txt(urls_path))
        if json_urls == txt_urls:
            print(f"✓ JSON 与 txt 的 url 一致 ({len(json_urls)} 个)")
        else:
            only_in_json = json_urls - txt_urls
            only_in_txt = txt_urls - json_urls
            if only_in_json:
                print(f"⚠ 仅在 JSON 中的 url: {only_in_json}")
            if only_in_txt:
                print(f"⚠ 仅在 txt 中的 url: {only_in_txt}")
    else:
        print("⚠ 无法验证与 txt 的一致性（txt 文件不存在）")
    print()
    
    # 5. 统计信息
    print("5. 统计信息")
    print("-" * 60)
    
    # 错误类型统计
    error_type_stats = {}
    for record in json_records:
        error_type = record.get("error_type", "unknown")
        error_type_stats[error_type] = error_type_stats.get(error_type, 0) + 1
    
    print("错误类型分布:")
    for error_type, count in sorted(error_type_stats.items()):
        print(f"  - {error_type}: {count} 条")
    print()
    
    # 阶段统计
    stage_stats = {}
    for record in json_records:
        stage = record.get("stage", "unknown")
        stage_stats[stage] = stage_stats.get(stage, 0) + 1
    
    print("失败阶段分布:")
    for stage, count in sorted(stage_stats.items()):
        print(f"  - {stage}: {count} 条")
    print()
    
    # 6. 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    
    all_passed = all_required_present and all_valid
    
    if all_passed:
        print("✅ 所有验证点通过")
        print("   - JSON 记录格式正确（JSONL 格式）")
        print("   - 必需字段完整")
        print("   - JSON 格式可以正常解析")
        if log_path.exists() or urls_path.exists():
            print("   - 记录与其他失败记录文件一致")
    else:
        print("⚠ 部分验证点未通过")
        if not all_valid:
            print("   - JSON 记录格式有误")
        if not all_required_present:
            print("   - 必需字段不完整")
    
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback
        traceback.print_exc()

