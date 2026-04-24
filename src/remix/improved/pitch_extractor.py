"""
音高提取器模块

提供精确的音高轮廓提取功能，使用 librosa.pyin 算法。
支持音高到 MIDI 转换和音符起始点检测。

需求: 1.1, 1.4, 1.5
"""

import numpy as np
import librosa
from typing import Tuple


class PitchExtractor:
    """
    音高提取器
    
    从音频中提取精确的音高序列和音高轮廓。
    使用 librosa.pyin 算法，时间分辨率达到 10ms。
    """
    
    def __init__(self, 
                 fmin: float = 80.0,
                 fmax: float = 400.0,
                 frame_length: int = 2048,
                 hop_length: int = 512):
        """
        初始化音高提取器
        
        Args:
            fmin: 最小音高频率（Hz），默认 80Hz（适合人声）
            fmax: 最大音高频率（Hz），默认 400Hz（适合人声）
            frame_length: 帧长度（采样点），默认 2048
            hop_length: 跳跃长度（采样点），默认 512（约 10ms @ 22050Hz）
        """
        self.fmin = fmin
        self.fmax = fmax
        self.frame_length = frame_length
        self.hop_length = hop_length
    
    def extract_pitch_contour(self, 
                             audio: np.ndarray, 
                             sr: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        提取音高轮廓
        
        使用 librosa.pyin 算法提取音高轮廓，并过滤低置信度的结果。
        
        Args:
            audio: 音频数据（单声道）
            sr: 采样率
            
        Returns:
            (pitch_contour, confidence): 
                - pitch_contour: 音高轮廓数组（Hz），低置信度位置为 0
                - confidence: 置信度数组（0-1）
        """
        # 使用 pyin 算法提取音高
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio,
            fmin=self.fmin,
            fmax=self.fmax,
            sr=sr,
            frame_length=self.frame_length,
            hop_length=self.hop_length
        )
        
        # 过滤置信度低于 0.5 的音高
        pitch_contour = np.copy(f0)
        pitch_contour[voiced_probs < 0.5] = 0
        
        # 将 NaN 替换为 0
        pitch_contour = np.nan_to_num(pitch_contour, nan=0.0)
        confidence = np.nan_to_num(voiced_probs, nan=0.0)
        
        return pitch_contour, confidence
    
    def pitch_to_midi(self, pitch_hz: float) -> int:
        """
        将音高（Hz）转换为 MIDI 音符编号
        
        使用标准公式: MIDI = 69 + 12 * log2(f / 440)
        
        Args:
            pitch_hz: 音高频率（Hz）
            
        Returns:
            MIDI 音符编号（0-127），如果音高无效则返回 0
        """
        if pitch_hz <= 0:
            return 0
        
        # 计算 MIDI 音符编号
        midi_note = 69 + 12 * np.log2(pitch_hz / 440.0)
        
        # 限制在有效范围内
        midi_note = int(np.clip(np.round(midi_note), 0, 127))
        
        return midi_note
    
    def detect_onsets(self, 
                     audio: np.ndarray, 
                     sr: int) -> np.ndarray:
        """
        检测音符起始点
        
        使用 librosa.onset.onset_detect 检测音频中的起始点。
        
        Args:
            audio: 音频数据（单声道）
            sr: 采样率
            
        Returns:
            起始点时间数组（秒）
        """
        # 检测起始点（返回帧索引）
        onset_frames = librosa.onset.onset_detect(
            y=audio,
            sr=sr,
            hop_length=self.hop_length,
            backtrack=True
        )
        
        # 转换为时间（秒）
        onset_times = librosa.frames_to_time(
            onset_frames,
            sr=sr,
            hop_length=self.hop_length
        )
        
        return onset_times
