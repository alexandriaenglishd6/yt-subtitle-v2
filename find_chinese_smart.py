#!/usr/bin/env python3
"""
智能查找中文硬编码工具
- 精确识别需要国际化的中文硬编码
- 排除已国际化的代码（t(), logger.info_i18n() 等）
- 排除注释、文档字符串、翻译文件
- 按优先级分类显示（日志 > UI文本 > 其他）
"""
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# 中文字符范围
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

# 排除的目录
EXCLUDE_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', '.venv',
    'AI analysis', 'dist', 'build', '.pytest_cache', 'tests', 'test',
    '__init__.py'
}

# 排除的文件
EXCLUDE_FILES = {
    'find_chinese_hardcode.py', 'find_chinese_quick.py',
    'find_chinese_smart.py', 'zh_CN.json', 'en_US.json',
    'find_and_replace_chinese.py', 'find_log_hardcode.py'
}

# 已国际化的模式（这些行应该被排除）
I18N_PATTERNS = [
    r't\s*\(',  # t("key")
    r'logger\.(info|debug|warning|error|critical)_i18n\s*\(',  # logger.info_i18n("key")
    r'translate_(log|exception)\s*\(',  # translate_log("key")
    r'gettext\s*\(',  # gettext("key")
    r'["\']log\.',  # "log.key" 或 'log.key'
    r'["\']exception\.',  # "exception.key" 或 'exception.key'
    r'["\']cookie_',  # "cookie_xxx"
    r'["\']proxy_',  # "proxy_xxx"
    r'["\']concurrency_',  # "concurrency_xxx"
    r'["\'][a-z_]+_[a-z_]+["\']',  # 可能是翻译键（如 "cookie_test_failed"）
]

# 常见的日志方法（这些方法中的中文需要国际化）
LOG_METHODS = [
    r'logger\.(info|debug|warning|error|critical)\s*\(',
    r'log_(info|debug|warning|error)\s*\(',
    r'print\s*\(',
    r'self\.on_log_message\s*\(',
    r'on_log\s*\(',
    r'AppException\s*\(',
    r'LLMException\s*\(',
]

# 常见的UI文本赋值（这些赋值中的中文需要国际化）
UI_TEXT_PATTERNS = [
    r'\.configure\s*\([^)]*text\s*=\s*',
    r'text\s*=\s*["\']',
    r'label\s*=\s*["\']',
    r'title\s*=\s*["\']',
    r'placeholder\s*=\s*["\']',
    r'error\s*=\s*["\']',
    r'message\s*=\s*["\']',
    r'description\s*=\s*["\']',
]


def is_i18n_line(line: str) -> bool:
    """检查行是否已经国际化"""
    for pattern in I18N_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def is_in_comment(line: str) -> bool:
    """检查是否在注释中"""
    stripped = line.strip()
    if stripped.startswith('#'):
        return True
    
    # 检查行内注释
    comment_pos = line.find('#')
    if comment_pos > 0:
        before_comment = line[:comment_pos]
        # 如果 # 前有奇数个引号，说明在字符串中
        if before_comment.count('"') % 2 == 1 or before_comment.count("'") % 2 == 1:
            return False
        return True
    
    return False


def is_in_docstring(content: str, line_num: int) -> bool:
    """检查是否在文档字符串中"""
    lines = content.split('\n')
    in_triple_quote = False
    quote_type = None
    
    for i, line in enumerate(lines[:line_num], 1):
        if '"""' in line:
            if not in_triple_quote:
                in_triple_quote = True
                quote_type = '"""'
            elif quote_type == '"""':
                in_triple_quote = False
                quote_type = None
        elif "'''" in line:
            if not in_triple_quote:
                in_triple_quote = True
                quote_type = "'''"
            elif quote_type == "'''":
                in_triple_quote = False
                quote_type = None
    
    return in_triple_quote


