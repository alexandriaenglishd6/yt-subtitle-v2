#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查项目文件的编码问题
"""
import os
import sys
import chardet
from pathlib import Path

# 设置输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def check_file_encoding(file_path: Path) -> dict:
    """检查文件编码"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return {
                'file': str(file_path),
                'encoding': result['encoding'],
                'confidence': result['confidence'],
                'size': len(raw_data)
            }
    except Exception as e:
        return {
            'file': str(file_path),
            'error': str(e)
        }

def check_chinese_chars(file_path: Path) -> dict:
    """检查文件中的中文字符是否正常"""
    try:
        # 尝试用 UTF-8 读取
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            chinese_count = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
            return {
                'file': str(file_path),
                'utf8_readable': True,
                'chinese_chars': chinese_count,
                'total_chars': len(content)
            }
    except UnicodeDecodeError as e:
        return {
            'file': str(file_path),
            'utf8_readable': False,
            'error': f'UTF-8 decode error: {e}'
        }
    except Exception as e:
        return {
            'file': str(file_path),
            'error': str(e)
        }

def main():
    """主函数"""
    print("=" * 60)
    print("文件编码检查工具")
    print("=" * 60)
    
    # 要检查的关键文件
    key_files = [
        'core/output.py',
        'core/pipeline.py',
        'core/prompts.py',
        'ui/i18n/zh_CN.json',
        'ui/i18n/en_US.json',
        'docs/dev_log.md',
        'docs/ide_修复任务表_AI层与流水线.md',
    ]
    
    print("\n1. 检查文件编码（使用 chardet）:")
    print("-" * 60)
    for file_path_str in key_files:
        file_path = Path(file_path_str)
        if file_path.exists():
            result = check_file_encoding(file_path)
            if 'error' in result:
                print(f"❌ {file_path_str}: {result['error']}")
            else:
                encoding = result['encoding']
                confidence = result['confidence']
                status = "[OK]" if encoding and confidence > 0.7 else "[WARN]"
                print(f"{status} {file_path_str}: {encoding} (置信度: {confidence:.2f})")
        else:
            print(f"[WARN] {file_path_str}: 文件不存在")
    
    print("\n2. 检查 UTF-8 可读性和中文字符:")
    print("-" * 60)
    for file_path_str in key_files:
        file_path = Path(file_path_str)
        if file_path.exists():
            result = check_chinese_chars(file_path)
            if 'error' in result:
                print(f"[ERROR] {file_path_str}: {result['error']}")
            else:
                if result['utf8_readable']:
                    chinese = result.get('chinese_chars', 0)
                    total = result.get('total_chars', 0)
                    status = "[OK]" if chinese > 0 or total > 0 else "[WARN]"
                    print(f"{status} {file_path_str}: UTF-8 可读, 中文字符: {chinese}, 总字符: {total}")
                else:
                    print(f"[ERROR] {file_path_str}: UTF-8 不可读 - {result.get('error', 'Unknown')}")
        else:
            print(f"[WARN] {file_path_str}: 文件不存在")
    
    print("\n3. Git 配置检查:")
    print("-" * 60)
    import subprocess
    try:
        result = subprocess.run(['git', 'config', '--global', '--get', 'i18n.commitencoding'], 
                              capture_output=True, text=True)
        commit_encoding = result.stdout.strip() or '未设置'
        print(f"i18n.commitencoding: {commit_encoding}")
        
        result = subprocess.run(['git', 'config', '--global', '--get', 'i18n.logoutputencoding'], 
                              capture_output=True, text=True)
        log_encoding = result.stdout.strip() or '未设置'
        print(f"i18n.logoutputencoding: {log_encoding}")
        
        result = subprocess.run(['git', 'config', '--global', '--get', 'core.quotepath'], 
                              capture_output=True, text=True)
        quotepath = result.stdout.strip() or '未设置'
        print(f"core.quotepath: {quotepath}")
    except Exception as e:
        print(f"检查 Git 配置时出错: {e}")
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)

if __name__ == '__main__':
    main()

