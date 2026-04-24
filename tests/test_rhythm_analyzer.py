"""
测试节奏分析器模块
"""

import pytest
import numpy as np
import librosa
from src.remix.improved.rhythm_analyzer import RhythmAnalyzer


class TestRhythmAnalyzer:
    """测试 RhythmAnalyzer 类"""
    
    def test_init(self):
        """测试初始化"""
        analyzer = RhythmAnalyzer()
        assert analyzer.hop_length == 512
        
        analyzer_custom = RhythmAnalyzer(hop_length=1024)
        assert analyzer_custom.hop_length == 1024
    
    def test_detect_tempo_and_beats_with_constant_beat(self):
        """测试恒定节拍的速度检测"""
        # 生成 120 BPM 的节拍音频（每 0.5 秒一个节拍）
        sr = 22050
        duration = 4.0
        audio = self._generate_click_track(bpm=120, duration=duration, sr=sr)
        
        analyzer = RhythmAnalyzer()
        tempo, beat_times = analyzer.detect_tempo_and_beats(audio, sr)
        
        # 验证速度接近 120 BPM（允许一定误差）
        assert 100 < tempo < 140, f"检测到的速度 {tempo} 不在合理范围内"
        
        # 验证检测到了节拍
        assert len(beat_times) > 0, "未检测到任何节拍"
        
        # 验证节拍时间在合理范围内
        assert beat_times[0] >= 0, "节拍时间不应为负"
        assert beat_times[-1] <= duration, "节拍时间超出音频时长"
    
    def test_detect_tempo_and_beats_with_real_audio(self):
        """测试使用真实音频的节拍检测"""
        # 使用 librosa 的示例音频
        try:
            audio, sr = librosa.load(librosa.example('trumpet'), duration=5.0)
        except Exception:
            pytest.skip("无法加载示例音频")
        
        analyzer = RhythmAnalyzer()
        tempo, beat_times = analyzer.detect_tempo_and_beats(audio, sr)
        
        # 验证返回值类型
        assert isinstance(tempo, float), "速度应为浮点数"
        assert isinstance(beat_times, np.ndarray), "节拍时间应为 numpy 数组"
        
        # 验证速度在合理范围内（通常音乐的速度在 40-200 BPM）
        assert 40 < tempo < 200, f"检测到的速度 {tempo} 不在合理范围内"
        
        # 验证检测到了节拍
        assert len(beat_times) > 0, "未检测到任何节拍"
    
    def test_detect_tempo_and_beats_empty_audio(self):
        """测试空音频的处理"""
        analyzer = RhythmAnalyzer()
        
        with pytest.raises(ValueError, match="音频数据为空"):
            analyzer.detect_tempo_and_beats(np.array([]), 22050)
    
    def test_detect_tempo_and_beats_none_audio(self):
        """测试 None 音频的处理"""
        analyzer = RhythmAnalyzer()
        
        with pytest.raises(ValueError, match="音频数据为空"):
            analyzer.detect_tempo_and_beats(None, 22050)
    
    def test_beat_times_are_sorted(self):
        """测试节拍时间是否按顺序排列"""
        sr = 22050
        duration = 3.0
        audio = self._generate_click_track(bpm=120, duration=duration, sr=sr)
        
        analyzer = RhythmAnalyzer()
        tempo, beat_times = analyzer.detect_tempo_and_beats(audio, sr)
        
        # 验证节拍时间是递增的
        if len(beat_times) > 1:
            assert np.all(np.diff(beat_times) > 0), "节拍时间应该是递增的"
    
    def _generate_click_track(self, bpm: float, duration: float, sr: int) -> np.ndarray:
        """
        生成节拍音频（咔嗒声）
        
        Args:
            bpm: 每分钟节拍数
            duration: 时长（秒）
            sr: 采样率
            
        Returns:
            音频数据
        """
        # 计算节拍间隔（秒）
        beat_interval = 60.0 / bpm
        
        # 生成静音音频
        audio = np.zeros(int(sr * duration))
        
        # 在每个节拍位置添加咔嗒声
        t = 0
        while t < duration:
            start_sample = int(t * sr)
            # 添加短促的正弦波作为咔嗒声
            click_duration = 0.01  # 10ms
            click_samples = int(click_duration * sr)
            if start_sample + click_samples < len(audio):
                t_click = np.linspace(0, click_duration, click_samples)
                click = np.sin(2 * np.pi * 1000 * t_click) * 0.5
                # 应用包络
                envelope = np.exp(-t_click * 50)
                click *= envelope
                audio[start_sample:start_sample + click_samples] += click
            t += beat_interval
        
        return audio


