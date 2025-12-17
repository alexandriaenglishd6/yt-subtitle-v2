"""
LLM 客户端测试示例
演示如何使用符合 ai_design.md 规范的 LLM 调用
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.manager import AIConfig, ConfigManager
from core.ai_providers import create_llm_client
from core.llm_client import LLMException, LLMErrorType
from core.logger import get_logger

logger = get_logger()


def test_llm_translation():
    """测试 LLM 翻译功能"""
    print("=" * 60)
    print("测试 LLM 翻译功能")
    print("=" * 60)
    
    # 从配置加载 AI 设置
    config_manager = ConfigManager()
    config = config_manager.load()
    ai_config = config.ai
    
    print(f"Provider: {ai_config.provider}")
    print(f"Model: {ai_config.model}")
    print(f"Timeout: {ai_config.timeout_seconds}s")
    print(f"Max Retries: {ai_config.max_retries}")
    print()
    
    try:
        # 创建 LLM 客户端
        llm = create_llm_client(ai_config)
        print(f"✓ LLM 客户端创建成功: {ai_config.provider}")
        print()
        
        # 测试翻译
        test_prompt = """请将以下字幕从 English 翻译成 中文。

要求：
1. 保持字幕的时间轴格式（时间码）
2. 翻译要自然流畅，符合目标语言的表达习惯
3. 保持字幕的原始结构和换行

字幕内容：
1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
This is a test

请直接返回翻译后的字幕内容，保持 SRT 格式。"""
        
        system_prompt = "你是一个专业的字幕翻译助手，擅长将字幕从一种语言翻译成另一种语言，保持 SRT 格式和时间轴。"
        
        print("正在调用 LLM 进行翻译...")
        result = llm.generate(
            prompt=test_prompt,
            system=system_prompt,
            temperature=0.3
        )
        
        print("✓ 翻译成功！")
        print(f"Provider: {result.provider}")
        print(f"Model: {result.model}")
        if result.usage:
            print(f"Tokens: {result.usage.total_tokens} (prompt: {result.usage.prompt_tokens}, completion: {result.usage.completion_tokens})")
        print()
        print("翻译结果：")
        print(result.text)
        print()
        
        return True
        
    except LLMException as e:
        print(f"✗ LLM 调用失败: {e}")
        print(f"错误类型: {e.error_type}")
        if e.error_type == LLMErrorType.AUTH:
            print("提示: 请检查 API Key 是否正确配置")
        elif e.error_type == LLMErrorType.NETWORK:
            print("提示: 请检查网络连接")
        elif e.error_type == LLMErrorType.RATE_LIMIT:
            print("提示: 遇到频率限制，请稍后重试")
        return False
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_summary():
    """测试 LLM 摘要功能"""
    print("=" * 60)
    print("测试 LLM 摘要功能")
    print("=" * 60)
    
    # 从配置加载 AI 设置
    config_manager = ConfigManager()
    config = config_manager.load()
    ai_config = config.ai
    
    try:
        # 创建 LLM 客户端
        llm = create_llm_client(ai_config)
        print(f"✓ LLM 客户端创建成功: {ai_config.provider}")
        print()
        
        # 测试摘要
        test_prompt = """请用 中文 为以下视频字幕生成一份摘要。

要求：
1. 摘要语言：中文
2. 摘要长度：200-500 字（或等价的英文单词数）
3. 内容要点：
   - 视频的主要话题和核心观点
   - 关键信息和数据（如有）
   - 结论或总结（如有）
4. 格式：使用 Markdown 格式，包含标题和段落

字幕内容：
这是一个测试视频的字幕内容。视频主要讲述了人工智能的发展历史，从早期的机器学习算法到现在的深度学习模型。关键信息包括：1950年代图灵测试的提出，1980年代反向传播算法的发明，2010年代深度学习的突破。结论是人工智能正在快速发展，未来将在更多领域发挥作用。

请直接返回摘要内容（Markdown 格式）。"""
        
        system_prompt = "你是一个专业的视频内容摘要助手，擅长从字幕文本中提取关键信息，生成结构化的摘要。"
        
        print("正在调用 LLM 生成摘要...")
        result = llm.generate(
            prompt=test_prompt,
            system=system_prompt,
            temperature=0.3
        )
        
        print("✓ 摘要生成成功！")
        print(f"Provider: {result.provider}")
        print(f"Model: {result.model}")
        if result.usage:
            print(f"Tokens: {result.usage.total_tokens} (prompt: {result.usage.prompt_tokens}, completion: {result.usage.completion_tokens})")
        print()
        print("摘要结果：")
        print(result.text)
        print()
        
        return True
        
    except LLMException as e:
        print(f"✗ LLM 调用失败: {e}")
        print(f"错误类型: {e.error_type}")
        return False
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LLM 客户端测试（符合 ai_design.md 规范）")
    print("=" * 60 + "\n")
    
    print("注意：")
    print("1. 请确保已设置环境变量 YTSUB_API_KEY（或对应的 API Key）")
    print("2. 请确保已安装相应的 AI 库（openai 或 anthropic）")
    print("3. 日志中会显示 provider/model/耗时，但不会泄露 API Key")
    print()
    
    # 测试翻译
    success1 = test_llm_translation()
    
    print()
    
    # 测试摘要
    success2 = test_llm_summary()
    
    print("=" * 60)
    if success1 and success2:
        print("所有测试通过 ✓")
    else:
        print("部分测试失败，请检查配置和网络连接")
    print("=" * 60)

