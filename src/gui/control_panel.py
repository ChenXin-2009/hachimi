"""
播放控制面板
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QStyle
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
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
        self._is_seeking = False
        
        self._init_ui()
        self._connect_signals()
        
        logger.info("控制面板初始化")
    
    def _init_ui(self):
        """初始化 UI"""
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #888888;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3c3c3c;
                height: 8px;
                background: #3c3c3c;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #0078d4;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #e0e0e0;
            }
            QLabel {
                color: #ffffff;
                font-size: 11px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # 播放控制按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 播放按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(50, 40)
        self.play_btn.setToolTip("播放 (空格)")
        self.play_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                background-color: #0078d4;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        self.play_btn.clicked.connect(self._on_play_clicked)
        button_layout.addWidget(self.play_btn)
        
        # 暂停按钮
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setFixedSize(50, 40)
        self.pause_btn.setToolTip("暂停 (空格)")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
            }
        """)
        self.pause_btn.clicked.connect(self.player.pause)
        button_layout.addWidget(self.pause_btn)
        
        # 停止按钮
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(50, 40)
        self.stop_btn.setToolTip("停止 (Enter)")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
            }
        """)
        self.stop_btn.clicked.connect(self.player.stop)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 播放位置控制
        position_layout = QHBoxLayout()
        position_layout.setSpacing(12)
        
        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Segoe UI", 10))
        self.time_label.setFixedWidth(50)
        position_layout.addWidget(self.time_label)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(1000)
        self.position_slider.setTracking(True)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        position_layout.addWidget(self.position_slider)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setFont(QFont("Segoe UI", 10))
        self.duration_label.setFixedWidth(50)
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        position_layout.addWidget(self.duration_label)
        
        layout.addLayout(position_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.player.position_updated.connect(self.update_position)
    
    def _on_play_clicked(self):
        """播放按钮点击"""
        # 重新加载音轨
        tracks = self.track_manager.get_all_tracks()
        if tracks:
            self.player.load_tracks(tracks)
        self.player.play()
    
    def _on_slider_pressed(self):
        """滑块按下"""
        self._is_seeking = True
    
    def _on_slider_released(self):
        """滑块释放"""
        self._is_seeking = False
        # 跳转到新位置
        tracks = self.track_manager.get_all_tracks()
        if tracks and tracks[0].audio_data is not None:
            duration_ms = tracks[0].get_duration_ms()
            position_ms = (self.position_slider.value() / 1000.0) * duration_ms
            self.player.seek(position_ms)
    
    def _on_slider_moved(self, value: int):
        """滑块移动"""
        # 更新时间显示
        tracks = self.track_manager.get_all_tracks()
        if tracks and tracks[0].audio_data is not None:
            duration_ms = tracks[0].get_duration_ms()
            position_ms = (value / 1000.0) * duration_ms
            current_time = self._format_time(position_ms / 1000.0)
            self.time_label.setText(current_time)
    
    def update_position(self, position_ms: float):
        """更新播放位置显示"""
        if self._is_seeking:
            return
        
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
                self.time_label.setText(current_time)
                self.duration_label.setText(total_time)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
