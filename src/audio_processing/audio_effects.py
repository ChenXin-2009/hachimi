"""
音频效果处理 - 使用 numba 加速
"""
import numpy as np
from numba import jit
import logging

logger = logging.getLogger(__name__)


@jit(nopython=True, cache=True)
def apply_gain_fast(audio: np.ndarray, gain_linear: float) -> np.ndarray:
    """
    快速应用增益（使用 numba 加速）
    
    Args:
        audio: 音频数据
        gain_linear: 线性增益值
        
    Returns:
        处理后的音频
    """
    return audio * gain_linear


@jit(nopython=True, cache=True)
def apply_pan_fast(audio: np.ndarray, pan: float) -> np.ndarray:
    """
    快速应用平衡（使用 numba 加速）
    
    Args:
        audio: 音频数据 (2, samples) - 必须是立体声
        pan: 平衡值 (-1.0 到 1.0)
        
    Returns:
        处理后的音频
    """
    result = audio.copy()
    
    if pan < 0:
        # 偏左：减小右声道
        result[1] *= (1 + pan)
    else:
        # 偏右：减小左声道
        result[0] *= (1 - pan)
    
    return result


@jit(nopython=True, cache=True)
def mix_audio_fast(audio_list: list, max_length: int) -> np.ndarray:
    """
    快速混合多个音频（使用 numba 加速）
    
    注意：numba 不支持动态列表，这个函数需要特殊处理
    
    Args:
        audio_list: 音频数组列表
        max_length: 最大长度
        
    Returns:
        混合后的音频
    """
    # 这个函数由于 numba 限制，实际上不能直接使用
    # 保留作为示例
    pass


@jit(nopython=True, cache=True)
def normalize_audio_fast(audio: np.ndarray, target_level: float = 1.0) -> np.ndarray:
    """
    快速归一化音频（使用 numba 加速）
    
    Args:
        audio: 音频数据
        target_level: 目标电平
        
    Returns:
        归一化后的音频
    """
    max_val = np.max(np.abs(audio))
    
    if max_val > 0:
        # 确保返回类型一致
        return audio * np.float32(target_level / max_val)
    else:
        return audio.copy()


@jit(nopython=True, cache=True)
def apply_fade_in_fast(audio: np.ndarray, fade_samples: int) -> np.ndarray:
    """
    快速应用淡入效果（使用 numba 加速）
    
    Args:
        audio: 音频数据 (channels, samples)
        fade_samples: 淡入样本数
        
    Returns:
        处理后的音频
    """
    result = audio.copy()
    channels, samples = audio.shape
    
    fade_samples = min(fade_samples, samples)
    
    for i in range(fade_samples):
        factor = i / fade_samples
        for ch in range(channels):
            result[ch, i] *= factor
    
    return result


@jit(nopython=True, cache=True)
def apply_fade_out_fast(audio: np.ndarray, fade_samples: int) -> np.ndarray:
    """
    快速应用淡出效果（使用 numba 加速）
    
    Args:
        audio: 音频数据 (channels, samples)
        fade_samples: 淡出样本数
        
    Returns:
        处理后的音频
    """
    result = audio.copy()
    channels, samples = audio.shape
    
    fade_samples = min(fade_samples, samples)
    start_pos = samples - fade_samples
    
    for i in range(fade_samples):
        factor = 1.0 - (i / fade_samples)
        pos = start_pos + i
        for ch in range(channels):
            result[ch, pos] *= factor
    
    return result


class FastAudioEffects:
    """快速音频效果处理器"""
    
    @staticmethod
    def apply_volume(audio: np.ndarray, volume_db: float) -> np.ndarray:
        """
        应用音量调整
        
        Args:
            audio: 音频数据
            volume_db: 音量（dB）
            
        Returns:
            处理后的音频
        """
        gain_linear = 10 ** (volume_db / 20.0)
        return apply_gain_fast(audio, gain_linear)
    
    @staticmethod
    def apply_pan(audio: np.ndarray, pan: float) -> np.ndarray:
        """
        应用平衡调整
        
        Args:
            audio: 音频数据 (channels, samples)
            pan: 平衡值 (-1.0 到 1.0)
            
        Returns:
            处理后的音频
        """
        if audio.shape[0] < 2:
            # 单声道，无法应用平衡
            return audio
        
        return apply_pan_fast(audio, pan)
    
    @staticmethod
    def normalize(audio: np.ndarray, target_db: float = 0.0) -> np.ndarray:
        """
        归一化音频
        
        Args:
            audio: 音频数据
            target_db: 目标电平（dB）
            
        Returns:
            归一化后的音频
        """
        target_level = 10 ** (target_db / 20.0)
        return normalize_audio_fast(audio, target_level)
    
    @staticmethod
    def apply_fade_in(audio: np.ndarray, duration_ms: float, sample_rate: int) -> np.ndarray:
        """
        应用淡入效果
        
        Args:
            audio: 音频数据
            duration_ms: 淡入时长（毫秒）
            sample_rate: 采样率
            
        Returns:
            处理后的音频
        """
        fade_samples = int(duration_ms * sample_rate / 1000.0)
        return apply_fade_in_fast(audio, fade_samples)
    
    @staticmethod
    def apply_fade_out(audio: np.ndarray, duration_ms: float, sample_rate: int) -> np.ndarray:
        """
        应用淡出效果
        
        Args:
            audio: 音频数据
            duration_ms: 淡出时长（毫秒）
            sample_rate: 采样率
            
        Returns:
            处理后的音频
        """
        fade_samples = int(duration_ms * sample_rate / 1000.0)
        return apply_fade_out_fast(audio, fade_samples)
