"""
CLI 完整流程验收测试脚本
用于自动化测试各个验收场景
"""
import subprocess
import sys
from pathlib import Path

def run_test(name: str, command: list, expected_exit_code: int = 0, allow_timeout: bool = False):
    """运行测试命令
    
    Args:
        name: 测试名称
        command: 命令列表
        expected_exit_code: 预期退出码
        allow_timeout: 是否允许超时（网络问题）
    """
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"命令: {' '.join(command)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120  # 2分钟超时
        )
        
        if result.returncode == expected_exit_code:
            print(f"[OK] 测试通过（退出码: {result.returncode}）")
            if result.stdout:
                print(f"输出:\n{result.stdout[:500]}")  # 只显示前500字符
            return True
        else:
            print(f"[FAIL] 测试失败（退出码: {result.returncode}，预期: {expected_exit_code}）")
            if result.stderr:
                print(f"错误:\n{result.stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        if allow_timeout:
            print(f"[WARN] 测试超时（允许）")
            return True
        else:
            print(f"[FAIL] 测试超时")
            return False
    except Exception as e:
        print(f"[FAIL] 测试异常: {e}")
        return False


def main():
    """运行所有验收测试"""
    print("=" * 60)
    print("CLI 完整流程验收测试")
    print("=" * 60)
    
    # 确保在项目根目录
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    results = []
    
    # 测试 1: CLI 帮助信息
    results.append((
        "CLI 帮助信息",
        run_test(
            "CLI 帮助信息",
            ["python", "cli.py", "--help"],
            expected_exit_code=0
        )
    ))
    
    # 测试 2: 频道命令帮助
    results.append((
        "频道命令帮助",
        run_test(
            "频道命令帮助",
            ["python", "cli.py", "channel", "--help"],
            expected_exit_code=0
        )
    ))
    
    # 测试 3: URL 列表命令帮助
    results.append((
        "URL 列表命令帮助",
        run_test(
            "URL 列表命令帮助",
            ["python", "cli.py", "urls", "--help"],
            expected_exit_code=0
        )
    ))
    
    # 测试 4: Cookie 命令帮助
    results.append((
        "Cookie 命令帮助",
        run_test(
            "Cookie 命令帮助",
            ["python", "cli.py", "cookie", "--help"],
            expected_exit_code=0
        )
    ))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有验收测试通过！")
        return 0
    else:
        print("\n[WARNING] 部分测试失败，请检查错误信息。")
        return 1


if __name__ == "__main__":
    import os
    sys.exit(main())

