"""
音频加载器 - 使用 pydub 简化音频加载
"""
from pydub import AudioSegment
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioLoader:
    """音频加载器 - 支持更多格式"""
    
    @staticmethod
    def load(file_path: str, target_sr: int = None) -> tuple:
        """
        加载音频文件
        
        Args:
            file_path: 音频文件路径
            target_sr: 目标采样率（如果指定，会重采样）
            
        Returns:
            (audio_data, sample_rate) - 音频数据 (channels, samples) 和采样率
        """
        try:
            logger.info(f"加载音频: {file_path}")
            
            # 使用 pydub 加载（支持更多格式）
            audio = AudioSegment.from_file(file_path)
            
            # 转换为 numpy 数组
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # 归一化到 -1.0 到 1.0
            samples = samples / (2 ** (8 * audio.sample_width - 1))
            
            # 处理声道
            if audio.channels == 2:
                # 立体声：重塑为 (2, samples)
                samples = samples.reshape((-1, 2)).T
            else:
                # 单声道：重塑为 (1, samples)
                samples = samples.reshape((1, -1))
            
            sample_rate = audio.frame_rate
            
            # 重采样（如果需要）
            if target_sr and target_sr != sample_rate:
                logger.info(f"重采样: {sample_rate}Hz -> {target_sr}Hz")
                samples = AudioLoader._resample(samples, sample_rate, target_sr)
                sample_rate = target_sr
            
            logger.info(f"加载成功: {samples.shape}, {sample_rate}Hz")
            return samples, sample_rate
            
        except Exception as e:
            logger.error(f"加载音频失败: {e}", exc_info=True)
            raise
    
    @staticmethod
    def _resample(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        重采样音频
        
        Args:
            audio_data: 音频数据 (channels, samples)
            orig_sr: 原始采样率
            target_sr: 目标采样率
            
        Returns:
            重采样后的音频数据
        """
        import librosa
        
        resampled = []
        for channel in audio_data:
            resampled_channel = librosa.resample(
                channel,
                orig_sr=orig_sr,
                target_sr=target_sr
            )
            resampled.append(resampled_channel)
        
        return np.array(resampled)
    
    @staticmethod
    def save(file_path: str, audio_data: np.ndarray, sample_rate: int, format: str = None):
        """
        保存音频文件
        
        Args:
            file_path: 输出文件路径
            audio_data: 音频数据 (channels, samples)
            sample_rate: 采样率
            format: 输出格式（如果不指定，从文件扩展名推断）
        """
        try:
            logger.info(f"保存音频: {file_path}")
            
            # 转换为 int16
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # 转换为 pydub 格式
            if audio_data.shape[0] == 2:
                # 立体声
                audio_int16 = audio_int16.T.flatten()
                channels = 2
            else:
                # 单声道
                audio_int16 = audio_int16.flatten()
                channels = 1
            
            # 创建 AudioSegment
            audio = AudioSegment(
                audio_int16.tobytes(),
                frame_rate=sample_rate,
                sample_width=2,  # 16-bit
                channels=channels
            )
            
            # 推断格式
            if format is None:
                format = Path(file_path).suffix[1:]  # 去掉点号
            
            # 导出
            audio.export(file_path, format=format)
            
            logger.info(f"保存成功: {file_path}")
            
        except Exception as e:
            logger.error(f"保存音频失败: {e}", exc_info=True)
            raise
    
    @staticmethod
    def get_duration(file_path: str) -> float:
        """
        获取音频时长（秒）
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            时长（秒）
        """
        try:
            audio = AudioSegment.from_file(file_path)
            return len(audio) / 1000.0  # 转换为秒
        except Exception as e:
            logger.error(f"获取时长失败: {e}")
            return 0.0
    
    @staticmethod
    def get_info(file_path: str) -> dict:
        """
        获取音频文件信息
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            包含音频信息的字典
        """
        try:
            audio = AudioSegment.from_file(file_path)
            return {
                'duration': len(audio) / 1000.0,
                'sample_rate': audio.frame_rate,
                'channels': audio.channels,
                'sample_width': audio.sample_width,
                'frame_count': audio.frame_count(),
                'format': Path(file_path).suffix[1:]
            }
        except Exception as e:
            logger.error(f"获取信息失败: {e}")
            return {}
