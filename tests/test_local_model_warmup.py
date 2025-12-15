"""
本地模型预热功能测试脚本

测试 OpenAICompatibleClient 对本地模型的检测和预热功能。
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.manager import AIConfig
from core.ai_providers import OpenAICompatibleClient
from core.logger import get_logger

logger = get_logger()


def test_local_model_detection():
    """测试本地模型检测功能"""
    print("=" * 60)
    print("测试 1: 本地模型检测")
    print("=" * 60)
    
    # 测试本地 URL
    local_urls = [
        "http://localhost:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://0.0.0.0:8000/v1",
        "http://[::1]:11434/v1",
    ]
    
    # 测试云端 URL
    cloud_urls = [
        None,
        "https://api.openai.com/v1",
        "https://api.deepseek.com/v1",
        "http://api.example.com/v1",
    ]
    
    # 创建一个临时配置来测试检测方法
    temp_config = AIConfig(
        provider="openai",
        model="test",
        base_url=None,
        api_keys={"openai": "test"}
    )
    client = OpenAICompatibleClient(temp_config)
    
    print("\n本地 URL 检测:")
    for url in local_urls:
        is_local = client._is_local_base_url(url)
        status = "✅" if is_local else "❌"
        print(f"  {status} {url} -> {is_local}")
    
    print("\n云端 URL 检测:")
    for url in cloud_urls:
        is_local = client._is_local_base_url(url)
        status = "❌" if not is_local else "✅"
        print(f"  {status} {url or 'None'} -> {is_local}")
    
    print("\n✅ 本地模型检测测试完成")


def test_warmup_with_local_model():
    """测试本地模型预热功能（需要本地服务运行）"""
    print("\n" + "=" * 60)
    print("测试 2: 本地模型预热（需要本地服务运行）")
    print("=" * 60)
    
    # 创建本地模型配置（Ollama 示例）
    local_config = AIConfig(
        provider="openai",
        model="qwen2.5:7b",  # 或其他本地模型
        base_url="http://localhost:11434/v1",
        timeout_seconds=60,
        max_retries=2,
        max_concurrency=3,
        api_keys={"openai": "ollama"},  # Ollama 不需要真实的 API Key
        enabled=True
    )
    
    print(f"\n配置信息:")
    print(f"  Model: {local_config.model}")
    print(f"  Base URL: {local_config.base_url}")
    print(f"  Max Concurrency: {local_config.max_concurrency}")
    
    try:
        print("\n正在创建客户端（应该触发预热）...")
        start_time = time.time()
        
        client = OpenAICompatibleClient(local_config)
        
        init_time = time.time() - start_time
        print(f"✅ 客户端创建成功（耗时: {init_time:.2f}s）")
        print(f"   注意：预热在后台线程中执行，不会阻塞初始化")
        
        # 等待预热完成（最多等待 30 秒）
        print("\n等待预热完成...")
        time.sleep(2)  # 给预热线程一些时间
        
        # 测试实际调用（预热后应该更快）
        print("\n测试实际调用（预热后）...")
        call_start = time.time()
        
        try:
            result = client.generate(
                prompt="Say hello",
                max_tokens=10,
                temperature=0.0
            )
            call_time = time.time() - call_start
            print(f"✅ 调用成功（耗时: {call_time:.2f}s）")
            print(f"   响应: {result.text[:50]}")
        except Exception as e:
            print(f"⚠️  调用失败（可能是服务未启动）: {e}")
            print("   这是正常的，如果本地服务未运行")
        
    except Exception as e:
        print(f"❌ 客户端创建失败: {e}")
        print("   可能的原因：")
        print("   1. 本地服务未启动（如 Ollama）")
        print("   2. API Key 配置错误")
        print("   3. 网络连接问题")


def test_warmup_with_cloud_model():
    """测试云端模型（不应该触发预热）"""
    print("\n" + "=" * 60)
    print("测试 3: 云端模型（不应该触发预热）")
    print("=" * 60)
    
    # 创建云端模型配置
    cloud_config = AIConfig(
        provider="openai",
        model="gpt-4o-mini",
        base_url=None,  # 使用默认的 OpenAI API
        timeout_seconds=30,
        max_retries=2,
        max_concurrency=5,
        api_keys={"openai": "env:OPENAI_API_KEY"},
        enabled=True
    )
    
    print(f"\n配置信息:")
    print(f"  Model: {cloud_config.model}")
    print(f"  Base URL: {cloud_config.base_url or '默认 (OpenAI)'}")
    
    try:
        print("\n正在创建客户端（不应该触发预热）...")
        start_time = time.time()
        
        client = OpenAICompatibleClient(cloud_config)
        
        init_time = time.time() - start_time
        print(f"✅ 客户端创建成功（耗时: {init_time:.2f}s）")
        print(f"   注意：云端模型不会触发预热")
        
    except Exception as e:
        print(f"⚠️  客户端创建失败: {e}")
        print("   可能的原因：")
        print("   1. API Key 未配置")
        print("   2. 网络连接问题")
        print("   这是正常的，如果 API Key 未设置")


def test_concurrency_control():
    """测试并发控制（预热也受 Semaphore 限制）"""
    print("\n" + "=" * 60)
    print("测试 4: 并发控制验证")
    print("=" * 60)
    
    local_config = AIConfig(
        provider="openai",
        model="qwen2.5:7b",
        base_url="http://localhost:11434/v1",
        timeout_seconds=60,
        max_retries=2,
        max_concurrency=2,  # 低并发数，便于观察
        api_keys={"openai": "ollama"},
        enabled=True
    )
    
    print(f"\n配置信息:")
    print(f"  Max Concurrency: {local_config.max_concurrency}")
    print(f"  预热请求也会使用 Semaphore 进行并发控制")
    
    try:
        client = OpenAICompatibleClient(local_config)
        print(f"✅ 客户端创建成功")
        print(f"   Semaphore 限制: {client.max_concurrency}")
        print(f"   预热请求会占用一个 Semaphore 槽位")
        
    except Exception as e:
        print(f"⚠️  客户端创建失败: {e}")


def main():
    """主测试函数"""
    print("本地模型预热功能测试")
    print("=" * 60)
    print()
    
    try:
        # 测试 1: 本地模型检测
        test_local_model_detection()
        
        # 测试 2: 本地模型预热（需要本地服务）
        test_warmup_with_local_model()
        
        # 测试 3: 云端模型（不应该触发预热）
        test_warmup_with_cloud_model()
        
        # 测试 4: 并发控制验证
        test_concurrency_control()
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print("\n提示:")
        print("1. 本地模型预热在后台线程中执行，不会阻塞初始化")
        print("2. 预热失败不会影响客户端的使用")
        print("3. 预热请求也受 Semaphore 并发控制")
        print("4. 如果本地服务未运行，预热会失败但不影响功能")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

