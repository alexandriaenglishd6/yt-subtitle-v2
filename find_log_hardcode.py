#!/usr/bin/env python3
"""
专门查找日志相关的中文硬编码
用法: python find_log_hardcode.py
"""
import re
from pathlib import Path
from typing import List, Tuple

# 中文字符范围
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

# 排除的目录
EXCLUDE_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', '.venv', 
    'AI analysis', 'dist', 'build', '.pytest_cache', 'docs'
}

# 日志相关的模式
LOG_PATTERNS = [
    r'logger\.(info|warning|error|debug|critical)\([^)]*[\u4e00-\u9fff]',  # logger.info/warning/error 等
    r'on_log\([^)]*[\u4e00-\u9fff]',  # on_log 回调
    r'on_log_message\([^)]*[\u4e00-\u9fff]',  # on_log_message 回调
    r'\.configure\([^)]*text\s*=\s*[^)]*[\u4e00-\u9fff]',  # UI 组件的 text 配置
    r'AppException\([^)]*[\u4e00-\u9fff]',  # AppException
    r'LLMException\([^)]*[\u4e00-\u9fff]',  # LLMException
    r'raise\s+\w+Exception\([^)]*[\u4e00-\u9fff]',  # 其他异常
]

# 排除的关键词（这些行通常包含中文但可能是合法的）
EXCLUDE_KEYWORDS = [
    'i18n', 'translation', 'translated', 'locale', 'language',
    'zh_CN', 'en_US', 'encoding', 'charset', 'utf-8', 'gbk',
    'logger.info_i18n', 'logger.warning_i18n', 'logger.error_i18n',
    'logger.debug_i18n', 'logger.critical_i18n',
    't(', 'translate', 'gettext', 'docstring', '"""', "'''",
    '#',  # 注释
]


def should_exclude_line(line: str) -> bool:
    """判断是否应该排除这一行"""
    line_lower = line.lower().strip()
    
    # 跳过空行
    if not line_lower:
        return True
    
    # 跳过注释
    if line_lower.startswith('#'):
        return True
    
    # 跳过文档字符串
    if line_lower.startswith('"""') or line_lower.startswith("'''"):
        return True
    
    # 检查排除关键词
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in line_lower:
            return True
    
    return False


def is_log_related(line: str) -> bool:
    """判断是否是日志相关的行"""
    for pattern in LOG_PATTERNS:
        if re.search(pattern, line):
            return True
    return False


def scan_file(file_path: Path) -> List[Tuple[int, str, List[str]]]:
    """扫描单个文件中的日志相关中文硬编码"""
    results = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                # 跳过排除的行
                if should_exclude_line(line):
                    continue
                
                # 检查是否是日志相关的行
                if not is_log_related(line):
                    continue
                
                # 检查是否包含中文
                if CHINESE_PATTERN.search(line):
                    chinese_matches = CHINESE_PATTERN.findall(line)
                    results.append((line_num, line.rstrip(), chinese_matches))
    except Exception as e:
        print(f"警告: 无法读取文件 {file_path}: {e}")
    
    return results


def scan_directory(root_dir: Path = None) -> List[Tuple[Path, int, str, List[str]]]:
    """扫描目录中的所有 Python 文件"""
    if root_dir is None:
        root_dir = Path('.')
    
    all_results = []
    
    # 扫描所有 .py 文件
    for py_file in root_dir.rglob('*.py'):
        # 跳过排除的目录
        if any(exclude in str(py_file) for exclude in EXCLUDE_DIRS):
            continue
        
        # 扫描文件
        file_results = scan_file(py_file)
        for line_num, line, chinese_matches in file_results:
            all_results.append((py_file, line_num, line, chinese_matches))
    
    return all_results


def main():
    """主函数"""
    import sys
    import io
    
    # 设置输出编码为 UTF-8
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    root_dir = Path('.')
    
    print("正在扫描日志相关的中文硬编码...")
    print("=" * 80)
    
    results = scan_directory(root_dir)
    
    if not results:
        print("未找到日志相关的中文硬编码！")
        return
    
    print(f"\n找到 {len(results)} 处日志相关的中文硬编码:\n")
    
    # 按文件分组显示
    current_file = None
    for file_path, line_num, line, chinese_matches in sorted(results):
        if current_file != file_path:
            current_file = file_path
            print(f"\n[FILE] {file_path}")
            print("-" * 80)
        
        print(f"  {line_num:4d} | {line}")
        if chinese_matches:
            print(f"       | Chinese: {', '.join(chinese_matches)}")
    
    print("\n" + "=" * 80)
    print(f"Total: {len(results)} places")
    print("\nSuggestions:")
    print("  1. Migrate these log messages to translation keys")
    print("  2. Use logger.info_i18n() instead of logger.info()")
    print("  3. Add corresponding translation keys to ui/i18n/zh_CN.json and en_US.json")


if __name__ == '__main__':
    main()

