"""
播放控制面板
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel
)
from PyQt6.QtCore import Qt
import logging
from src.audio_processing.audio_player import AudioPlayer
from src.models.track_manager import TrackManager

logger = logging.getLogger(__name__)


class ControlPanel(QWidget):
    """播放控制面板"""
    
    def __init__(self, player: AudioPlayer, track_manager: TrackManager):
        super().__init__()
        self.player = player
        self.track_manager = track_manager
        
        self._init_ui()
        self._connect_signals()
        
        logger.info("控制面板初始化")
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        
        # 播放控制按钮
        button_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self.player.play)
        button_layout.addWidget(self.play_btn)
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.player.pause)
        button_layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.player.stop)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 播放位置滑块
        position_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00 / 00:00")
        position_layout.addWidget(self.time_label)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(1000)
        self.position_slider.sliderMoved.connect(self.on_slider_moved)
        position_layout.addWidget(self.position_slider)
        
        layout.addLayout(position_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.player.position_updated.connect(self.update_position)
    
    def update_position(self, position_ms: float):
        """更新播放位置显示"""
        # 更新滑块
        tracks = self.track_manager.get_all_tracks()
        if tracks and tracks[0].audio_data is not None:
            duration_ms = tracks[0].get_duration_ms()
            if duration_ms > 0:
                slider_value = int((position_ms / duration_ms) * 1000)
                self.position_slider.setValue(slider_value)
                
                # 更新时间标签
                current_time = self._format_time(position_ms / 1000.0)
                total_time = self._format_time(duration_ms / 1000.0)
                self.time_label.setText(f"{current_time} / {total_time}")
    
    def on_slider_moved(self, value: int):
        """滑块移动"""
        tracks = self.track_manager.get_all_tracks()
        if tracks and tracks[0].audio_data is not None:
            duration_ms = tracks[0].get_duration_ms()
            position_ms = (value / 1000.0) * duration_ms
            self.player.seek(position_ms)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
