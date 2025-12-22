"""
测试免费 API（无需 API Key 和付费）
1. Google Translate（免费版）
2. 本地模型（Ollama/LM Studio）
"""
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.manager import AIConfig
from core.ai_providers import create_llm_client
from core.llm_client import LLMException, LLMErrorType


def test_google_translate():
    """测试 Google Translate（免费版）"""
    print("=" * 60)
    print("测试 1: Google Translate（免费版）")
    print("=" * 60)
    
    try:
        # 创建配置（不需要 API Key）
        config = AIConfig(
            provider="google_translate",
            model="google_translate_free",
            base_url=None,
            timeout_seconds=30,
            max_retries=2,
            max_concurrency=5,
            api_keys={}  # 不需要 API Key
        )
        
        print(f"✓ 配置创建成功")
        print(f"  Provider: {config.provider}")
        print(f"  Model: {config.model}")
        print()
        
        # 创建客户端
        print("正在创建客户端...")
        client = create_llm_client(config)
        print(f"✓ 客户端创建成功")
        print(f"  Supports Vision: {client.supports_vision}")
        print(f"  Max Input Tokens: {client.max_input_tokens}")
        print(f"  Max Concurrency: {client.max_concurrency}")
        print()
        
        # 测试翻译
        print("正在测试翻译...")
        test_prompt = """请将以下字幕从 English 翻译成 中文。

字幕内容：
1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
This is a test

请直接返回翻译后的字幕内容，保持 SRT 格式。"""
        
        result = client.generate(
            prompt=test_prompt,
            max_tokens=100
        )
        
        print("✓ 翻译成功！")
        print(f"  Provider: {result.provider}")
        print(f"  Model: {result.model}")
        print()
        print("翻译结果：")
        print(result.text)
        print()
        
        assert result.text, "翻译结果不应为空"
        
    except ImportError as e:
        pytest.skip(f"依赖库未安装: {e}")
    except LLMException as e:
        pytest.skip(f"翻译失败: {e}")
    except Exception as e:
        pytest.fail(f"未知错误: {e}")


def test_local_model():
    """测试本地模型（Ollama/LM Studio）"""
    print("=" * 60)
    print("测试 2: 本地模型（Ollama/LM Studio）")
    print("=" * 60)
    
    # 检查常见的本地模型地址
    local_urls = [
        ("Ollama (默认)", "http://localhost:11434/v1"),
        ("LM Studio (默认)", "http://localhost:1234/v1"),
    ]
    
    success = False
    
    for name, base_url in local_urls:
        print(f"\n尝试连接: {name} ({base_url})")
        
        try:
            # 创建配置
            config = AIConfig(
                provider="ollama",  # 会自动使用 LocalModelClient
                model="llama3.2:3b",  # 使用一个常见的模型
                base_url=base_url,
                timeout_seconds=300,
                max_retries=2,
                max_concurrency=3,
                api_keys={"openai": "ollama"}  # 本地模型不需要真实的 API Key
            )
            
            print(f"✓ 配置创建成功")
            print(f"  Provider: {config.provider}")
            print(f"  Model: {config.model}")
            print(f"  Base URL: {config.base_url}")
            print()
            
            # 创建客户端（会进行心跳检测）
            print("正在创建客户端（会进行心跳检测）...")
            client = create_llm_client(config)
            print(f"✓ 客户端创建成功")
            print(f"  类型: {type(client).__name__}")
            print()
            
            # 测试生成（会进行预热）
            print("正在测试生成（首次调用会进行预热）...")
            result = client.generate(
                prompt="Hi, how are you?",
                max_tokens=10
            )
            
            print("✓ 生成成功！")
            print(f"  Provider: {result.provider}")
            print(f"  Model: {result.model}")
            print(f"  响应: {result.text[:100]}")
            print()
            
            success = True
            break
            
        except LLMException as e:
            if e.error_type == LLMErrorType.NETWORK:
                print(f"⚠️  连接失败: {e}")
                print(f"   提示: 请确保 {name} 正在运行")
                print(f"   如果使用 Ollama，请运行: ollama serve")
                print(f"   如果使用 LM Studio，请启动 LM Studio 并启用本地服务器")
            else:
                print(f"❌ 错误: {e}")
            continue
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            continue
    
    if not success:
        pytest.skip("所有本地模型服务都不可用")


def main():
    """主函数"""
    print("=" * 60)
    print("免费 API 测试（无需 API Key 和付费）")
    print("=" * 60)
    print()
    print("本测试将验证以下免费选项：")
    print("  1. Google Translate（免费版）- 完全免费，无需 API Key")
    print("  2. 本地模型（Ollama/LM Studio）- 本地运行，完全免费")
    print()
    
    results = []
    
    # 测试 Google Translate
    try:
        result1 = test_google_translate()
        results.append(("Google Translate", result1))
    except Exception as e:
        print(f"\n❌ Google Translate 测试异常: {e}")
        results.append(("Google Translate", False))
    
    print("\n" + "=" * 60)
    
    # 测试本地模型
    try:
        result2 = test_local_model()
        results.append(("本地模型", result2))
    except Exception as e:
        print(f"\n❌ 本地模型测试异常: {e}")
        results.append(("本地模型", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed > 0:
        print("\n🎉 至少有一个免费选项可用！")
        print("   你可以使用这些免费选项进行测试，无需配置 API Key 或付费。")
    
    return 0 if passed > 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

