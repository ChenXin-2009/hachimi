"""
音轨管理器模块
"""
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import numpy as np
import soundfile as sf
import librosa
import logging
from .track import Track

logger = logging.getLogger(__name__)


class Command:
    """命令基类（用于撤销/重做）"""
    
    def execute(self):
        """执行命令"""
        raise NotImplementedError
    
    def undo(self):
        """撤销命令"""
        raise NotImplementedError


class UpdateTrackParamCommand(Command):
    """更新音轨参数命令"""
    
    def __init__(self, track: Track, param: str, new_value: Any):
        self.track = track
        self.param = param
        self.old_value = getattr(track, param)
        self.new_value = new_value
    
    def execute(self):
        setattr(self.track, self.param, self.new_value)
    
    def undo(self):
        setattr(self.track, self.param, self.old_value)


class TrackManager(QObject):
    """音轨管理器"""
    
    # 信号
    tracks_updated = pyqtSignal()  # 音轨列表更新
    track_param_changed = pyqtSignal(str, str, object)  # (track_id, param, value)
    
    def __init__(self):
        super().__init__()
        self._tracks: Dict[str, Track] = {}
        self._track_order: List[str] = []  # 保持音轨顺序
        
        # 撤销/重做历史
        self._history: List[Command] = []
        self._history_index = -1
        self._max_history = 50
        
        # 性能优化：防抖定时器
        self._param_change_timer = QTimer()
        self._param_change_timer.setSingleShot(True)
        self._param_change_timer.timeout.connect(self._emit_batch_changes)
        self._debounce_delay_ms = 200  # 增加到 200ms 防抖延迟
        self._pending_changes: Dict[str, tuple] = {}  # {change_key: (track_id, param, value)}
        
        logger.info("音轨管理器初始化")
    
    def add_separated_tracks(self, stems: Dict[str, np.ndarray], sample_rate: int):
        """
        添加分离后的音轨
        
        Args:
            stems: 字典，键为音轨类型，值为音频数据
            sample_rate: 采样率
        """
        logger.info(f"添加 {len(stems)} 个分离音轨")
        
        for source_type, audio_data in stems.items():
            track = Track(
                name=source_type.capitalize(),
                audio_data=audio_data,
                sample_rate=sample_rate,
                track_type="separated",
                source_type=source_type
            )
            
            self._tracks[track.id] = track
            self._track_order.append(track.id)
            logger.info(f"添加音轨: {track.name} (ID: {track.id})")
        
        self.tracks_updated.emit()
    
    def add_replacement_track(self, track_id: str, audio_path: str) -> bool:
        """
        替换指定音轨
        
        Args:
            track_id: 要替换的音轨 ID
            audio_path: 替换音频文件路径
            
        Returns:
            是否成功
        """
        if track_id not in self._tracks:
            logger.error(f"音轨不存在: {track_id}")
            return False
        
        try:
            logger.info(f"加载替换音频: {audio_path}")
            
            # 加载音频文件
            audio_data, sr = sf.read(audio_path, always_2d=True)
            audio_data = audio_data.T  # 转换为 (channels, samples)
            
            # 获取目标音轨
            target_track = self._tracks[track_id]
            
            # 重采样到匹配的采样率
            if sr != target_track.sample_rate:
                logger.info(f"重采样: {sr} Hz -> {target_track.sample_rate} Hz")
                audio_data_resampled = []
                for channel in audio_data:
                    resampled = librosa.resample(
                        channel,
                        orig_sr=sr,
                        target_sr=target_track.sample_rate
                    )
                    audio_data_resampled.append(resampled)
                audio_data = np.array(audio_data_resampled)
            
            # 更新音轨
            target_track.audio_data = audio_data
            target_track.track_type = "replacement"
            
            logger.info(f"音轨替换成功: {track_id}")
            self.tracks_updated.emit()
            return True
            
        except Exception as e:
            logger.error(f"替换音轨失败: {e}", exc_info=True)
            return False
    
    def update_track_param(self, track_id: str, param: str, value: Any, immediate: bool = False):
        """
        更新音轨参数（带防抖优化）
        
        Args:
            track_id: 音轨 ID
            param: 参数名称
            value: 新值
            immediate: 是否立即更新（跳过防抖）
        """
        if track_id not in self._tracks:
            logger.error(f"音轨不存在: {track_id}")
            return
        
        track = self._tracks[track_id]
        
        # 创建并执行命令
        command = UpdateTrackParamCommand(track, param, value)
        command.execute()
        
        # 添加到历史记录
        self._add_to_history(command)
        
        logger.debug(f"更新音轨参数: {track_id}.{param} = {value}")
        
        if immediate:
            # 立即发送信号
            self.track_param_changed.emit(track_id, param, value)
        else:
            # 使用防抖：收集变化，延迟发送
            # 为每个音轨+参数组合创建唯一键
            change_key = f"{track_id}:{param}"
            self._pending_changes[change_key] = (track_id, param, value)
            
            # 重启定时器
            if self._param_change_timer.isActive():
                self._param_change_timer.stop()
            self._param_change_timer.start(self._debounce_delay_ms)
    
    def _emit_batch_changes(self):
        """批量发送参数变化信号"""
        if not self._pending_changes:
            return
        
        logger.debug(f"批量发送 {len(self._pending_changes)} 个参数变化")
        
        for change_key, (track_id, param, value) in self._pending_changes.items():
            self.track_param_changed.emit(track_id, param, value)
        
        self._pending_changes.clear()
    
    def _add_to_history(self, command: Command):
        """添加命令到历史记录"""
        # 清除当前位置之后的历史
        self._history = self._history[:self._history_index + 1]
        
        # 添加新命令
        self._history.append(command)
        self._history_index += 1
        
        # 限制历史记录大小
        if len(self._history) > self._max_history:
            self._history.pop(0)
            self._history_index -= 1
    
    def undo(self) -> bool:
        """
        撤销操作
        
        Returns:
            是否成功
        """
        if self._history_index < 0:
            logger.debug("没有可撤销的操作")
            return False
        
        command = self._history[self._history_index]
        command.undo()
        self._history_index -= 1
        
        logger.info("撤销操作")
        self.tracks_updated.emit()
        return True
    
    def redo(self) -> bool:
        """
        重做操作
        
        Returns:
            是否成功
        """
        if self._history_index >= len(self._history) - 1:
            logger.debug("没有可重做的操作")
            return False
        
        self._history_index += 1
        command = self._history[self._history_index]
        command.execute()
        
        logger.info("重做操作")
        self.tracks_updated.emit()
        return True
    
    def get_all_tracks(self) -> List[Track]:
        """
        获取所有音轨
        
        Returns:
            音轨列表
        """
        return [self._tracks[track_id] for track_id in self._track_order]
    
    def get_track(self, track_id: str) -> Optional[Track]:
        """
        获取指定音轨
        
        Args:
            track_id: 音轨 ID
            
        Returns:
            音轨对象，如果不存在则返回 None
        """
        return self._tracks.get(track_id)
    
    def delete_track(self, track_id: str) -> bool:
        """
        删除音轨
        
        Args:
            track_id: 音轨 ID
            
        Returns:
            是否成功
        """
        if track_id not in self._tracks:
            logger.error(f"音轨不存在: {track_id}")
            return False
        
        del self._tracks[track_id]
        self._track_order.remove(track_id)
        
        logger.info(f"删除音轨: {track_id}")
        self.tracks_updated.emit()
        return True
    
    def rename_track(self, track_id: str, new_name: str):
        """
        重命名音轨
        
        Args:
            track_id: 音轨 ID
            new_name: 新名称
        """
        self.update_track_param(track_id, "name", new_name)
    
    def clear(self):
        """清除所有音轨"""
        self._tracks.clear()
        self._track_order.clear()
        self._history.clear()
        self._history_index = -1
        
        logger.info("清除所有音轨")
        self.tracks_updated.emit()
