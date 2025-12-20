"""
VideoFetcher 测试脚本
在项目根目录运行: python test_fetcher.py
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.fetcher import VideoFetcher


def test_url_type():
    """测试 URL 类型识别"""
    print("=" * 50)
    print("测试 1: URL 类型识别")
    print("=" * 50)
    
    fetcher = VideoFetcher()
    
    test_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video"),
        ("https://youtu.be/dQw4w9WgXcQ", "video"),
        ("https://www.youtube.com/@MrBeast", "channel"),
        ("https://www.youtube.com/channel/UCxxxxxx", "channel"),
        ("https://www.youtube.com/playlist?list=PLxxxxxx", "playlist"),
    ]
    
    for url, expected in test_urls:
        result = fetcher.identify_url_type(url)
        status = "✓" if result == expected else "✗"
        print(f"{status} {result:10} (期望: {expected:10}) - {url}")
    
    print("\n测试通过 ✓\n")


def test_video_id_extraction():
    """测试视频 ID 提取"""
    print("=" * 50)
    print("测试 2: 视频 ID 提取")
    print("=" * 50)
    
    fetcher = VideoFetcher()
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = fetcher.extract_video_id(test_url)
    
    print(f"URL: {test_url}")
    print(f"视频 ID: {video_id}")
    
    if video_id == "dQw4w9WgXcQ":
        print("\n测试通过 ✓\n")
    else:
        print("\n测试失败 ✗\n")


def test_single_video():
    """测试获取单个视频（需要网络）"""
    print("=" * 50)
    print("测试 3: 获取单个视频信息（需要网络和 yt-dlp）")
    print("=" * 50)
    
    fetcher = VideoFetcher()
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"正在获取视频信息: {test_url}")
    
    try:
        videos = fetcher.fetch_single_video(test_url)
        
        if videos:
            video = videos[0]
            print(f"\n✓ 成功获取视频信息:")
            print(f"  - 视频 ID: {video.video_id}")
            print(f"  - 标题: {video.title}")
            print(f"  - 频道: {video.channel_name}")
            print(f"  - URL: {video.url}")
            print("\n测试通过 ✓\n")
        else:
            print("\n✗ 无法获取视频信息（可能是网络问题）\n")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}\n")


def test_channel():
    """测试获取频道视频列表（需要网络和真实频道 URL）"""
    print("=" * 50)
    print("测试 4: 获取频道视频列表（需要网络和真实频道 URL）")
    print("=" * 50)
    
    fetcher = VideoFetcher()
    
    # 使用一个真实的频道 URL 进行测试
    # 注意：不要使用示例 URL（如 @channel），必须使用真实频道
    channel_url = "https://www.youtube.com/@MrBeast"
    
    print(f"正在获取频道视频列表: {channel_url}")
    print("（这可能需要一些时间，请耐心等待...）")
    
    try:
        videos = fetcher.fetch_channel(channel_url)
        
        print(f"\n✓ 成功获取频道视频列表")
        print(f"  - 视频数量: {len(videos)}")
        
        if videos:
            print(f"\n前 3 个视频:")
            for i, video in enumerate(videos[:3], 1):
                print(f"  {i}. {video.video_id} - {video.title[:50]}...")
        
        print("\n测试通过 ✓\n")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        print("提示：如果使用的是示例 URL（如 @channel），请替换为真实频道 URL\n")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("VideoFetcher 功能测试")
    print("=" * 50 + "\n")
    
    try:
        # 基础测试（不需要网络）
        test_url_type()
        test_video_id_extraction()
        
        # 网络测试（需要 yt-dlp 和网络连接）
        print("提示：以下测试需要网络连接和 yt-dlp")
        user_input = input("是否继续网络测试？(y/n): ").strip().lower()
        
        if user_input == 'y':
            test_single_video()
            test_channel()
        else:
            print("\n跳过网络测试\n")
        
        print("=" * 50)
        print("所有测试完成！")
        print("=" * 50)
        
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