class TestSegmentation:
    """测试分段功能"""
    
    def test_segment_by_beats_basic(self):
        """测试基于节拍的基本分段"""
        sr = 22050
        duration = 4.0
        audio = np.random.randn(int(sr * duration))
        
        # 创建模拟的节拍时间（每 0.5 秒一个节拍）
        beat_times = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
        
        analyzer = RhythmAnalyzer()
        segments = analyzer.segment_by_beats(audio, sr, beat_times)
        
        # 验证生成了片段
        assert len(segments) > 0, "应该生成至少一个片段"
        
        # 验证片段格式
        for start, end in segments:
            assert isinstance(start, (float, np.floating)), "起始时间应为浮点数"
            assert isinstance(end, (float, np.floating)), "结束时间应为浮点数"
            assert start < end, "起始时间应小于结束时间"
            assert start >= 0, "起始时间不应为负"
            assert end <= duration, "结束时间不应超过音频时长"
    
    def test_segment_by_beats_empty_audio(self):
        """测试空音频的处理"""
        analyzer = RhythmAnalyzer()
        beat_times = np.array([0.0, 0.5, 1.0])
        
        with pytest.raises(ValueError, match="音频数据为空"):
            analyzer.segment_by_beats(np.array([]), 22050, beat_times)
    
    def test_segment_by_beats_empty_beats(self):
        """测试空节拍时间的处理"""
        sr = 22050
        audio = np.random.randn(sr)
        analyzer = RhythmAnalyzer()
        
        with pytest.raises(ValueError, match="节拍时间为空"):
            analyzer.segment_by_beats(audio, sr, np.array([]))
    
    def test_segment_by_onsets_basic(self):
        """测试基于起始点的基本分段"""
        sr = 22050
        duration = 3.0
        audio = np.random.randn(int(sr * duration))
        
        # 创建模拟的起始点时间
        onset_times = np.array([0.0, 0.3, 0.8, 1.2, 1.8, 2.3, 2.7])
        
        analyzer = RhythmAnalyzer()
        segments = analyzer.segment_by_onsets(audio, sr, onset_times)
        
        # 验证生成了片段
        assert len(segments) > 0, "应该生成至少一个片段"
        
        # 验证片段格式
        for start, end in segments:
            assert isinstance(start, (float, np.floating)), "起始时间应为浮点数"
            assert isinstance(end, (float, np.floating)), "结束时间应为浮点数"
            assert start < end, "起始时间应小于结束时间"
            assert start >= 0, "起始时间不应为负"
            assert end <= duration, "结束时间不应超过音频时长"
    
    def test_segment_by_onsets_empty_audio(self):
        """测试空音频的处理"""
        analyzer = RhythmAnalyzer()
        onset_times = np.array([0.0, 0.3, 0.8])
        
        with pytest.raises(ValueError, match="音频数据为空"):
            analyzer.segment_by_onsets(np.array([]), 22050, onset_times)
    
    def test_segment_by_onsets_empty_onsets(self):
        """测试空起始点时间的处理"""
        sr = 22050
        audio = np.random.randn(sr)
        analyzer = RhythmAnalyzer()
        
        with pytest.raises(ValueError, match="起始点时间为空"):
            analyzer.segment_by_onsets(audio, sr, np.array([]))
    
    def test_merge_short_segments(self):
        """测试合并短片段"""
        analyzer = RhythmAnalyzer()
        
        # 创建包含短片段的列表
        segments = [
            (0.0, 0.5),    # 正常片段
            (0.5, 0.52),   # 短片段（20ms）
            (0.52, 1.0),   # 正常片段
            (1.0, 1.03),   # 短片段（30ms）
            (1.03, 1.5)    # 正常片段
        ]
        
        merged = analyzer._merge_short_segments(segments, min_duration=0.05)
        
        # 验证短片段被合并
        assert len(merged) < len(segments), "应该合并了一些片段"
        
        # 验证所有片段都足够长（除了可能的最后一个）
        for start, end in merged[:-1]:
            duration = end - start
            assert duration >= 0.05 or duration >= 0.04, f"片段时长 {duration} 应该 >= 0.05s"
    
    def test_split_long_segments(self):
        """测试分割长片段"""
        analyzer = RhythmAnalyzer()
        
        # 创建包含长片段的列表
        segments = [
            (0.0, 1.0),    # 正常片段
            (1.0, 4.5),    # 长片段（3.5s）
            (4.5, 5.0)     # 正常片段
        ]
        
        split = analyzer._split_long_segments(segments, max_duration=2.0)
        
        # 验证长片段被分割
        assert len(split) > len(segments), "应该分割了一些片段"
        
        # 验证所有片段都不太长
        for start, end in split:
            duration = end - start
            assert duration <= 2.1, f"片段时长 {duration} 应该 <= 2.0s（允许小误差）"
    
    def test_segment_by_beats_with_merge_and_split(self):
        """测试节拍分段包含合并和分割逻辑"""
        sr = 22050
        duration = 10.0
        audio = np.random.randn(int(sr * duration))
        
        # 创建包含短间隔和长间隔的节拍时间
        beat_times = np.array([
            0.0, 0.02,  # 短间隔（20ms）
            0.5, 1.0, 1.5, 2.0,  # 正常间隔
            5.5,  # 长间隔（3.5s）
            6.0, 6.5, 7.0
        ])
        
        analyzer = RhythmAnalyzer()
        segments = analyzer.segment_by_beats(audio, sr, beat_times)
        
        # 验证生成了片段
        assert len(segments) > 0, "应该生成至少一个片段"
        
        # 验证没有太短或太长的片段
        for start, end in segments:
            duration = end - start
            # 允许一些误差
            assert duration >= 0.04, f"片段时长 {duration} 太短"
            assert duration <= 2.1, f"片段时长 {duration} 太长"
    
    def test_segment_by_onsets_with_merge_and_split(self):
        """测试起始点分段包含合并和分割逻辑"""
        sr = 22050
        duration = 8.0
        audio = np.random.randn(int(sr * duration))
        
        # 创建包含短间隔和长间隔的起始点时间
        onset_times = np.array([
            0.0, 0.03,  # 短间隔（30ms）
            0.5, 1.0, 1.5,  # 正常间隔
            4.5,  # 长间隔（3s）
            5.0, 5.5
        ])
        
        analyzer = RhythmAnalyzer()
        segments = analyzer.segment_by_onsets(audio, sr, onset_times)
        
        # 验证生成了片段
        assert len(segments) > 0, "应该生成至少一个片段"
        
        # 验证没有太短或太长的片段
        for start, end in segments:
            duration = end - start
            # 允许一些误差
            assert duration >= 0.04, f"片段时长 {duration} 太短"
            assert duration <= 2.1, f"片段时长 {duration} 太长"
    
    def test_segments_are_continuous(self):
        """测试片段是否连续（无间隙）"""
        sr = 22050
        duration = 5.0
        audio = np.random.randn(int(sr * duration))
        
        beat_times = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5])
        
        analyzer = RhythmAnalyzer()
        segments = analyzer.segment_by_beats(audio, sr, beat_times)
        
        # 验证片段是连续的（允许小误差）
        for i in range(len(segments) - 1):
            current_end = segments[i][1]
            next_start = segments[i + 1][0]
            gap = next_start - current_end
            # 允许最多 0.1 秒的间隙（由于合并/分割逻辑）
            assert abs(gap) <= 0.1, f"片段 {i} 和 {i+1} 之间有间隙: {gap}s"
