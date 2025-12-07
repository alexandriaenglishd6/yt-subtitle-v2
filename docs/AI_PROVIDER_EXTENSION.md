# AI 提供商扩展指南

## 概述

本项目使用**策略模式**和**工厂模式**设计 AI 提供商架构，使得添加新的 AI 提供商变得非常简单，**无需修改核心代码**。

## 架构设计

### 核心组件

1. **`AIProvider` 抽象基类** (`core/ai_providers.py`)
   - 定义统一的接口：`call()` 和 `check_dependencies()`
   - 所有提供商都必须实现这个接口

2. **提供商注册表** (`_PROVIDER_REGISTRY`)
   - 自动注册所有内置提供商
   - 支持动态注册新提供商

3. **工厂方法** (`get_provider()`)
   - 根据配置自动创建对应的提供商实例
   - 核心代码无需关心具体是哪个提供商

## 如何添加新的 AI 提供商

### 方法 1：在项目中添加（推荐用于常用提供商）

1. **创建提供商类**

   在 `core/ai_providers.py` 中添加新类：

   ```python
   class GoogleProvider(AIProvider):
       """Google Gemini 提供商实现"""
       
       def check_dependencies(self) -> bool:
           """检查依赖库是否已安装"""
           try:
               import google.generativeai
               return True
           except ImportError:
               logger.error("未安装 google-generativeai 库，请运行: pip install google-generativeai")
               return False
       
       def call(self, system_prompt: str, user_prompt: str) -> Optional[str]:
           """调用 Google Gemini API"""
           if not self.check_dependencies():
               return None
           
           try:
               import google.generativeai as genai
               
               genai.configure(api_key=self.api_key)
               model = genai.GenerativeModel(self.ai_config.model)
               
               full_prompt = f"{system_prompt}\n\n{user_prompt}"
               response = model.generate_content(full_prompt)
               
               return response.text
               
           except Exception as e:
               logger.error(f"Google Gemini API 调用失败: {e}")
               return None
   ```

2. **注册提供商**

   在 `_PROVIDER_REGISTRY` 中添加：

   ```python
   _PROVIDER_REGISTRY: dict[str, type[AIProvider]] = {
       "openai": OpenAIProvider,
       "anthropic": AnthropicProvider,
       "google": GoogleProvider,  # 新增
   }
   ```

3. **完成！**

   现在用户只需要在 `config.json` 中设置：
   ```json
   {
     "ai": {
       "provider": "google",
       "model": "gemini-pro",
       "api_key_env": "GOOGLE_API_KEY"
     }
   }
   ```

### 方法 2：作为插件添加（推荐用于第三方扩展）

如果不想修改项目核心代码，可以在用户代码或插件中注册：

```python
# 用户代码或插件文件
from core.ai_providers import register_provider, AIProvider
from typing import Optional

class MyCustomProvider(AIProvider):
    """自定义 AI 提供商"""
    
    def check_dependencies(self) -> bool:
        try:
            import my_ai_library
            return True
        except ImportError:
            return False
    
    def call(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.check_dependencies():
            return None
        
        # 实现自定义逻辑
        import my_ai_library
        client = my_ai_library.Client(api_key=self.api_key)
        result = client.generate(
            model=self.ai_config.model,
            system=system_prompt,
            prompt=user_prompt
        )
        return result.text

# 注册提供商
register_provider("my_custom", MyCustomProvider)
```

## 优势

### ✅ 无需修改核心代码

添加新提供商时，**完全不需要修改**：
- `core/translator.py` - 翻译模块
- `core/summarizer.py` - 摘要模块（未来）
- 任何使用 AI 的代码

### ✅ 统一的接口

所有提供商都实现相同的接口：
- `call(system_prompt, user_prompt)` - 调用 AI
- `check_dependencies()` - 检查依赖

### ✅ 自动依赖检查

每个提供商自动检查自己的依赖库，给出清晰的错误提示。

### ✅ 配置驱动

用户只需修改 `config.json` 即可切换提供商，无需改代码。

## 示例：添加支持

假设要添加对以下提供商的支持：

- **Google Gemini**: 添加 `GoogleProvider` 类
- **Cohere**: 添加 `CohereProvider` 类
- **本地模型 (Ollama)**: 添加 `OllamaProvider` 类
- **自定义 API**: 添加 `CustomProvider` 类

每个提供商只需要：
1. 继承 `AIProvider`
2. 实现 `call()` 和 `check_dependencies()`
3. 注册到 `_PROVIDER_REGISTRY`

**核心代码完全不需要改动！**

## 当前支持的提供商

- ✅ OpenAI (GPT-4, GPT-3.5 等)
- ✅ Anthropic (Claude 系列)

## 未来可扩展的提供商

- Google Gemini
- Cohere
- 本地模型 (Ollama, LM Studio)
- 其他兼容 OpenAI API 的提供商

## 总结

通过使用**抽象基类 + 工厂模式 + 注册表**的设计，添加新 AI 提供商变得非常简单：

1. **创建新类**（继承 `AIProvider`）
2. **注册到表**（一行代码）
3. **完成！**（无需修改其他代码）

这种设计遵循了**开闭原则**（对扩展开放，对修改关闭），使得系统具有良好的可扩展性。

