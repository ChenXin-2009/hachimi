"""
音频混合器模块
"""
import numpy as np
from typing import List, Optional, Callable
from pedalboard import Pedalboard, Gain
import soundfile as sf
from pydub import AudioSegment
import logging
from src.models.track import Track
from .audio_effects import FastAudioEffects
from .audio_loader import AudioLoader

logger = logging.getLogger(__name__)


class AudioMixer:
    """音频混合器"""
    
    def __init__(self):
        logger.info("音频混合器初始化")
    
    def apply_track_effects(self, track: Track) -> np.ndarray:
        """
        应用音轨效果（音量、平衡、时间偏移）
        
        Args:
            track: 音轨对象
            
        Returns:
            处理后的音频数据
        """
        if track.audio_data is None:
            return np.array([])
        
        audio = track.audio_data.copy()
        
        # 应用音量调整
        if track.volume_db != 0.0:
            audio = self._apply_volume(audio, track.volume_db, track.sample_rate)
        
        # 应用平衡调整
        if track.pan != 0.0:
            audio = self._apply_pan(audio, track.pan, track.sample_rate)
        
        # 应用时间偏移
        if track.time_offset_ms != 0.0:
            audio = self._apply_time_offset(audio, track.time_offset_ms, track.sample_rate)
        
        return audio
    
    def _apply_volume(self, audio: np.ndarray, volume_db: float, sample_rate: int) -> np.ndarray:
        """
        应用音量调整
        
        Args:
            audio: 音频数据 (channels, samples)
            volume_db: 音量（dB）
            sample_rate: 采样率
            
        Returns:
            处理后的音频
        """
        try:
            # 使用 FastAudioEffects（numba 加速）
            return FastAudioEffects.apply_volume(audio, volume_db)
        except Exception as e:
            logger.error(f"FastAudioEffects 失败，使用备用方案: {e}")
            try:
                # 备用方案 1：使用 pedalboard
                board = Pedalboard([Gain(gain_db=volume_db)])
                audio_transposed = audio.T
                processed = board(audio_transposed, sample_rate)
                return processed.T
            except Exception as e2:
                logger.error(f"Pedalboard 失败，使用手动计算: {e2}")
                # 备用方案 2：手动计算
                gain_linear = 10 ** (volume_db / 20.0)
                return audio * gain_linear
    
    def _apply_pan(self, audio: np.ndarray, pan: float, sample_rate: int) -> np.ndarray:
        """
        应用平衡调整
        
        Args:
            audio: 音频数据 (channels, samples)
            pan: 平衡值 (-1.0 到 1.0)
            sample_rate: 采样率
            
        Returns:
            处理后的音频
        """
        if audio.shape[0] < 2:
            # 单声道，无法应用平衡
            return audio
        
        try:
            # 使用 FastAudioEffects（numba 加速）
            return FastAudioEffects.apply_pan(audio, pan)
        except Exception as e:
            logger.error(f"FastAudioEffects 失败，使用备用方案: {e}")
            # 备用方案：手动实现
            result = audio.copy()
            if pan < 0:  # 偏左
                result[1] *= (1 + pan)  # 减小右声道
            else:  # 偏右
                result[0] *= (1 - pan)  # 减小左声道
            return result
    
    def _apply_time_offset(self, audio: np.ndarray, offset_ms: float, sample_rate: int) -> np.ndarray:
        """
        应用时间偏移
        
        Args:
            audio: 音频数据 (channels, samples)
            offset_ms: 时间偏移（毫秒）
            sample_rate: 采样率
            
        Returns:
            处理后的音频
        """
        offset_samples = int(offset_ms * sample_rate / 1000.0)
        
        if offset_samples == 0:
            return audio
        
        channels, samples = audio.shape
        
        if offset_samples > 0:
            # 正偏移：在前面添加静音
            padding = np.zeros((channels, offset_samples))
            return np.concatenate([padding, audio], axis=1)
        else:
            # 负偏移：裁剪前面的部分
            offset_samples = abs(offset_samples)
            if offset_samples >= samples:
                # 偏移量大于音频长度，返回静音
                return np.zeros((channels, 1))
            return audio[:, offset_samples:]
    
    def mix_tracks(self, tracks: List[Track]) -> Optional[np.ndarray]:
        """
        混合多个音轨（使用缓存优化）
        
        Args:
            tracks: 音轨列表
            
        Returns:
            混合后的音频数据，如果没有启用的音轨则返回 None
        """
        # 过滤出启用的音轨
        enabled_tracks = []
        solo_tracks = []
        
        for track in tracks:
            if track.solo:
                solo_tracks.append(track)
            elif not track.muted:
                enabled_tracks.append(track)
        
        # 如果有独奏音轨，只混合独奏音轨
        if solo_tracks:
            tracks_to_mix = solo_tracks
        else:
            tracks_to_mix = enabled_tracks
        
        if not tracks_to_mix:
            logger.warning("没有启用的音轨")
            return None
        
        logger.info(f"混合 {len(tracks_to_mix)} 个音轨")
        
        # 使用缓存获取处理后的音频
        processed_tracks = []
        max_length = 0
        
        for track in tracks_to_mix:
            # 使用缓存的处理后音频
            processed = track.get_processed_audio(self)
            if processed is not None and processed.size > 0:
                processed_tracks.append(processed)
                max_length = max(max_length, processed.shape[1])
        
        if not processed_tracks:
            return None
        
        # 确保所有音轨长度一致（填充静音）
        aligned_tracks = []
        for audio in processed_tracks:
            if audio.shape[1] < max_length:
                padding = np.zeros((audio.shape[0], max_length - audio.shape[1]))
                audio = np.concatenate([audio, padding], axis=1)
            aligned_tracks.append(audio)
        
        # 混合音轨（简单相加）
        mixed = np.sum(aligned_tracks, axis=0)
        
        # 归一化防止削波
        max_val = np.abs(mixed).max()
        if max_val > 1.0:
            mixed = mixed / max_val
            logger.info(f"音频归一化: {max_val:.2f} -> 1.0")
        
        return mixed
    
    def export(
        self,
        tracks: List[Track],
        output_path: str,
        format: str = "wav",
        quality: str = "high",
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """
        导出混合音频
        
        Args:
            tracks: 音轨列表
            output_path: 输出文件路径
            format: 格式（wav, flac, mp3）
            quality: 质量（low, medium, high）
            progress_callback: 进度回调
            
        Returns:
            是否成功
        """
        try:
            logger.info(f"导出音频: {output_path}, 格式: {format}")
            
            if progress_callback:
                progress_callback(10.0)
            
            # 混合音轨
            mixed = self.mix_tracks(tracks)
            if mixed is None:
                logger.error("没有可导出的音频")
                return False
            
            if progress_callback:
                progress_callback(50.0)
            
            # 获取采样率
            sample_rate = tracks[0].sample_rate if tracks else 44100
            
            # 转换为 (samples, channels) 格式
            audio_to_export = mixed.T
            
            # 使用 AudioLoader 统一保存（支持更多格式）
            try:
                AudioLoader.save(output_path, mixed, sample_rate, format=format)
            except Exception as e:
                logger.warning(f"AudioLoader 保存失败，使用备用方案: {e}")
                # 备用方案：使用原始方法
                if format.lower() in ["wav", "flac"]:
                    subtype = "PCM_24" if quality == "high" else "PCM_16"
                    sf.write(output_path, audio_to_export, sample_rate, subtype=subtype)
                elif format.lower() == "mp3":
                    import tempfile
                    import os
                    
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    sf.write(tmp_path, audio_to_export, sample_rate)
                    audio_segment = AudioSegment.from_wav(tmp_path)
                    
                    bitrate_map = {
                        "low": "128k",
                        "medium": "192k",
                        "high": "320k"
                    }
                    bitrate = bitrate_map.get(quality, "192k")
                    audio_segment.export(output_path, format="mp3", bitrate=bitrate)
                    os.unlink(tmp_path)
                else:
                    logger.error(f"不支持的格式: {format}")
                    return False
            
            if progress_callback:
                progress_callback(100.0)
            
            logger.info("音频导出成功")
            return True
            
        except Exception as e:
            logger.error(f"导出音频失败: {e}", exc_info=True)
            return False
