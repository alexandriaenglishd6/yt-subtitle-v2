#!/usr/bin/env python3
"""
扫描中文硬编码并输出到文件
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')
EXCLUDE_DIRS = {'__pycache__', '.git', 'node_modules', 'venv', '.venv', 'AI analysis', 'dist', 'build', '.pytest_cache', 'tests', 'test'}
EXCLUDE_FILES = {'find_chinese_hardcode.py', 'find_chinese_quick.py', 'find_chinese_smart.py', 'scan_chinese.py'}

I18N_PATTERNS = [
    r't\s*\(', r'logger\.(info|debug|warning|error|critical)_i18n\s*\(',
    r'translate_(log|exception)\s*\(', r'gettext\s*\(',
    r'["\']log\.', r'["\']exception\.',
]

LOG_METHODS = [
    r'logger\.(info|debug|warning|error|critical)\s*\(',
    r'AppException\s*\(', r'LLMException\s*\(',
]

def is_i18n_line(line):
    for pattern in I18N_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False

def is_in_comment(line):
    stripped = line.strip()
    if stripped.startswith('#'):
        return True
    comment_pos = line.find('#')
    if comment_pos > 0:
        before = line[:comment_pos]
        if before.count('"') % 2 == 1 or before.count("'") % 2 == 1:
            return False
        return True
    return False

def find_chinese_in_file(file_path):
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            if is_i18n_line(line) or is_in_comment(line):
                continue
            
            if CHINESE_PATTERN.search(line):
                is_log = any(re.search(p, line, re.IGNORECASE) for p in LOG_METHODS)
                results.append({
                    'file': str(file_path),
                    'line_num': line_num,
                    'line': line.rstrip(),
                    'is_log': is_log
                })
    except Exception as e:
        pass
    return results

def scan_directory(root_dir=Path('.')):
    all_results = []
    for py_file in root_dir.rglob('*.py'):
        if any(exclude in str(py_file) for exclude in EXCLUDE_DIRS):
            continue
        if py_file.name in EXCLUDE_FILES:
            continue
        results = find_chinese_in_file(py_file)
        all_results.extend(results)
    return all_results

def main():
    results = scan_directory()
    
    # 按文件分组
    by_file = defaultdict(list)
    for r in results:
        by_file[r['file']].append(r)
    
    # 输出到文件
    with open('chinese_hardcode_report.txt', 'w', encoding='utf-8') as f:
        f.write(f"总计: {len(results)} 处中文硬编码\n")
        f.write("=" * 80 + "\n\n")
        
        # 优先显示日志相关的
        log_files = []
        other_files = []
        for file_path, file_results in by_file.items():
            if any(r['is_log'] for r in file_results):
                log_files.append((file_path, file_results))
            else:
                other_files.append((file_path, file_results))
        
        f.write("[日志相关] 优先处理:\n")
        f.write("-" * 80 + "\n")
        for file_path, file_results in sorted(log_files):
            f.write(f"\n{file_path} ({len(file_results)} 处):\n")
            for r in file_results[:20]:  # 每个文件最多20处
                f.write(f"  {r['line_num']:4d} | {r['line'][:100]}\n")
            if len(file_results) > 20:
                f.write(f"  ... 还有 {len(file_results) - 20} 处\n")
        
        f.write(f"\n\n[其他] ({len([r for _, rs in other_files for r in rs])} 处):\n")
        f.write("-" * 80 + "\n")
        for file_path, file_results in sorted(other_files)[:10]:  # 只显示前10个文件
            f.write(f"\n{file_path} ({len(file_results)} 处):\n")
            for r in file_results[:5]:
                f.write(f"  {r['line_num']:4d} | {r['line'][:100]}\n")
    
    print(f"扫描完成！找到 {len(results)} 处中文硬编码")
    print("报告已保存到: chinese_hardcode_report.txt")
    print(f"日志相关: {len([r for r in results if r['is_log']])} 处")
    print(f"其他: {len([r for r in results if not r['is_log']])} 处")

if __name__ == '__main__':
    main()

