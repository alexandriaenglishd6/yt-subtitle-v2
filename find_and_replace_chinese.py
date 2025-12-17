#!/usr/bin/env python3
"""
智能查找和替换中文硬编码工具
- 精确识别需要国际化的中文硬编码
- 排除已国际化的代码（t(), logger.info_i18n() 等）
- 提供替换建议和批量替换功能
"""
import re
import sys
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

# 中文字符范围
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

# 排除的目录
EXCLUDE_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', '.venv',
    'AI analysis', 'dist', 'build', '.pytest_cache', 'tests', 'test'
}

# 排除的文件
EXCLUDE_FILES = {
    'find_chinese_hardcode.py', 'find_chinese_quick.py', 
    'find_and_replace_chinese.py', 'zh_CN.json', 'en_US.json'
}

# 已国际化的模式（这些行应该被排除）
I18N_PATTERNS = [
    r't\s*\(',  # t("key")
    r'logger\.(info|debug|warning|error|critical)_i18n\s*\(',  # logger.info_i18n("key")
    r'translate_(log|exception)\s*\(',  # translate_log("key")
    r'gettext\s*\(',  # gettext("key")
    r'_\s*\(',  # _("key")
    r'["\']log\.',  # "log.key" 或 'log.key'
    r'["\']exception\.',  # "exception.key" 或 'exception.key'
    r'["\'][a-z_]+_[a-z_]+["\']',  # 可能是翻译键（如 "cookie_test_failed"）
]

# 常见的日志方法（这些方法中的中文需要国际化）
LOG_METHODS = [
    r'logger\.(info|debug|warning|error|critical)\s*\(',
    r'log_(info|debug|warning|error)\s*\(',
    r'print\s*\(',
    r'self\.on_log_message\s*\(',
    r'on_log\s*\(',
]

# 常见的字符串赋值（这些赋值中的中文需要国际化）
STRING_ASSIGNMENTS = [
    r'text\s*=',
    r'label\s*=',
    r'title\s*=',
    r'placeholder\s*=',
    r'error\s*=',
    r'message\s*=',
    r'description\s*=',
]


def is_i18n_line(line: str) -> bool:
    """检查行是否已经国际化"""
    for pattern in I18N_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def is_in_comment(line: str) -> bool:
    """检查是否在注释中"""
    # 移除字符串内容，只检查注释
    # 简单处理：查找 # 号，如果前面没有未闭合的引号，就是注释
    comment_pos = line.find('#')
    if comment_pos == -1:
        return False
    
    before_comment = line[:comment_pos]
    # 检查引号是否配对
    single_quotes = before_comment.count("'") - before_comment.count("\\'")
    double_quotes = before_comment.count('"') - before_comment.count('\\"')
    
    # 如果引号配对，说明 # 在注释中
    if single_quotes % 2 == 0 and double_quotes % 2 == 0:
        return True
    
    return False


def is_in_docstring(content: str, line_num: int) -> bool:
    """检查行是否在文档字符串中"""
    lines = content.split('\n')
    in_triple_quote = False
    quote_type = None
    
    for i, line in enumerate(lines[:line_num], 1):
        # 检查三引号
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
    """提取行中的中文字符串（返回位置和内容）"""
    results = []
    
    # 匹配字符串字面量（单引号、双引号、三引号）
    patterns = [
        (r'["\']([^"\']*[\u4e00-\u9fff]+[^"\']*)["\']', 'single'),  # 单行字符串
        (r'"""([^"]*[\u4e00-\u9fff]+[^"]*)"""', 'triple_double'),  # 三引号双引号
        (r"'''([^']*[\u4e00-\u9fff]+[^']*)'''", 'triple_single'),  # 三引号单引号
    ]
    
    for pattern, quote_type in patterns:
        for match in re.finditer(pattern, line):
            start, end = match.span()
            chinese_text = match.group(1)
            if CHINESE_PATTERN.search(chinese_text):
                results.append((start, end, chinese_text))
    
    return results


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
            
            # 检查是否在日志方法或字符串赋值中
            is_log_method = any(re.search(pattern, line, re.IGNORECASE) for pattern in LOG_METHODS)
            is_string_assign = any(re.search(pattern, line, re.IGNORECASE) for pattern in STRING_ASSIGNMENTS)
            
            for start, end, chinese_text in chinese_strings:
                results.append({
                    'file': str(file_path),
                    'line_num': line_num,
                    'line': line.rstrip(),
                    'chinese': chinese_text,
                    'start': start,
                    'end': end,
                    'is_log': is_log_method,
                    'is_assign': is_string_assign,
                    'context': _get_context(lines, line_num),
                })
    
    except Exception as e:
        print(f"警告: 无法读取文件 {file_path}: {e}", file=sys.stderr)
    
    return results


