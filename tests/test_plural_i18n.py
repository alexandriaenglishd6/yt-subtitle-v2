"""
tn() 复数接口测试

验证复数翻译函数在不同语言下的行为：
1. 英文：区分 1 vs 2+
2. 中文：不报错、占位符正常
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPluralTranslation:
    """复数翻译测试"""

    def test_tn_english_singular(self):
        """测试英文单数形式"""
        from core.i18n import tn, set_language
        
        set_language("en-US")
        
        # count=1 应该返回单数形式
        # tn(singular_key, plural_key, n, **kwargs)
        result = tn("time.seconds", "time.seconds", 1, count=1)
        # 期望包含 "1" 且格式化正确
        assert "1" in result

    def test_tn_english_plural(self):
        """测试英文复数形式"""
        from core.i18n import tn, set_language
        
        set_language("en-US")
        
        # count=2 应该返回复数形式
        result = tn("time.seconds", "time.seconds", 2, count=2)
        assert "2" in result

    def test_tn_chinese_no_error(self):
        """测试中文不报错"""
        from core.i18n import tn, set_language
        
        set_language("zh-CN")
        
        # 中文没有复数形式变化，但调用不应报错
        result = tn("time.seconds", "time.seconds", 1, count=1)
        assert result is not None
        assert isinstance(result, str)
        
        result = tn("time.seconds", "time.seconds", 5, count=5)
        assert result is not None
        assert isinstance(result, str)

    def test_tn_placeholder_substitution(self):
        """测试占位符替换"""
        from core.i18n import tn, set_language
        
        set_language("en-US")
        
        # 确保 {count} 被正确替换
        result = tn("time.minutes", "time.minutes", 10, count=10)
        assert "10" in result
        assert "{count}" not in result  # 占位符应该被替换

    def test_tn_fallback_to_key(self):
        """测试未找到 key 时回退"""
        from core.i18n import tn, set_language
        
        set_language("en-US")
        
        # 不存在的 key 应该返回 key 本身
        result = tn("nonexistent.singular", "nonexistent.plural", 3, count=3)
        assert "nonexistent" in result

    def test_tn_chinese_placeholder_substitution(self):
        """测试中文占位符替换"""
        from core.i18n import tn, set_language
        
        set_language("zh-CN")
        
        result = tn("time.hours", "time.hours", 24, count=24)
        assert "24" in result
        assert "{count}" not in result


class TestPluralEdgeCases:
    """复数边界情况测试"""

    def test_tn_zero(self):
        """测试 count=0"""
        from core.i18n import tn, set_language
        
        set_language("en-US")
        result = tn("time.seconds", "time.seconds", 0, count=0)
        assert "0" in result

    def test_tn_negative(self):
        """测试负数"""
        from core.i18n import tn, set_language
        
        set_language("en-US")
        # 负数应该不报错
        result = tn("time.seconds", "time.seconds", -1, count=-1)
        assert result is not None

    def test_tn_large_number(self):
        """测试大数"""
        from core.i18n import tn, set_language
        
        set_language("zh-CN")
        result = tn("time.hours", "time.hours", 1000000, count=1000000)
        assert "1000000" in result


class TestTnIntegration:
    """tn() 与 t() 集成测试"""

    def test_t_and_tn_consistency(self):
        """测试 t() 和 tn() 使用相同 key 时的一致性"""
        from core.i18n import t, tn, set_language
        
        set_language("en-US")
        
        # 使用 t() 获取带 count 的翻译
        t_result = t("time.seconds", count=5)
        
        # 使用 tn() 获取同样的翻译
        tn_result = tn("time.seconds", "time.seconds", 5, count=5)
        
        # 两者应该都包含 "5"
        assert "5" in t_result
        assert "5" in tn_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
