"""
二创功能对话框
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QProgressDialog,
    QListWidget, QListWidgetItem, QComboBox, QSlider,
    QGroupBox, QSpinBox, QDoubleSpinBox, QSplitter, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import pyqtgraph as pg
import numpy as np
import logging
from pathlib import Path
from typing import List

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
    
    def __init__(self, tracks, match_points):
        super().__init__()
        self.tracks = tracks
        self.match_points = match_points
    
    def run(self):
        try:
            self.progress.emit("正在为所有音轨生成二创版本...")
            generator = RemixGenerator()
            remix_tracks = generator.generate_remix_for_all_tracks(
                self.tracks,
                self.match_points,
                replace_mode=True  # 完全替换模式
            )
            self.finished.emit(remix_tracks)
        except Exception as e:
            logger.error(f"二创生成失败: {e}", exc_info=True)
            self.error.emit(str(e))


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
        
        # 手动分段状态（旧方式，保留兼容）
        self.adding_segment = False
        self.segment_start_time = None
        self.temp_line = None
        
        self.segmenter = ManualSegmenter()
        self.matcher = RemixMatcher()
        
        self._init_ui()
        
        logger.info("二创对话框初始化")
    
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
                logger.debug(f"选中分段: {seg.name}")
                return
        
        # 没有点击到分段，取消选择
        self.selected_region = None
        self._update_waveform()
    
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
        self.segment_list.itemDoubleClicked.connect(self.edit_segment_name)
        layout.addWidget(self.segment_list)
        
        # 删除选中片段按钮
        delete_btn = QPushButton("删除选中片段")
        delete_btn.clicked.connect(self.delete_selected_segment)
        layout.addWidget(delete_btn)
        
        return group
    
    def _create_step2_group(self) -> QGroupBox:
        """步骤2: 选择目标音轨"""
        group = QGroupBox("步骤 2: 选择目标音轨")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("选择要应用二创的音轨（通常选择人声）")
        info_label.setStyleSheet("color: #888888;")
        layout.addWidget(info_label)
        
        self.track_combo = QComboBox()
        self._update_track_list()
        layout.addWidget(self.track_combo)
        
        return group
    
    def _create_step3_group(self) -> QGroupBox:
        """步骤3: 智能匹配"""
        group = QGroupBox("步骤 3: 智能匹配")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("调整匹配参数，然后点击\"开始匹配\"")
        info_label.setStyleSheet("color: #888888;")
        layout.addWidget(info_label)
        
        # 密度控制
        density_layout = QHBoxLayout()
        density_layout.addWidget(QLabel("插入密度:"))
        
        self.density_slider = QSlider(Qt.Orientation.Horizontal)
        self.density_slider.setMinimum(10)
        self.density_slider.setMaximum(100)
        self.density_slider.setValue(50)
        self.density_slider.valueChanged.connect(self._on_density_changed)
        density_layout.addWidget(self.density_slider)
        
        self.density_label = QLabel("50%")
        self.density_label.setFixedWidth(40)
        density_layout.addWidget(self.density_label)
        
        layout.addLayout(density_layout)
        
        # 匹配按钮
        match_btn = QPushButton("🎯 开始智能匹配")
        match_btn.clicked.connect(self.start_matching)
        layout.addWidget(match_btn)
        
        # 匹配结果
        self.match_label = QLabel("未开始匹配")
        self.match_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.match_label)
        
        return group
    
    def _create_step4_group(self) -> QGroupBox:
        """步骤4: 生成二创"""
        group = QGroupBox("步骤 4: 生成二创")
        layout = QVBoxLayout(group)
        
        info_label = QLabel("为所有音轨生成二创版本（完全替换模式）")
        info_label.setStyleSheet("color: #888888;")
        layout.addWidget(info_label)
        
        # 生成按钮
        generate_btn = QPushButton("✨ 生成所有音轨的二创版本")
        generate_btn.clicked.connect(self.generate_remix)
        layout.addWidget(generate_btn)
        
        return group
    
    def _update_track_list(self):
        """更新音轨列表"""
        self.track_combo.clear()
        tracks = self.track_manager.get_all_tracks()
        for track in tracks:
            self.track_combo.addItem(f"{track.name} ({track.source_type})", track)
    
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
    
    def edit_segment_name(self, item):
        """编辑片段名称"""
        from PyQt6.QtWidgets import QInputDialog
        
        row = self.segment_list.row(item)
        if row < 0 or row >= len(self.segments):
            return
        
        segment = self.segments[row]
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
    
    def _update_waveform(self):
        """更新波形显示"""
        if self.sample_audio is None:
            return
        
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
            self.waveform_plot.addItem(self.hover_cursor)
        
        # 更新提示
        hints = {
            'select': '选择工具：点击选中分段，拖拽边缘调整范围',
            'cut': '分段工具：在波形上拖拽创建新分段',
            'delete': '删除工具：点击分段删除'
        }
        self.waveform_hint.setText(f"{hints[self.current_tool]} | 共 {len(self.segments)} 个片段 | 时长: {duration:.2f}秒")
    
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
    
    def start_matching(self):
        """开始智能匹配"""
        if not self.segments:
            QMessageBox.warning(self, "提示", "请先导入素材音频！")
            return
        
        # 获取选中的音轨
        self.selected_track = self.track_combo.currentData()
        if not self.selected_track:
            QMessageBox.warning(self, "提示", "请选择目标音轨！")
            return
        
        logger.info(f"开始匹配到音轨: {self.selected_track.name}")
        self.match_label.setText("正在匹配...")
        
        # 创建进度对话框
        progress = QProgressDialog("正在智能匹配...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        try:
            # 获取密度
            density = self.density_slider.value() / 100.0
            
            # 智能匹配
            self.match_points = self.matcher.auto_arrange(
                self.selected_track,
                self.segments,
                density=density
            )
            
            self.match_label.setText(f"✓ 找到 {len(self.match_points)} 个匹配点")
            
            QMessageBox.information(
                self,
                "匹配完成",
                f"成功找到 {len(self.match_points)} 个插入位置！\n"
                f"平均置信度: {sum(m.confidence for m in self.match_points) / len(self.match_points):.2%}"
            )
            
        except Exception as e:
            logger.error(f"匹配失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"智能匹配失败：\n{e}")
            self.match_label.setText("匹配失败")
        
        finally:
            progress.close()
    
    def generate_remix(self):
        """生成二创"""
        if not self.match_points:
            QMessageBox.warning(self, "提示", "请先进行智能匹配！")
            return
        
        logger.info("开始为所有音轨生成二创")
        
        # 获取所有音轨
        all_tracks = self.track_manager.get_all_tracks()
        
        # 创建进度对话框
        progress = QProgressDialog("正在为所有音轨生成二创...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # 创建线程
        self.remix_thread = RemixThread(
            all_tracks,
            self.match_points
        )
        
        self.remix_thread.finished.connect(lambda tracks: self._on_remix_finished(tracks, progress))
        self.remix_thread.error.connect(lambda err: self._on_remix_error(err, progress))
        
        self.remix_thread.start()
    
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
