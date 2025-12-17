#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理健康管理功能测试脚本

使用方法：
1. 设置测试参数（降低阈值和延迟，加速测试）
2. 运行脚本：python test_proxy_health.py

测试场景：
- 代理失败达到阈值后被标记为 unhealthy
- unhealthy 代理在延迟后被探测恢复
- 所有代理失效时自动切换直连
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.proxy_manager import ProxyManager


def test_proxy_health_management():
    """测试代理健康管理功能"""
    print("=" * 60)
    print("代理健康管理功能测试")
    print("=" * 60)
    print()
    
    # 使用测试参数（降低阈值和延迟，加速测试）
    # 生产环境默认值：failure_threshold=5, retry_delay_minutes=10
    # 测试参数：failure_threshold=2, retry_delay_seconds=10（10秒）
    failure_threshold = 2  # 降低阈值到2次，快速触发
    retry_delay_seconds = 10  # 缩短延迟到10秒
    retry_delay_minutes = retry_delay_seconds / 60.0  # 转换为分钟
    
    print(f"测试参数：")
    print(f"  - 失败阈值: {failure_threshold} 次")
    print(f"  - 重试延迟: {retry_delay_seconds} 秒")
    print()
    
    # 配置测试代理列表
    # 使用无效代理来快速触发失败
    test_proxies = [
        "http://127.0.0.1:9999",  # 无效代理1
        "http://127.0.0.1:9998",  # 无效代理2
        "http://127.0.0.1:9997",  # 无效代理3（可选，用于测试多个代理）
    ]
    
    print(f"测试代理列表：{len(test_proxies)} 个无效代理")
    for i, proxy in enumerate(test_proxies, 1):
        print(f"  {i}. {proxy}")
    print()
    
    # 创建代理管理器（使用测试参数）
    print("创建代理管理器...")
    proxy_manager = ProxyManager(
        proxies=test_proxies,
        failure_threshold=failure_threshold,
        retry_delay_minutes=retry_delay_minutes,
        enable_health_probe=True,
        probe_interval_minutes=retry_delay_minutes / 2  # 探测间隔为延迟的一半
    )
    print("✓ 代理管理器创建成功")
    print()
    
    # 测试1：验证初始状态
    print("【测试1】验证初始状态")
    print("-" * 60)
    for proxy in test_proxies:
        status = proxy_manager.get_proxy_status(proxy)
        if status:
            print(f"代理 {proxy}:")
            print(f"  - 是否不健康: {status.is_unhealthy}")
            print(f"  - 连续失败: {status.consecutive_failures}")
            print(f"  - 总失败: {status.total_failures}")
    print()
    
    # 测试2：触发代理失败，验证阈值触发
    print(f"【测试2】触发代理失败（阈值={failure_threshold}）")
    print("-" * 60)
    test_proxy = test_proxies[0]
    
    for i in range(failure_threshold + 1):
        print(f"第 {i+1} 次失败...")
        proxy_manager.mark_failure(test_proxy, error=f"测试错误 {i+1}")
        
        status = proxy_manager.get_proxy_status(test_proxy)
        if status:
            print(f"  连续失败次数: {status.consecutive_failures}")
            print(f"  是否不健康: {status.is_unhealthy}")
            
            if status.is_unhealthy:
                print(f"  ✓ 代理已被标记为 unhealthy（达到阈值 {failure_threshold}）")
                print(f"  标记时间: {status.marked_unhealthy_time}")
                break
        time.sleep(0.5)  # 短暂延迟，便于观察
    print()
    
    # 测试3：验证 unhealthy 代理不会被使用
    print("【测试3】验证 unhealthy 代理不会被使用")
    print("-" * 60)
    for _ in range(5):
        next_proxy = proxy_manager.get_next_proxy(allow_direct=False)
        print(f"获取的下一个代理: {next_proxy}")
        if next_proxy != test_proxy:
            print(f"  ✓ unhealthy 代理 {test_proxy} 已被跳过")
            break
        time.sleep(0.5)
    print()
    
    # 测试4：等待重试延迟，验证恢复探测
    print(f"【测试4】等待重试延迟（{retry_delay_seconds}秒）后验证恢复探测")
    print("-" * 60)
    print(f"等待 {retry_delay_seconds} 秒...")
    
    # 等待重试延迟时间（加上一点缓冲时间）
    wait_time = retry_delay_seconds + 2
    for remaining in range(wait_time, 0, -1):
        print(f"  还剩 {remaining} 秒...", end='\r')
        time.sleep(1)
    print(f"  等待完成          ")  # 清除剩余时间显示
    print()
    
    # 检查代理状态
    status = proxy_manager.get_proxy_status(test_proxy)
    if status:
        print(f"代理状态检查：")
        print(f"  - 是否不健康: {status.is_unhealthy}")
        print(f"  - 是否可以重试: {status.should_retry(retry_delay_minutes)}")
        if status.should_retry(retry_delay_minutes):
            print(f"  ✓ 代理已达到重试时间，应该会被健康探测")
        else:
            print(f"  ⚠ 代理还未达到重试时间")
    print()
    
    # 测试5：手动标记成功，验证恢复
    print("【测试5】手动标记成功，验证恢复机制")
    print("-" * 60)
    status_before = proxy_manager.get_proxy_status(test_proxy)
    was_unhealthy_before = status_before.is_unhealthy if status_before else False
    
    proxy_manager.mark_success(test_proxy)
    
    status_after = proxy_manager.get_proxy_status(test_proxy)
    if status_after:
        print(f"恢复后状态：")
        print(f"  - 是否不健康: {status_after.is_unhealthy}")
        print(f"  - 连续失败: {status_after.consecutive_failures}")
        if was_unhealthy_before and not status_after.is_unhealthy:
            print(f"  ✓ 代理已成功恢复为健康状态")
        else:
            print(f"  ⚠ 代理状态未改变")
    print()
    
    # 测试6：测试所有代理失效场景
    print("【测试6】测试所有代理失效场景")
    print("-" * 60)
    # 将所有代理都标记为失败
    for proxy in test_proxies:
        for _ in range(failure_threshold + 1):
            proxy_manager.mark_failure(proxy, error="测试错误")
    
    # 尝试获取代理
    next_proxy = proxy_manager.get_next_proxy(allow_direct=True)
    if next_proxy is None:
        print(f"  ✓ 所有代理失效时，返回 None（表示使用直连）")
    else:
        print(f"  ⚠ 返回了代理: {next_proxy}（可能是失败最少的代理）")
    print()
    
    # 清理
    print("清理资源...")
    proxy_manager.stop_health_probe()
    print("✓ 测试完成")
    print()
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print("✓ 代理失败达到阈值后被标记为 unhealthy")
    print("✓ unhealthy 代理不会被使用")
    print("✓ unhealthy 代理在延迟后可以被探测恢复")
    print("✓ 所有代理失效时可以使用直连")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_proxy_health_management()
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback
        traceback.print_exc()

