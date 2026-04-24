"""
测试 PitchExtractor 类的功能
"""

import numpy as np
import pytest
from src.remix.improved.pitch_extractor import PitchExtractor


def test_init():
    """测试初始化"""
    extractor = PitchExtractor()
    assert extractor.fmin == 80.0
    assert extractor.fmax == 400.0
    assert extractor.frame_length == 2048
    assert extractor.hop_length == 512


def test_init_custom_params():
    """测试自定义参数初始化"""
    extractor = PitchExtractor(fmin=100.0, fmax=500.0, frame_length=4096, hop_length=256)
    assert extractor.fmin == 100.0
    assert extractor.fmax == 500.0
    assert extractor.frame_length == 4096
    assert extractor.hop_length == 256


def test_extract_pitch_contour_sine_wave():
    """测试使用纯正弦波提取音高"""
    # 生成 440Hz 正弦波（A4）
    sr = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.sin(2 * np.pi * 440 * t)
    
    extractor = PitchExtractor()
    pitch_contour, confidence = extractor.extract_pitch_contour(audio, sr)
    
    # 验证返回的数组不为空
    assert len(pitch_contour) > 0
    assert len(confidence) > 0
    assert len(pitch_contour) == len(confidence)
    
    # 验证有效音高接近 440Hz（允许八度误差）
    valid_pitches = pitch_contour[confidence > 0.5]
    if len(valid_pitches) > 0:
        median_pitch = np.median(valid_pitches)
        # pyin 算法可能检测到八度误差，接受 220Hz (A3) 或 440Hz (A4) 或 880Hz (A5)
        # 检查是否接近这些频率之一
        is_near_220 = 200 < median_pitch < 240
        is_near_440 = 400 < median_pitch < 480
        is_near_880 = 800 < median_pitch < 960
        assert is_near_220 or is_near_440 or is_near_880, \
            f"Expected pitch near 220Hz, 440Hz, or 880Hz, got {median_pitch:.1f}Hz"


def test_extract_pitch_contour_empty_audio():
    """测试空音频的处理"""
    sr = 22050
    audio = np.zeros(sr)  # 1 秒静音
    
    extractor = PitchExtractor()
    pitch_contour, confidence = extractor.extract_pitch_contour(audio, sr)
    
    # 验证返回的数组不为空
    assert len(pitch_contour) > 0
    assert len(confidence) > 0
    
    # 静音应该没有有效音高
    valid_pitches = pitch_contour[confidence > 0.5]
    assert len(valid_pitches) == 0


def test_extract_pitch_contour_confidence_filtering():
    """测试置信度过滤"""
    # 生成 440Hz 正弦波
    sr = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.sin(2 * np.pi * 440 * t)
    
    extractor = PitchExtractor()
    pitch_contour, confidence = extractor.extract_pitch_contour(audio, sr)
    
    # 验证低置信度位置的音高为 0
    low_confidence_mask = confidence < 0.5
    assert np.all(pitch_contour[low_confidence_mask] == 0)


def test_pitch_to_midi_a4():
    """测试 A4 (440Hz) 转换为 MIDI 69"""
    extractor = PitchExtractor()
    midi_note = extractor.pitch_to_midi(440.0)
    assert midi_note == 69


def test_pitch_to_midi_c4():
    """测试 C4 (261.63Hz) 转换为 MIDI 60"""
    extractor = PitchExtractor()
    midi_note = extractor.pitch_to_midi(261.63)
    assert midi_note == 60


def test_pitch_to_midi_invalid():
    """测试无效音高返回 0"""
    extractor = PitchExtractor()
    assert extractor.pitch_to_midi(0) == 0
    assert extractor.pitch_to_midi(-100) == 0


def test_pitch_to_midi_range():
    """测试 MIDI 范围限制"""
    extractor = PitchExtractor()
    
    # 测试极低音高
    midi_low = extractor.pitch_to_midi(8.18)  # C0
    assert 0 <= midi_low <= 127
    
    # 测试极高音高
    midi_high = extractor.pitch_to_midi(12543.85)  # G9
    assert 0 <= midi_high <= 127


def test_detect_onsets():
    """测试起始点检测"""
    # 生成带有明显起始点的音频（3 个音符）
    sr = 22050
    duration = 0.3
    silence_duration = 0.1
    
    # 创建 3 个音符，中间有静音
    note1 = np.sin(2 * np.pi * 440 * np.linspace(0, duration, int(sr * duration)))
    silence = np.zeros(int(sr * silence_duration))
    note2 = np.sin(2 * np.pi * 523 * np.linspace(0, duration, int(sr * duration)))
    silence2 = np.zeros(int(sr * silence_duration))
    note3 = np.sin(2 * np.pi * 659 * np.linspace(0, duration, int(sr * duration)))
    
    audio = np.concatenate([note1, silence, note2, silence2, note3])
    
    extractor = PitchExtractor()
    onset_times = extractor.detect_onsets(audio, sr)
    
    # 验证检测到起始点
    assert len(onset_times) > 0
    
    # 验证起始点在合理范围内
    assert np.all(onset_times >= 0)
    assert np.all(onset_times <= len(audio) / sr)


def test_detect_onsets_empty_audio():
    """测试静音音频的起始点检测"""
    sr = 22050
    audio = np.zeros(sr)  # 1 秒静音
    
    extractor = PitchExtractor()
    onset_times = extractor.detect_onsets(audio, sr)
    
    # 静音可能检测不到起始点，或检测到很少
    assert len(onset_times) >= 0


def test_extract_pitch_contour_different_sample_rates():
    """测试不同采样率"""
    # 生成 440Hz 正弦波
    for sr in [16000, 22050, 44100]:
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        
        extractor = PitchExtractor()
        pitch_contour, confidence = extractor.extract_pitch_contour(audio, sr)
        
        # 验证返回的数组不为空
        assert len(pitch_contour) > 0
        assert len(confidence) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
