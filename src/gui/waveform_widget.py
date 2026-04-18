"""
波形显示组件
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np
import logging
from src.models.track_manager import TrackManager
from src.gui.waveform_renderer import WaveformRenderer

logger = logging.getLogger(__name__)


class WaveformWidget(QWidget):
    """波形显示组件"""
    
    # 音轨颜色映射
    TRACK_COLORS = {
        "vocals": (100, 200, 255),
        "drums": (255, 100, 100),
        "bass": (100, 255, 100),
        "other": (255, 200, 100),
        "guitar": (255, 150, 200),
        "piano": (200, 150, 255)
    }
    
    def __init__(self, track_manager: TrackManager):
        super().__init__()
        self.track_manager = track_manager
        self.renderer = WaveformRenderer()
        self.playhead_position = 0.0  # 毫秒
        
        self._init_ui()
        logger.info("波形显示组件初始化")
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建 PyQtGraph 绘图窗口
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', '幅度')
        self.plot_widget.setLabel('bottom', '时间', units='s')
        
        # 启用鼠标交互
        self.plot_widget.setMouseEnabled(x=True, y=False)
        
        # 播放头线
        self.playhead_line = pg.InfiniteLine(
            pos=0,
            angle=90,
            pen=pg.mkPen('r', width=2),
            movable=False
        )
        self.plot_widget.addItem(self.playhead_line)
        
        layout.addWidget(self.plot_widget)
    
    def update_waveforms(self):
        """更新波形显示"""
        self.plot_widget.clear()
        self.plot_widget.addItem(self.playhead_line)
        
        tracks = self.track_manager.get_all_tracks()
        
        if not tracks:
            logger.debug("没有音轨可显示")
            return
        
        logger.info(f"更新波形显示: {len(tracks)} 个音轨")
        
        # 为每个音轨绘制波形
        y_offset = 0
        y_spacing = 2.0
        
        for track in tracks:
            if track.audio_data is None:
                continue
            
            # 获取颜色
            color = self.TRACK_COLORS.get(track.source_type, (150, 150, 150))
            
            # 计算波形数据
            sample_rate = track.sample_rate
            duration = track.get_duration_ms() / 1000.0  # 秒
            
            # 使用第一个声道
            audio_channel = track.audio_data[0]
            
            # 降采样用于显示
            num_points = min(10000, len(audio_channel))
            min_peaks, max_peaks = self.renderer.calculate_peaks(
                track.audio_data,
                num_points
            )
            
            # 时间轴
            time_axis = np.linspace(0, duration, num_points)
            
            # 绘制波形（使用第一个声道）
            self.plot_widget.plot(
                time_axis,
                min_peaks[0] + y_offset,
                pen=pg.mkPen(color, width=1),
                name=track.name
            )
            self.plot_widget.plot(
                time_axis,
                max_peaks[0] + y_offset,
                pen=pg.mkPen(color, width=1)
            )
            
            # 填充波形
            fill_path = pg.arrayToQPath(
                time_axis,
                max_peaks[0] + y_offset
            )
            fill_item = pg.FillBetweenItem(
                pg.PlotCurveItem(time_axis, min_peaks[0] + y_offset),
                pg.PlotCurveItem(time_axis, max_peaks[0] + y_offset),
                brush=(*color, 50)
            )
            self.plot_widget.addItem(fill_item)
            
            y_offset -= y_spacing
        
        # 调整视图范围
        self.plot_widget.autoRange()
    
    def update_playhead(self, position_ms: float):
        """
        更新播放头位置
        
        Args:
            position_ms: 位置（毫秒）
        """
        self.playhead_position = position_ms
        position_s = position_ms / 1000.0
        self.playhead_line.setPos(position_s)
