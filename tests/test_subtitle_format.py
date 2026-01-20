"""
subtitle_format 模块的单元测试

测试各种字幕格式转换功能
"""

import pytest
from core.subtitle_format import (
    ms_to_srt_time,
    convert_vtt_to_srt,
    convert_json3_to_srt,
    convert_srv3_to_srt,
    detect_format,
    convert_to_srt,
)


class TestMsToSrtTime:
    """时间格式转换测试"""

    def test_zero(self):
        assert ms_to_srt_time(0) == "00:00:00,000"

    def test_milliseconds_only(self):
        assert ms_to_srt_time(500) == "00:00:00,500"

    def test_seconds(self):
        assert ms_to_srt_time(5000) == "00:00:05,000"

    def test_minutes(self):
        assert ms_to_srt_time(65000) == "00:01:05,000"

    def test_hours(self):
        assert ms_to_srt_time(3661500) == "01:01:01,500"

    def test_large_value(self):
        # 10小时 30分 45秒 123毫秒
        ms = 10 * 3600000 + 30 * 60000 + 45 * 1000 + 123
        assert ms_to_srt_time(ms) == "10:30:45,123"


class TestConvertVttToSrt:
    """VTT 转 SRT 测试"""

    def test_simple_vtt(self):
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello World

00:00:05.000 --> 00:00:08.000
This is a test
"""
        result = convert_vtt_to_srt(vtt_content)
        assert "1" in result
        assert "00:00:01,000 --> 00:00:04,000" in result
        assert "Hello World" in result

    def test_vtt_with_position_info(self):
        """测试带位置信息的 VTT"""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.000 align:start position:10%
Hello with position
"""
        result = convert_vtt_to_srt(vtt_content)
        # 位置信息应该被移除
        assert "align:" not in result
        assert "position:" not in result
        assert "Hello with position" in result

    def test_empty_vtt(self):
        vtt_content = "WEBVTT\n"
        result = convert_vtt_to_srt(vtt_content)
        assert result.strip() == ""


class TestConvertJson3ToSrt:
    """JSON3 格式转 SRT 测试"""

    def test_simple_json3(self):
        json3_content = '''{"events": [
            {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hello"}]},
            {"tStartMs": 3000, "dDurationMs": 2000, "segs": [{"utf8": "World"}]}
        ]}'''
        result = convert_json3_to_srt(json3_content)
        assert "1" in result
        assert "Hello" in result
        assert "World" in result

    def test_json3_with_multiple_segs(self):
        """测试多段文本合并"""
        json3_content = '''{"events": [
            {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Hello "}, {"utf8": "World"}]}
        ]}'''
        result = convert_json3_to_srt(json3_content)
        assert "Hello World" in result

    def test_invalid_json(self):
        """无效 JSON 应返回原内容"""
        invalid_content = "not a json"
        result = convert_json3_to_srt(invalid_content)
        assert result == invalid_content

    def test_json3_without_events(self):
        """没有 events 的 JSON"""
        json_content = '{"foo": "bar"}'
        result = convert_json3_to_srt(json_content)
        # 应该返回空字符串（没有事件）
        assert result.strip() == ""


class TestConvertSrv3ToSrt:
    """SRV3 (XML) 格式转 SRT 测试"""

    def test_simple_srv3(self):
        srv3_content = '''<?xml version="1.0"?>
<transcript>
<p t="0" d="2000">Hello</p>
<p t="3000" d="2000">World</p>
</transcript>'''
        result = convert_srv3_to_srt(srv3_content)
        assert "Hello" in result
        assert "World" in result

    def test_srv3_with_html_entities(self):
        """测试 HTML 实体解码"""
        srv3_content = '<p t="0" d="2000">Hello &amp; World</p>'
        result = convert_srv3_to_srt(srv3_content)
        assert "Hello & World" in result

    def test_invalid_srv3(self):
        """无效格式应返回原内容"""
        invalid_content = "just some text"
        result = convert_srv3_to_srt(invalid_content)
        assert result == invalid_content


class TestDetectFormat:
    """格式检测测试"""

    def test_detect_vtt(self):
        assert detect_format("WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello") == "vtt"

    def test_detect_json3(self):
        assert detect_format('{"events": []}') == "json3"

    def test_detect_srv3(self):
        assert detect_format('<?xml version="1.0"?><transcript>') == "srv3"
        assert detect_format('<p t="0" d="1000">text</p>') == "srv3"

    def test_detect_srt(self):
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello World
"""
        assert detect_format(srt_content) == "srt"

    def test_detect_unknown(self):
        assert detect_format("random text here") is None


class TestConvertToSrt:
    """统一转换入口测试"""

    def test_auto_detect_vtt(self):
        vtt_content = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello"
        result = convert_to_srt(vtt_content)
        assert "00:00:01,000" in result  # VTT 的 . 应该转换为 ,

    def test_explicit_format(self):
        content = '{"events": [{"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "Test"}]}]}'
        result = convert_to_srt(content, source_format="json3")
        assert "Test" in result

    def test_srt_passthrough(self):
        """SRT 格式应该直接返回"""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello World
"""
        result = convert_to_srt(srt_content, source_format="srt")
        assert result == srt_content

    def test_unknown_format_passthrough(self):
        """未知格式应返回原内容"""
        content = "random content"
        result = convert_to_srt(content)
        assert result == content
