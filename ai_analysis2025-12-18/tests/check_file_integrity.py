"""文件完整性检查脚本

用于验证 T0-4 测试：文件写入锁 + 原子写测试
检查高并发下文件写入是否正确，无错乱、无截断
"""
from pathlib import Path
from datetime import datetime
import json

def check_append_files(output_dir: Path):
    """检查追加写入的文件（with_subtitle.txt, without_subtitle.txt, failed_urls.txt, failed_records.json）"""
    print("=" * 60)
    print("1. 检查追加写入的文件")
    print("=" * 60)
    
    files_to_check = [
        "with_subtitle.txt",
        "without_subtitle.txt",
        "failed_urls.txt",
        "failed_records.json"
    ]
    
    results = {}
    
    for filename in files_to_check:
        file_path = output_dir / filename
        print(f"\n文件: {filename}")
        print(f"  路径: {file_path}")
        
        if not file_path.exists():
            print(f"  [INFO] 文件不存在（可能没有相关记录）")
            results[filename] = {"exists": False}
            continue
        
        try:
            size = file_path.stat().st_size
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            print(f"  大小: {size} 字节")
            print(f"  修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 读取文件内容检查
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                non_empty_lines = [line for line in lines if line.strip()]
                
                print(f"  总行数: {len(lines)}")
                print(f"  非空行数: {len(non_empty_lines)}")
                
                # 检查是否有明显的格式错误
                issues = []
                
                # 检查是否有不完整的行（除了最后一行）
                for i, line in enumerate(non_empty_lines[:-1] if non_empty_lines else []):
                    if line and not line.endswith('\n') and i < len(non_empty_lines) - 1:
                        # 这不应该发生，因为我们已经用 split('\n') 分割了
                        pass
                
                # 检查 JSON 文件格式
                if filename == "failed_records.json":
                    json_issues = []
                    for i, line in enumerate(non_empty_lines, 1):
                        if line.strip():
                            try:
                                json.loads(line)
                            except json.JSONDecodeError as e:
                                json_issues.append(f"第 {i} 行: {str(e)}")
                    
                    if json_issues:
                        issues.extend(json_issues)
                        print(f"  [ERROR] 发现 {len(json_issues)} 个 JSON 格式错误")
                        for issue in json_issues[:5]:  # 只显示前5个
                            print(f"    - {issue}")
                    else:
                        print(f"  [OK] JSON 格式正确")
                
                # 检查是否有明显的行错乱（同一行被拆开）
                # 简单检查：URL 行是否完整
                if filename in ["with_subtitle.txt", "without_subtitle.txt", "failed_urls.txt"]:
                    url_issues = []
                    for i, line in enumerate(non_empty_lines, 1):
                        line = line.strip()
                        if line and not line.startswith('#') and not line.startswith('http'):
                            # 可能是分隔符或格式行，跳过
                            if '|' in line or '=' in line:
                                continue
                            # 如果看起来像是不完整的 URL
                            if len(line) > 0 and not line.startswith('http'):
                                url_issues.append(f"第 {i} 行可能不完整: {line[:50]}")
                    
                    if url_issues:
                        print(f"  [WARN] 发现 {len(url_issues)} 个可能不完整的行")
                        for issue in url_issues[:3]:  # 只显示前3个
                            print(f"    - {issue}")
                    else:
                        print(f"  [OK] URL 格式正常")
                
                if not issues:
                    print(f"  [OK] 文件内容检查通过")
                else:
                    print(f"  [WARN] 发现 {len(issues)} 个潜在问题")
                
                results[filename] = {
                    "exists": True,
                    "size": size,
                    "lines": len(non_empty_lines),
                    "issues": issues
                }
                
        except Exception as e:
            print(f"  [ERROR] 读取文件失败: {e}")
            results[filename] = {"exists": True, "error": str(e)}
    
    return results

def check_output_files(output_dir: Path, video_id: str = None):
    """检查输出文件（字幕、摘要、metadata.json）是否完整"""
    print("\n" + "=" * 60)
    print("2. 检查输出文件（字幕、摘要、metadata.json）")
    print("=" * 60)
    
    if video_id:
        # 检查特定视频的输出文件
        video_dirs = [output_dir / "original" / video_id,
                     output_dir / "translated" / video_id,
                     output_dir / "summary" / video_id,
                     output_dir / "metadata" / video_id]
    else:
        # 检查所有视频的输出文件（采样检查）
        print("[INFO] 未指定视频 ID，将采样检查")
        # 查找第一个存在的视频目录
        original_dir = output_dir / "original"
        if original_dir.exists():
            video_dirs_list = list(original_dir.iterdir())
            if video_dirs_list:
                sample_video_id = video_dirs_list[0].name
                print(f"  采样视频 ID: {sample_video_id}")
                video_dirs = [
                    output_dir / "original" / sample_video_id,
                    output_dir / "translated" / sample_video_id,
                    output_dir / "summary" / sample_video_id,
                    output_dir / "metadata" / sample_video_id
                ]
            else:
                print("  [INFO] 未找到任何视频输出目录")
                return {}
        else:
            print("  [INFO] original/ 目录不存在")
            return {}
    
    results = {}
    
    for video_dir in video_dirs:
        if not video_dir.exists():
            continue
        
        print(f"\n目录: {video_dir.relative_to(output_dir)}")
        
        # 检查该目录下的所有文件
        files = list(video_dir.iterdir())
        if not files:
            print("  [INFO] 目录为空")
            continue
        
        for file_path in files:
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    print(f"  文件: {file_path.name} ({size} 字节)")
                    
                    # 检查文件是否完整（简单检查：文件大小是否合理）
                    if size == 0:
                        print(f"    [WARN] 文件为空")
                    elif size < 10:
                        print(f"    [WARN] 文件过小，可能不完整")
                    else:
                        # 尝试读取文件内容验证
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                                # 检查 JSON 文件
                                if file_path.suffix == '.json':
                                    try:
                                        json.loads(content)
                                        print(f"    [OK] JSON 格式正确")
                                    except json.JSONDecodeError as e:
                                        print(f"    [ERROR] JSON 格式错误: {e}")
                                
                                # 检查 SRT 文件
                                elif file_path.suffix == '.srt':
                                    if len(content) > 0:
                                        print(f"    [OK] SRT 文件有内容")
                                    else:
                                        print(f"    [WARN] SRT 文件为空")
                                
                                # 检查文本文件
                                elif file_path.suffix in ['.txt', '.md']:
                                    if len(content) > 0:
                                        print(f"    [OK] 文本文件有内容")
                                    else:
                                        print(f"    [WARN] 文本文件为空")
                                
                        except UnicodeDecodeError:
                            print(f"    [ERROR] 文件编码错误，无法读取")
                        except Exception as e:
                            print(f"    [WARN] 读取文件时出错: {e}")
                    
                except Exception as e:
                    print(f"    [ERROR] 检查文件失败: {e}")
    
    return results

def main():
    """主函数"""
    import sys
    
    print("=" * 60)
    print("文件完整性检查工具（T0-4 测试辅助）")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 默认输出目录
    output_dir = Path("out")
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    
    print(f"输出目录: {output_dir}")
    print(f"目录存在: {output_dir.exists()}")
    
    if not output_dir.exists():
        print("\n[WARN] 输出目录不存在，请先运行处理任务")
        return
    
    # 检查追加写入的文件
    append_results = check_append_files(output_dir)
    
    # 检查输出文件
    video_id = None
    if len(sys.argv) > 2:
        video_id = sys.argv[2]
    
    output_results = check_output_files(output_dir, video_id)
    
    # 总结
    print("\n" + "=" * 60)
    print("检查总结")
    print("=" * 60)
    
    total_issues = 0
    for filename, result in append_results.items():
        if result.get("issues"):
            total_issues += len(result["issues"])
    
    if total_issues == 0:
        print("[OK] 所有文件检查通过，未发现明显的格式错误或内容截断")
    else:
        print(f"[WARN] 发现 {total_issues} 个潜在问题，请仔细检查")
    
    print("\n使用说明：")
    print("1. 在高并发（10）处理 30-50 个视频后运行此脚本")
    print("2. 检查追加写入的文件是否有错乱")
    print("3. 检查输出文件是否有截断")
    print("4. 如果发现问题，查看日志中的文件写入相关异常")

if __name__ == "__main__":
    main()

