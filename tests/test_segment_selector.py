"""
测试片段选择器模块

测试 SegmentSelector 类的功能，包括：
- 综合匹配分数计算
- 各维度相似度计算
- 最佳片段选择
- 重复避免机制
- 子片段提取
"""

import pytest
import numpy as np
from src.remix.improved.segment_selector import SegmentSelector
from src.remix.segment_detector import Segment


def create_test_segment(name: str = "test", 
                       pitch: float = 440.0, 
                       energy: float = 0.5,
                       tempo: float = 120.0,
                       duration: float = 1.0,
                       sr: int = 22050) -> Segment:
    """创建测试片段"""
    audio_data = np.random.randn(int(sr * duration)) * energy
    segment = Segment(
        start_time=0.0,
        end_time=duration,
        audio_data=audio_data,
        sample_rate=sr,
        name=name
    )
    segment.pitch = pitch
    segment.energy = energy
    segment.tempo = tempo
    segment.mfcc = np.random.randn(13, 10)  # 13 维 MFCC，10 帧
    return segment


class TestSegmentSelector:
    """测试 SegmentSelector 类"""
    
    def test_init_default_weights(self):
        """测试默认权重初始化"""
        selector = SegmentSelector()
        
        assert selector.pitch_weight == 0.4
        assert selector.rhythm_weight == 0.3
        assert selector.timbre_weight == 0.2
        assert selector.loudness_weight == 0.1
        assert selector.min_score == 0.6
        assert selector.max_repeat == 3
    
    def test_init_custom_weights(self):
        """测试自定义权重初始化"""
        selector = SegmentSelector(
            pitch_weight=0.5,
            rhythm_weight=0.3,
            timbre_weight=0.1,
            loudness_weight=0.1,
            min_score=0.7,
            max_repeat=5
        )
        
        assert selector.pitch_weight == 0.5
        assert selector.rhythm_weight == 0.3
        assert selector.timbre_weight == 0.1
        assert selector.loudness_weight == 0.1
        assert selector.min_score == 0.7
        assert selector.max_repeat == 5
    
    def test_init_weight_normalization(self):
        """测试权重自动归一化"""
        selector = SegmentSelector(
            pitch_weight=0.8,
            rhythm_weight=0.6,
            timbre_weight=0.4,
            loudness_weight=0.2
        )
        
        # 权重总和应该为 1.0
        total = (selector.pitch_weight + selector.rhythm_weight + 
                selector.timbre_weight + selector.loudness_weight)
        assert np.isclose(total, 1.0)
    
    def test_calculate_pitch_similarity_identical(self):
        """测试相同音高的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(pitch=440.0)
        target_features = {'pitch': 440.0}
        
        similarity = selector._calculate_pitch_similarity(segment, target_features)
        
        # 相同音高应该相似度为 1.0
        assert np.isclose(similarity, 1.0)
    
    def test_calculate_pitch_similarity_octave(self):
        """测试八度音高的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(pitch=440.0)
        target_features = {'pitch': 880.0}  # 高一个八度
        
        similarity = selector._calculate_pitch_similarity(segment, target_features)
        
        # 八度差异（12 半音）应该相似度为 0.0
        assert np.isclose(similarity, 0.0)
    
    def test_calculate_pitch_similarity_semitone(self):
        """测试半音差异的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(pitch=440.0)
        # 466.16 Hz 是 A4 上方 1 个半音（A#4）
        target_features = {'pitch': 466.16}
        
        similarity = selector._calculate_pitch_similarity(segment, target_features)
        
        # 1 个半音差异应该相似度约为 0.917
        assert 0.9 < similarity < 0.95
    
    def test_calculate_pitch_similarity_invalid_pitch(self):
        """测试无效音高的处理"""
        selector = SegmentSelector()
        segment = create_test_segment(pitch=0.0)
        target_features = {'pitch': 440.0}
        
        similarity = selector._calculate_pitch_similarity(segment, target_features)
        
        # 无效音高应该返回 0.0
        assert similarity == 0.0
    
    def test_calculate_rhythm_similarity_identical(self):
        """测试相同速度的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(tempo=120.0)
        target_features = {'tempo': 120.0}
        
        similarity = selector._calculate_rhythm_similarity(segment, target_features)
        
        # 相同速度应该相似度为 1.0
        assert np.isclose(similarity, 1.0)
    
    def test_calculate_rhythm_similarity_different(self):
        """测试不同速度的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(tempo=120.0)
        target_features = {'tempo': 60.0}  # 慢一倍
        
        similarity = selector._calculate_rhythm_similarity(segment, target_features)
        
        # 速度比例为 0.5
        assert np.isclose(similarity, 0.5)
    
    def test_calculate_rhythm_similarity_missing_tempo(self):
        """测试缺失速度信息的处理"""
        selector = SegmentSelector()
        segment = create_test_segment()
        segment.tempo = None
        target_features = {'tempo': 120.0}
        
        similarity = selector._calculate_rhythm_similarity(segment, target_features)
        
        # 缺失速度应该返回中等相似度 0.5
        assert similarity == 0.5
    
    def test_calculate_timbre_similarity_identical(self):
        """测试相同音色的相似度"""
        selector = SegmentSelector()
        mfcc = np.random.randn(13, 10)
        
        segment = create_test_segment()
        segment.mfcc = mfcc
        target_features = {'mfcc': mfcc}
        
        similarity = selector._calculate_timbre_similarity(segment, target_features)
        
        # 相同音色应该相似度接近 1.0
        assert similarity > 0.99
    
    def test_calculate_timbre_similarity_missing_mfcc(self):
        """测试缺失 MFCC 的处理"""
        selector = SegmentSelector()
        segment = create_test_segment()
        segment.mfcc = None
        target_features = {'mfcc': np.random.randn(13, 10)}
        
        similarity = selector._calculate_timbre_similarity(segment, target_features)
        
        # 缺失 MFCC 应该返回中等相似度 0.5
        assert similarity == 0.5
    
    def test_calculate_loudness_similarity_identical(self):
        """测试相同响度的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(energy=0.5)
        target_features = {'rms': 0.5}
        
        similarity = selector._calculate_loudness_similarity(segment, target_features)
        
        # 相同响度应该相似度为 1.0
        assert np.isclose(similarity, 1.0)
    
    def test_calculate_loudness_similarity_different(self):
        """测试不同响度的相似度"""
        selector = SegmentSelector()
        segment = create_test_segment(energy=0.5)
        target_features = {'rms': 0.25}  # 一半响度
        
        similarity = selector._calculate_loudness_similarity(segment, target_features)
        
        # 响度比例为 0.5
        assert np.isclose(similarity, 0.5)
    
    def test_calculate_match_score(self):
        """测试综合匹配分数计算"""
        selector = SegmentSelector()
        segment = create_test_segment(pitch=440.0, energy=0.5, tempo=120.0)
        target_features = {
            'pitch': 440.0,
            'tempo': 120.0,
            'mfcc': segment.mfcc,
            'rms': 0.5
        }
        
        score = selector.calculate_match_score(segment, target_features)
        
        # 完全匹配应该分数接近 1.0
        assert score > 0.95
        assert score <= 1.0
    
    def test_calculate_match_score_partial_match(self):
        """测试部分匹配的分数"""
        selector = SegmentSelector()
        segment = create_test_segment(pitch=440.0, energy=0.5, tempo=120.0)
        target_features = {
            'pitch': 880.0,  # 不匹配（八度差异）
            'tempo': 120.0,  # 匹配
            'mfcc': segment.mfcc,  # 匹配
            'rms': 0.5  # 匹配
        }
        
        score = selector.calculate_match_score(segment, target_features)
        
        # 音高不匹配（权重 40%），其他匹配（权重 60%）
        # 预期分数约为 0.6
        assert 0.5 < score < 0.7
    
    def test_select_best_segment_single(self):
        """测试从单个片段中选择"""
        selector = SegmentSelector(min_score=0.5)
        segments = [create_test_segment(name="seg1", pitch=440.0)]
        target_features = {'pitch': 440.0, 'tempo': 120.0, 'rms': 0.5}
        used_segments = []
        
        best = selector.select_best_segment(segments, target_features, used_segments)
        
        assert best is not None
        assert best.name == "seg1"
    
    def test_select_best_segment_multiple(self):
        """测试从多个片段中选择最佳"""
        selector = SegmentSelector(min_score=0.5)
        segments = [
            create_test_segment(name="seg1", pitch=440.0),
            create_test_segment(name="seg2", pitch=880.0),  # 不匹配
            create_test_segment(name="seg3", pitch=450.0),  # 接近匹配
        ]
        target_features = {'pitch': 440.0, 'tempo': 120.0, 'rms': 0.5}
        used_segments = []
        
        best = selector.select_best_segment(segments, target_features, used_segments)
        
        # 应该选择 seg1（完全匹配）
        assert best is not None
        assert best.name == "seg1"
    
    def test_select_best_segment_avoid_repeat(self):
        """测试重复避免机制"""
        selector = SegmentSelector(min_score=0.5, max_repeat=2)
        segments = [
            create_test_segment(name="seg1", pitch=440.0),
            create_test_segment(name="seg2", pitch=445.0),
        ]
        target_features = {'pitch': 440.0, 'tempo': 120.0, 'rms': 0.5}
        used_segments = [0, 0]  # seg1 已使用 2 次
        
        best = selector.select_best_segment(segments, target_features, used_segments)
        
        # 应该选择 seg2（避免 seg1）
        assert best is not None
        assert best.name == "seg2"
    
    def test_select_best_segment_below_threshold(self):
        """测试低于阈值的情况"""
        selector = SegmentSelector(min_score=0.9)
        segments = [create_test_segment(name="seg1", pitch=880.0)]
        target_features = {'pitch': 440.0, 'tempo': 120.0, 'rms': 0.5}
        used_segments = []
        
        best = selector.select_best_segment(segments, target_features, used_segments)
        
        # 分数低于阈值，应该返回 None
        assert best is None
    
    def test_select_best_segment_empty_list(self):
        """测试空片段列表"""
        selector = SegmentSelector()
        segments = []
        target_features = {'pitch': 440.0, 'tempo': 120.0, 'rms': 0.5}
        used_segments = []
        
        best = selector.select_best_segment(segments, target_features, used_segments)
        
        assert best is None
    
    def test_extract_sub_segment_shorter_than_target(self):
        """测试片段短于目标时长"""
        selector = SegmentSelector()
        segment = create_test_segment(duration=0.5)
        target_duration = 1.0
        
        sub_segment = selector.extract_sub_segment(segment, target_duration)
        
        # 应该返回原片段
        assert sub_segment.duration == segment.duration
        assert np.array_equal(sub_segment.audio_data, segment.audio_data)
    
    def test_extract_sub_segment_longer_than_target(self):
        """测试片段长于目标时长"""
        selector = SegmentSelector()
        segment = create_test_segment(duration=2.0)
        target_duration = 0.5
        
        sub_segment = selector.extract_sub_segment(segment, target_duration)
        
        # 应该返回子片段
        assert sub_segment.duration == pytest.approx(target_duration, rel=0.01)
        assert len(sub_segment.audio_data) == pytest.approx(
            target_duration * segment.sample_rate, rel=0.01
        )
        assert sub_segment.name == f"{segment.name}_sub"
    
    def test_extract_sub_segment_preserves_features(self):
        """测试子片段保留原片段特征"""
        selector = SegmentSelector()
        segment = create_test_segment(duration=2.0, pitch=440.0, energy=0.5, tempo=120.0)
        target_duration = 0.5
        
        sub_segment = selector.extract_sub_segment(segment, target_duration)
        
        # 应该保留原片段的特征
        assert sub_segment.pitch == segment.pitch
        assert sub_segment.energy == segment.energy
        assert sub_segment.tempo == segment.tempo
        assert np.array_equal(sub_segment.mfcc, segment.mfcc)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
