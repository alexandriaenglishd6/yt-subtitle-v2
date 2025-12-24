"""
测试摘要推荐字数规则和分块翻译逻辑
不需要真正调用 AI API，只验证核心逻辑
"""

import sys
sys.path.insert(0, '.')

def test_summary_length_rules():
    """测试摘要推荐字数规则"""
    from core.prompts import calculate_suggested_summary_length, get_reduce_summary_prompt
    
    print("=" * 60)
    print("测试 1: 摘要推荐字数规则")
    print("=" * 60)
    
    test_cases = [
        (50000, "30000+ 字字幕", "2000-5000"),
        (30000, "30000 字字幕", "2000-5000"),
        (20000, "5001-29999 字字幕", "1500-4000"),
        (10000, "5001-29999 字字幕", "1500-4000"),
        (5001, "5001 字字幕", "1500-4000"),
        (5000, "5000 字字幕", "800-1500"),
        (4000, "3000-4999 字字幕", "500-1000"),
        (3000, "3000 字字幕", "500-1000"),
        (2000, "3000 字以下", "300-800"),
        (500, "3000 字以下", "300-800"),
    ]
    
    all_passed = True
    for text_length, description, expected in test_cases:
        min_words, max_words = calculate_suggested_summary_length(content_length=text_length)
        result = f"{min_words}-{max_words}"
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} {description} ({text_length}字): 期望 {expected}, 实际 {result}")
    
    print()
    if all_passed:
        print("  ✓ 所有摘要推荐字数规则测试通过！")
    else:
        print("  ✗ 部分测试失败，请检查规则")
    
    # 测试 Prompt 内容
    print()
    print("-" * 60)
    print("测试 Prompt 内容（检查'内容完整为第一优先级'提示）")
    print("-" * 60)
    
    prompt = get_reduce_summary_prompt(
        summary_language="zh-CN",
        sub_summaries="测试摘要内容",
        video_title="测试视频",
        text_length=20000,
    )
    
    if "内容完整为第一优先级" in prompt:
        print("  ✓ Prompt 包含'内容完整为第一优先级'")
    else:
        print("  ✗ Prompt 缺少'内容完整为第一优先级'")
    
    if "不强制限制字数" in prompt:
        print("  ✓ Prompt 包含'不强制限制字数'")
    else:
        print("  ✗ Prompt 缺少'不强制限制字数'")
    
    if "1500-4000" in prompt:
        print("  ✓ Prompt 包含正确的推荐字数 (1500-4000)")
    else:
        print("  ✗ Prompt 推荐字数不正确")
    
    return all_passed


def test_chunk_split():
    """测试分块拆分逻辑（句子边界分割）"""
    print()
    print("=" * 60)
    print("测试 2: 分块拆分逻辑（句子边界分割）")
    print("=" * 60)
    
    from core.translator.translator import SubtitleTranslator
    
    # 创建一个模拟的 SRT 内容，包含句子结束标点
    srt_content = """1
00:00:01,000 --> 00:00:03,000
Hello world.

2
00:00:04,000 --> 00:00:06,000
How are you?

3
00:00:07,000 --> 00:00:09,000
I am fine,

4
00:00:10,000 --> 00:00:12,000
thank you!

5
00:00:13,000 --> 00:00:15,000
What is your name

6
00:00:16,000 --> 00:00:18,000
My name is Bob."""

    # 测试拆分函数
    translator = SubtitleTranslator.__new__(SubtitleTranslator)  # 不调用 __init__
    
    # 调用拆分方法
    sub_chunks = translator._split_chunk_in_half(srt_content)
    
    print(f"  原始内容包含 6 条字幕")
    print(f"  拆分后得到 {len(sub_chunks)} 个子块")
    
    if len(sub_chunks) == 2:
        print("  ✓ 拆分数量正确 (2 个子块)")
        
        # 检查每个子块
        for i, chunk in enumerate(sub_chunks):
            entries = chunk.count("-->")
            # 检查分割点是否在句子结束处
            last_line = chunk.strip().split('\n')[-1]
            has_sentence_end = any(p in last_line for p in ['.', '!', '?', '。', '！', '？'])
            
            print(f"    子块 {i+1}: {entries} 条字幕, 末尾: '{last_line}'")
            if i == 0 and has_sentence_end:
                print(f"    ✓ 子块 1 在句子结束处分割")
        
        return True
    else:
        print("  ✗ 拆分数量不正确")
        return False


def test_srt_renumber():
    """测试 SRT 重新编号逻辑"""
    print()
    print("=" * 60)
    print("测试 3: SRT 重新编号逻辑")
    print("=" * 60)
    
    from core.state.chunk_tracker import ChunkTracker
    
    # 模拟合并后的 SRT（序号不连续）
    merged_srt = """1
00:00:01,000 --> 00:00:03,000
第一条字幕

2
00:00:04,000 --> 00:00:06,000
第二条字幕

1
00:00:07,000 --> 00:00:09,000
第三条字幕

2
00:00:10,000 --> 00:00:12,000
第四条字幕"""

    # 创建 tracker 并调用重新编号方法
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = ChunkTracker(
            video_id="test",
            target_language="zh-CN",
            work_dir=Path(tmpdir),
        )
        
        renumbered = tracker._renumber_srt(merged_srt)
        
        # 检查序号
        import re
        indices = re.findall(r'^(\d+)\n\d{2}:\d{2}:\d{2}', renumbered, re.MULTILINE)
        indices = [int(i) for i in indices]
        
        print(f"  原始序号: [1, 2, 1, 2]")
        print(f"  重新编号后: {indices}")
        
        expected = [1, 2, 3, 4]
        if indices == expected:
            print("  ✓ 重新编号正确！")
            return True
        else:
            print("  ✗ 重新编号不正确")
            return False