def _get_context(lines: List[str], line_num: int, context_lines: int = 2) -> str:
    """获取上下文"""
    start = max(0, line_num - context_lines - 1)
    end = min(len(lines), line_num + context_lines)
    context = lines[start:end]
    return '\n'.join(context)


def scan_directory(root_dir: Path = None) -> List[Dict]:
    """扫描目录中的所有 Python 文件"""
    if root_dir is None:
        root_dir = Path('.')
    
    all_results = []
    
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


def suggest_translation_key(chinese_text: str, context: Dict) -> str:
    """建议翻译键名称"""
    # 简化中文文本，提取关键词
    # 移除标点、空格等
    simplified = re.sub(r'[^\u4e00-\u9fff]', '', chinese_text)
    
    # 根据上下文生成键名
    if context['is_log']:
        prefix = 'log.'
    elif context['is_assign']:
        prefix = ''
    else:
        prefix = 'log.'
    
    # 简单的键名生成（实际应该更智能）
    # 这里只是示例，实际应该根据具体内容生成
    key = simplified[:20] if len(simplified) > 20 else simplified
    
    return f"{prefix}{key}"


def print_results(results: List[Dict], output_format: str = 'text'):
    """打印结果"""
    if not results:
        print("✅ 未找到需要国际化的中文硬编码！")
        return
    
    # 按文件分组
    by_file = defaultdict(list)
    for result in results:
        by_file[result['file']].append(result)
    
    if output_format == 'text':
        print(f"\n找到 {len(results)} 处需要国际化的中文硬编码:\n")
        print("=" * 100)
        
        for file_path, file_results in sorted(by_file.items()):
            print(f"\n[FILE] {file_path}")
            print("-" * 100)
            
            for result in file_results:
                print(f"\n  行 {result['line_num']:4d} | {result['line']}")
                print(f"         | 中文: {result['chinese'][:60]}...")
                if result['is_log']:
                    print(f"         | 类型: 日志消息")
                elif result['is_assign']:
                    print(f"         | 类型: 字符串赋值")
                else:
                    print(f"         | 类型: 其他")
                print(f"         | 建议键: {suggest_translation_key(result['chinese'], result)}")
        
        print("\n" + "=" * 100)
        print(f"总计: {len(results)} 处")
        print("\n提示:")
        print("  - 使用 --json 参数可以导出 JSON 格式")
        print("  - 使用 --replace 参数可以批量替换（需要手动确认）")
    
    elif output_format == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2))


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='智能查找和替换中文硬编码')
    parser.add_argument('directory', nargs='?', default='.', help='要扫描的目录（默认：当前目录）')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')
    parser.add_argument('--output', '-o', help='输出到文件')
    parser.add_argument('--replace', action='store_true', help='交互式批量替换（实验性）')
    
    args = parser.parse_args()
    
    root_dir = Path(args.directory)
    if not root_dir.exists():
        print(f"错误: 目录不存在: {root_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"正在扫描目录: {root_dir.absolute()}")
    print("排除已国际化的代码（t(), logger.info_i18n() 等）...")
    
    results = scan_directory(root_dir)
    
    output_format = 'json' if args.json else 'text'
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            if output_format == 'json':
                json.dump(results, f, ensure_ascii=False, indent=2)
            else:
                # 重定向输出到文件
                import io
                output = io.StringIO()
                print_results(results, output_format)
                f.write(output.getvalue())
        print(f"\n结果已保存到: {args.output}")
    else:
        print_results(results, output_format)


if __name__ == '__main__':
    main()

