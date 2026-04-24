"""
音轨行组件 - 将控制和波形显示在同一行
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QFrame, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEasingCurve
from PyQt6.QtGui import QFont
import pyqtgraph as pg
import numpy as np
import logging
from src.models.track import Track

logger = logging.getLogger(__name__)


class TrackRowWidget(QWidget):
    """单个音轨行 - 左侧控制，右侧波形"""
    
    # 信号
    volume_changed = pyqtSignal(str, float)  # (track_id, volume_db)
    mute_toggled = pyqtSignal(str, bool)  # (track_id, muted)
    solo_toggled = pyqtSignal(str, bool)  # (track_id, solo)
    delete_requested = pyqtSignal(str)  # (track_id)
    seek_requested = pyqtSignal(float)  # (position_ms)
    zoom_changed = pyqtSignal(float)  # (zoom_level) - 缩放信号
    range_changed = pyqtSignal(float, float)  # (x_min, x_max) - 范围变化信号
    
    # 音轨颜色映射
    TRACK_COLORS = {
        "vocals": (100, 200, 255),
        "drums": (255, 100, 100),
        "bass": (100, 255, 100),
        "other": (255, 200, 100),
        "guitar": (255, 150, 200),
        "piano": (200, 150, 255)
    }
    
    def __init__(self, track: Track):
        super().__init__()
        self.track = track
        self.waveform_data = None
        self.playhead_line = None
        self.zoom_level = 1.0  # 缩放级别
        self._updating_range = False  # 防止循环更新
        
        # 动画相关
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_step)
        self._animation_steps = 0
        self._animation_total_steps = 15  # 动画总帧数
        self._target_x_min = 0
        self._target_x_max = 1
        self._current_x_min = 0
        self._current_x_max = 1
        
        # 音量调整防抖定时器
        self._volume_debounce_timer = QTimer()
        self._volume_debounce_timer.setSingleShot(True)
        self._volume_debounce_timer.timeout.connect(self._emit_volume_changed)
        self._pending_volume = None
        
        self._init_ui()
        
        # 设置固定高度
        self.setFixedHeight(120)
    
    def _init_ui(self):
        """初始化 UI"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧控制面板
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
        
        # 右侧波形显示
        self.waveform_plot = self._create_waveform_plot()
        layout.addWidget(self.waveform_plot, stretch=1)
    
    def _create_control_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        panel.setFixedWidth(180)
        panel.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-right: 1px solid #3c3c3c;
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
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
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
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # 顶部：名称和颜色
        top_layout = QVBoxLayout()
        top_layout.setSpacing(4)
        
        name_label = QLabel(self.track.name)
        name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(name_label)
        
        # 颜色指示器
        color_rgb = self.TRACK_COLORS.get(self.track.source_type, (150, 150, 150))
        color_hex = f"#{color_rgb[0]:02x}{color_rgb[1]:02x}{color_rgb[2]:02x}"
        color_indicator = QFrame()
        color_indicator.setFixedSize(80, 3)
        color_indicator.setStyleSheet(f"background-color: {color_hex}; border-radius: 1px;")
        top_layout.addWidget(color_indicator, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addLayout(top_layout)
        
        # 中部：控制按钮
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)
        
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(self.track.muted)
        self.mute_btn.setToolTip("静音 (M)")
        self.mute_btn.clicked.connect(self._on_mute_clicked)
        controls_layout.addWidget(self.mute_btn)
        
        self.solo_btn = QPushButton("🎧")
        self.solo_btn.setCheckable(True)
        self.solo_btn.setChecked(self.track.solo)
        self.solo_btn.setToolTip("独奏 (S)")
        self.solo_btn.clicked.connect(self._on_solo_clicked)
        controls_layout.addWidget(self.solo_btn)
        
        delete_btn = QPushButton("✕")
        delete_btn.setObjectName("deleteBtn")
        delete_btn.setToolTip("删除音轨 (Delete)")
        delete_btn.clicked.connect(self._on_delete_clicked)
        controls_layout.addWidget(delete_btn)
        
        layout.addLayout(controls_layout)
        
        # 底部：音量控制（横向）
        volume_layout = QVBoxLayout()
        volume_layout.setSpacing(4)
        
        vol_label = QLabel("音量")
        vol_label.setFont(QFont("Segoe UI", 8))
        vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vol_label.setStyleSheet("color: #888888;")
        volume_layout.addWidget(vol_label)
        
        slider_layout = QHBoxLayout()
        slider_layout.setSpacing(6)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(-60)
        self.volume_slider.setMaximum(12)
        self.volume_slider.setValue(int(self.track.volume_db))
        self.volume_slider.setToolTip("音量调整")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        slider_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel(f"{self.track.volume_db:+.0f}")
        self.volume_label.setFont(QFont("Consolas", 8))
        self.volume_label.setFixedWidth(25)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider_layout.addWidget(self.volume_label)
        
        volume_layout.addLayout(slider_layout)
        
        layout.addLayout(volume_layout)
        
        layout.addStretch()
        
        return panel
    
    def _create_waveform_plot(self) -> pg.PlotWidget:
        """创建波形显示"""
        plot = pg.PlotWidget()
        plot.setBackground('#1e1e1e')
        
        # 隐藏坐标轴
        plot.hideAxis('left')
        plot.hideAxis('bottom')
        
        # 启用鼠标交互
        plot.setMouseEnabled(x=True, y=False)
        plot.setMenuEnabled(False)
        
        # 隐藏按钮
        plot.hideButtons()
        
        # 创建播放头线
        self.playhead_line = pg.InfiniteLine(
            pos=0,
            angle=90,
            pen=pg.mkPen('#ff0000', width=2),
            movable=False
        )
        plot.addItem(self.playhead_line)
        
        # 连接鼠标点击事件
        plot.scene().sigMouseClicked.connect(self._on_waveform_clicked)
        
        # 连接滚轮事件
        plot.wheelEvent = self._on_wheel_event
        
        # 连接视图范围变化事件（用于同步平移）
        plot.sigRangeChanged.connect(self._on_range_changed)
        
        return plot
    
    def _on_range_changed(self, view_box, ranges):
        """视图范围变化（平移）"""
        x_range = ranges[0]
        # 发送范围变化信号，让其他音轨同步
        if hasattr(self, '_updating_range') and self._updating_range:
            return
        
        self.range_changed.emit(x_range[0], x_range[1])
    
    def set_range(self, x_min: float, x_max: float):
        """设置视图范围（从其他音轨同步）"""
        self._updating_range = True
        self.waveform_plot.setXRange(x_min, x_max, padding=0)
        self._updating_range = False
    
    def _on_wheel_event(self, event):
        """滚轮缩放事件"""
        # 获取滚轮增量
        delta = event.angleDelta().y()
        
        # 计算缩放因子
        zoom_factor = 1.15 if delta > 0 else 0.87
        
        # 更新缩放级别
        new_zoom = self.zoom_level * zoom_factor
        new_zoom = max(0.1, min(10.0, new_zoom))  # 限制在 0.1 到 10 倍之间
        
        if new_zoom != self.zoom_level:
            self.zoom_level = new_zoom
            self.zoom_changed.emit(self.zoom_level)
            self._apply_zoom_animated()
        
        event.accept()
    
    def set_zoom(self, zoom_level: float, animated: bool = True):
        """设置缩放级别（从其他音轨同步）"""
        self.zoom_level = zoom_level
        if animated:
            self._apply_zoom_animated()
        else:
            self._apply_zoom()
    
    def _apply_zoom_animated(self):
        """应用缩放（带动画）"""
        if self.track.audio_data is None:
            return
        
        duration_s = self.track.get_duration_ms() / 1000.0
        
        # 根据缩放级别计算新的视图范围
        view_range = duration_s / self.zoom_level
        
        # 获取当前视图中心
        current_range = self.waveform_plot.viewRange()[0]
        center = (current_range[0] + current_range[1]) / 2
        
        # 计算新的范围，保持中心位置
        new_min = center - view_range / 2
        new_max = center + view_range / 2
        
        # 限制在有效范围内
        if new_min < 0:
            new_min = 0
            new_max = view_range
        if new_max > duration_s:
            new_max = duration_s
            new_min = duration_s - view_range
        
        # 启动动画
        self._start_animation(new_min, new_max)
    
    def _apply_zoom(self):
        """应用缩放（无动画）"""
        if self.track.audio_data is None:
            return
        
        duration_s = self.track.get_duration_ms() / 1000.0
        view_range = duration_s / self.zoom_level
        current_range = self.waveform_plot.viewRange()[0]
        center = (current_range[0] + current_range[1]) / 2
        
        new_min = center - view_range / 2
        new_max = center + view_range / 2
        
        if new_min < 0:
            new_min = 0
            new_max = view_range
        if new_max > duration_s:
            new_max = duration_s
            new_min = duration_s - view_range
        
        self._updating_range = True
        self.waveform_plot.setXRange(new_min, new_max, padding=0)
        self._updating_range = False
        
        self._current_x_min = new_min
        self._current_x_max = new_max
    
    def _start_animation(self, target_x_min: float, target_x_max: float):
        """启动范围变化动画"""
        current_range = self.waveform_plot.viewRange()[0]
        self._current_x_min = current_range[0]
        self._current_x_max = current_range[1]
        self._target_x_min = target_x_min
        self._target_x_max = target_x_max
        self._animation_steps = 0
        
        if not self._animation_timer.isActive():
            self._animation_timer.start(16)  # 约 60 FPS
    
    def _animate_step(self):
        """动画步进"""
        self._animation_steps += 1
        
        # 使用缓动函数（ease-out）
        progress = self._animation_steps / self._animation_total_steps
        eased_progress = 1 - (1 - progress) ** 3  # cubic ease-out
        
        # 插值计算当前位置
        current_min = self._current_x_min + (self._target_x_min - self._current_x_min) * eased_progress
        current_max = self._current_x_max + (self._target_x_max - self._current_x_max) * eased_progress
        
        # 更新视图
        self._updating_range = True
        self.waveform_plot.setXRange(current_min, current_max, padding=0)
        self._updating_range = False
        
        # 检查是否完成
        if self._animation_steps >= self._animation_total_steps:
            self._animation_timer.stop()
            self._current_x_min = self._target_x_min
            self._current_x_max = self._target_x_max
    
    def _on_waveform_clicked(self, event):
        """波形图点击事件"""
        if self.track.audio_data is None:
            return
        
        # 获取点击位置
        pos = event.scenePos()
        mouse_point = self.waveform_plot.plotItem.vb.mapSceneToView(pos)
        
        # 转换为时间（秒）
        time_s = mouse_point.x()
        
        # 限制在有效范围内
        duration_s = self.track.get_duration_ms() / 1000.0
        time_s = max(0, min(time_s, duration_s))
        
        # 发送跳转信号
        time_ms = time_s * 1000.0
        self.seek_requested.emit(time_ms)
        
        logger.debug(f"波形图点击跳转: {time_ms:.2f} ms")
    
    def update_waveform(self):
        """更新波形显示"""
        if self.track.audio_data is None:
            return
        
        self.waveform_plot.clear()
        self.waveform_plot.addItem(self.playhead_line)
        
        # 获取颜色
        color = self.TRACK_COLORS.get(self.track.source_type, (150, 150, 150))
        
        # 计算波形数据
        sample_rate = self.track.sample_rate
        duration = self.track.get_duration_ms() / 1000.0  # 秒
        
        # 使用第一个声道
        audio_channel = self.track.audio_data[0]
        
        # 降采样用于显示
        num_points = min(5000, len(audio_channel))
        step = len(audio_channel) // num_points
        
        if step > 0:
            downsampled = audio_channel[::step][:num_points]
        else:
            downsampled = audio_channel
        
        # 时间轴
        time_axis = np.linspace(0, duration, len(downsampled))
        
        # 绘制波形
        self.waveform_plot.plot(
            time_axis,
            downsampled,
            pen=pg.mkPen(color, width=1),
            fillLevel=0,
            brush=(*color, 80)
        )
        
        # 设置视图范围
        self.waveform_plot.setXRange(0, duration, padding=0)
        self.waveform_plot.setYRange(-1, 1, padding=0.1)
    
    def update_playhead(self, position_ms: float):
        """更新播放头位置"""
        position_s = position_ms / 1000.0
        self.playhead_line.setPos(position_s)
    
    def _on_mute_clicked(self):
        """静音按钮点击"""
        is_muted = self.mute_btn.isChecked()
        self.mute_btn.setText("🔇" if is_muted else "🔊")
        self.mute_toggled.emit(self.track.id, is_muted)
    
    def _on_solo_clicked(self):
        """独奏按钮点击"""
        self.solo_toggled.emit(self.track.id, self.solo_btn.isChecked())
    
    def _on_volume_changed(self, value: int):
        """音量滑块变化（带防抖）"""
        # 立即更新显示
        self.volume_label.setText(f"{value:+.1f}")
        
        # 保存待发送的值
        self._pending_volume = float(value)
        
        # 使用防抖：100ms 后才发送信号
        self._volume_debounce_timer.start(100)
    
    def _emit_volume_changed(self):
        """实际发送音量变化信号"""
        if self._pending_volume is not None:
            self.volume_changed.emit(self.track.id, self._pending_volume)
            self._pending_volume = None
    
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
    """音轨列表组件 - 垂直堆叠多个音轨行"""
    
    # 信号
    seek_requested = pyqtSignal(float)  # (position_ms)
    
    def __init__(self, track_manager):
        super().__init__()
        self.track_manager = track_manager
        self.track_widgets = {}
        self.current_zoom = 1.0
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #4c4c4c;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5c5c5c;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建容器
        container = QWidget()
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.layout.addStretch()
        
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)
    
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
            widget = TrackRowWidget(track)
            
            # 连接信号
            widget.volume_changed.connect(self._on_volume_changed)
            widget.mute_toggled.connect(self._on_mute_toggled)
            widget.solo_toggled.connect(self._on_solo_toggled)
            widget.delete_requested.connect(self._on_delete_requested)
            widget.seek_requested.connect(self._on_seek_requested)
            widget.zoom_changed.connect(self._on_zoom_changed)
            widget.range_changed.connect(self._on_range_changed)
            
            # 更新波形
            widget.update_waveform()
            
            # 应用当前缩放级别
            widget.set_zoom(self.current_zoom, animated=False)
            
            self.track_widgets[track.id] = widget
            self.layout.insertWidget(self.layout.count() - 1, widget)
    
    def update_playhead(self, position_ms: float):
        """更新所有音轨的播放头位置"""
        for widget in self.track_widgets.values():
            widget.update_playhead(position_ms)
    
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
    
    def _on_seek_requested(self, position_ms: float):
        """跳转请求"""
        self.seek_requested.emit(position_ms)
    
    def _on_zoom_changed(self, zoom_level: float):
        """缩放变化 - 同步到所有音轨"""
        self.current_zoom = zoom_level
        
        # 同步到其他音轨
        for widget in self.track_widgets.values():
            if widget.zoom_level != zoom_level:
                widget.set_zoom(zoom_level, animated=True)
    
    def _on_range_changed(self, x_min: float, x_max: float):
        """范围变化（平移）- 同步到所有音轨"""
        # 同步到其他音轨
        for widget in self.track_widgets.values():
            current_range = widget.waveform_plot.viewRange()[0]
            # 只有当范围不同时才更新
            if abs(current_range[0] - x_min) > 0.01 or abs(current_range[1] - x_max) > 0.01:
                widget.set_range(x_min, x_max)
