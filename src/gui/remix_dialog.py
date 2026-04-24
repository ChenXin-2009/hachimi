"""
二创功能对话框
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QProgressDialog,
    QListWidget, QListWidgetItem, QComboBox, QSlider,
    QGroupBox, QSpinBox, QDoubleSpinBox, QSplitter, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg
import numpy as np
import logging
from pathlib import Path
from typing import List
import soundfile as sf
import sounddevice as sd
import threading
import time

from src.models.track_manager import TrackManager
from src.remix.manual_segmenter import ManualSegmenter, Segment
from src.remix.matcher import RemixMatcher, MatchPoint
from src.remix.generator import RemixGenerator

logger = logging.getLogger(__name__)


class RemixThread(QThread):
    """二创处理线程"""
    progress = pyqtSignal(str)  # 进度消息
    finished = pyqtSignal(list)  # 完成（返回新音轨列表）
    error = pyqtSignal(str)  # 错误
    
    def __init__(self, tracks, segments):
        super().__init__()
        self.tracks = tracks
        self.segments = segments
        self._is_running = True
    
    def run(self):
        try:
            self.progress.emit("正在为所有音轨生成二创版本...")
            generator = RemixGenerator()
            
            remix_tracks = []
            for i, track in enumerate(self.tracks):
                if not self._is_running:
                    logger.info("二创生成被取消")
                    self.error.emit("生成已取消")
                    return
                
                try:
                    self.progress.emit(f"正在处理音轨 {i+1}/{len(self.tracks)}: {track.name}")
                    remix_track = generator.generate_full_replacement_remix(track, self.segments)
                    remix_tracks.append(remix_track)
                except Exception as e:
                    logger.error(f"处理音轨 {track.name} 失败: {e}", exc_info=True)
                    # 继续处理其他音轨
                    continue
            
            if remix_tracks:
                self.finished.emit(remix_tracks)
            else:
                self.error.emit("没有成功生成任何音轨")
                
        except Exception as e:
            logger.error(f"二创生成失败: {e}", exc_info=True)
            self.error.emit(str(e))
    
    def stop(self):
        """停止线程"""
        self._is_running = False


class RemixDialog(QDialog):
    """二创功能主对话框"""
    
    def __init__(self, track_manager: TrackManager, parent=None):
        super().__init__(parent)
        self.track_manager = track_manager
        self.segments: List[Segment] = []
        self.match_points: List[MatchPoint] = []
        self.selected_track = None
        self.sample_audio = None  # 素材音频数据
        self.sample_sr = None  # 素材采样率
        self.segment_markers = []  # 分段标记线
        self.current_audio_path = None  # 当前音频路径
        
        # 编辑工具状态
        self.current_tool = 'select'  # select, cut, delete
        self.selected_region = None  # 当前选中的区域
        self.region_items = []  # 所有区域对象
        self.dragging_edge = None  # 正在拖拽的边缘 (region, 'left'/'right')
        self.hover_cursor = None  # 鼠标悬停的光标线
        
        # 音频播放
        self.is_playing = False
        self.playback_thread = None
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self._update_playback_position)
        self.playback_line = None  # 播放位置线
        self.playback_start_time = 0  # 播放起始时间（在波形中的位置）
        self.playback_audio = None  # 当前播放的音频
        self.playback_sr = None  # 当前播放的采样率
        self.playback_start_timestamp = 0  # 播放开始的时间戳
        
        # 手动分段状态（旧方式，保留兼容）
        self.adding_segment = False
        self.segment_start_time = None
        self.temp_line = None
        
        self.segmenter = ManualSegmenter()
        self.matcher = RemixMatcher()
        
        self._init_ui()
        
        logger.info("二创对话框初始化")
    
    def closeEvent(self, event):
        """关闭事件 - 清理资源"""
        try:
            logger.info("正在关闭二创对话框...")
            
            # 1. 首先停止所有定时器（最重要！）
            if hasattr(self, 'playback_timer') and self.playback_timer:
                try:
                    self.playback_timer.stop()
                    self.playback_timer.timeout.disconnect()
                    self.playback_timer.deleteLater()
                    self.playback_timer = None
                except Exception as e:
                    logger.error(f"停止定时器失败: {e}")
            
            # 2. 停止播放
            if hasattr(self, 'is_playing') and self.is_playing:
                try:
                    self._stop_playback()
                except Exception as e:
                    logger.error(f"停止播放失败: {e}")
            
            # 3. 停止并等待线程结束
            if hasattr(self, 'remix_thread') and self.remix_thread and self.remix_thread.isRunning():
                logger.info("等待二创线程结束...")
                try:
                    self.remix_thread.stop()
                    self.remix_thread.quit()
                    if not self.remix_thread.wait(5000):  # 等待最多5秒
                        logger.warning("二创线程未能正常结束，强制终止")
                        self.remix_thread.terminate()
                        self.remix_thread.wait(1000)
                except Exception as e:
                    logger.error(f"停止线程失败: {e}")
            
            # 4. 清理波形图
            if hasattr(self, 'waveform_plot') and self.waveform_plot:
                try:
                    self.waveform_plot.clear()
                    self.waveform_plot.close()
                except Exception as e:
                    logger.error(f"清理波形图失败: {e}")
            
            # 5. 断开所有信号连接
            try:
                if hasattr(self, 'region_items'):
                    for region in self.region_items:
                        try:
                            region.sigRegionChanged.disconnect()
                        except:
                            pass
            except Exception as e:
                logger.error(f"断开信号失败: {e}")
            
            logger.info("二创对话框关闭完成")
            
        except Exception as e:
            logger.error(f"关闭对话框时出错: {e}", exc_info=True)
        finally:
            # 确保事件被接受
            event.accept()
    
    def _init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("智能二创")
        self.setModal(True)
        self.setMinimumSize(1000, 700)
        
        # 应用深色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QGroupBox {
                background-color: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                color: #ffffff;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #ffffff;
            }
            QListWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3c3c3c;
                height: 6px;
                background: #3c3c3c;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: none;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("🎵 智能二创工具")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 创建分割器（左侧控制，右侧波形）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧控制面板
        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)
        
        # 右侧波形显示
        right_panel = self._create_waveform_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _create_control_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # 步骤1: 导入素材
        step1_group = self._create_step1_group()
        layout.addWidget(step1_group)
        
        # 步骤2: 选择目标音轨
        step2_group = self._create_step2_group()
        layout.addWidget(step2_group)
        
        # 步骤3: 智能匹配
        step3_group = self._create_step3_group()
        layout.addWidget(step3_group)
        
        # 步骤4: 生成二创
        step4_group = self._create_step4_group()
        layout.addWidget(step4_group)
        
        layout.addStretch()
        
        return panel
    
    def _create_waveform_panel(self) -> QWidget:
        """创建右侧波形显示面板"""
        panel = QWidget()
        panel.setStyleSheet("background-color: #1e1e1e;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 8, 8, 8)
        
        # 工具按钮
        self.tool_select_btn = QPushButton("🖱 选择")
        self.tool_select_btn.setCheckable(True)
        self.tool_select_btn.setChecked(True)
        self.tool_select_btn.clicked.connect(lambda: self._set_tool('select'))
        self.tool_select_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                padding: 6px 12px;
            }
            QPushButton:checked {
                background-color: #0078d4;
            }
        """)
        toolbar.addWidget(self.tool_select_btn)
        
        self.tool_cut_btn = QPushButton("✂ 分段")
        self.tool_cut_btn.setCheckable(True)
        self.tool_cut_btn.clicked.connect(lambda: self._set_tool('cut'))
        self.tool_cut_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                padding: 6px 12px;
            }
            QPushButton:checked {
                background-color: #0078d4;
            }
        """)
        toolbar.addWidget(self.tool_cut_btn)
        
        self.tool_delete_btn = QPushButton("🗑 删除")
        self.tool_delete_btn.setCheckable(True)
        self.tool_delete_btn.clicked.connect(lambda: self._set_tool('delete'))
        self.tool_delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                padding: 6px 12px;
            }
            QPushButton:checked {
                background-color: #0078d4;
            }
        """)
        toolbar.addWidget(self.tool_delete_btn)
        
        toolbar.addStretch()
        
        # 缩放控制
        zoom_label = QLabel("缩放:")
        zoom_label.setStyleSheet("color: #888888;")
        toolbar.addWidget(zoom_label)
        
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(30, 30)
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(30, 30)
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        zoom_fit_btn = QPushButton("适应")
        zoom_fit_btn.clicked.connect(self._zoom_fit)
        toolbar.addWidget(zoom_fit_btn)
        
        # 分隔线
        separator = QLabel("|")
        separator.setStyleSheet("color: #555555; padding: 0 8px;")
        toolbar.addWidget(separator)
        
        # 播放控制（暂时禁用，避免崩溃）
        # self.play_all_btn = QPushButton("▶ 播放全部")
        # self.play_all_btn.clicked.connect(self._play_all)
        # self.play_all_btn.setEnabled(False)
        # toolbar.addWidget(self.play_all_btn)
        
        # self.play_segment_btn = QPushButton("▶ 播放片段")
        # self.play_segment_btn.clicked.connect(self._play_selected_segment)
        # self.play_segment_btn.setEnabled(False)
        # toolbar.addWidget(self.play_segment_btn)
        
        # self.stop_btn = QPushButton("⏹ 停止")
        # self.stop_btn.clicked.connect(self._stop_playback)
        # self.stop_btn.setEnabled(False)
        # toolbar.addWidget(self.stop_btn)
        
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setStyleSheet("background-color: #2b2b2b;")
        layout.addWidget(toolbar_widget)
        
        # 波形图
        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setBackground('#1e1e1e')
        self.waveform_plot.setLabel('left', '幅度', color='#ffffff')
        self.waveform_plot.setLabel('bottom', '时间 (秒)', color='#ffffff')
        self.waveform_plot.showGrid(x=True, y=True, alpha=0.3)
        
        # 设置坐标轴颜色
        self.waveform_plot.getAxis('left').setPen('#ffffff')
        self.waveform_plot.getAxis('bottom').setPen('#ffffff')
        self.waveform_plot.getAxis('left').setTextPen('#ffffff')
        self.waveform_plot.getAxis('bottom').setTextPen('#ffffff')
        
        # 连接鼠标事件
        self.waveform_plot.scene().sigMouseClicked.connect(self._on_waveform_clicked)
        self.waveform_plot.scene().sigMouseMoved.connect(self._on_waveform_mouse_moved)
        
        layout.addWidget(self.waveform_plot)
        
        # 状态栏
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(8, 4, 8, 4)
        
        self.waveform_hint = QLabel("请导入素材音频")
        self.waveform_hint.setStyleSheet("color: #888888;")
        status_bar.addWidget(self.waveform_hint)
        
        status_bar.addStretch()
        
        self.cursor_time_label = QLabel("00:00.000")
        self.cursor_time_label.setStyleSheet("color: #888888; font-family: monospace;")
        status_bar.addWidget(self.cursor_time_label)
        
        status_widget = QWidget()
        status_widget.setLayout(status_bar)
        status_widget.setStyleSheet("background-color: #2b2b2b;")
        layout.addWidget(status_widget)
        
        return panel
    
    def _set_tool(self, tool: str):
        """设置当前工具"""
        self.current_tool = tool
        
        # 更新按钮状态
        self.tool_select_btn.setChecked(tool == 'select')
        self.tool_cut_btn.setChecked(tool == 'cut')
        self.tool_delete_btn.setChecked(tool == 'delete')
        
        # 更新提示
        hints = {
            'select': '选择工具：点击选中分段，拖拽边缘调整范围',
            'cut': '分段工具：在波形上拖拽创建新分段',
            'delete': '删除工具：点击分段删除'
        }
        if self.sample_audio is not None:
            duration = len(self.sample_audio) / self.sample_sr
            self.waveform_hint.setText(f"{hints[tool]} | 共 {len(self.segments)} 个片段 | 时长: {duration:.2f}秒")
        else:
            self.waveform_hint.setText(hints[tool])
        
        logger.debug(f"切换工具: {tool}")
    
    def _zoom_in(self):
        """放大"""
        self.waveform_plot.getViewBox().scaleBy((0.5, 1))
    
    def _zoom_out(self):
        """缩小"""
        self.waveform_plot.getViewBox().scaleBy((2, 1))
    
    def _zoom_fit(self):
        """适应窗口"""
        if self.sample_audio is not None:
            duration = len(self.sample_audio) / self.sample_sr
            self.waveform_plot.setXRange(0, duration, padding=0.02)
            self.waveform_plot.setYRange(-1, 1, padding=0.1)
    
    def _on_waveform_mouse_moved(self, pos):
        """鼠标移动事件"""
        if self.sample_audio is None:
            return
        
        # 获取鼠标位置
        scene_pos = pos
        if self.waveform_plot.sceneBoundingRect().contains(scene_pos):
            mouse_point = self.waveform_plot.plotItem.vb.mapSceneToView(scene_pos)
            time = mouse_point.x()
            
            # 更新时间显示
            minutes = int(time // 60)
            seconds = time % 60
            self.cursor_time_label.setText(f"{minutes:02d}:{seconds:06.3f}")
            
            # 显示悬停光标
            if self.hover_cursor is None:
                self.hover_cursor = pg.InfiniteLine(
                    pos=time,
                    angle=90,
                    pen=pg.mkPen('#888888', width=1, style=Qt.PenStyle.DashLine)
                )
                self.waveform_plot.addItem(self.hover_cursor)
            else:
                self.hover_cursor.setPos(time)
    
    def _on_waveform_clicked(self, event):
        """波形图点击事件"""
        if self.sample_audio is None:
            return
        
        # 获取点击位置
        pos = event.scenePos()
        if not self.waveform_plot.sceneBoundingRect().contains(pos):
            return
        
        mouse_point = self.waveform_plot.plotItem.vb.mapSceneToView(pos)
        click_time = mouse_point.x()
        
        # 限制在有效范围内
        duration = len(self.sample_audio) / self.sample_sr
        click_time = max(0, min(click_time, duration))
        
        if self.current_tool == 'select':
            self._handle_select_click(click_time)
        elif self.current_tool == 'cut':
            self._handle_cut_click(click_time, event)
        elif self.current_tool == 'delete':
            self._handle_delete_click(click_time)
    
    def _handle_select_click(self, time: float):
        """处理选择工具点击"""
        # 查找点击位置的分段
        for i, seg in enumerate(self.segments):
            if seg.start_time <= time <= seg.end_time:
                self.selected_region = i
                self._update_waveform()
                self._update_play_segment_button()
                logger.debug(f"选中分段: {seg.name}")
                return
        
        # 没有点击到分段，取消选择
        self.selected_region = None
        self._update_waveform()
        self._update_play_segment_button()
    
    def _handle_cut_click(self, time: float, event):
        """处理分段工具点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.segment_start_time is None:
                # 第一次点击 - 设置起始点
                self.segment_start_time = time
                
                # 显示临时标记线
                self.temp_line = pg.InfiniteLine(
                    pos=time,
                    angle=90,
                    pen=pg.mkPen('#00FF00', width=2, style=Qt.PenStyle.DashLine),
                    label='起始点'
                )
                self.waveform_plot.addItem(self.temp_line)
                
                duration = len(self.sample_audio) / self.sample_sr
                self.waveform_hint.setText(f"起始点: {time:.2f}s | 请点击结束点 | 共 {len(self.segments)} 个片段 | 时长: {duration:.2f}秒")
                logger.debug(f"分段起始点: {time:.2f}s")
            else:
                # 第二次点击 - 设置结束点并创建分段
                end_time = time
                start_time = self.segment_start_time
                
                # 确保 start < end
                if start_time > end_time:
                    start_time, end_time = end_time, start_time
                
                # 移除临时线
                if self.temp_line:
                    self.waveform_plot.removeItem(self.temp_line)
                    self.temp_line = None
                
                # 创建分段
                try:
                    segment = self.segmenter.add_segment(start_time, end_time)
                    self.segments = self.segmenter.get_segments()
                    
                    # 更新显示
                    self._update_waveform()
                    self._update_segment_list()
                    
                    logger.info(f"创建分段: {segment.name} ({start_time:.2f}s - {end_time:.2f}s)")
                except Exception as e:
                    logger.error(f"创建分段失败: {e}")
                    QMessageBox.warning(self, "错误", f"创建分段失败：\n{e}")
                
                # 重置状态
                self.segment_start_time = None
                duration = len(self.sample_audio) / self.sample_sr
                self.waveform_hint.setText(f"分段工具：在波形上拖拽创建新分段 | 共 {len(self.segments)} 个片段 | 时长: {duration:.2f}秒")
    
    def _handle_delete_click(self, time: float):
        """处理删除工具点击"""
        # 查找点击位置的分段
        for i, seg in enumerate(self.segments):
            if seg.start_time <= time <= seg.end_time:
                self.segmenter.remove_segment(i)
                self.segments = self.segmenter.get_segments()
                self._update_waveform()
                self._update_segment_list()
                self._update_play_segment_button()
                logger.info(f"删除分段: {seg.name}")
                return
    
    def _create_step1_group(self) -> QGroupBox:
        """步骤1: 导入素材"""
        group = QGroupBox("步骤 1: 导入素材音频")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("导入音频文件，使用工具栏创建分段")
        info_label.setStyleSheet("color: #888888;")
        layout.addWidget(info_label)
        
        # 导入和裁剪按钮
        btn_layout = QHBoxLayout()
        
        import_btn = QPushButton("📁 选择音频文件")
        import_btn.clicked.connect(self.import_sample)
        btn_layout.addWidget(import_btn)
        
        crop_btn = QPushButton("✂ 裁剪音频")
        crop_btn.clicked.connect(self.crop_audio)
        btn_layout.addWidget(crop_btn)
        
        btn_layout.addStretch()
        
        self.sample_label = QLabel("未选择文件")
        self.sample_label.setStyleSheet("color: #888888;")
        btn_layout.addWidget(self.sample_label)
        
        layout.addLayout(btn_layout)
        
        # 分段操作按钮
        segment_btn_layout = QHBoxLayout()
        
        add_segment_btn = QPushButton("➕ 快速添加")
        add_segment_btn.setToolTip("切换到分段工具")
        add_segment_btn.clicked.connect(lambda: self._set_tool('cut'))
        segment_btn_layout.addWidget(add_segment_btn)
        
        clear_segments_btn = QPushButton("🗑 清除所有")
        clear_segments_btn.clicked.connect(self.clear_segments)
        segment_btn_layout.addWidget(clear_segments_btn)
        
        segment_btn_layout.addStretch()
        
        layout.addLayout(segment_btn_layout)
        
        # 片段列表
        list_label = QLabel("片段列表:")
        list_label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(list_label)
        
        self.segment_list = QListWidget()
        self.segment_list.setMaximumHeight(100)
        self.segment_list.itemClicked.connect(self._on_segment_list_clicked)
        self.segment_list.itemDoubleClicked.connect(self._on_segment_list_double_clicked)
        layout.addWidget(self.segment_list)
        
        # 删除选中片段按钮
        segment_actions_layout = QHBoxLayout()
        
        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(self.delete_selected_segment)
        segment_actions_layout.addWidget(delete_btn)
        
        rename_btn = QPushButton("重命名")
        rename_btn.clicked.connect(self._rename_selected_segment)
        segment_actions_layout.addWidget(rename_btn)
        
        play_btn = QPushButton("▶ 播放")
        play_btn.clicked.connect(self._play_segment_from_list)
        segment_actions_layout.addWidget(play_btn)
        
        layout.addLayout(segment_actions_layout)
        
        return group
    
    def _create_step2_group(self) -> QGroupBox:
        """步骤2: 选择目标音轨"""
        group = QGroupBox("步骤 2: 选择需要二创的音轨")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("选择要生成二创版本的音轨（可多选）")
        info_label.setStyleSheet("color: #888888;")
        layout.addWidget(info_label)
        
        # 音轨选择列表
        self.track_selection_list = QListWidget()
        self.track_selection_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.track_selection_list.setMaximumHeight(150)
        self.track_selection_list.setStyleSheet("""
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #3c3c3c;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #2b2b2b;
            }
        """)
        layout.addWidget(self.track_selection_list)
        
        # 快速选择按钮
        quick_select_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._select_all_tracks)
        quick_select_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self._deselect_all_tracks)
        quick_select_layout.addWidget(deselect_all_btn)
        
        select_vocals_btn = QPushButton("仅人声")
        select_vocals_btn.clicked.connect(lambda: self._select_tracks_by_type("vocals"))
        quick_select_layout.addWidget(select_vocals_btn)
        
        quick_select_layout.addStretch()
        
        layout.addLayout(quick_select_layout)
        
        # 选中数量提示
        self.track_selection_label = QLabel("未选择音轨")
        self.track_selection_label.setStyleSheet("color: #888888; padding: 4px;")
        layout.addWidget(self.track_selection_label)
        
        # 更新音轨列表
        self._update_track_selection_list()
        
        # 连接选择变化事件
        self.track_selection_list.itemSelectionChanged.connect(self._on_track_selection_changed)
        
        return group
    
    def _create_step3_group(self) -> QGroupBox:
        """步骤3: 智能匹配（已简化）"""
        group = QGroupBox("步骤 3: 准备生成")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("系统将自动分析原曲音高，智能选择素材片段并调整音高")
        info_label.setStyleSheet("color: #888888;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 显示片段信息
        self.segment_info_label = QLabel("请先导入素材并创建分段")
        self.segment_info_label.setStyleSheet("color: #888888; padding: 8px;")
        layout.addWidget(self.segment_info_label)
        
        return group
    
    def _create_step4_group(self) -> QGroupBox:
        """步骤4: 生成二创"""
        group = QGroupBox("步骤 4: 生成二创")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("用素材片段完全替换选中的音轨，自动匹配音高")
        info_label.setStyleSheet("color: #888888;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 生成按钮
        generate_btn = QPushButton("✨ 生成选中音轨的二创版本")
        generate_btn.clicked.connect(self.generate_remix)
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 12px 16px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
        """)
        layout.addWidget(generate_btn)
        
        return group
    
    def _update_track_list(self):
        """更新音轨列表（保留兼容）"""
        self._update_track_selection_list()
    
    def _update_track_selection_list(self):
        """更新音轨选择列表"""
        if not hasattr(self, 'track_selection_list'):
            return
        
        self.track_selection_list.clear()
        tracks = self.track_manager.get_all_tracks()
        
        for track in tracks:
            # 创建列表项
            item_text = f"{track.name} ({track.source_type})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, track)  # 存储音轨对象
            
            # 添加图标（根据音轨类型）
            icon_map = {
                "vocals": "🎤",
                "drums": "🥁",
                "bass": "🎸",
                "guitar": "🎸",
                "piano": "🎹",
                "other": "🎵"
            }
            icon = icon_map.get(track.source_type, "🎵")
            item.setText(f"{icon} {item_text}")
            
            self.track_selection_list.addItem(item)
        
        # 默认全选
        self._select_all_tracks()
    
    def _select_all_tracks(self):
        """全选音轨"""
        for i in range(self.track_selection_list.count()):
            self.track_selection_list.item(i).setSelected(True)
        self._on_track_selection_changed()
    
    def _deselect_all_tracks(self):
        """取消全选"""
        self.track_selection_list.clearSelection()
        self._on_track_selection_changed()
    
    def _select_tracks_by_type(self, track_type: str):
        """按类型选择音轨"""
        self.track_selection_list.clearSelection()
        
        for i in range(self.track_selection_list.count()):
            item = self.track_selection_list.item(i)
            track = item.data(Qt.ItemDataRole.UserRole)
            if track.source_type == track_type:
                item.setSelected(True)
        
        self._on_track_selection_changed()
    
    def _on_track_selection_changed(self):
        """音轨选择变化"""
        selected_count = len(self.track_selection_list.selectedItems())
        total_count = self.track_selection_list.count()
        
        if selected_count == 0:
            self.track_selection_label.setText("⚠️ 未选择音轨")
            self.track_selection_label.setStyleSheet("color: #ff6464; padding: 4px;")
        elif selected_count == total_count:
            self.track_selection_label.setText(f"✓ 已选择全部 {selected_count} 个音轨")
            self.track_selection_label.setStyleSheet("color: #00ff00; padding: 4px;")
        else:
            self.track_selection_label.setText(f"✓ 已选择 {selected_count}/{total_count} 个音轨")
            self.track_selection_label.setStyleSheet("color: #00ff00; padding: 4px;")
    
    def _get_selected_tracks(self):
        """获取选中的音轨"""
        selected_tracks = []
        for item in self.track_selection_list.selectedItems():
            track = item.data(Qt.ItemDataRole.UserRole)
            if track:
                selected_tracks.append(track)
        return selected_tracks
    
    def _on_density_changed(self, value):
        """密度滑块变化"""
        self.density_label.setText(f"{value}%")
    
    def import_sample(self):
        """导入素材"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择素材音频",
            "",
            "音频文件 (*.mp3 *.wav *.flac *.ogg *.m4a)"
        )
        
        if not file_path:
            return
        
        logger.info(f"导入素材: {file_path}")
        self.sample_label.setText(f"正在加载: {Path(file_path).name}")
        self.current_audio_path = file_path
        
        # 创建进度对话框
        progress = QProgressDialog("正在加载音频...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        try:
            # 使用手动分段器加载音频
            self.segmenter.load_audio(file_path)
            self.sample_audio = self.segmenter.audio
            self.sample_sr = self.segmenter.sr
            self.segments = []
            
            self.sample_label.setText(f"✓ {Path(file_path).name}")
            
            # 播放按钮已禁用
            # self.play_all_btn.setEnabled(True)
            # self._update_play_segment_button()
            
            # 更新波形显示
            self._update_waveform()
            
            QMessageBox.information(
                self,
                "加载完成",
                f"音频加载成功！\n"
                f"时长: {len(self.sample_audio)/self.sample_sr:.2f}秒\n"
                f"采样率: {self.sample_sr}Hz\n\n"
                f"使用工具栏的\"✂ 分段\"工具在波形上创建分段。\n"
                f"或点击\"➕ 快速添加\"按钮切换到分段工具。"
            )
            
        except Exception as e:
            logger.error(f"素材加载失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"素材加载失败：\n{e}")
            self.sample_label.setText("加载失败")
        
        finally:
            progress.close()
    
    def start_add_segment(self):
        """开始添加分段（兼容旧方法）"""
        self._set_tool('cut')
    
    def clear_segments(self):
        """清除所有分段"""
        if not self.segments:
            return
        
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要清除所有分段吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.segmenter.clear_segments()
            self.segments = []
            self._update_waveform()
            self._update_segment_list()
            logger.info("已清除所有分段")
    
    def delete_selected_segment(self):
        """删除选中的分段"""
        current_row = self.segment_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的片段！")
            return
        
        self.segmenter.remove_segment(current_row)
        self.segments = self.segmenter.get_segments()
        self._update_waveform()
        self._update_segment_list()
        logger.info(f"删除片段: 索引 {current_row}")
    
    def _on_segment_list_clicked(self, item):
        """片段列表点击事件"""
        row = self.segment_list.row(item)
        if 0 <= row < len(self.segments):
            self.selected_region = row
            self._update_waveform()
            self._update_play_segment_button()
    
    def _on_segment_list_double_clicked(self, item):
        """片段列表双击事件 - 播放片段"""
        row = self.segment_list.row(item)
        if 0 <= row < len(self.segments):
            self.selected_region = row
            self._play_selected_segment()
    
    def _rename_selected_segment(self):
        """重命名选中的片段"""
        current_row = self.segment_list.currentRow()
        if current_row < 0 or current_row >= len(self.segments):
            QMessageBox.warning(self, "提示", "请先选择要重命名的片段！")
            return
        
        segment = self.segments[current_row]
        from PyQt6.QtWidgets import QInputDialog
        
        new_name, ok = QInputDialog.getText(
            self,
            "重命名片段",
            "请输入新名称:",
            text=segment.name
        )
        
        if ok and new_name:
            segment.name = new_name
            self._update_segment_list()
            self._update_waveform()
            logger.info(f"重命名片段: {segment.name}")
    
    def _play_segment_from_list(self):
        """从列表播放选中的片段"""
        current_row = self.segment_list.currentRow()
        if current_row < 0 or current_row >= len(self.segments):
            QMessageBox.warning(self, "提示", "请先选择要播放的片段！")
            return
        
        self.selected_region = current_row
        self._play_selected_segment()
    
    def edit_segment_name(self, item):
        """编辑片段名称（保留兼容）"""
        self._rename_selected_segment()
    
    def crop_audio(self):
        """裁剪音频"""
        if self.sample_audio is None:
            QMessageBox.warning(self, "提示", "请先导入音频文件！")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        
        duration = len(self.sample_audio) / self.sample_sr
        
        # 输入起始时间
        start_time, ok1 = QInputDialog.getDouble(
            self,
            "裁剪音频",
            f"请输入起始时间（秒）\n当前时长: {duration:.2f}秒",
            0, 0, duration, 2
        )
        
        if not ok1:
            return
        
        # 输入结束时间
        end_time, ok2 = QInputDialog.getDouble(
            self,
            "裁剪音频",
            f"请输入结束时间（秒）\n当前时长: {duration:.2f}秒",
            duration, start_time, duration, 2
        )
        
        if not ok2:
            return
        
        try:
            self.segmenter.crop_audio(start_time, end_time)
            self.sample_audio = self.segmenter.audio
            self.segments = []
            
            self._update_waveform()
            self._update_segment_list()
            
            QMessageBox.information(
                self,
                "裁剪完成",
                f"音频已裁剪！\n"
                f"新时长: {len(self.sample_audio)/self.sample_sr:.2f}秒\n\n"
                f"注意：所有分段已清除，请重新标记。"
            )
            
            logger.info(f"音频裁剪完成: {start_time:.2f}s - {end_time:.2f}s")
            
        except Exception as e:
            logger.error(f"裁剪失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"裁剪失败：\n{e}")
    
    def _update_segment_list(self):
        """更新片段列表"""
        self.segment_list.clear()
        for i, seg in enumerate(self.segments):
            item_text = f"{seg.name}: {seg.start_time:.2f}s - {seg.end_time:.2f}s"
            if seg.pitch > 0:
                item_text += f" (音高: {seg.pitch:.0f}Hz)"
            self.segment_list.addItem(item_text)
        
        # 更新步骤3的信息
        if hasattr(self, 'segment_info_label'):
            if self.segments:
                self.segment_info_label.setText(
                    f"✓ 已准备 {len(self.segments)} 个素材片段\n"
                    f"系统将智能选择片段并调整音高以匹配原曲"
                )
                self.segment_info_label.setStyleSheet("color: #00ff00; padding: 8px;")
            else:
                self.segment_info_label.setText("请先导入素材并创建分段")
                self.segment_info_label.setStyleSheet("color: #888888; padding: 8px;")
    
    def _update_waveform(self):
        """更新波形显示"""
        if self.sample_audio is None:
            return
        
        try:
            # 清除旧的图形项
            self.waveform_plot.clear()
            self.region_items = []
            
            # 计算时间轴
            duration = len(self.sample_audio) / self.sample_sr
            
            # 性能优化：对长音频进行降采样显示
            max_display_points = 10000  # 最大显示点数
            audio_to_display = self.sample_audio
            
            if len(self.sample_audio) > max_display_points:
                # 降采样以提高性能
                downsample_factor = len(self.sample_audio) // max_display_points
                audio_to_display = self.sample_audio[::downsample_factor]
            
            time_axis = np.linspace(0, duration, len(audio_to_display))
            
            # 绘制波形
            self.waveform_plot.plot(
                time_axis,
                audio_to_display,
                pen=pg.mkPen('#64C8FF', width=1)
            )
            
            # 绘制分段标记
            for i, seg in enumerate(self.segments):
                is_selected = (i == self.selected_region)
                
                # 分段区域
                region = pg.LinearRegionItem(
                    values=[seg.start_time, seg.end_time],
                    brush=pg.mkBrush(0, 120, 215, 60 if is_selected else 30),
                    pen=pg.mkPen('#0078d4' if is_selected else '#64C8FF', width=2 if is_selected else 1),
                    movable=True
                )
                
                # 连接区域变化事件
                region.sigRegionChanged.connect(lambda r, idx=i: self._on_region_changed(idx, r))
                
                self.waveform_plot.addItem(region)
                self.region_items.append(region)
                
                # 分段标签（使用 TextItem）
                label_text = pg.TextItem(
                    text=seg.name,
                    color='#FF6464',
                    anchor=(0, 1)
                )
                label_text.setPos(seg.start_time, 0.9)
                self.waveform_plot.addItem(label_text)
            
            # 重新添加悬停光标（确保在最上层）
            if self.hover_cursor is not None:
                try:
                    self.waveform_plot.addItem(self.hover_cursor)
                except RuntimeError:
                    # 对象可能已失效
                    self.hover_cursor = None
            
            # 更新提示
            hints = {
                'select': '选择工具：点击选中分段，拖拽边缘调整范围',
                'cut': '分段工具：在波形上拖拽创建新分段',
                'delete': '删除工具：点击分段删除'
            }
            self.waveform_hint.setText(f"{hints[self.current_tool]} | 共 {len(self.segments)} 个片段 | 时长: {duration:.2f}秒")
            
        except Exception as e:
            logger.error(f"更新波形显示失败: {e}", exc_info=True)
    
    def _on_region_changed(self, index: int, region: pg.LinearRegionItem):
        """分段区域被拖拽改变"""
        if index >= len(self.segments):
            return
        
        # 获取新的范围
        start_time, end_time = region.getRegion()
        
        # 更新分段数据
        segment = self.segments[index]
        
        # 重新提取音频数据
        start_sample = int(start_time * self.sample_sr)
        end_sample = int(end_time * self.sample_sr)
        start_sample = max(0, start_sample)
        end_sample = min(len(self.sample_audio), end_sample)
        
        segment.start_time = start_time
        segment.end_time = end_time
        segment.duration = end_time - start_time
        segment.audio_data = self.sample_audio[start_sample:end_sample]
        
        # 重新提取特征
        segment.extract_features()
        
        # 更新列表显示
        self._update_segment_list()
        
        logger.debug(f"分段 {segment.name} 调整为: {start_time:.2f}s - {end_time:.2f}s")
    
    def _update_play_segment_button(self):
        """更新播放片段按钮状态"""
        # 检查按钮是否存在（可能被注释掉了）
        if not hasattr(self, 'play_segment_btn'):
            return
        
        self.play_segment_btn.setEnabled(
            self.sample_audio is not None and 
            self.selected_region is not None and 
            self.selected_region < len(self.segments)
        )
    
    def _play_all(self):
        """播放整个素材音频"""
        if self.sample_audio is None:
            return
        
        if self.is_playing:
            self._stop_playback()
            return
        
        try:
            # 准备播放
            self.playback_audio = self.sample_audio.copy()  # 复制一份，避免引用问题
            self.playback_sr = self.sample_sr
            self.playback_start_time = 0
            self.playback_start_timestamp = time.time()
            
            # 在后台线程播放
            def play_audio():
                try:
                    sd.play(self.playback_audio, self.playback_sr, blocking=True)
                except Exception as e:
                    logger.error(f"播放出错: {e}")
            
            self.playback_thread = threading.Thread(target=play_audio, daemon=True)
            self.playback_thread.start()
            
            # 启动定时器更新播放位置
            if self.playback_timer:
                self.playback_timer.start(100)  # 每100ms更新一次，降低频率
            
            self.is_playing = True
            if hasattr(self, 'play_all_btn'):
                self.play_all_btn.setText("⏹ 停止")
            if hasattr(self, 'stop_btn'):
                self.stop_btn.setEnabled(True)
            
            logger.info("开始播放全部音频")
            
        except Exception as e:
            logger.error(f"播放失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"播放失败：\n{e}")
            self._stop_playback()
    
    def _play_selected_segment(self):
        """播放选中的片段"""
        if self.selected_region is None or self.selected_region >= len(self.segments):
            return
        
        if self.is_playing:
            self._stop_playback()
            return
        
        try:
            segment = self.segments[self.selected_region]
            
            # 准备播放
            self.playback_audio = segment.audio_data.copy()  # 复制一份
            self.playback_sr = segment.sample_rate
            self.playback_start_time = segment.start_time
            self.playback_start_timestamp = time.time()
            
            # 在后台线程播放
            def play_audio():
                try:
                    sd.play(self.playback_audio, self.playback_sr, blocking=True)
                except Exception as e:
                    logger.error(f"播放出错: {e}")
            
            self.playback_thread = threading.Thread(target=play_audio, daemon=True)
            self.playback_thread.start()
            
            # 启动定时器更新播放位置
            if self.playback_timer:
                self.playback_timer.start(100)  # 每100ms更新一次
            
            self.is_playing = True
            if hasattr(self, 'play_segment_btn'):
                self.play_segment_btn.setText("⏹ 停止")
            if hasattr(self, 'stop_btn'):
                self.stop_btn.setEnabled(True)
            
            logger.info(f"开始播放片段: {segment.name}")
            
        except Exception as e:
            logger.error(f"播放失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"播放失败：\n{e}")
            self._stop_playback()
    
    def _stop_playback(self):
        """停止播放"""
        try:
            # 停止音频
            try:
                sd.stop()
            except Exception as e:
                logger.debug(f"停止 sounddevice 时出错（可能已停止）: {e}")
            
            # 停止定时器
            if self.playback_timer:
                try:
                    self.playback_timer.stop()
                except:
                    pass
            
            # 等待播放线程结束
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=1.0)
            
            self.is_playing = False
            
            # 更新按钮状态
            if hasattr(self, 'play_all_btn'):
                self.play_all_btn.setText("▶ 播放全部")
            if hasattr(self, 'play_segment_btn'):
                self.play_segment_btn.setText("▶ 播放片段")
            if hasattr(self, 'stop_btn'):
                self.stop_btn.setEnabled(False)
            
            logger.debug("停止播放")
            
        except Exception as e:
            logger.error(f"停止播放出错: {e}", exc_info=True)
    
    def _update_playback_position(self):
        """更新播放位置（简化版 - 仅检查播放状态）"""
        if not self.is_playing:
            return
        
        try:
            # 检查线程是否还活着
            if self.playback_thread and not self.playback_thread.is_alive():
                # 播放结束
                self._stop_playback()
                return
                    
        except Exception as e:
            logger.error(f"更新播放位置出错: {e}")
            if self.is_playing:
                self._stop_playback()
    
    def _on_playback_status_changed(self, status):
        """播放状态改变（已移除，保留兼容）"""
        pass
    
    def _on_playback_position_changed(self, position_ms: int):
        """播放位置改变（已移除，保留兼容）"""
        pass
    
    def _on_segment_playback_position_changed(self, position_ms: int, segment: Segment):
        """播放位置改变（已移除，保留兼容）"""
        pass
    
    def start_matching(self):
        """开始智能匹配（已移除，保留兼容）"""
        pass
    
    def _on_density_changed(self, value):
        """密度滑块变化（已移除，保留兼容）"""
        pass
    
    def generate_remix(self):
        """生成二创"""
        if not self.segments:
            QMessageBox.warning(self, "提示", "请先导入素材并创建分段！")
            return
        
        # 获取选中的音轨
        selected_tracks = self._get_selected_tracks()
        
        if not selected_tracks:
            QMessageBox.warning(self, "提示", "请至少选择一个音轨！")
            return
        
        logger.info(f"开始为 {len(selected_tracks)} 个选中音轨生成二创")
        
        # 确认对话框
        track_names = "\n".join([f"  • {track.name} ({track.source_type})" for track in selected_tracks[:5]])
        if len(selected_tracks) > 5:
            track_names += f"\n  ... 还有 {len(selected_tracks) - 5} 个音轨"
        
        reply = QMessageBox.question(
            self,
            "确认生成",
            f"将用 {len(self.segments)} 个素材片段为以下 {len(selected_tracks)} 个音轨生成二创版本：\n\n"
            f"{track_names}\n\n"
            f"系统会自动分析原曲音高，智能选择片段并调整音高。\n"
            f"这可能需要几分钟时间，确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # 创建进度对话框
            progress = QProgressDialog(
                f"正在为 {len(selected_tracks)} 个音轨生成二创...", 
                "取消", 
                0, 
                0, 
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            # 创建线程
            self.remix_thread = RemixThread(
                selected_tracks,  # 使用选中的音轨
                self.segments
            )
            
            # 连接取消按钮
            progress.canceled.connect(lambda: self._cancel_remix(progress))
            
            self.remix_thread.finished.connect(lambda tracks: self._on_remix_finished(tracks, progress))
            self.remix_thread.error.connect(lambda err: self._on_remix_error(err, progress))
            self.remix_thread.progress.connect(lambda msg: progress.setLabelText(msg))
            
            logger.info(f"启动二创线程，处理 {len(selected_tracks)} 个音轨")
            self.remix_thread.start()
            
        except Exception as e:
            logger.error(f"启动二创失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"启动二创失败：\n{e}")
    
    def _cancel_remix(self, progress):
        """取消二创生成"""
        if hasattr(self, 'remix_thread') and self.remix_thread and self.remix_thread.isRunning():
            logger.info("用户取消二创生成")
            self.remix_thread.stop()
            progress.close()
    
    def _on_remix_finished(self, remix_tracks, progress):
        """二创完成"""
        progress.close()
        
        # 添加所有二创音轨到音轨管理器
        for remix_track in remix_tracks:
            self.track_manager._tracks[remix_track.id] = remix_track
            self.track_manager._track_order.append(remix_track.id)
        
        self.track_manager.tracks_updated.emit()
        
        QMessageBox.information(
            self,
            "成功",
            f"已为 {len(remix_tracks)} 个音轨生成二创版本！\n"
            f"新音轨已添加到项目中。"
        )
        
        logger.info(f"成功生成 {len(remix_tracks)} 个二创音轨")
    
    def _on_remix_error(self, error, progress):
        """二创失败"""
        progress.close()
        QMessageBox.critical(self, "错误", f"二创生成失败：\n{error}")
