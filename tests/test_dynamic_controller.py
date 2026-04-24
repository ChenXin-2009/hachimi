"""
测试动态控制器模块

测试 DynamicController 类的功能：
- RMS 包络提取
- 动态范围计算
- 包络应用
- 响度归一化
"""

import pytest
import numpy as np
import librosa
from src.remix.improved.dynamic_controller import DynamicController


class TestDynamicController:
    """测试 DynamicController 类"""
    
    def test_init(self):
        """测试初始化"""
        controller = DynamicController(hop_length=512)
        assert controller.hop_length == 512
        
        controller2 = DynamicController(hop_length=1024)
        assert controller2.hop_length == 1024
    
    def test_extract_rms_envelope_sine_wave(self):
        """测试使用正弦波提取 RMS 包络"""
        # 生成 1 秒 440Hz 正弦波
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        
        controller = DynamicController()
        rms_envelope = controller.extract_rms_envelope(audio, sr)
        
        # 验证返回的是一维数组
        assert rms_envelope.ndim == 1
        
        # 验证 RMS 值在合理范围内（正弦波的 RMS 约为 0.707）
        assert len(rms_envelope) > 0
        mean_rms = np.mean(rms_envelope)
        assert 0.5 < mean_rms < 0.9
    
    def test_extract_rms_envelope_varying_amplitude(self):
        """测试提取变化幅度的音频的 RMS 包络"""
        # 生成幅度渐变的正弦波（从 0 到 1）
        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration))
        envelope = np.linspace(0, 1, len(t))
        audio = envelope * np.sin(2 * np.pi * 440 * t)
        
        controller = DynamicController()
        rms_envelope = controller.extract_rms_envelope(audio, sr)
        
        # 验证 RMS 包络是递增的
        assert len(rms_envelope) > 10
        # 前半部分的平均值应该小于后半部分
        first_half = np.mean(rms_envelope[:len(rms_envelope)//2])
        second_half = np.mean(rms_envelope[len(rms_envelope)//2:])
        assert first_half < second_half
    
    def test_extract_rms_envelope_empty_audio(self):
        """测试空音频的 RMS 包络提取"""
        sr = 22050
        audio = np.zeros(sr)  # 1 秒静音
        
        controller = DynamicController()
        rms_envelope = controller.extract_rms_envelope(audio, sr)
        
        # 验证返回的包络全为零或接近零
        assert len(rms_envelope) > 0
        assert np.max(rms_envelope) < 1e-6
    
    def test_calculate_dynamic_range_constant_amplitude(self):
        """测试恒定幅度音频的动态范围"""
        # 恒定幅度的 RMS 包络
        rms_envelope = np.ones(100) * 0.5
        
        controller = DynamicController()
        dynamic_range = controller.calculate_dynamic_range(rms_envelope)
        
        # 恒定幅度的动态范围应该接近 0 dB
        assert abs(dynamic_range) < 0.1
    
    def test_calculate_dynamic_range_varying_amplitude(self):
        """测试变化幅度音频的动态范围"""
        # 创建从 0.1 到 1.0 的 RMS 包络
        rms_envelope = np.linspace(0.1, 1.0, 100)
        
        controller = DynamicController()
        dynamic_range = controller.calculate_dynamic_range(rms_envelope)
        
        # 动态范围应该是 20 * log10(1.0 / 0.1) = 20 dB
        expected_range = 20 * np.log10(1.0 / 0.1)
        assert abs(dynamic_range - expected_range) < 0.5
    
    def test_calculate_dynamic_range_zero_values(self):
        """测试包含零值的 RMS 包络"""
        # 包含零值的 RMS 包络
        rms_envelope = np.array([0.0, 0.0, 0.5, 1.0, 0.0])
        
        controller = DynamicController()
        dynamic_range = controller.calculate_dynamic_range(rms_envelope)
        
        # 应该忽略零值，只计算有效值的动态范围
        assert dynamic_range > 0
        expected_range = 20 * np.log10(1.0 / 0.5)
        assert abs(dynamic_range - expected_range) < 0.5
    
    def test_calculate_dynamic_range_all_zeros(self):
        """测试全零 RMS 包络"""
        rms_envelope = np.zeros(100)
        
        controller = DynamicController()
        dynamic_range = controller.calculate_dynamic_range(rms_envelope)
        
        # 全零应该返回 0 dB
        assert dynamic_range == 0.0
    
    def test_apply_envelope(self):
        """测试应用响度包络"""
        # 生成恒定幅度的音频
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t) * 0.5
        
        # 创建目标包络（渐变）
        controller = DynamicController()
        current_envelope = controller.extract_rms_envelope(audio, sr)
        target_envelope = np.linspace(0.1, 1.0, len(current_envelope))
        
        # 应用包络
        result = controller.apply_envelope(audio, target_envelope)
        
        # 验证结果
        assert len(result) == len(audio)
        assert np.max(np.abs(result)) <= 1.0  # 没有削波
        
        # 验证音频幅度确实发生了变化
        result_envelope = controller.extract_rms_envelope(result, sr)
        # 后半部分应该比前半部分响度更大
        first_half = np.mean(result_envelope[:len(result_envelope)//2])
        second_half = np.mean(result_envelope[len(result_envelope)//2:])
        assert second_half > first_half
    
    def test_normalize_loudness(self):
        """测试响度归一化"""
        # 生成低响度音频
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t) * 0.1  # 低幅度
        
        controller = DynamicController()
        
        # 归一化到 -20 LUFS
        normalized = controller.normalize_loudness(audio, target_lufs=-20.0)
        
        # 验证结果
        assert len(normalized) == len(audio)
        assert np.max(np.abs(normalized)) <= 1.0  # 没有削波
        
        # 验证响度确实增加了
        original_rms = np.sqrt(np.mean(audio ** 2))
        normalized_rms = np.sqrt(np.mean(normalized ** 2))
        assert normalized_rms > original_rms
    
    def test_normalize_loudness_silent_audio(self):
        """测试静音音频的归一化"""
        audio = np.zeros(22050)  # 1 秒静音
        
        controller = DynamicController()
        normalized = controller.normalize_loudness(audio, target_lufs=-20.0)
        
        # 静音音频应该保持不变
        assert np.allclose(normalized, audio)
    
    def test_normalize_loudness_no_clipping(self):
        """测试归一化不会导致削波"""
        # 生成高响度音频
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t) * 0.9  # 高幅度
        
        controller = DynamicController()
        
        # 归一化到更高的响度
        normalized = controller.normalize_loudness(audio, target_lufs=-10.0)
        
        # 验证没有削波
        assert np.max(np.abs(normalized)) < 1.0
    
    def test_different_hop_lengths(self):
        """测试不同的跳跃长度"""
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        
        # 测试不同的 hop_length
        for hop_length in [256, 512, 1024]:
            controller = DynamicController(hop_length=hop_length)
            rms_envelope = controller.extract_rms_envelope(audio, sr)
            
            # 验证返回的包络长度合理
            expected_frames = len(audio) // hop_length
            assert abs(len(rms_envelope) - expected_frames) < 10
    
    def test_real_audio_workflow(self):
        """测试完整的工作流程"""
        # 生成测试音频
        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration))
        
        # 原始音频：幅度渐变
        envelope = np.linspace(0.3, 0.8, len(t))
        audio = envelope * np.sin(2 * np.pi * 440 * t)
        
        controller = DynamicController()
        
        # 1. 提取 RMS 包络
        rms_envelope = controller.extract_rms_envelope(audio, sr)
        assert len(rms_envelope) > 0
        
        # 2. 计算动态范围
        dynamic_range = controller.calculate_dynamic_range(rms_envelope)
        assert dynamic_range > 0
        
        # 3. 归一化响度
        normalized = controller.normalize_loudness(audio, target_lufs=-20.0)
        assert len(normalized) == len(audio)
        
        # 4. 应用新的包络
        target_envelope = np.ones(len(rms_envelope)) * 0.5  # 恒定包络
        result = controller.apply_envelope(normalized, target_envelope)
        assert len(result) == len(audio)
        
        # 验证最终结果没有削波
        assert np.max(np.abs(result)) < 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
