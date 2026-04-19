"""
音轨控制组件
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QCheckBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
import logging
from src.models.track import Track

logger = logging.getLogger(__name__)


class TrackControlWidget(QWidget):
    """单个音轨的控制组件"""
    
    # 信号
    volume_changed = pyqtSignal(str, float)  # (track_id, volume_db)
    mute_toggled = pyqtSignal(str, bool)  # (track_id, muted)
    solo_toggled = pyqtSignal(str, bool)  # (track_id, solo)
    delete_requested = pyqtSignal(str)  # (track_id)
    
    # 音轨颜色映射
    TRACK_COLORS = {
        "vocals": "#64C8FF",
        "drums": "#FF6464",
        "bass": "#64FF64",
        "other": "#FFC864",
        "guitar": "#FF96C8",
        "piano": "#C896FF"
    }
    
    def __init__(self, track: Track):
        super().__init__()
        self.track = track
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        # 设置样式
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-radius: 4px;
                padding: 4px;
            }
            QLabel {
                color: #ffffff;
                background: transparent;
                padding: 0px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 4px;
                font-size: 11px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #2c2c2c;
            }
            QPushButton:checked {
                background-color: #0078d4;
            }
            QPushButton#deleteBtn {
                background-color: #c42b1c;
            }
            QPushButton#deleteBtn:hover {
                background-color: #d43b2c;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3c3c3c;
                height: 4px;
                background: #3c3c3c;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: none;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #1084d8;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)
        
        # 左侧控制区域
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)
        
        # 静音按钮 (使用 Unicode 图标)
        self.mute_btn = QPushButton("🔇")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(self.track.muted)
        self.mute_btn.setToolTip("静音 (M)")
        self.mute_btn.clicked.connect(self._on_mute_clicked)
        controls_layout.addWidget(self.mute_btn)
        
        # 独奏按钮
        self.solo_btn = QPushButton("🎧")
        self.solo_btn.setCheckable(True)
        self.solo_btn.setChecked(self.track.solo)
        self.solo_btn.setToolTip("独奏 (S)")
        self.solo_btn.clicked.connect(self._on_solo_clicked)
        controls_layout.addWidget(self.solo_btn)
        
        layout.addLayout(controls_layout)
        
        # 颜色指示器
        color = self.TRACK_COLORS.get(self.track.source_type, "#888888")
        color_indicator = QFrame()
        color_indicator.setFixedSize(3, 32)
        color_indicator.setStyleSheet(f"background-color: {color}; border-radius: 1px;")
        layout.addWidget(color_indicator)
        
        # 音轨名称
        name_label = QLabel(self.track.name)
        name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_label.setFixedWidth(70)
        layout.addWidget(name_label)
        
        # 音量滑块区域
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(6)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(-60)
        self.volume_slider.setMaximum(12)
        self.volume_slider.setValue(int(self.track.volume_db))
        self.volume_slider.setFixedWidth(200)
        self.volume_slider.setToolTip("音量调整")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel(f"{self.track.volume_db:+.1f}")
        self.volume_label.setFont(QFont("Consolas", 8))
        self.volume_label.setFixedWidth(35)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        volume_layout.addWidget(self.volume_label)
        
        layout.addLayout(volume_layout)
        
        layout.addStretch()
        
        # 删除按钮
        delete_btn = QPushButton("✕")
        delete_btn.setObjectName("deleteBtn")
        delete_btn.setToolTip("删除音轨 (Delete)")
        delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(delete_btn)
    
    def _on_mute_clicked(self):
        """静音按钮点击"""
        is_muted = self.mute_btn.isChecked()
        self.mute_btn.setText("🔇" if is_muted else "🔊")
        self.mute_toggled.emit(self.track.id, is_muted)
    
    def _on_solo_clicked(self):
        """独奏按钮点击"""
        self.solo_toggled.emit(self.track.id, self.solo_btn.isChecked())
    
    def _on_volume_changed(self, value: int):
        """音量滑块变化"""
        self.volume_label.setText(f"{value:+.1f}")
        self.volume_changed.emit(self.track.id, float(value))
    
    def _on_delete_clicked(self):
        """删除按钮点击"""
        self.delete_requested.emit(self.track.id)
    
    def update_from_track(self, track: Track):
        """从音轨对象更新 UI"""
        self.track = track
        self.mute_btn.setChecked(track.muted)
        self.mute_btn.setText("🔇" if track.muted else "🔊")
        self.solo_btn.setChecked(track.solo)
        self.volume_slider.setValue(int(track.volume_db))


class TrackListWidget(QWidget):
    """音轨列表组件"""
    
    def __init__(self, track_manager):
        super().__init__()
        self.track_manager = track_manager
        self.track_widgets = {}
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化 UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.layout.addStretch()
    
    def _connect_signals(self):
        """连接信号"""
        self.track_manager.tracks_updated.connect(self.update_tracks)
    
    def update_tracks(self):
        """更新音轨列表"""
        # 清除现有组件
        for widget in self.track_widgets.values():
            widget.deleteLater()
        self.track_widgets.clear()
        
        # 添加新的音轨组件
        tracks = self.track_manager.get_all_tracks()
        for track in tracks:
            widget = TrackControlWidget(track)
            
            # 连接信号
            widget.volume_changed.connect(self._on_volume_changed)
            widget.mute_toggled.connect(self._on_mute_toggled)
            widget.solo_toggled.connect(self._on_solo_toggled)
            widget.delete_requested.connect(self._on_delete_requested)
            
            self.track_widgets[track.id] = widget
            self.layout.insertWidget(self.layout.count() - 1, widget)
    
    def _on_volume_changed(self, track_id: str, volume_db: float):
        """音量变化"""
        self.track_manager.update_track_param(track_id, "volume_db", volume_db)
    
    def _on_mute_toggled(self, track_id: str, muted: bool):
        """静音切换"""
        self.track_manager.update_track_param(track_id, "muted", muted)
    
    def _on_solo_toggled(self, track_id: str, solo: bool):
        """独奏切换"""
        self.track_manager.update_track_param(track_id, "solo", solo)
    
    def _on_delete_requested(self, track_id: str):
        """删除音轨"""
        self.track_manager.delete_track(track_id)
