#!/usr/bin/env python3
"""
快速扫描代码中的中文硬编码
用法: python find_chinese_hardcode.py [目录路径]
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple

# 中文字符范围
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')

# 排除的文件和目录
EXCLUDE_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', '.venv', 
    'AI analysis', 'dist', 'build', '.pytest_cache'
}

# 排除的文件模式
EXCLUDE_FILES = {
    '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll'
}

# 排除的行模式（注释、文档字符串等）
EXCLUDE_LINE_PATTERNS = [
    r'^\s*#',  # 注释
    r'^\s*"""',  # 文档字符串开始
    r'^\s*"""',  # 文档字符串结束
    r'^\s*$',  # 空行
]

# 排除的关键词（这些行通常包含中文但可能是合法的）
EXCLUDE_KEYWORDS = [
    'i18n', 'translation', 'translated', 'locale', 'language',
    'zh_CN', 'en_US', '中文', '英文',  # 这些是配置相关的
    'encoding', 'charset', 'utf-8', 'gbk',
    'logger.info_i18n', 'logger.warning_i18n', 'logger.error_i18n',
    't(', 'translate', 'gettext'
]


def should_exclude_line(line: str) -> bool:
    """判断是否应该排除这一行"""
    line_lower = line.lower()
    
    # 检查排除关键词
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in line_lower:
            return True
    
    # 检查排除模式
    for pattern in EXCLUDE_LINE_PATTERNS:
        if re.match(pattern, line):
            return True
    
    return False


def scan_file(file_path: Path) -> List[Tuple[int, str]]:
    """扫描单个文件中的中文硬编码"""
    results = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                # 跳过排除的行
                if should_exclude_line(line):
                    continue
                
                # 检查是否包含中文
                if CHINESE_PATTERN.search(line):
                    # 提取中文部分
                    chinese_matches = CHINESE_PATTERN.findall(line)
                    results.append((line_num, line.rstrip(), chinese_matches))
    except Exception as e:
        print(f"警告: 无法读取文件 {file_path}: {e}", file=sys.stderr)
    
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
    root_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    
    print(f"正在扫描目录: {root_dir.absolute()}")
    print("=" * 80)
    
    results = scan_directory(root_dir)
    
    if not results:
        print("✅ 未找到中文硬编码！")
        return
    
    print(f"\n找到 {len(results)} 处可能的中文硬编码:\n")
    
    # 按文件分组显示
    current_file = None
    for file_path, line_num, line, chinese_matches in sorted(results):
        if current_file != file_path:
            current_file = file_path
            print(f"\n[FILE] {file_path}")
            print("-" * 80)
        
        # 显示行号和内容（Windows 控制台可能不支持颜色，所以直接显示）
        print(f"  {line_num:4d} | {line}")
        if chinese_matches:
            print(f"       | 中文部分: {', '.join(chinese_matches)}")
    
    print("\n" + "=" * 80)
    print(f"总计: {len(results)} 处")
    print("\n提示:")
    print("  - 检测到的中文已列出")
    print("  - 请检查这些是否应该迁移到翻译键")
    print("  - 如果是在注释或文档字符串中，可以忽略")


if __name__ == '__main__':
    main()
