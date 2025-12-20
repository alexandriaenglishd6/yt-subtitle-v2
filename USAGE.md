# VideoFetcher 使用说明

## 快速开始

### 1. 基本导入

```python
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（如果在项目根目录运行，可以省略）
sys.path.insert(0, str(Path(__file__).parent))

from core.fetcher import VideoFetcher
```

### 2. URL 类型识别

```python
fetcher = VideoFetcher()

# 识别 URL 类型
url_type = fetcher.identify_url_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(url_type)  # 输出: video
```

### 3. 获取单个视频信息

```python
fetcher = VideoFetcher()

# 获取单个视频信息
videos = fetcher.fetch_single_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

if videos:
    video = videos[0]
    print(f"视频 ID: {video.video_id}")
    print(f"标题: {video.title}")
    print(f"频道: {video.channel_name}")
```

### 4. 获取频道视频列表

**重要提示：** 必须使用**真实的频道 URL**，不能使用示例 URL（如 `https://www.youtube.com/@channel`）

```python
fetcher = VideoFetcher()

# 使用真实的频道 URL（例如）
channel_url = "https://www.youtube.com/@MrBeast"  # 真实频道
# channel_url = "https://www.youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA"  # 或使用频道 ID

videos = fetcher.fetch_channel(channel_url)
print(f"获取到 {len(videos)} 个视频")
```

### 5. 从文件读取 URL 列表

```python
from pathlib import Path

fetcher = VideoFetcher()

# 从文件读取 URL 列表（每行一个 URL）
url_file = Path("urls.txt")
videos = fetcher.fetch_from_file(url_file)
print(f"获取到 {len(videos)} 个视频")
```

## 常见问题

### Q: 为什么频道获取返回空列表？

A: 可能的原因：
1. **使用了示例 URL**：`https://www.youtube.com/@channel` 不是真实频道，必须使用真实频道 URL
2. **网络问题**：无法连接到 YouTube
3. **yt-dlp 未安装**：需要先安装 `pip install yt-dlp`
4. **频道不存在或私有**：某些频道可能无法访问

### Q: 如何找到真实的频道 URL？

A: 在浏览器中打开 YouTube 频道页面，复制地址栏的 URL，例如：
- `https://www.youtube.com/@MrBeast`
- `https://www.youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA`

### Q: 导入错误怎么办？

A: 确保项目根目录在 Python 路径中：

```python
import sys
from pathlib import Path

# 方法 1: 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

# 方法 2: 在项目根目录运行
# python -m core.fetcher
```

## 测试示例

### 完整测试代码

```python
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.fetcher import VideoFetcher

# 创建 fetcher 实例
fetcher = VideoFetcher()

# 测试 1: URL 类型识别
print("测试 1: URL 类型识别")
url_type = fetcher.identify_url_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(f"  URL 类型: {url_type}")  # 应该输出: video

# 测试 2: 获取单个视频
print("\n测试 2: 获取单个视频")
videos = fetcher.fetch_single_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
if videos:
    print(f"  ✓ 成功获取视频: {videos[0].title}")
else:
    print("  ✗ 获取失败")

# 测试 3: 获取频道（需要真实频道 URL）
print("\n测试 3: 获取频道视频列表")
# 注意：这里使用真实频道 URL，不是示例
channel_url = "https://www.youtube.com/@MrBeast"  # 替换为你要测试的频道
videos = fetcher.fetch_channel(channel_url)
print(f"  获取到 {len(videos)} 个视频")
if videos:
    print(f"  第一个视频: {videos[0].title}")
```

## 依赖要求

- Python 3.7+
- yt-dlp: `pip install yt-dlp`

