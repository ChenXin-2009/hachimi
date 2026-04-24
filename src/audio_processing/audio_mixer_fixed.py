"""
音频混合器模块 - 修复版本

修复内容：
1. 限制同时处理的音轨数量
2. 优化内存使用
3. 添加内存监控
4. 流式处理大文件
"""
import numpy as np
from typing import List, Optional, Callable
from pedalboard import Pedalboard, Gain
import soundfile as sf
from pydub import AudioSegment
import logging
import psutil
import gc
from src.models.track import Track

logger = logging.getLogger(__name__)


class AudioMixer:
    """音频混合器 - 修复版本"""
    
    # 常量
    MAX_CONCURRENT_TRACKS = 16  # 最大同时处理音轨数
    MAX_MEMORY_MB = 1024  # 最大内存使用（MB）
    CHUNK_SIZE = 44100 * 10  # 分块处理大小（10秒）
    
    def __init__(self):
        self._memory_warning_shown = False
        logger.info("音频混合器初始化（修复版本）")
    
    def _check_memory(self) -> bool:
        """
        检查内存使用情况
        
        Returns:
            是否有足够内存
        """
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            if memory_mb > self.MAX_MEMORY_MB:
                if not self._memory_warning_shown:
                    logger.warning(f"内存使用过高: {memory_mb:.1f} MB")
                    self._memory_warning_shown = True
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查内存失败: {e}")
            return True  # 如果无法检查，假设有足够内存
    
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
        
        try:
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
            
        except Exception as e:
            logger.error(f"应用音轨效果失败: {e}", exc_info=True)
            return track.audio_data.copy() if track.audio_data is not None else np.array([])
    
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
            # 使用 pedalboard 的 Gain 效果
            board = Pedalboard([Gain(gain_db=volume_db)])
            
            # pedalboard 需要 (samples, channels) 格式
            audio_transposed = audio.T
            processed = board(audio_transposed, sample_rate)
            
            return processed.T
        except Exception as e:
            logger.error(f"应用音量失败: {e}")
            # 降级方案：手动计算
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
        
        # 手动实现平衡调整
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
        混合多个音轨（优化版本）
        
        Args:
            tracks: 音轨列表
            
        Returns:
            混合后的音频数据，如果没有启用的音轨则返回 None
        """
        try:
            # 检查内存
            if not self._check_memory():
                logger.warning("内存不足，尝试清理")
                gc.collect()
            
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
            
            # 限制同时处理的音轨数量
            if len(tracks_to_mix) > self.MAX_CONCURRENT_TRACKS:
                logger.warning(f"音轨数量过多 ({len(tracks_to_mix)})，限制为 {self.MAX_CONCURRENT_TRACKS}")
                tracks_to_mix = tracks_to_mix[:self.MAX_CONCURRENT_TRACKS]
            
            logger.info(f"混合 {len(tracks_to_mix)} 个音轨")
            
            # 应用效果并收集处理后的音频
            processed_tracks = []
            max_length = 0
            
            for i, track in enumerate(tracks_to_mix):
                try:
                    processed = self.apply_track_effects(track)
                    if processed.size > 0:
                        processed_tracks.append(processed)
                        max_length = max(max_length, processed.shape[1])
                    
                    # 定期检查内存
                    if i % 4 == 0 and not self._check_memory():
                        logger.warning("内存不足，停止处理更多音轨")
                        break
                        
                except Exception as e:
                    logger.error(f"处理音轨 {i} 失败: {e}", exc_info=True)
                    continue
            
            if not processed_tracks:
                return None
            
            # 使用分块处理来减少内存峰值
            if max_length > self.CHUNK_SIZE:
                logger.info(f"使用分块处理（音频长度: {max_length} 采样点）")
                return self._mix_tracks_chunked(processed_tracks, max_length)
            else:
                return self._mix_tracks_direct(processed_tracks, max_length)
                
        except Exception as e:
            logger.error(f"混合音轨失败: {e}", exc_info=True)
            return None
    
    def _mix_tracks_direct(self, processed_tracks: List[np.ndarray], max_length: int) -> np.ndarray:
        """
        直接混合音轨（适用于短音频）
        
        Args:
            processed_tracks: 处理后的音轨列表
            max_length: 最大长度
            
        Returns:
            混合后的音频
        """
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
    
    def _mix_tracks_chunked(self, processed_tracks: List[np.ndarray], max_length: int) -> np.ndarray:
        """
        分块混合音轨（适用于长音频）
        
        Args:
            processed_tracks: 处理后的音轨列表
            max_length: 最大长度
            
        Returns:
            混合后的音频
        """
        channels = processed_tracks[0].shape[0]
        mixed = np.zeros((channels, max_length), dtype=np.float32)
        
        # 分块处理
        num_chunks = (max_length + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
        
        for chunk_idx in range(num_chunks):
            start = chunk_idx * self.CHUNK_SIZE
            end = min(start + self.CHUNK_SIZE, max_length)
            chunk_length = end - start
            
            # 混合当前块
            chunk_sum = np.zeros((channels, chunk_length), dtype=np.float32)
            
            for audio in processed_tracks:
                if audio.shape[1] > start:
                    chunk_end = min(audio.shape[1], end)
                    chunk_data = audio[:, start:chunk_end]
                    
                    # 如果块不够长，填充零
                    if chunk_data.shape[1] < chunk_length:
                        padding = np.zeros((channels, chunk_length - chunk_data.shape[1]))
                        chunk_data = np.concatenate([chunk_data, padding], axis=1)
                    
                    chunk_sum += chunk_data
            
            # 归一化当前块
            max_val = np.abs(chunk_sum).max()
            if max_val > 1.0:
                chunk_sum = chunk_sum / max_val
            
            mixed[:, start:end] = chunk_sum
            
            # 定期触发垃圾回收
            if chunk_idx % 10 == 0:
                gc.collect()
        
        logger.info(f"分块混合完成，共 {num_chunks} 块")
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
            
            if format.lower() in ["wav", "flac"]:
                # 使用 soundfile 导出 WAV/FLAC
                subtype = "PCM_24" if quality == "high" else "PCM_16"
                sf.write(output_path, audio_to_export, sample_rate, subtype=subtype)
                
            elif format.lower() == "mp3":
                # 使用 pydub 导出 MP3
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                
                sf.write(tmp_path, audio_to_export, sample_rate)
                
                # 转换为 MP3
                audio_segment = AudioSegment.from_wav(tmp_path)
                
                bitrate_map = {
                    "low": "128k",
                    "medium": "192k",
                    "high": "320k"
                }
                bitrate = bitrate_map.get(quality, "192k")
                
                audio_segment.export(output_path, format="mp3", bitrate=bitrate)
                
                # 删除临时文件
                os.unlink(tmp_path)
            
            else:
                logger.error(f"不支持的格式: {format}")
                return False
            
            if progress_callback:
                progress_callback(100.0)
            
            logger.info("音频导出成功")
            
            # 清理内存
            del mixed
            del audio_to_export
            gc.collect()
            
            return True
            
        except Exception as e:
            logger.error(f"导出音频失败: {e}", exc_info=True)
            return False
