"""
音频播放器模块 - 修复版本

修复内容：
1. 修复内存泄漏问题
2. 优化音频流管理
3. 添加异常处理防止崩溃
4. 限制内存使用
"""
import numpy as np
import sounddevice as sd
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import logging
import gc
from src.models.track import Track
from src.audio_processing.audio_mixer import AudioMixer

logger = logging.getLogger(__name__)


class AudioPlayer(QObject):
    """音频播放器 - 修复版本"""
    
    # 信号
    position_updated = pyqtSignal(float)  # 播放位置更新（毫秒）
    playback_finished = pyqtSignal()  # 播放完成
    
    # 常量
    MAX_AUDIO_LENGTH_SECONDS = 600  # 最大音频长度（10分钟）
    BUFFER_SIZE = 2048  # 音频缓冲区大小
    
    def __init__(self, mixer: AudioMixer):
        super().__init__()
        self.mixer = mixer
        self._is_playing = False
        self._is_paused = False
        self._position_ms = 0.0
        self._mixed_audio: Optional[np.ndarray] = None
        self._sample_rate = 44100
        self._stream: Optional[sd.OutputStream] = None
        self._current_frame = 0
        self._tracks: List[Track] = []
        
        # 位置更新定时器
        self._position_timer = QTimer()
        self._position_timer.timeout.connect(self._update_position)
        self._position_timer.setInterval(50)
        
        # 添加锁防止并发问题
        self._stream_lock = False
        
        logger.info("音频播放器初始化（修复版本）")
    
    def load_tracks(self, tracks: List[Track]):
        """
        加载音轨并准备播放
        
        Args:
            tracks: 音轨列表
        """
        logger.info(f"加载 {len(tracks)} 个音轨用于播放")
        
        try:
            # 清理旧的音频数据
            self._cleanup_audio()
            
            # 保存音轨引用
            self._tracks = tracks
            
            # 混合音轨
            self._mixed_audio = self.mixer.mix_tracks(tracks)
            
            if self._mixed_audio is not None:
                # 检查音频长度
                duration_seconds = self._mixed_audio.shape[1] / self._sample_rate
                if duration_seconds > self.MAX_AUDIO_LENGTH_SECONDS:
                    logger.warning(f"音频过长 ({duration_seconds:.1f}s)，可能导致内存问题")
                
                self._sample_rate = tracks[0].sample_rate if tracks else 44100
                self._current_frame = 0
                self._position_ms = 0.0
                
                # 记录内存使用
                audio_size_mb = self._mixed_audio.nbytes / (1024 * 1024)
                logger.info(f"音频加载成功，采样率: {self._sample_rate} Hz, 大小: {audio_size_mb:.2f} MB")
            else:
                logger.warning("没有可播放的音频")
                
        except Exception as e:
            logger.error(f"加载音轨失败: {e}", exc_info=True)
            self._cleanup_audio()
    
    def reload_mix(self):
        """重新混合音轨（用于实时更新音轨参数）"""
        if not self._tracks:
            return
        
        try:
            # 保存当前位置
            current_position = self._current_frame
            
            # 清理旧的混合音频
            old_audio = self._mixed_audio
            
            # 重新混合
            self._mixed_audio = self.mixer.mix_tracks(self._tracks)
            
            # 恢复位置
            if self._mixed_audio is not None:
                max_frame = self._mixed_audio.shape[1]
                self._current_frame = min(current_position, max_frame)
            
            # 显式删除旧音频并触发垃圾回收
            if old_audio is not None:
                del old_audio
                gc.collect()
            
            logger.debug("实时重新混合音轨完成")
            
        except Exception as e:
            logger.error(f"重新混合失败: {e}", exc_info=True)
    
    def play(self):
        """开始播放"""
        if self._mixed_audio is None:
            logger.warning("没有加载音频")
            return
        
        if self._is_playing and not self._is_paused:
            logger.debug("已经在播放中")
            return
        
        if self._stream_lock:
            logger.warning("音频流正在操作中，请稍后")
            return
        
        logger.info("开始播放")
        self._is_playing = True
        self._is_paused = False
        
        try:
            self._stream_lock = True
            
            # 关闭旧的音频流
            if self._stream is not None:
                try:
                    if self._stream.active:
                        self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning(f"关闭旧音频流时出错: {e}")
                finally:
                    self._stream = None
            
            # 创建新的音频流
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._mixed_audio.shape[0],
                blocksize=self.BUFFER_SIZE,
                callback=self._audio_callback,
                finished_callback=self._playback_finished_callback
            )
            self._stream.start()
            
            # 启动位置更新定时器
            self._position_timer.start()
            
        except Exception as e:
            logger.error(f"播放失败: {e}", exc_info=True)
            self._is_playing = False
            self._cleanup_stream()
        finally:
            self._stream_lock = False
    
    def pause(self):
        """暂停播放"""
        if not self._is_playing:
            return
        
        logger.info("暂停播放")
        self._is_paused = True
        self._is_playing = False
        
        try:
            if self._stream and self._stream.active:
                self._stream.stop()
        except Exception as e:
            logger.error(f"暂停失败: {e}", exc_info=True)
        
        self._position_timer.stop()
    
    def stop(self):
        """停止播放"""
        logger.info("停止播放")
        self._is_playing = False
        self._is_paused = False
        self._current_frame = 0
        self._position_ms = 0.0
        
        self._cleanup_stream()
        self._position_timer.stop()
        self.position_updated.emit(0.0)
    
    def seek(self, position_ms: float):
        """
        跳转到指定位置
        
        Args:
            position_ms: 位置（毫秒）
        """
        if self._mixed_audio is None:
            return
        
        try:
            # 计算帧位置
            frame = int(position_ms * self._sample_rate / 1000.0)
            max_frame = self._mixed_audio.shape[1]
            
            self._current_frame = max(0, min(frame, max_frame))
            self._position_ms = self._current_frame * 1000.0 / self._sample_rate
            
            logger.debug(f"跳转到位置: {self._position_ms:.2f} ms")
            self.position_updated.emit(self._position_ms)
            
        except Exception as e:
            logger.error(f"跳转失败: {e}", exc_info=True)
    
    def get_position(self) -> float:
        """获取当前播放位置（毫秒）"""
        return self._position_ms
    
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """
        音频流回调函数
        
        添加异常处理防止崩溃
        """
        try:
            if status:
                logger.warning(f"音频流状态: {status}")
            
            if self._mixed_audio is None or not self._is_playing:
                outdata.fill(0)
                return
            
            # 获取当前帧的音频数据
            start_frame = self._current_frame
            end_frame = start_frame + frames
            
            if start_frame >= self._mixed_audio.shape[1]:
                # 播放完成
                outdata.fill(0)
                self._is_playing = False
                return
            
            # 提取音频片段
            audio_chunk = self._mixed_audio[:, start_frame:end_frame]
            
            # 转换为 (frames, channels) 格式
            audio_chunk = audio_chunk.T
            
            # 如果不足 frames，填充静音
            if audio_chunk.shape[0] < frames:
                padding = np.zeros((frames - audio_chunk.shape[0], audio_chunk.shape[1]))
                audio_chunk = np.vstack([audio_chunk, padding])
            
            outdata[:] = audio_chunk
            self._current_frame = end_frame
            
        except Exception as e:
            # 捕获所有异常，防止崩溃
            logger.error(f"音频回调异常: {e}", exc_info=True)
            outdata.fill(0)
            self._is_playing = False
    
    def _update_position(self):
        """更新播放位置"""
        try:
            if self._is_playing and self._mixed_audio is not None:
                self._position_ms = self._current_frame * 1000.0 / self._sample_rate
                self.position_updated.emit(self._position_ms)
        except Exception as e:
            logger.error(f"更新位置失败: {e}", exc_info=True)
    
    def _playback_finished_callback(self):
        """播放完成回调"""
        try:
            logger.info("播放完成")
            self._is_playing = False
            self._position_timer.stop()
            self.playback_finished.emit()
        except Exception as e:
            logger.error(f"播放完成回调异常: {e}", exc_info=True)
    
    def _cleanup_stream(self):
        """清理音频流"""
        if self._stream_lock:
            return
        
        try:
            self._stream_lock = True
            
            if self._stream is not None:
                try:
                    if self._stream.active:
                        self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning(f"清理音频流时出错: {e}")
                finally:
                    self._stream = None
                    
        except Exception as e:
            logger.error(f"清理音频流失败: {e}", exc_info=True)
        finally:
            self._stream_lock = False
    
    def _cleanup_audio(self):
        """清理音频数据"""
        try:
            # 停止播放
            if self._is_playing:
                self.stop()
            
            # 清理音频数据
            if self._mixed_audio is not None:
                del self._mixed_audio
                self._mixed_audio = None
            
            # 触发垃圾回收
            gc.collect()
            
            logger.debug("音频数据已清理")
            
        except Exception as e:
            logger.error(f"清理音频数据失败: {e}", exc_info=True)
    
    def __del__(self):
        """析构函数 - 确保资源被释放"""
        try:
            self._cleanup_stream()
            self._cleanup_audio()
        except:
            pass
