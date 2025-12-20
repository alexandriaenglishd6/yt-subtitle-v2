"""
CLI 入口文件（向后兼容）
实际实现已移至 cli/ 模块
"""
import sys
from cli.main import main

if __name__ == "__main__":
    sys.exit(main())
