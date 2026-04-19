"""
音高调整模块
"""
import numpy as np
import librosa
import logging

logger = logging.getLogger(__name__)


class PitchShifter:
    """音高调整器"""
    
    def __init__(self):
        pass
    
    def shift_pitch(self, audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
        """
        调整音高（保持时长）
        
        Args:
            audio: 音频数据
            sr: 采样率
            semitones: 半音数（正数升高，负数降低）
            
        Returns:
            调整后的音频
        """
        if abs(semitones) < 0.1:
            return audio
        
        logger.debug(f"调整音高: {semitones:+.2f} 半音")
        
        # 使用 librosa 的音高调整
        shifted = librosa.effects.pitch_shift(
            y=audio,
            sr=sr,
            n_steps=semitones
        )
        
        return shifted
    
    def calculate_shift(self, source_pitch: float, target_pitch: float) -> float:
        """
        计算需要调整的半音数
        
        Args:
            source_pitch: 源音高（Hz）
            target_pitch: 目标音高（Hz）
            
        Returns:
            半音数
        """
        if source_pitch <= 0 or target_pitch <= 0:
            return 0.0
        
        semitones = 12 * np.log2(target_pitch / source_pitch)
        return semitones
    
    def apply_fade(self, audio: np.ndarray, fade_in_samples: int = 100, 
                  fade_out_samples: int = 100) -> np.ndarray:
        """
        应用淡入淡出
        
        Args:
            audio: 音频数据
            fade_in_samples: 淡入采样数
            fade_out_samples: 淡出采样数
            
        Returns:
            处理后的音频
        """
        result = audio.copy()
        
        # 淡入
        if fade_in_samples > 0:
            fade_in = np.linspace(0, 1, fade_in_samples)
            result[:fade_in_samples] *= fade_in
        
        # 淡出
        if fade_out_samples > 0:
            fade_out = np.linspace(1, 0, fade_out_samples)
            result[-fade_out_samples:] *= fade_out
        
        return result
