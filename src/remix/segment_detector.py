"""
音频分段检测模块 - 自动检测音频中的音节/字
"""
import numpy as np
import librosa
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class Segment:
    """音频片段"""
    
    def __init__(self, start_time: float, end_time: float, audio_data: np.ndarray, 
                 sample_rate: int, name: str = ""):
        self.start_time = start_time  # 秒
        self.end_time = end_time  # 秒
        self.audio_data = audio_data  # 音频数据
        self.sample_rate = sample_rate
        self.name = name
        
        # 特征（用于匹配）
        self.pitch = None  # 平均音高
        self.energy = None  # 能量
        self.duration = end_time - start_time
    
    def extract_features(self):
        """提取音频特征"""
        # 提取音高
        pitches, magnitudes = librosa.piptrack(
            y=self.audio_data,
            sr=self.sample_rate,
            fmin=50,
            fmax=2000
        )
        
        # 计算平均音高（忽略静音部分）
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)
        
        self.pitch = np.median(pitch_values) if pitch_values else 0
        
        # 计算能量
        self.energy = np.sqrt(np.mean(self.audio_data ** 2))
        
        logger.debug(f"片段特征: pitch={self.pitch:.2f}Hz, energy={self.energy:.4f}, duration={self.duration:.2f}s")


class SegmentDetector:
    """自动分段检测器"""
    
    def __init__(self):
        self.min_silence_duration = 0.1  # 最小静音时长（秒）
        self.silence_threshold = 0.02  # 静音阈值
        self.min_segment_duration = 0.1  # 最小片段时长（秒）
        self.max_segment_duration = 2.0  # 最大片段时长（秒）
    
    def detect_segments(self, audio_path: str) -> List[Segment]:
        """
        自动检测音频片段
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            片段列表
        """
        logger.info(f"开始检测音频片段: {audio_path}")
        
        # 加载音频
        audio, sr = librosa.load(audio_path, sr=None, mono=True)
        
        # 检测静音区间
        intervals = librosa.effects.split(
            audio,
            top_db=30,  # 静音阈值（dB）
            frame_length=2048,
            hop_length=512
        )
        
        logger.info(f"检测到 {len(intervals)} 个非静音区间")
        
        # 创建片段
        segments = []
        for i, (start_frame, end_frame) in enumerate(intervals):
            start_time = start_frame / sr
            end_time = end_frame / sr
            duration = end_time - start_time
            
            # 过滤太短或太长的片段
            if duration < self.min_segment_duration or duration > self.max_segment_duration:
                logger.debug(f"跳过片段 {i}: 时长 {duration:.2f}s 不在范围内")
                continue
            
            # 提取音频数据
            segment_audio = audio[start_frame:end_frame]
            
            # 创建片段
            segment = Segment(
                start_time=start_time,
                end_time=end_time,
                audio_data=segment_audio,
                sample_rate=sr,
                name=f"片段{i+1}"
            )
            
            # 提取特征
            segment.extract_features()
            
            segments.append(segment)
            logger.info(f"片段 {i+1}: {start_time:.2f}s - {end_time:.2f}s (时长: {duration:.2f}s)")
        
        logger.info(f"共检测到 {len(segments)} 个有效片段")
        return segments
    
    def refine_segments(self, segments: List[Segment], target_count: int = None) -> List[Segment]:
        """
        优化片段（合并或分割）
        
        Args:
            segments: 原始片段列表
            target_count: 目标片段数量（可选）
            
        Returns:
            优化后的片段列表
        """
        # TODO: 实现智能合并和分割
        # 例如：如果检测到太多片段，可以合并相邻的短片段
        # 如果片段太少，可以尝试进一步分割
        return segments
