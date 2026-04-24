"""
音频播放器模块
"""
import numpy as np
import sounddevice as sd
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRunnable, QThreadPool, pyqtSlot
import logging
from src.models.track import Track
from src.audio_processing.audio_mixer import AudioMixer

logger = logging.getLogger(__name__)


class MixAudioTask(QRunnable):
    """异步音频混合任务"""
    
    def __init__(self, mixer: AudioMixer, tracks: List[Track], callback):
        super().__init__()
        self.mixer = mixer
        self.tracks = tracks
        self.callback = callback
        self.setAutoDelete(True)
    
    def run(self):
        """在后台线程执行混音"""
        try:
            logger.debug("开始异步混音")
            mixed_audio = self.mixer.mix_tracks(self.tracks)
            self.callback(mixed_audio)
            logger.debug("异步混音完成")
        except Exception as e:
            logger.error(f"异步混音失败: {e}", exc_info=True)
            self.callback(None)


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
        self._tracks: List[Track] = []  # 保存音轨引用
        
        # 位置更新定时器
        self._position_timer = QTimer()
        self._position_timer.timeout.connect(self._update_position)
        self._position_timer.setInterval(50)  # 每 50ms 更新一次
        
        # 性能优化：异步混音
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(1)  # 限制为单线程，避免并发
        self._is_mixing = False  # 是否正在混音
        self._needs_remix = False  # 是否需要重新混音
        
        # 性能优化：混音防抖定时器
        self._remix_timer = QTimer()
        self._remix_timer.setSingleShot(True)
        self._remix_timer.timeout.connect(self._do_reload_mix)
        self._remix_debounce_ms = 300  # 增加到 300ms 防抖延迟
        
        # 性能优化：混音频率限制
        self._last_mix_time = 0  # 上次混音时间
        self._min_mix_interval_ms = 500  # 最小混音间隔 500ms
        
        logger.info("音频播放器初始化")
    
    def load_tracks(self, tracks: List[Track]):
        """
        加载音轨并准备播放
        
        Args:
            tracks: 音轨列表
        """
        logger.info("加载音轨用于播放")
        
        # 保存音轨引用
        self._tracks = tracks
        
        # 混合音轨
        self._mixed_audio = self.mixer.mix_tracks(tracks)
        
        if self._mixed_audio is not None:
            self._sample_rate = tracks[0].sample_rate if tracks else 44100
            self._current_frame = 0
            self._position_ms = 0.0
            logger.info(f"音频加载成功，采样率: {self._sample_rate} Hz")
        else:
            logger.warning("没有可播放的音频")
    
    def reload_mix(self):
        """重新混合音轨（带防抖、节流和智能策略）"""
        if not self._tracks:
            return
        
        # 检查是否正在混音
        if self._is_mixing:
            logger.debug("正在混音中，标记需要重新混音")
            self._needs_remix = True
            return
        
        if self._is_playing:
            # 播放中：使用更激进的策略
            # 1. 如果定时器已激活，不做任何事（等待当前定时器完成）
            if self._remix_timer.isActive():
                logger.debug("混音定时器已激活，跳过本次请求")
                return
            
            # 2. 启动定时器
            self._remix_timer.start(self._remix_debounce_ms)
        else:
            # 暂停中：标记需要混音，播放时再执行
            self._needs_remix = True
            logger.debug("标记需要重新混音（延迟到播放时）")
    
    def _do_reload_mix(self):
        """实际执行重新混音（带保护和频率限制）"""
        if self._is_mixing:
            # 正在混音中，稍后重试
            logger.debug("正在混音中，延迟 100ms 重试")
            self._remix_timer.start(100)
            return
        
        # 检查混音频率限制
        import time
        current_time = time.time() * 1000  # 转换为毫秒
        elapsed = current_time - self._last_mix_time
        
        if elapsed < self._min_mix_interval_ms:
            # 距离上次混音时间太短，延迟执行
            delay = int(self._min_mix_interval_ms - elapsed)
            logger.debug(f"混音频率限制，延迟 {delay}ms")
            self._remix_timer.start(delay)
            return
        
        try:
            logger.debug("开始重新混音")
            self._last_mix_time = current_time
            self._reload_mix_async()
        except Exception as e:
            logger.error(f"启动异步混音失败: {e}", exc_info=True)
            self._is_mixing = False
            self._needs_remix = True  # 标记需要重试
    
    def _reload_mix_async(self):
        """异步重新混音（带保护）"""
        if not self._tracks:
            return
        
        try:
            self._is_mixing = True
            
            # 保存当前位置
            current_position = self._current_frame
            
            # 创建异步任务
            task = MixAudioTask(self.mixer, self._tracks, self._on_mix_complete)
            self._thread_pool.start(task)
            
            # 保存位置以便恢复
            self._saved_position = current_position
        except Exception as e:
            logger.error(f"创建异步混音任务失败: {e}", exc_info=True)
            self._is_mixing = False
    
    @pyqtSlot(object)
    def _on_mix_complete(self, mixed_audio):
        """混音完成回调（带保护）"""
        try:
            self._is_mixing = False
            
            if mixed_audio is not None:
                self._mixed_audio = mixed_audio
                
                # 恢复播放位置
                if hasattr(self, '_saved_position'):
                    self._current_frame = min(self._saved_position, self._mixed_audio.shape[1])
                
                logger.debug("混音更新完成")
                
                # 如果在混音期间又有新的请求，重新混音
                if self._needs_remix:
                    self._needs_remix = False
                    logger.debug("检测到待处理的混音请求，重新混音")
                    self._remix_timer.start(100)
            else:
                logger.warning("混音失败，返回 None")
        except Exception as e:
            logger.error(f"混音完成回调出错: {e}", exc_info=True)
            self._is_mixing = False
    
    def play(self):
        """开始播放"""
        if self._mixed_audio is None:
            logger.warning("没有加载音频")
            return
        
        if self._is_playing and not self._is_paused:
            logger.debug("已经在播放中")
            return
        
        # 如果需要重新混音，先执行混音
        if self._needs_remix:
            logger.info("播放前重新混音")
            self._reload_mix_async()
            self._needs_remix = False
            # 等待混音完成后再播放
            QTimer.singleShot(200, self._start_playback)
            return
        
        self._start_playback()
    
    def _start_playback(self):
        """实际开始播放"""
        if self._mixed_audio is None:
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
