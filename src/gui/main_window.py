"""
主窗口模块
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QPushButton, QFileDialog,
    QMessageBox, QProgressDialog, QStatusBar, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
import logging
from pathlib import Path

from src.audio_processing.separation_engine import SeparationEngine
from src.audio_processing.audio_mixer import AudioMixer
from src.audio_processing.audio_player import AudioPlayer
from src.models.track_manager import TrackManager
from src.models.project_manager import ProjectManager
from src.gui.waveform_widget import WaveformWidget
from src.gui.control_panel import ControlPanel

logger = logging.getLogger(__name__)


class SeparationThread(QThread):
    """音频分离线程"""
    progress = pyqtSignal(float)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, engine: SeparationEngine, audio_path: str):
        super().__init__()
        self.engine = engine
        self.audio_path = audio_path
    
    def run(self):
        try:
            stems = self.engine.separate(
                self.audio_path,
                progress_callback=self.progress.emit
            )
            self.finished.emit(stems)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化组件
        self.separation_engine = SeparationEngine()
        self.mixer = AudioMixer()
        self.track_manager = TrackManager()
        self.project_manager = ProjectManager()
        self.player = AudioPlayer(self.mixer)
        
        self.current_project_path = None
        self.is_modified = False
        
        # 初始化 UI
        self._init_ui()
        self._connect_signals()
        
        logger.info("主窗口初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Hachimi - 音频分离和二创工具")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 创建工具栏
        self._create_tool_bar()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 波形显示区域
        self.waveform_widget = WaveformWidget(self.track_manager)
        splitter.addWidget(self.waveform_widget)
        
        # 控制面板
        self.control_panel = ControlPanel(self.player, self.track_manager)
        splitter.addWidget(self.control_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()
        
        # 文件菜单
        file_menu = menu_bar.addMenu("文件(&F)")
        
        open_action = QAction("打开音频(&O)...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_audio_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("保存项目(&S)...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        load_action = QAction("加载项目(&L)...", self)
        load_action.triggered.connect(self.load_project)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("导出音频(&E)...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_audio)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menu_bar.addMenu("编辑(&E)")
        
        undo_action = QAction("撤销(&U)", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.track_manager.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("重做(&R)", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.track_manager.redo)
        edit_menu.addAction(redo_action)
        
        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_tool_bar(self):
        """创建工具栏"""
        tool_bar = QToolBar("主工具栏")
        self.addToolBar(tool_bar)
        
        # 打开按钮
        open_btn = QPushButton("打开音频")
        open_btn.clicked.connect(self.open_audio_file)
        tool_bar.addWidget(open_btn)
        
        tool_bar.addSeparator()
        
        # 播放控制按钮
        play_btn = QPushButton("播放")
        play_btn.clicked.connect(self.player.play)
        tool_bar.addWidget(play_btn)
        
        pause_btn = QPushButton("暂停")
        pause_btn.clicked.connect(self.player.pause)
        tool_bar.addWidget(pause_btn)
        
        stop_btn = QPushButton("停止")
        stop_btn.clicked.connect(self.player.stop)
        tool_bar.addWidget(stop_btn)
    
    def _connect_signals(self):
        """连接信号"""
        self.track_manager.tracks_updated.connect(self.on_tracks_updated)
        self.player.position_updated.connect(self.waveform_widget.update_playhead)
    
    def open_audio_file(self):
        """打开音频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            "",
            "音频文件 (*.mp3 *.wav *.flac *.ogg *.m4a);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        logger.info(f"打开音频文件: {file_path}")
        self.status_bar.showMessage(f"正在分离音频: {Path(file_path).name}")
        
        # 创建进度对话框
        progress_dialog = QProgressDialog("正在分离音频...", "取消", 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        
        # 创建分离线程
        self.separation_thread = SeparationThread(self.separation_engine, file_path)
        
        # 连接信号
        self.separation_thread.progress.connect(progress_dialog.setValue)
        self.separation_thread.finished.connect(lambda stems: self.on_separation_finished(stems, progress_dialog))
        self.separation_thread.error.connect(lambda err: self.on_separation_error(err, progress_dialog))
        progress_dialog.canceled.connect(self.separation_engine.cancel)
        
        # 启动线程
        self.separation_thread.start()
    
    def on_separation_finished(self, stems: dict, progress_dialog: QProgressDialog):
        """分离完成"""
        progress_dialog.close()
        
        if not stems:
            logger.warning("分离被取消或失败")
            self.status_bar.showMessage("分离已取消")
            return
        
        # 添加分离的音轨
        sample_rate = self.separation_engine.get_sample_rate()
        self.track_manager.add_separated_tracks(stems, sample_rate)
        
        self.status_bar.showMessage(f"分离完成，共 {len(stems)} 个音轨")
        self.is_modified = True
    
    def on_separation_error(self, error: str, progress_dialog: QProgressDialog):
        """分离错误"""
        progress_dialog.close()
        
        logger.error(f"分离失败: {error}")
        QMessageBox.critical(self, "错误", f"音频分离失败：\n{error}")
        self.status_bar.showMessage("分离失败")
    
    def on_tracks_updated(self):
        """音轨更新"""
        tracks = self.track_manager.get_all_tracks()
        
        # 更新播放器
        self.player.load_tracks(tracks)
        
        # 更新波形显示
        self.waveform_widget.update_waveforms()
        
        self.is_modified = True
    
    def save_project(self):
        """保存项目"""
        if self.current_project_path:
            file_path = self.current_project_path
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存项目",
                "",
                "项目文件 (*.json)"
            )
        
        if not file_path:
            return
        
        tracks = self.track_manager.get_all_tracks()
        metadata = {
            "created_at": "",
            "modified_at": ""
        }
        
        success = self.project_manager.save_project(file_path, tracks, metadata)
        
        if success:
            self.current_project_path = file_path
            self.is_modified = False
            self.status_bar.showMessage(f"项目已保存: {Path(file_path).name}")
            QMessageBox.information(self, "成功", "项目保存成功！")
        else:
            QMessageBox.critical(self, "错误", "项目保存失败！")
    
    def load_project(self):
        """加载项目"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载项目",
            "",
            "项目文件 (*.json)"
        )
        
        if not file_path:
            return
        
        tracks, metadata = self.project_manager.load_project(file_path)
        
        if tracks is None:
            QMessageBox.critical(self, "错误", "项目加载失败！")
            return
        
        # 清除当前音轨
        self.track_manager.clear()
        
        # 添加加载的音轨
        for track in tracks:
            self.track_manager._tracks[track.id] = track
            self.track_manager._track_order.append(track.id)
        
        self.track_manager.tracks_updated.emit()
        
        self.current_project_path = file_path
        self.is_modified = False
        self.status_bar.showMessage(f"项目已加载: {Path(file_path).name}")
    
    def export_audio(self):
        """导出音频"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出音频",
            "",
            "WAV 文件 (*.wav);;FLAC 文件 (*.flac);;MP3 文件 (*.mp3)"
        )
        
        if not file_path:
            return
        
        # 确定格式
        suffix = Path(file_path).suffix.lower()
        format_map = {".wav": "wav", ".flac": "flac", ".mp3": "mp3"}
        format = format_map.get(suffix, "wav")
        
        # 创建进度对话框
        progress_dialog = QProgressDialog("正在导出音频...", None, 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        
        tracks = self.track_manager.get_all_tracks()
        
        success = self.mixer.export(
            tracks,
            file_path,
            format=format,
            quality="high",
            progress_callback=progress_dialog.setValue
        )
        
        progress_dialog.close()
        
        if success:
            self.status_bar.showMessage(f"音频已导出: {Path(file_path).name}")
            QMessageBox.information(self, "成功", "音频导出成功！")
        else:
            QMessageBox.critical(self, "错误", "音频导出失败！")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            "Hachimi (ハチミ) v1.0\n\n"
            "基于 Demucs 的音频源分离工具\n\n"
            "开源许可证: Apache License 2.0\n"
            "GitHub: https://github.com/ChenXin-2009/hachimi"
        )
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "确认",
                "项目未保存，是否保存？",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self.save_project()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
