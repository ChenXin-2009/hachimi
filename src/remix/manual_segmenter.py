"""
手动分段编辑器 - 用户手动标记音频片段
"""
import numpy as np
import librosa
from typing import List
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
        if len(self.audio_data) == 0:
            self.pitch = 0
            self.energy = 0
            return
        
        # 提取音高
        try:
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
        except:
            self.pitch = 0
        
        # 计算能量
        self.energy = np.sqrt(np.mean(self.audio_data ** 2))
        
        logger.debug(f"片段特征: pitch={self.pitch:.2f}Hz, energy={self.energy:.4f}, duration={self.duration:.2f}s")


class ManualSegmenter:
    """手动分段管理器"""
    
    def __init__(self):
        self.audio = None
        self.sr = None
        self.segments: List[Segment] = []
    
    def load_audio(self, audio_path: str):
        """加载音频"""
        logger.info(f"加载音频: {audio_path}")
        self.audio, self.sr = librosa.load(audio_path, sr=None, mono=True)
        self.segments = []
    
    def add_segment(self, start_time: float, end_time: float, name: str = "") -> Segment:
        """
        添加片段
        
        Args:
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            name: 片段名称
            
        Returns:
            创建的片段
        """
        if self.audio is None:
            raise ValueError("请先加载音频")
        
        # 转换为采样点
        start_sample = int(start_time * self.sr)
        end_sample = int(end_time * self.sr)
        
        # 边界检查
        start_sample = max(0, start_sample)
        end_sample = min(len(self.audio), end_sample)
        
        # 提取音频数据
        segment_audio = self.audio[start_sample:end_sample]
        
        # 创建片段
        segment = Segment(
            start_time=start_time,
            end_time=end_time,
            audio_data=segment_audio,
            sample_rate=self.sr,
            name=name or f"片段{len(self.segments)+1}"
        )
        
        # 提取特征
        segment.extract_features()
        
        self.segments.append(segment)
        logger.info(f"添加片段: {segment.name} ({start_time:.2f}s - {end_time:.2f}s)")
        
        return segment
    
    def remove_segment(self, index: int):
        """删除片段"""
        if 0 <= index < len(self.segments):
            removed = self.segments.pop(index)
            logger.info(f"删除片段: {removed.name}")
    
    def clear_segments(self):
        """清除所有片段"""
        self.segments = []
        logger.info("清除所有片段")
    
    def get_segments(self) -> List[Segment]:
        """获取所有片段"""
        return self.segments
    
    def crop_audio(self, start_time: float, end_time: float):
        """
        裁剪音频
        
        Args:
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        """
        if self.audio is None:
            raise ValueError("请先加载音频")
        
        start_sample = int(start_time * self.sr)
        end_sample = int(end_time * self.sr)
        
        start_sample = max(0, start_sample)
        end_sample = min(len(self.audio), end_sample)
        
        self.audio = self.audio[start_sample:end_sample]
        
        # 清除现有片段（因为时间轴变了）
        self.segments = []
        
        logger.info(f"音频已裁剪: {start_time:.2f}s - {end_time:.2f}s")
