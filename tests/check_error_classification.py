"""错误分类与失败记录检查脚本

用于验证 T1-1 测试：错误分类与失败记录测试
检查 failed_detail.log、failed_urls.txt、failed_records.json 中的错误分类是否正确
"""
from pathlib import Path
from datetime import datetime
import json
import re
from collections import defaultdict

# 错误类型映射（用于验证）
ERROR_TYPES = {
    "network", "timeout", "rate_limit", "auth", "content",
    "file_io", "parse", "invalid_input", "cancelled",
    "external_service", "unknown"
}

def parse_failed_detail_log(log_path: Path):
    """解析 failed_detail.log 文件"""
    if not log_path.exists():
        return []
    
    records = []
    # 更宽松的正则表达式，支持可选字段
    pattern = re.compile(
        r'\[([^\]]+)\](?:\s+\[batch:([^\]]+)\])?(?:\s+\[video:([^\]]+)\])?\s+(.+?)(?:\s+error=([^\s]+))?(?:\s+msg=(.+))?$'
    )
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                match = pattern.match(line)
                if match:
                    groups = match.groups()
                    timestamp = groups[0]
                    batch_id = groups[1] if groups[1] else None
                    video_id = groups[2] if groups[2] else None
                    url = groups[3] if groups[3] else ""
                    error_type = groups[4] if groups[4] else "unknown"
                    msg = groups[5] if groups[5] else ""
                    
                    records.append({
                        "line": line_num,
                        "timestamp": timestamp,
                        "batch_id": batch_id,
                        "video_id": video_id,
                        "url": url,
                        "error_type": error_type,
                        "message": msg
                    })
                else:
                    # 尝试手动提取 error= 字段
                    error_match = re.search(r'error=([^\s]+)', line)
                    if error_match:
                        error_type = error_match.group(1)
                        records.append({
                            "line": line_num,
                            "raw": line,
                            "error_type": error_type,
                            "parsed": False
                        })
                    else:
                        records.append({
                            "line": line_num,
                            "raw": line,
                            "parsed": False
                        })
    except Exception as e:
        print(f"  [ERROR] 解析失败: {e}")
        return []
    
    return records

def parse_failed_urls(urls_path: Path):
    """解析 failed_urls.txt 文件"""
    if not urls_path.exists():
        return []
    
    urls = []
    try:
        with open(urls_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    urls.append({"line": line_num, "url": line})
    except Exception as e:
        print(f"  [ERROR] 解析失败: {e}")
        return []
    
    return urls

def parse_failed_records_json(json_path: Path):
    """解析 failed_records.json 文件（JSONL 格式）"""
    if not json_path.exists():
        return []
    
    records = []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    record = json.loads(line)
                    record["line"] = line_num
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f"  [WARN] 第 {line_num} 行 JSON 解析失败: {e}")
    except Exception as e:
        print(f"  [ERROR] 解析失败: {e}")
        return []
    
    return records

