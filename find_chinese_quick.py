#!/usr/bin/env python3
"""
快速查找中文硬编码 - 简化版
只查找字符串字面量中的中文，排除注释和docstring
"""
import re
from pathlib import Path

CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

def find_in_file(file_path: Path):
    """查找文件中的中文硬编码"""
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        in_docstring = False
        for i, line in enumerate(lines, 1):
            # 跳过 docstring
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            
            # 跳过注释
            if '#' in line:
                comment_pos = line.find('#')
                # 简单检查：如果 # 前有引号，可能不是注释
                before_comment = line[:comment_pos]
                if before_comment.count('"') % 2 == 0 and before_comment.count("'") % 2 == 0:
                    line = before_comment
            
            # 查找字符串中的中文
            # 匹配引号内的内容
            for match in re.finditer(r'["\']([^"\']*[\u4e00-\u9fff]+[^"\']*)["\']', line):
                chinese_text = match.group(1)
                if CHINESE_PATTERN.search(chinese_text):
                    # 排除翻译键和已国际化的调用
                    before = line[:match.start()].strip()
                    if 't(' not in before and 'translate_' not in before:
                        results.append((i, line.strip(), chinese_text[:50]))
    except Exception as e:
        pass
    
    return results

# 扫描
if __name__ == '__main__':
    import sys
    
    target = sys.argv[1] if len(sys.argv) > 1 else '.'
    path = Path(target)
    
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob('*.py'))
    
    # 排除
    exclude_dirs = {'__pycache__', '.git', 'venv', 'env', 'tests', 'test'}
    files = [f for f in files if not any(part in exclude_dirs for part in f.parts)]
    files = [f for f in files if f.name not in {'zh_CN.json', 'en_US.json', 'find_chinese_quick.py'}]
    
    total = 0
    file_count = 0
    for f in files:
        results = find_in_file(f)
        if results:
            file_count += 1
            print(f"\n[FILE] {f}")
            for line_num, line, chinese in results[:10]:  # 每个文件最多显示10处
                print(f"  {line_num:4d} | {line[:80]}")
            if len(results) > 10:
                print(f"  ... 还有 {len(results) - 10} 处")
            total += len(results)
    
    print(f"\n总计: {file_count} 个文件, {total} 处中文硬编码")