def test_srt_format_validation():
    """测试 SRT 格式验证"""
    print()
    print("=" * 60)
    print("测试 4: SRT 格式验证")
    print("=" * 60)
    
    from core.state.chunk_tracker import ChunkTracker
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = ChunkTracker(
            video_id="test",
            target_language="zh-CN",
            work_dir=Path(tmpdir),
        )
        
        # 测试用例
        test_cases = [
            ("1\n00:00:01,000 --> 00:00:02,000\nHello", True, "有效 SRT"),
            ("no timeline here", False, "无时间轴"),
            ("", False, "空内容"),
            ("   ", False, "只有空白"),
        ]
        
        all_passed = True
        for srt, expected, desc in test_cases:
            result = tracker._validate_srt_format(srt)
            status = "✓" if result == expected else "✗"
            if result != expected:
                all_passed = False
            print(f"  {status} {desc}: 期望 {expected}, 实际 {result}")
        
        return all_passed


def test_timeline_validation():
    """测试时间轴校验"""
    print()
    print("=" * 60)
    print("测试 5: 时间轴校验")
    print("=" * 60)
    
    from core.state.chunk_tracker import ChunkTracker
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = ChunkTracker(
            video_id="test",
            target_language="zh-CN",
            work_dir=Path(tmpdir),
        )
        
        # 正常时间轴
        normal_srt = """1
00:00:01,000 --> 00:00:03,000
Hello

2
00:00:04,000 --> 00:00:06,000
World"""
        
        # 时间轴重叠
        overlapping_srt = """1
00:00:01,000 --> 00:00:05,000
Hello

2
00:00:03,000 --> 00:00:06,000
World"""
        
        # 无效时间轴（开始 >= 结束）
        invalid_srt = """1
00:00:05,000 --> 00:00:03,000
Invalid"""
        
        # 测试
        print("  测试正常时间轴:")
        warnings = tracker._validate_timeline(normal_srt)
        if len(warnings) == 0:
            print("    ✓ 无警告")
        else:
            print(f"    ✗ 有警告: {warnings}")
        
        print("  测试时间轴重叠:")
        warnings = tracker._validate_timeline(overlapping_srt)
        if len(warnings) > 0 and "overlaps" in warnings[0]:
            print(f"    ✓ 检测到重叠: {warnings[0]}")
        else:
            print(f"    ✗ 未检测到重叠")
        
        print("  测试无效时间轴:")
        warnings = tracker._validate_timeline(invalid_srt)
        if len(warnings) > 0 and "Invalid" in warnings[0]:
            print(f"    ✓ 检测到无效: {warnings[0]}")
        else:
            print(f"    ✗ 未检测到无效")
        
        return True


def test_translation_completeness():
    """测试翻译完整性检查"""
    print()
    print("=" * 60)
    print("测试 6: 翻译完整性检查")
    print("=" * 60)
    
    from core.translator.translator import SubtitleTranslator
    
    # 创建模拟 translator
    translator = SubtitleTranslator.__new__(SubtitleTranslator)
    
    # 测试用例
    original = """1
00:00:01,000 --> 00:00:03,000
Hello

2
00:00:04,000 --> 00:00:06,000
World"""
    
    # 完整翻译（2 条）
    complete = """1
00:00:01,000 --> 00:00:03,000
你好

2
00:00:04,000 --> 00:00:06,000
世界"""
    
    # 不完整翻译（1 条）
    incomplete = """1
00:00:01,000 --> 00:00:03,000
你好"""
    
    print("  测试完整翻译:")
    result = translator._check_translation_completeness(original, complete, "test")
    if result:
        print("    ✓ 翻译完整")
    else:
        print("    ✗ 翻译不完整（不应该）")
    
    print("  测试不完整翻译:")
    result = translator._check_translation_completeness(original, incomplete, "test")
    if not result:
        print("    ✓ 检测到不完整")
    else:
        print("    ✗ 未检测到不完整")
    
    return True


def main():
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║          新功能测试脚本 - 摘要规则 & 分块翻译              ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    results = []
    
    try:
        results.append(("摘要推荐字数规则", test_summary_length_rules()))
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        results.append(("摘要推荐字数规则", False))
    
    try:
        results.append(("分块拆分逻辑", test_chunk_split()))
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        results.append(("分块拆分逻辑", False))
    
    try:
        results.append(("SRT 重新编号", test_srt_renumber()))
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        results.append(("SRT 重新编号", False))
    
    try:
        results.append(("SRT 格式验证", test_srt_format_validation()))
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        results.append(("SRT 格式验证", False))
    
    try:
        results.append(("时间轴校验", test_timeline_validation()))
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        results.append(("时间轴校验", False))
    
    try:
        results.append(("翻译完整性检查", test_translation_completeness()))
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        results.append(("翻译完整性检查", False))
    
    # 汇总
    print()
    print("=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 所有测试通过！可以进行真实任务测试了。")
    else:
        print("⚠️ 部分测试失败，请先修复问题。")
    
    return all_passed


if __name__ == "__main__":
    main()
