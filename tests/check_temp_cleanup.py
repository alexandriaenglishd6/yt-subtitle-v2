"""临时目录清理检查脚本

用于验证 T0-5 测试：临时目录清理测试
检查 temp/ 目录是否在任务结束后被正确清理
"""
from pathlib import Path
from datetime import datetime
import os

def find_temp_directories():
    """查找所有可能的 temp 目录"""
    temp_dirs = []
    
    # 检查项目根目录下的 temp/
    project_temp = Path("temp")
    if project_temp.exists():
        temp_dirs.append(project_temp)
    
    # 检查用户数据目录下的 temp/
    try:
        from config.manager import get_user_data_dir
        user_data_temp = get_user_data_dir() / "temp"
        if user_data_temp.exists():
            temp_dirs.append(user_data_temp)
    except Exception:
        pass
    
    # 检查输出目录下的 temp/
    output_temp = Path("out") / "temp"
    if output_temp.exists():
        temp_dirs.append(output_temp)
    
    return temp_dirs

def check_temp_directory(temp_dir: Path):
    """检查单个 temp 目录"""
    print(f"\n目录: {temp_dir}")
    print(f"  完整路径: {temp_dir.absolute()}")
    
    if not temp_dir.exists():
        print(f"  [OK] 目录不存在（已清理）")
        return {"exists": False, "files": 0, "size": 0}
    
    # 统计目录内容
    total_files = 0
    total_dirs = 0
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(temp_dir):
            total_dirs += len(dirs)
            for file in files:
                total_files += 1
                file_path = Path(root) / file
                try:
                    total_size += file_path.stat().st_size
                except Exception:
                    pass
        
        print(f"  存在: 是")
        print(f"  子目录数: {total_dirs}")
        print(f"  文件数: {total_files}")
        print(f"  总大小: {total_size} 字节 ({total_size / 1024:.2f} KB)")
        
        if total_files > 0 or total_dirs > 0:
            print(f"  [WARN] 目录不为空，可能未正确清理")
            
            # 列出前几个文件/目录
            print(f"  内容预览:")
            items = list(temp_dir.iterdir())[:5]
            for item in items:
                if item.is_dir():
                    print(f"    - {item.name}/ (目录)")
                else:
                    size = item.stat().st_size
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    print(f"    - {item.name} ({size} 字节, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
            
            if len(list(temp_dir.iterdir())) > 5:
                print(f"    ... 还有更多文件/目录")
        else:
            print(f"  [OK] 目录为空（已清理）")
        
        return {
            "exists": True,
            "files": total_files,
            "dirs": total_dirs,
            "size": total_size
        }
    except Exception as e:
        print(f"  [ERROR] 检查目录失败: {e}")
        return {"exists": True, "error": str(e)}

def check_temp_cleanup():
    """检查临时目录清理情况"""
    print("=" * 60)
    print("临时目录清理检查工具（T0-5 测试辅助）")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    temp_dirs = find_temp_directories()
    
    if not temp_dirs:
        print("[OK] 未找到任何 temp/ 目录（所有临时目录已清理）")
        print("\n说明：")
        print("1. 正常完成的任务应该清理所有临时目录")
        print("2. 如果任务失败且 keep_temp_on_error=True，可能会保留 temp 目录")
        print("3. 如果发现 temp 目录，请检查任务是否正常完成")
        return
    
    print(f"找到 {len(temp_dirs)} 个 temp/ 目录：")
    print("-" * 60)
    
    results = []
    for temp_dir in temp_dirs:
        result = check_temp_directory(temp_dir)
        results.append((temp_dir, result))
    
    # 总结
    print("\n" + "=" * 60)
    print("检查总结")
    print("=" * 60)
    
    total_files = sum(r[1].get("files", 0) for r in results)
    total_size = sum(r[1].get("size", 0) for r in results)
    
    if total_files == 0:
        print("[OK] 所有 temp 目录为空或不存在，清理正常")
    else:
        print(f"[WARN] 发现 {total_files} 个临时文件，总大小 {total_size / 1024:.2f} KB")
        print("可能原因：")
        print("1. 任务正在运行中（临时文件正在使用）")
        print("2. 任务失败且 keep_temp_on_error=True（保留失败现场）")
        print("3. 清理逻辑未正确执行（需要检查代码）")
        print("\n建议：")
        print("1. 确认任务是否已完成")
        print("2. 检查日志中是否有清理相关的错误信息")
        print("3. 如果任务已完成但仍有文件，可能是清理逻辑问题")
    
    print("\n使用说明：")
    print("1. 在任务运行前，运行此脚本记录初始状态")
    print("2. 运行处理任务（正常完成或失败场景）")
    print("3. 任务结束后，再次运行此脚本，对比前后变化")
    print("4. 验证 temp 目录是否被正确清理")

if __name__ == "__main__":
    check_temp_cleanup()