def extract_chinese_strings(line: str) -> List[Tuple[int, int, str]]:
    """提取行中的中文字符串（返回 (start, end, text) 元组列表）"""
    results = []
    
    # 匹配字符串字面量（单引号、双引号、三引号）
    string_patterns = [
        (r'["\']([^"\']*[\u4e00-\u9fff]+[^"\']*)["\']', 1),  # 普通字符串
        (r'"""([^"]*[\u4e00-\u9fff]+[^"]*)"""', 1),  # 三引号双引号
        (r"'''([^']*[\u4e00-\u9fff]+[^']*)'''", 1),  # 三引号单引号
    ]
    
    for pattern, group_num in string_patterns:
        for match in re.finditer(pattern, line):
            chinese_text = match.group(group_num)
            if CHINESE_PATTERN.search(chinese_text):
                results.append((match.start(), match.end(), chinese_text))
    
    return results


def classify_line(line: str) -> str:
    """分类行的类型"""
    # 检查是否是日志相关
    for pattern in LOG_METHODS:
        if re.search(pattern, line, re.IGNORECASE):
            return 'log'
    
    # 检查是否是UI文本相关
    for pattern in UI_TEXT_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return 'ui'
    
    return 'other'


def find_chinese_in_file(file_path: Path) -> List[Dict]:
    """查找文件中的中文硬编码"""
    results = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # 跳过已国际化的行
            if is_i18n_line(line):
                continue
            
            # 跳过注释
            if is_in_comment(line):
                continue
            
            # 跳过文档字符串
            if is_in_docstring(content, line_num):
                continue
            
            # 提取中文字符串
            chinese_strings = extract_chinese_strings(line)
            if not chinese_strings:
                continue
            
            # 分类
            line_type = classify_line(line)
            
            for start, end, chinese_text in chinese_strings:
                results.append({
                    'file': str(file_path),
                    'line_num': line_num,
                    'line': line.rstrip(),
                    'chinese': chinese_text,
                    'type': line_type,
                    'start': start,
                    'end': end,
                })
    
    except Exception as e:
        print(f"警告: 无法读取文件 {file_path}: {e}", file=sys.stderr)
    
    return results


def scan_directory(root_dir: Path = None) -> List[Dict]:
    """扫描目录中的所有 Python 文件"""
    if root_dir is None:
        root_dir = Path('.')
    
    all_results = []
    
    # 扫描所有 .py 文件
    for py_file in root_dir.rglob('*.py'):
        # 跳过排除的目录
        if any(exclude in str(py_file) for exclude in EXCLUDE_DIRS):
            continue
        
        # 跳过排除的文件
        if py_file.name in EXCLUDE_FILES:
            continue
        
        # 扫描文件
        file_results = find_chinese_in_file(py_file)
        all_results.extend(file_results)
    
    return all_results


def main():
    """主函数"""
    root_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    
    print(f"正在扫描目录: {root_dir.absolute()}")
    print("=" * 80)
    
    results = scan_directory(root_dir)
    
    if not results:
        print("未找到中文硬编码！")
        return
    
    # 按类型分组
    by_type = defaultdict(list)
    for result in results:
        by_type[result['type']].append(result)
    
    # 按优先级显示：log > ui > other
    type_order = ['log', 'ui', 'other']
    type_names = {'log': '[日志相关]', 'ui': '[UI文本相关]', 'other': '[其他]'}
    
    total = 0
    for type_key in type_order:
        if type_key not in by_type:
            continue
        
        type_results = by_type[type_key]
        if not type_results:
            continue
        
        print(f"\n{type_names[type_key]} ({len(type_results)} 处):")
        print("-" * 80)
        
        # 按文件分组
        by_file = defaultdict(list)
        for result in type_results:
            by_file[result['file']].append(result)
        
        for file_path in sorted(by_file.keys()):
            file_results = by_file[file_path]
            print(f"\n  [FILE] {file_path}")
            for result in file_results[:10]:  # 每个文件最多显示10处
                print(f"    {result['line_num']:4d} | {result['line'][:75]}")
                print(f"         | 中文: {result['chinese'][:60]}")
            if len(file_results) > 10:
                print(f"    ... 还有 {len(file_results) - 10} 处")
        
        total += len(type_results)
    
    print("\n" + "=" * 80)
    print(f"总计: {total} 处中文硬编码")
    print("\n提示:")
    print("  - 日志相关: 应使用 logger.info_i18n() 等方法")
    print("  - UI文本相关: 应使用 t() 函数")
    print("  - 其他: 请检查是否需要国际化")
    print("  - 如果是在注释或文档字符串中，可以忽略")


if __name__ == '__main__':
    main()

