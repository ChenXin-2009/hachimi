"""
TimbreMatcher 单元测试

测试音色匹配器的核心功能：
- MFCC 提取
- 频谱质心提取
"""

import pytest
import numpy as np
import librosa
from src.remix.improved.timbre_matcher import TimbreMatcher


class TestTimbreMatcher:
    """TimbreMatcher 测试类"""
    
    def test_init_default(self):
        """测试默认初始化"""
        matcher = TimbreMatcher()
        assert matcher.n_mfcc == 13
    
    def test_init_custom_mfcc(self):
        """测试自定义 MFCC 维度"""
        matcher = TimbreMatcher(n_mfcc=20)
        assert matcher.n_mfcc == 20
    
    def test_extract_mfcc_sine_wave(self):
        """测试使用正弦波提取 MFCC"""
        # 生成 440Hz 正弦波（A4）
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        
        matcher = TimbreMatcher()
        mfcc = matcher.extract_mfcc(audio, sr)
        
        # 验证 MFCC 形状
        assert mfcc.shape[0] == 13  # 13 维 MFCC
        assert mfcc.shape[1] > 0  # 至少有一帧
    
    def test_extract_mfcc_empty_audio(self):
        """测试空音频的 MFCC 提取"""
        matcher = TimbreMatcher()
        
        with pytest.raises(ValueError, match="音频数据为空"):
            matcher.extract_mfcc(np.array([]), 22050)
    
    def test_extract_mfcc_none_audio(self):
        """测试 None 音频的 MFCC 提取"""
        matcher = TimbreMatcher()
        
        with pytest.raises(ValueError, match="音频数据为空"):
            matcher.extract_mfcc(None, 22050)
    
    def test_extract_spectral_centroid_sine_wave(self):
        """测试使用正弦波提取频谱质心"""
        # 生成 440Hz 正弦波
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        
        matcher = TimbreMatcher()
        spectral_centroid = matcher.extract_spectral_centroid(audio, sr)
        
        # 验证频谱质心形状
        assert spectral_centroid.shape[0] == 1  # 单维特征
        assert spectral_centroid.shape[1] > 0  # 至少有一帧
        
        # 验证频谱质心值在合理范围内（应该接近 440Hz）
        mean_centroid = np.mean(spectral_centroid)
        assert mean_centroid > 0
        assert mean_centroid < sr / 2  # 不应超过奈奎斯特频率
    
    def test_extract_spectral_centroid_empty_audio(self):
        """测试空音频的频谱质心提取"""
        matcher = TimbreMatcher()
        
        with pytest.raises(ValueError, match="音频数据为空"):
            matcher.extract_spectral_centroid(np.array([]), 22050)
    
    def test_extract_spectral_centroid_none_audio(self):
        """测试 None 音频的频谱质心提取"""
        matcher = TimbreMatcher()
        
        with pytest.raises(ValueError, match="音频数据为空"):
            matcher.extract_spectral_centroid(None, 22050)
    
    def test_mfcc_dimensions_custom(self):
        """测试自定义 MFCC 维度"""
        sr = 22050
        duration = 0.5
        audio = np.random.randn(int(sr * duration))
        
        # 测试不同的 MFCC 维度
        for n_mfcc in [10, 13, 20, 30]:
            matcher = TimbreMatcher(n_mfcc=n_mfcc)
            mfcc = matcher.extract_mfcc(audio, sr)
            assert mfcc.shape[0] == n_mfcc
    
    def test_spectral_centroid_brightness(self):
        """测试频谱质心反映音色明亮度"""
        sr = 22050
        duration = 0.5
        t = np.linspace(0, duration, int(sr * duration))
        
        # 低频音（暗淡）
        low_freq_audio = np.sin(2 * np.pi * 200 * t)
        
        # 高频音（明亮）
        high_freq_audio = np.sin(2 * np.pi * 2000 * t)
        
        matcher = TimbreMatcher()
        
        low_centroid = matcher.extract_spectral_centroid(low_freq_audio, sr)
        high_centroid = matcher.extract_spectral_centroid(high_freq_audio, sr)
        
        # 高频音的频谱质心应该更高
        assert np.mean(high_centroid) > np.mean(low_centroid)
    
    def test_mfcc_consistency(self):
        """测试相同音频的 MFCC 一致性"""
        sr = 22050
        duration = 1.0
        audio = np.random.randn(int(sr * duration))
        
        matcher = TimbreMatcher()
        
        # 提取两次 MFCC
        mfcc1 = matcher.extract_mfcc(audio, sr)
        mfcc2 = matcher.extract_mfcc(audio, sr)
        
        # 应该完全相同
        np.testing.assert_array_almost_equal(mfcc1, mfcc2)
    
    def test_spectral_centroid_consistency(self):
        """测试相同音频的频谱质心一致性"""
        sr = 22050
        duration = 1.0
        audio = np.random.randn(int(sr * duration))
        
        matcher = TimbreMatcher()
        
        # 提取两次频谱质心
        centroid1 = matcher.extract_spectral_centroid(audio, sr)
        centroid2 = matcher.extract_spectral_centroid(audio, sr)
        
        # 应该完全相同
        np.testing.assert_array_almost_equal(centroid1, centroid2)
    
    def test_calculate_timbre_similarity_identical(self):
        """测试相同音频的音色相似度"""
        sr = 22050
        duration = 1.0
        audio = np.random.randn(int(sr * duration))
        
        matcher = TimbreMatcher()
        mfcc1 = matcher.extract_mfcc(audio, sr)
        mfcc2 = matcher.extract_mfcc(audio, sr)
        
        similarity = matcher.calculate_timbre_similarity(mfcc1, mfcc2)
        
        # 相同音频的相似度应接近 1.0
        assert similarity > 0.99
        assert similarity <= 1.0
    
    def test_calculate_timbre_similarity_different(self):
        """测试不同音频的音色相似度"""
        sr = 22050
        duration = 1.0
        
        # 生成两个不同的音频
        audio1 = np.random.randn(int(sr * duration))
        audio2 = np.random.randn(int(sr * duration))
        
        matcher = TimbreMatcher()
        mfcc1 = matcher.extract_mfcc(audio1, sr)
        mfcc2 = matcher.extract_mfcc(audio2, sr)
        
        similarity = matcher.calculate_timbre_similarity(mfcc1, mfcc2)
        
        # 不同音频的相似度应该在 [0, 1] 范围内
        assert 0.0 <= similarity <= 1.0
    
    def test_calculate_timbre_similarity_sine_waves(self):
        """测试不同频率正弦波的音色相似度"""
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        
        # 两个不同频率的正弦波
        audio1 = np.sin(2 * np.pi * 440 * t)  # A4
        audio2 = np.sin(2 * np.pi * 880 * t)  # A5 (八度)
        
        matcher = TimbreMatcher()
        mfcc1 = matcher.extract_mfcc(audio1, sr)
        mfcc2 = matcher.extract_mfcc(audio2, sr)
        
        similarity = matcher.calculate_timbre_similarity(mfcc1, mfcc2)
        
        # 正弦波的音色应该相似（都是纯音）
        assert similarity > 0.5
        assert similarity <= 1.0
    
    def test_calculate_timbre_similarity_none_input(self):
        """测试 None 输入的音色相似度计算"""
        matcher = TimbreMatcher()
        
        with pytest.raises(ValueError, match="MFCC 数据为空"):
            matcher.calculate_timbre_similarity(None, None)
    
    def test_calculate_timbre_similarity_dimension_mismatch(self):
        """测试维度不匹配的 MFCC"""
        sr = 22050
        duration = 1.0
        audio = np.random.randn(int(sr * duration))
        
        matcher1 = TimbreMatcher(n_mfcc=13)
        matcher2 = TimbreMatcher(n_mfcc=20)
        
        mfcc1 = matcher1.extract_mfcc(audio, sr)
        mfcc2 = matcher2.extract_mfcc(audio, sr)
        
        with pytest.raises(ValueError, match="MFCC 维度不匹配"):
            matcher1.calculate_timbre_similarity(mfcc1, mfcc2)
    
    def test_calculate_timbre_similarity_invalid_shape(self):
        """测试无效形状的 MFCC"""
        matcher = TimbreMatcher()
        
        # 一维数组（无效）
        mfcc1 = np.array([1, 2, 3, 4, 5])
        mfcc2 = np.array([1, 2, 3, 4, 5])
        
        with pytest.raises(ValueError, match="MFCC 数据必须是二维数组"):
            matcher.calculate_timbre_similarity(mfcc1, mfcc2)
    
    def test_calculate_timbre_similarity_zero_norm(self):
        """测试零范数的 MFCC（边界情况）"""
        matcher = TimbreMatcher()
        
        # 创建零 MFCC
        mfcc1 = np.zeros((13, 10))
        mfcc2 = np.random.randn(13, 10)
        
        similarity = matcher.calculate_timbre_similarity(mfcc1, mfcc2)
        
        # 零向量的相似度应该是 0
        assert similarity == 0.0
    
    def test_calculate_timbre_similarity_range(self):
        """测试相似度始终在 [0, 1] 范围内"""
        sr = 22050
        duration = 0.5
        matcher = TimbreMatcher()
        
        # 测试多对随机音频
        for _ in range(10):
            audio1 = np.random.randn(int(sr * duration))
            audio2 = np.random.randn(int(sr * duration))
            
            mfcc1 = matcher.extract_mfcc(audio1, sr)
            mfcc2 = matcher.extract_mfcc(audio2, sr)
            
            similarity = matcher.calculate_timbre_similarity(mfcc1, mfcc2)
            
            # 相似度必须在 [0, 1] 范围内
            assert 0.0 <= similarity <= 1.0
    
    def test_calculate_timbre_similarity_symmetry(self):
        """测试相似度的对称性"""
        sr = 22050
        duration = 1.0
        audio1 = np.random.randn(int(sr * duration))
        audio2 = np.random.randn(int(sr * duration))
        
        matcher = TimbreMatcher()
        mfcc1 = matcher.extract_mfcc(audio1, sr)
        mfcc2 = matcher.extract_mfcc(audio2, sr)
        
        similarity_12 = matcher.calculate_timbre_similarity(mfcc1, mfcc2)
        similarity_21 = matcher.calculate_timbre_similarity(mfcc2, mfcc1)
        
        # 相似度应该是对称的
        assert abs(similarity_12 - similarity_21) < 1e-6
