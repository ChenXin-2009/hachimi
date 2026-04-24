"""
节奏分析器模块

提供节拍检测、速度分析和基于节奏的分段功能。
"""

import numpy as np
import librosa
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

# Import Segment class
from src.remix.segment_detector import Segment


class RhythmAnalyzer:
    """
    节奏分析器
    
    职责：检测节拍、速度和节奏模式
    """
    
    def __init__(self, hop_length: int = 512):
        """
        初始化节奏分析器
        
        Args:
            hop_length: 跳跃长度（采样点）
        """
        self.hop_length = hop_length
        logger.debug(f"RhythmAnalyzer initialized with hop_length={hop_length}")
    
    def detect_tempo_and_beats(self, 
                              audio: np.ndarray, 
                              sr: int) -> Tuple[float, np.ndarray]:
        """
        检测速度和节拍位置
        
        使用 librosa.beat.beat_track 检测原曲的 Tempo 和 Beat 位置。
        
        Args:
            audio: 音频数据
            sr: 采样率
            
        Returns:
            (tempo, beat_times): 速度（BPM）和节拍时间数组（秒）
            
        Raises:
            ValueError: 如果音频数据为空或无效
        """
        if audio is None or len(audio) == 0:
            raise ValueError("音频数据为空")
        
        try:
            # 使用 librosa.beat.beat_track 检测速度和节拍
            tempo, beat_frames = librosa.beat.beat_track(
                y=audio,
                sr=sr,
                hop_length=self.hop_length
            )
            
            # 将帧转换为时间（秒）
            beat_times = librosa.frames_to_time(
                beat_frames,
                sr=sr,
                hop_length=self.hop_length
            )
            
            # 确保 tempo 是标量（librosa 可能返回数组或标量）
            if isinstance(tempo, np.ndarray):
                tempo = float(tempo.item())
            else:
                tempo = float(tempo)
            
            logger.info(f"检测到速度: {tempo:.1f} BPM, 节拍数: {len(beat_times)}")
            
            return tempo, beat_times
            
        except Exception as e:
            logger.error(f"节拍检测失败: {e}")
            raise
    
    def segment_by_beats(self, 
                        audio: np.ndarray, 
                        sr: int, 
                        beat_times: np.ndarray) -> List[Tuple[float, float]]:
        """
        基于节拍位置分段
        
        将音频按节拍位置划分为片段，每个片段从一个节拍开始到下一个节拍结束。
        
        Args:
            audio: 音频数据
            sr: 采样率
            beat_times: 节拍时间数组（秒）
            
        Returns:
            片段边界列表，每个元素为 (start_time, end_time) 元组
            
        Raises:
            ValueError: 如果音频数据或节拍时间为空
        """
        if audio is None or len(audio) == 0:
            raise ValueError("音频数据为空")
        
        if beat_times is None or len(beat_times) == 0:
            raise ValueError("节拍时间为空")
        
        segments = []
        audio_duration = len(audio) / sr
        
        # 为每对相邻节拍创建片段
        for i in range(len(beat_times) - 1):
            start_time = beat_times[i]
            end_time = beat_times[i + 1]
            
            # 确保时间在有效范围内
            if start_time >= 0 and end_time <= audio_duration:
                segments.append((start_time, end_time))
        
        # 处理最后一个节拍到音频结束
        if len(beat_times) > 0:
            last_beat = beat_times[-1]
            if last_beat < audio_duration:
                segments.append((last_beat, audio_duration))
        
        logger.info(f"基于节拍分段: 生成 {len(segments)} 个片段")
        
        # 应用合并和分割逻辑
        segments = self._merge_short_segments(segments, min_duration=0.05)
        segments = self._split_long_segments(segments, max_duration=2.0)
        
        logger.info(f"合并和分割后: {len(segments)} 个片段")
        
        return segments
    
    def segment_by_onsets(self, 
                         audio: np.ndarray, 
                         sr: int, 
                         onset_times: np.ndarray) -> List[Tuple[float, float]]:
        """
        基于起始点分段
        
        将音频按起始点（onset）位置划分为片段，每个片段从一个起始点开始到下一个起始点结束。
        
        Args:
            audio: 音频数据
            sr: 采样率
            onset_times: 起始点时间数组（秒）
            
        Returns:
            片段边界列表，每个元素为 (start_time, end_time) 元组
            
        Raises:
            ValueError: 如果音频数据或起始点时间为空
        """
        if audio is None or len(audio) == 0:
            raise ValueError("音频数据为空")
        
        if onset_times is None or len(onset_times) == 0:
            raise ValueError("起始点时间为空")
        
        segments = []
        audio_duration = len(audio) / sr
        
        # 为每对相邻起始点创建片段
        for i in range(len(onset_times) - 1):
            start_time = onset_times[i]
            end_time = onset_times[i + 1]
            
            # 确保时间在有效范围内
            if start_time >= 0 and end_time <= audio_duration:
                segments.append((start_time, end_time))
        
        # 处理最后一个起始点到音频结束
        if len(onset_times) > 0:
            last_onset = onset_times[-1]
            if last_onset < audio_duration:
                segments.append((last_onset, audio_duration))
        
        logger.info(f"基于起始点分段: 生成 {len(segments)} 个片段")
        
        # 应用合并和分割逻辑
        segments = self._merge_short_segments(segments, min_duration=0.05)
        segments = self._split_long_segments(segments, max_duration=2.0)
        
        logger.info(f"合并和分割后: {len(segments)} 个片段")
        
        return segments
    
    def _merge_short_segments(self, 
                             segments: List[Tuple[float, float]], 
                             min_duration: float = 0.05) -> List[Tuple[float, float]]:
        """
        合并过短的片段（< 50ms）到相邻片段
        
        Args:
            segments: 片段边界列表
            min_duration: 最小片段时长（秒），默认 0.05 秒（50ms）
            
        Returns:
            合并后的片段边界列表
        """
        if not segments:
            return segments
        
        merged = []
        i = 0
        
        while i < len(segments):
            start_time, end_time = segments[i]
            duration = end_time - start_time
            
            # 如果片段足够长，直接添加
            if duration >= min_duration:
                merged.append((start_time, end_time))
                i += 1
            else:
                # 片段太短，尝试与相邻片段合并
                if i + 1 < len(segments):
                    # 与下一个片段合并
                    next_start, next_end = segments[i + 1]
                    merged.append((start_time, next_end))
                    i += 2  # 跳过下一个片段
                    logger.debug(f"合并短片段: [{start_time:.3f}, {end_time:.3f}] + [{next_start:.3f}, {next_end:.3f}] -> [{start_time:.3f}, {next_end:.3f}]")
                elif merged:
                    # 如果是最后一个片段且太短，与前一个片段合并
                    prev_start, prev_end = merged.pop()
                    merged.append((prev_start, end_time))
                    logger.debug(f"合并最后的短片段: [{prev_start:.3f}, {prev_end:.3f}] + [{start_time:.3f}, {end_time:.3f}] -> [{prev_start:.3f}, {end_time:.3f}]")
                    i += 1
                else:
                    # 如果是唯一的片段，保留它
                    merged.append((start_time, end_time))
                    i += 1
        
        return merged
    
    def _split_long_segments(self, 
                            segments: List[Tuple[float, float]], 
                            max_duration: float = 2.0) -> List[Tuple[float, float]]:
        """
        分割过长的片段（> 2s）为多个子片段
        
        Args:
            segments: 片段边界列表
            max_duration: 最大片段时长（秒），默认 2.0 秒
            
        Returns:
            分割后的片段边界列表
        """
        if not segments:
            return segments
        
        split_segments = []
        
        for start_time, end_time in segments:
            duration = end_time - start_time
            
            # 如果片段不太长，直接添加
            if duration <= max_duration:
                split_segments.append((start_time, end_time))
            else:
                # 片段太长，分割为多个子片段
                num_splits = int(np.ceil(duration / max_duration))
                sub_duration = duration / num_splits
                
                logger.debug(f"分割长片段: [{start_time:.3f}, {end_time:.3f}] (时长 {duration:.3f}s) -> {num_splits} 个子片段")
                
                for i in range(num_splits):
                    sub_start = start_time + i * sub_duration
                    sub_end = start_time + (i + 1) * sub_duration
                    
                    # 确保最后一个子片段的结束时间正确
                    if i == num_splits - 1:
                        sub_end = end_time
                    
                    split_segments.append((sub_start, sub_end))
        
        return split_segments
