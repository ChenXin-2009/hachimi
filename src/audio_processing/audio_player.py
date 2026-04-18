"""
音频播放器模块
"""
import numpy as np
import sounddevice as sd
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import logging
from src.models.track import Track
from src.audio_processing.audio_mixer import AudioMixer

logger = logging.getLogger(__name__)


class AudioPlayer(QObject):
    """音频播放器"""
    
    # 信号
    position_updated = pyqtSignal(float)  # 播放位置更新（毫秒）
    playback_finished = pyqtSignal()  # 播放完成
    
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
        
        # 位置更新定时器
        self._position_timer = QTimer()
        self._position_timer.timeout.connect(self._update_position)
        self._position_timer.setInterval(50)  # 每 50ms 更新一次
        
        logger.info("音频播放器初始化")
    
    def load_tracks(self, tracks: List[Track]):
        """
        加载音轨并准备播放
        
        Args:
            tracks: 音轨列表
        """
        logger.info("加载音轨用于播放")
        
        # 混合音轨
        self._mixed_audio = self.mixer.mix_tracks(tracks)
        
        if self._mixed_audio is not None:
            self._sample_rate = tracks[0].sample_rate if tracks else 44100
            self._current_frame = 0
            self._position_ms = 0.0
            logger.info(f"音频加载成功，采样率: {self._sample_rate} Hz")
        else:
            logger.warning("没有可播放的音频")
    
    def play(self):
        """开始播放"""
        if self._mixed_audio is None:
            logger.warning("没有加载音频")
            return
        
        if self._is_playing and not self._is_paused:
            logger.debug("已经在播放中")
            return
        
        logger.info("开始播放")
        self._is_playing = True
        self._is_paused = False
        
        try:
            # 创建音频流
            if self._stream is None or not self._stream.active:
                self._stream = sd.OutputStream(
                    samplerate=self._sample_rate,
                    channels=self._mixed_audio.shape[0],
                    callback=self._audio_callback,
                    finished_callback=self._playback_finished_callback
                )
                self._stream.start()
            
            # 启动位置更新定时器
            self._position_timer.start()
            
        except Exception as e:
            logger.error(f"播放失败: {e}", exc_info=True)
            self._is_playing = False
    
    def pause(self):
        """暂停播放"""
        if not self._is_playing:
            return
        
        logger.info("暂停播放")
        self._is_paused = True
        self._is_playing = False
        
        if self._stream:
            self._stream.stop()
        
        self._position_timer.stop()
    
    def stop(self):
        """停止播放"""
        logger.info("停止播放")
        self._is_playing = False
        self._is_paused = False
        self._current_frame = 0
        self._position_ms = 0.0
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
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
        
        # 计算帧位置
        frame = int(position_ms * self._sample_rate / 1000.0)
        max_frame = self._mixed_audio.shape[1]
        
        self._current_frame = max(0, min(frame, max_frame))
        self._position_ms = self._current_frame * 1000.0 / self._sample_rate
        
        logger.debug(f"跳转到位置: {self._position_ms:.2f} ms")
        self.position_updated.emit(self._position_ms)
    
    def get_position(self) -> float:
        """
        获取当前播放位置
        
        Returns:
            位置（毫秒）
        """
        return self._position_ms
    
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """音频流回调函数"""
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
    
    def _update_position(self):
        """更新播放位置"""
        if self._is_playing:
            self._position_ms = self._current_frame * 1000.0 / self._sample_rate
            self.position_updated.emit(self._position_ms)
    
    def _playback_finished_callback(self):
        """播放完成回调"""
        logger.info("播放完成")
        self._is_playing = False
        self._position_timer.stop()
        self.playback_finished.emit()
