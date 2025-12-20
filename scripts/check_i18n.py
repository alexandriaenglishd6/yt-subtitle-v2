#!/usr/bin/env python
"""
i18n 一致性检查脚本

手动验证步骤：
1. 运行此脚本检查 zh_CN.json 和 en_US.json 的 key 一致性
2. 使用 grep 检查硬编码中文：grep -r "[\u4e00-\u9fa5]" core/ --include="*.py"

用法：
    python scripts/check_i18n.py
"""

import json
from pathlib import Path
import sys


def main():
    locales_dir = Path(__file__).parent.parent / "core" / "i18n" / "locales"
    
    # 加载翻译文件
    zh_file = locales_dir / "zh_CN.json"
    en_file = locales_dir / "en_US.json"
    
    if not zh_file.exists():
        print(f"错误：找不到 {zh_file}")
        return 1
    
    if not en_file.exists():
        print(f"错误：找不到 {en_file}")
        return 1
    
    zh_data = json.loads(zh_file.read_text(encoding="utf-8"))
    en_data = json.loads(en_file.read_text(encoding="utf-8"))
    
    zh_keys = set(zh_data.keys())
    en_keys = set(en_data.keys())
    
    # 检查 key 一致性
    only_in_zh = zh_keys - en_keys
    only_in_en = en_keys - zh_keys
    
    has_errors = False
    
    if only_in_zh:
        print(f"⚠️ 仅在 zh_CN.json 中的 key ({len(only_in_zh)} 个):")
        for key in sorted(only_in_zh)[:10]:
            print(f"  - {key}")
        if len(only_in_zh) > 10:
            print(f"  ... 还有 {len(only_in_zh) - 10} 个")
        has_errors = True
    
    if only_in_en:
        print(f"⚠️ 仅在 en_US.json 中的 key ({len(only_in_en)} 个):")
        for key in sorted(only_in_en)[:10]:
            print(f"  - {key}")
        if len(only_in_en) > 10:
            print(f"  ... 还有 {len(only_in_en) - 10} 个")
        has_errors = True
    
    common_keys = zh_keys & en_keys
    print(f"\n✅ 共同 key 数量: {len(common_keys)}")
    print(f"📊 zh_CN.json: {len(zh_keys)} 个 key")
    print(f"📊 en_US.json: {len(en_keys)} 个 key")
    
    if has_errors:
        print("\n❌ i18n 检查未通过，请补齐缺失的翻译 key")
        return 1
    else:
        print("\n✅ i18n 检查通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
