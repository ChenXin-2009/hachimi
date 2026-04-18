"""
波形渲染器模块
"""
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class WaveformRenderer:
    """波形渲染器"""
    
    def __init__(self):
        self._peak_cache = {}  # 缓存峰值数据
        logger.info("波形渲染器初始化")
    
    def calculate_peaks(
        self,
        audio_data: np.ndarray,
        num_samples: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算波形峰值用于快速渲染
        
        Args:
            audio_data: 音频数据 (channels, samples)
            num_samples: 目标采样点数量
            
        Returns:
            (min_peaks, max_peaks) 元组，每个形状为 (channels, num_samples)
        """
        if audio_data.size == 0:
            return np.array([]), np.array([])
        
        channels, total_samples = audio_data.shape
        
        if num_samples >= total_samples:
            # 不需要降采样
            return audio_data, audio_data
        
        # 计算每个峰值点对应的样本数
        samples_per_peak = total_samples / num_samples
        
        min_peaks = np.zeros((channels, num_samples))
        max_peaks = np.zeros((channels, num_samples))
        
        for i in range(num_samples):
            start_idx = int(i * samples_per_peak)
            end_idx = int((i + 1) * samples_per_peak)
            
            if end_idx > total_samples:
                end_idx = total_samples
            
            # 计算该区间的最小值和最大值
            chunk = audio_data[:, start_idx:end_idx]
            min_peaks[:, i] = chunk.min(axis=1)
            max_peaks[:, i] = chunk.max(axis=1)
        
        return min_peaks, max_peaks
    
    def get_waveform_data(
        self,
        audio_data: np.ndarray,
        start_time: float,
        end_time: float,
        sample_rate: int,
        width: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        获取指定时间范围的波形数据
        
        Args:
            audio_data: 音频数据 (channels, samples)
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            sample_rate: 采样率
            width: 渲染宽度（像素）
            
        Returns:
            (min_peaks, max_peaks) 元组
        """
        if audio_data.size == 0:
            return np.array([]), np.array([])
        
        # 转换时间到样本索引
        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)
        
        # 边界检查
        total_samples = audio_data.shape[1]
        start_sample = max(0, start_sample)
        end_sample = min(total_samples, end_sample)
        
        if start_sample >= end_sample:
            return np.array([]), np.array([])
        
        # 提取音频片段
        audio_chunk = audio_data[:, start_sample:end_sample]
        
        # 计算峰值
        return self.calculate_peaks(audio_chunk, width)
    
    def clear_cache(self):
        """清除峰值缓存"""
        self._peak_cache.clear()
        logger.debug("清除波形缓存")
