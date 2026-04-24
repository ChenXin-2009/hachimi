"""
动态控制器模块

负责管理音量包络和动态变化，包括：
- 提取 RMS 响度包络
- 计算动态范围
- 应用响度包络到音频
- 响度归一化

需求: 4.1, 4.2
"""

import numpy as np
import librosa
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DynamicController:
    """
    动态控制器
    
    管理音频的响度包络和动态变化
    """
    
    def __init__(self, hop_length: int = 512):
        """
        初始化动态控制器
        
        Args:
            hop_length: 跳跃长度（采样点），默认 512
        """
        self.hop_length = hop_length
        logger.debug(f"DynamicController initialized with hop_length={hop_length}")
    
    def extract_rms_envelope(self, 
                            audio: np.ndarray, 
                            sr: int) -> np.ndarray:
        """
        提取 RMS 响度包络
        
        使用 librosa.feature.rms 提取音频的响度包络，时间分辨率约为 10ms
        
        Args:
            audio: 音频数据（numpy 数组）
            sr: 采样率
            
        Returns:
            RMS 包络数组（一维数组）
            
        需求: 4.1
        """
        try:
            # 使用 librosa.feature.rms 提取 RMS 包络
            rms = librosa.feature.rms(
                y=audio,
                frame_length=self.hop_length * 2,
                hop_length=self.hop_length
            )
            
            # rms 返回的是 (1, n_frames) 的二维数组，转换为一维
            rms_envelope = rms[0]
            
            logger.debug(f"Extracted RMS envelope with {len(rms_envelope)} frames")
            return rms_envelope
            
        except Exception as e:
            logger.error(f"Failed to extract RMS envelope: {e}")
            raise
    
    def calculate_dynamic_range(self, rms_envelope: np.ndarray) -> float:
        """
        计算动态范围
        
        动态范围定义为最大响度与最小响度的比值（dB）
        
        Args:
            rms_envelope: RMS 包络数组
            
        Returns:
            动态范围（dB）
            
        需求: 4.2
        """
        try:
            # 过滤掉零值或极小值，避免 log 计算问题
            valid_rms = rms_envelope[rms_envelope > 1e-10]
            
            if len(valid_rms) == 0:
                logger.warning("No valid RMS values found, returning 0 dB dynamic range")
                return 0.0
            
            # 计算最大和最小响度
            max_rms = np.max(valid_rms)
            min_rms = np.min(valid_rms)
            
            # 计算动态范围（dB）
            # 动态范围 = 20 * log10(max_rms / min_rms)
            dynamic_range = 20 * np.log10(max_rms / min_rms)
            
            logger.debug(f"Calculated dynamic range: {dynamic_range:.2f} dB")
            return float(dynamic_range)
            
        except Exception as e:
            logger.error(f"Failed to calculate dynamic range: {e}")
            raise
    
    def apply_envelope(self, 
                      audio: np.ndarray, 
                      target_envelope: np.ndarray) -> np.ndarray:
        """
        应用响度包络到音频
        
        将目标响度包络应用到音频信号上，保持原始的响度变化形状
        
        Args:
            audio: 音频数据
            target_envelope: 目标响度包络
            
        Returns:
            处理后的音频
        """
        try:
            # 提取当前音频的 RMS 包络
            current_envelope = self.extract_rms_envelope(audio, 22050)
            
            # 将包络插值到音频长度
            from scipy.interpolate import interp1d
            
            # 创建时间轴
            current_times = np.linspace(0, len(audio), len(current_envelope))
            target_times = np.linspace(0, len(audio), len(target_envelope))
            audio_times = np.arange(len(audio))
            
            # 插值当前包络和目标包络到音频长度
            current_interp = interp1d(
                current_times, 
                current_envelope, 
                kind='linear', 
                fill_value='extrapolate'
            )
            target_interp = interp1d(
                target_times, 
                target_envelope, 
                kind='linear', 
                fill_value='extrapolate'
            )
            
            current_full = current_interp(audio_times)
            target_full = target_interp(audio_times)
            
            # 避免除以零
            current_full = np.maximum(current_full, 1e-10)
            
            # 计算增益比例
            gain = target_full / current_full
            
            # 应用增益
            result = audio * gain
            
            # 防止削波
            max_val = np.max(np.abs(result))
            if max_val > 0.99:
                result = result * (0.99 / max_val)
            
            logger.debug("Applied envelope to audio")
            return result
            
        except Exception as e:
            logger.error(f"Failed to apply envelope: {e}")
            raise
    
    def normalize_loudness(self, 
                          audio: np.ndarray, 
                          target_lufs: float = -20.0) -> np.ndarray:
        """
        响度归一化
        
        将音频归一化到目标响度（LUFS）
        注意：这是简化实现，使用 RMS 近似 LUFS
        
        Args:
            audio: 音频数据
            target_lufs: 目标响度（LUFS），默认 -20.0
            
        Returns:
            归一化后的音频
        """
        try:
            # 计算当前 RMS
            current_rms = np.sqrt(np.mean(audio ** 2))
            
            if current_rms < 1e-10:
                logger.warning("Audio is silent, skipping normalization")
                return audio
            
            # 简化：使用 RMS 近似 LUFS
            # 实际的 LUFS 计算需要更复杂的滤波器
            # 这里使用简单的 RMS 到 dB 转换
            current_db = 20 * np.log10(current_rms)
            
            # 计算需要的增益
            gain_db = target_lufs - current_db
            gain_linear = 10 ** (gain_db / 20)
            
            # 应用增益
            result = audio * gain_linear
            
            # 防止削波
            max_val = np.max(np.abs(result))
            if max_val > 0.99:
                result = result * (0.99 / max_val)
            
            logger.debug(f"Normalized loudness from {current_db:.2f} dB to {target_lufs:.2f} LUFS")
            return result
            
        except Exception as e:
            logger.error(f"Failed to normalize loudness: {e}")
            raise