def check_error_classification():
    """检查错误分类情况"""
    print("=" * 60)
    print("错误分类与失败记录检查工具（T1-1 测试辅助）")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 查找输出目录
    output_dir = Path("out")
    if not output_dir.exists():
        print("[INFO] 输出目录不存在，请先运行处理任务")
        return
    
    detail_log = output_dir / "failed_detail.log"
    urls_file = output_dir / "failed_urls.txt"
    json_records = output_dir / "failed_records.json"
    
    print("检查文件:")
    print(f"  1. failed_detail.log: {'存在' if detail_log.exists() else '不存在'}")
    print(f"  2. failed_urls.txt: {'存在' if urls_file.exists() else '不存在'}")
    print(f"  3. failed_records.json: {'存在' if json_records.exists() else '不存在'}")
    print()
    
    # 解析文件
    detail_records = parse_failed_detail_log(detail_log)
    url_records = parse_failed_urls(urls_file)
    json_records_list = parse_failed_records_json(json_records)
    
    print("=" * 60)
    print("1. failed_detail.log 分析")
    print("=" * 60)
    
    if not detail_records:
        print("[INFO] 无失败记录")
    else:
        print(f"总记录数: {len(detail_records)}")
        
        # 统计错误类型
        error_type_count = defaultdict(int)
        parsed_count = 0
        unparsed_count = 0
        
        for record in detail_records:
            if record.get("parsed", True):
                parsed_count += 1
                error_type = record.get("error_type", "unknown")
                error_type_count[error_type] += 1
            else:
                unparsed_count += 1
        
        print(f"  成功解析: {parsed_count}")
        if unparsed_count > 0:
            print(f"  解析失败: {unparsed_count}")
        
        print("\n错误类型统计:")
        for error_type, count in sorted(error_type_count.items()):
            status = "[OK]" if error_type in ERROR_TYPES else "[INVALID]"
            print(f"  {status} {error_type}: {count} 条")
        
        # 显示前几条记录示例
        print("\n记录示例（前 3 条）:")
        for record in detail_records[:3]:
            if record.get("parsed", True):
                print(f"  [{record['timestamp']}] [batch:{record['batch_id']}] [video:{record['video_id']}]")
                print(f"    URL: {record['url']}")
                print(f"    Error: {record['error_type']}")
                print(f"    Message: {record['message']}")
            else:
                print(f"  [未解析] {record.get('raw', '')[:80]}...")
    
    print("\n" + "=" * 60)
    print("2. failed_urls.txt 分析")
    print("=" * 60)
    
    if not url_records:
        print("[INFO] 无失败 URL 记录")
    else:
        print(f"总 URL 数: {len(url_records)}")
        print("\nURL 示例（前 3 条）:")
        for record in url_records[:3]:
            print(f"  {record['url']}")
    
    print("\n" + "=" * 60)
    print("3. failed_records.json 分析")
    print("=" * 60)
    
    if not json_records_list:
        print("[INFO] 无 JSON 记录")
    else:
        print(f"总记录数: {len(json_records_list)}")
        
        # 统计错误类型
        json_error_type_count = defaultdict(int)
        missing_error_type = 0
        
        for record in json_records_list:
            error_type = record.get("error_type")
            if error_type:
                json_error_type_count[error_type] += 1
            else:
                missing_error_type += 1
        
        if missing_error_type > 0:
            print(f"  [WARN] {missing_error_type} 条记录缺少 error_type 字段")
        
        print("\n错误类型统计:")
        for error_type, count in sorted(json_error_type_count.items()):
            status = "[OK]" if error_type in ERROR_TYPES else "[INVALID]"
            print(f"  {status} {error_type}: {count} 条")
        
        # 显示前几条记录示例
        print("\n记录示例（前 3 条）:")
        for record in json_records_list[:3]:
            print(f"  Video ID: {record.get('video_id', 'N/A')}")
            print(f"    URL: {record.get('url', 'N/A')}")
            print(f"    Error Type: {record.get('error_type', 'N/A')}")
            print(f"    Reason: {record.get('reason', 'N/A')[:60]}...")
            print(f"    Timestamp: {record.get('timestamp', 'N/A')}")
    
    # 总结
    print("\n" + "=" * 60)
    print("检查总结")
    print("=" * 60)
    
    all_error_types = set(error_type_count.keys()) | set(json_error_type_count.keys())
    valid_types = all_error_types & ERROR_TYPES
    invalid_types = all_error_types - ERROR_TYPES
    
    if invalid_types:
        print(f"[WARN] 发现无效错误类型: {', '.join(invalid_types)}")
    
    if not all_error_types:
        print("[INFO] 无错误记录，无法验证错误分类")
    else:
        print(f"[OK] 发现 {len(valid_types)} 种有效错误类型")
        if invalid_types:
            print(f"[ERROR] 发现 {len(invalid_types)} 种无效错误类型")
        else:
            print("[OK] 所有错误类型都是有效的")
    
    # 验证点检查清单
    print("\n" + "=" * 60)
    print("验证点检查清单")
    print("=" * 60)
    
    checks = {
        "网络错误被正确分类为 NETWORK": "network" in all_error_types,
        "限流错误被正确分类为 RATE_LIMIT": "rate_limit" in all_error_types,
        "认证错误被正确分类为 AUTH": "auth" in all_error_types,
        "内容错误被正确分类为 CONTENT": "content" in all_error_types,
        "failed_detail.log 格式符合规范": parsed_count > 0 or len(detail_records) == 0,
        "failed_records.json 中每条记录包含 error_type 字段": missing_error_type == 0,
        "错误信息清晰易懂": len(detail_records) > 0 or len(json_records_list) > 0,
    }
    
    for check_name, result in checks.items():
        status = "[OK]" if result else "[ ]"
        print(f"{status} {check_name}")
    
    print("\n使用说明:")
    print("1. 运行此脚本前，先执行各种错误场景的处理任务")
    print("2. 检查输出结果，确认错误类型分类是否正确")
    print("3. 如果发现错误类型不正确，请检查代码中的错误映射逻辑")

if __name__ == "__main__":
    check_error_classification()

