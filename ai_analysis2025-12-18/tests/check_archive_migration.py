"""Archive 迁移和增量行为检查脚本

用于验证 T0-2 测试：Archive 位置 + 迁移测试
"""
from pathlib import Path
from config.manager import get_user_data_dir
from datetime import datetime
import os

def get_archives_dir():
    """获取 archives 目录"""
    return get_user_data_dir() / "archives"

def check_old_archive():
    """检查旧的 out/archive.txt 文件"""
    print("=" * 60)
    print("1. 检查旧的 out/archive.txt 文件")
    print("=" * 60)
    
    old_archive = Path("out") / "archive.txt"
    old_archive_alt = Path("archive.txt")  # 项目根目录
    
    found_files = []
    
    if old_archive.exists():
        mtime = datetime.fromtimestamp(old_archive.stat().st_mtime)
        size = old_archive.stat().st_size
        print(f"[OK] 找到: {old_archive}")
        print(f"   大小: {size} 字节")
        print(f"   修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        found_files.append(old_archive)
    
    if old_archive_alt.exists():
        mtime = datetime.fromtimestamp(old_archive_alt.stat().st_mtime)
        size = old_archive_alt.stat().st_size
        print(f"[OK] 找到: {old_archive_alt}")
        print(f"   大小: {size} 字节")
        print(f"   修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        found_files.append(old_archive_alt)
    
    if not found_files:
        print("[INFO] 未找到旧的 archive.txt 文件（这是正常的，如果之前没有使用过旧版本）")
    
    return found_files

def check_new_archives():
    """检查新的 archives/ 目录"""
    print("\n" + "=" * 60)
    print("2. 检查新的 archives/ 目录")
    print("=" * 60)
    
    archives_dir = get_archives_dir()
    print(f"Archive 目录: {archives_dir}")
    print(f"目录存在: {archives_dir.exists()}")
    
    if not archives_dir.exists():
        print("[WARN] archives/ 目录不存在，将在第一次运行时自动创建")
        return []
    
    # 列出所有文件
    files = sorted(archives_dir.iterdir())
    archive_files = [f for f in files if f.is_file() and f.suffix == '.txt']
    
    if not archive_files:
        print("[INFO] 目录为空，还没有生成 Archive 文件")
        return []
    
    print(f"\n找到 {len(archive_files)} 个 Archive 文件：")
    print("-" * 60)
    
    for f in archive_files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        size = f.stat().st_size
        
        print(f"\n文件: {f.name}")
        print(f"  完整路径: {f}")
        print(f"  大小: {size} 字节")
        print(f"  修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 判断文件类型
        if f.name.startswith("UC") and len(f.name) > 3:
            print(f"  类型: 频道 Archive (频道 ID: {f.stem})")
        elif f.name.startswith("batch_"):
            print(f"  类型: URL 列表批次 Archive")
        elif f.name.startswith("playlist_"):
            print(f"  类型: 播放列表 Archive")
        elif f.name == "migrated_archive.txt":
            print(f"  类型: 迁移的旧 Archive")
        else:
            print(f"  类型: 未知")
        
        # 显示文件内容预览
        if size > 0:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                    print(f"  行数: {len(lines)}")
                    if len(lines) > 0:
                        print(f"  第一行: {lines[0].strip()[:80]}")
                        if len(lines) > 1:
                            print(f"  最后一行: {lines[-1].strip()[:80]}")
            except Exception as e:
                print(f"  [WARN] 读取失败: {e}")
    
    return archive_files

def check_migration():
    """检查迁移状态"""
    print("\n" + "=" * 60)
    print("3. 检查迁移状态")
    print("=" * 60)
    
    old_files = check_old_archive()
    new_files = check_new_archives()
    
    migrated_file = get_archives_dir() / "migrated_archive.txt"
    
    if migrated_file.exists():
        mtime = datetime.fromtimestamp(migrated_file.stat().st_mtime)
        size = migrated_file.stat().st_size
        print(f"\n[OK] 找到迁移文件: {migrated_file}")
        print(f"   大小: {size} 字节")
        print(f"   修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print("   [OK] 旧 Archive 已成功迁移")
    elif old_files:
        print(f"\n[WARN] 发现旧的 archive.txt 文件，但未找到 migrated_archive.txt")
        print("   可能原因：")
        print("   1. 迁移尚未执行（将在第一次运行时自动迁移）")
        print("   2. 迁移逻辑未正确执行")
    else:
        print("\n[INFO] 没有旧的 archive.txt 文件需要迁移")
    
    # 检查是否有备份文件
    backup_files = []
    for old_file in old_files:
        backup = old_file.with_suffix(old_file.suffix + ".bak")
        if backup.exists():
            backup_files.append(backup)
            print(f"\n[OK] 找到备份文件: {backup}")
    
    if old_files and not backup_files and not migrated_file.exists():
        print("\n[WARN] 注意：旧的 archive.txt 文件存在，但未发现备份或迁移文件")
        print("   建议：在运行处理任务后再次检查")

def check_incremental_behavior(channel_id: str = None):
    """检查增量行为（需要提供频道 ID）"""
    print("\n" + "=" * 60)
    print("4. 增量行为检查")
    print("=" * 60)
    
    if not channel_id:
        print("[INFO] 需要提供频道 ID 才能检查增量行为")
        print("   使用方法：")
        print("   python check_archive_migration.py --channel-id UCxxxxxx")
        return
    
    archives_dir = get_archives_dir()
    channel_archive = archives_dir / f"{channel_id}.txt"
    
    if not channel_archive.exists():
        print(f"[WARN] 频道 Archive 文件不存在: {channel_archive}")
        print("   可能原因：")
        print("   1. 该频道尚未被处理过")
        print("   2. 频道 ID 不正确")
        return
    
    mtime = datetime.fromtimestamp(channel_archive.stat().st_mtime)
    size = channel_archive.stat().st_size
    
    print(f"频道 Archive: {channel_archive.name}")
    print(f"修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"大小: {size} 字节")
    
    # 读取并统计已处理的视频数量
    try:
        with open(channel_archive, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            video_ids = set()
            for line in lines:
                # yt-dlp 格式：youtube <video_id> 或 youtube <video_id> <ext>
                parts = line.split()
                if len(parts) >= 2 and parts[0] == 'youtube':
                    video_ids.add(parts[1])
            
            print(f"\n已处理的视频数量: {len(video_ids)}")
            if len(video_ids) > 0:
                print(f"示例视频 ID: {list(video_ids)[:5]}")
            
            print("\n[OK] 增量记录正常，下次运行同一频道时将跳过这些视频")
    except Exception as e:
        print(f"[WARN] 读取 Archive 文件失败: {e}")

def main():
    """主函数"""
    import sys
    
    print("=" * 60)
    print("Archive 迁移和增量行为检查工具")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查迁移
    check_migration()
    
    # 检查增量行为（如果提供了频道 ID）
    channel_id = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--channel-id' and len(sys.argv) > 2:
            channel_id = sys.argv[2]
        elif sys.argv[1].startswith('UC') and len(sys.argv[1]) > 3:
            channel_id = sys.argv[1]
    
    if channel_id:
        check_incremental_behavior(channel_id)
    else:
        check_incremental_behavior()
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    print("\n使用说明：")
    print("1. 运行处理任务前，先运行此脚本记录初始状态")
    print("2. 运行处理任务（CLI 或 GUI）")
    print("3. 再次运行此脚本，对比前后变化")
    print("4. 如需检查特定频道的增量行为，使用：")
    print("   python check_archive_migration.py --channel-id UCxxxxxx")

if __name__ == "__main__":
    main()

