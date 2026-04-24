"""
主窗口模块
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QPushButton, QFileDialog,
    QMessageBox, QProgressDialog, QStatusBar, QSplitter,
    QDialog, QLabel, QComboBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEvent
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
import logging
from pathlib import Path

from src.audio_processing.separation_engine import SeparationEngine
from src.audio_processing.audio_mixer import AudioMixer
from src.audio_processing.audio_player import AudioPlayer
from src.models.track_manager import TrackManager
from src.models.project_manager import ProjectManager
from src.gui.track_row_widget import TrackListWidget
from src.utils.crash_protection import CrashProtection

logger = logging.getLogger(__name__)


class ModelSelectionDialog(QDialog):
    """模型选择对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择分离模型")
        self.setModal(True)
        self.selected_model = "htdemucs_6s"  # 默认使用6音轨模型
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # 应用深色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
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
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        
        # 说明文字
        info_label = QLabel(
            "请选择音频分离模型：\n\n"
            "不同模型支持不同数量的音轨分离"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型："))
        
        self.model_combo = QComboBox()
        self.model_combo.addItem("htdemucs - 4音轨 (vocals, drums, bass, other)", "htdemucs")
        self.model_combo.addItem("htdemucs_ft - 4音轨微调版 (vocals, drums, bass, other)", "htdemucs_ft")
        self.model_combo.addItem("htdemucs_6s - 6音轨 (vocals, drums, bass, other, guitar, piano)", "htdemucs_6s")
        self.model_combo.setCurrentIndex(2)  # 默认选择6音轨模型
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.model_combo)
        
        layout.addLayout(model_layout)
        
        # 模型详细信息
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("padding: 12px; background-color: #f0f0f0; border-radius: 4px;")
        self._update_detail_text()
        layout.addWidget(self.detail_label)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setMinimumWidth(500)
    
    def _on_model_changed(self, index):
        """模型选择变化"""
        self.selected_model = self.model_combo.currentData()
        self._update_detail_text()
    
    def _update_detail_text(self):
        """更新详细信息"""
        details = {
            "htdemucs": (
                "📊 标准版本\n"
                "• 音轨：人声、鼓、贝斯、其他\n"
                "• 速度：快\n"
                "• 质量：高\n"
                "• 适用：大多数流行音乐"
            ),
            "htdemucs_ft": (
                "📊 微调版本\n"
                "• 音轨：人声、鼓、贝斯、其他\n"
                "• 速度：快\n"
                "• 质量：更高（针对特定音乐类型优化）\n"
                "• 适用：流行、摇滚音乐"
            ),
            "htdemucs_6s": (
                "📊 6音轨版本\n"
                "• 音轨：人声、鼓、贝斯、其他、吉他、钢琴\n"
                "• 速度：较慢\n"
                "• 质量：高（更细致的乐器分离）\n"
                "• 适用：包含吉他或钢琴的音乐"
            )
        }
        self.detail_label.setText(details.get(self.selected_model, ""))
    
    def get_selected_model(self):
        """获取选择的模型"""
        return self.selected_model


class SeparationThread(QThread):
    """音频分离线程"""
    progress = pyqtSignal(float)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, engine: SeparationEngine, audio_path: str):
        super().__init__()
        self.engine = engine
        self.audio_path = audio_path
        self.sample_rate = 44100
    
    def run(self):
        try:
            stems = self.engine.separate(
                self.audio_path,
                progress_callback=self.progress.emit
            )
            self.sample_rate = self.engine.get_sample_rate()
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
        self._setup_shortcuts()
        
        logger.info("主窗口初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Hachimi (ハチミ) - 音频分离和二创工具")
        self.setGeometry(100, 100, 1200, 700)
        self.setMinimumSize(800, 500)  # 设置最小窗口尺寸
        
        # 设置深色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-bottom: 1px solid #3c3c3c;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
            }
            QMenuBar::item:selected {
                background-color: #3c3c3c;
            }
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3c3c3c;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QToolBar {
                background-color: #2b2b2b;
                border: none;
                border-bottom: 1px solid #3c3c3c;
                spacing: 8px;
                padding: 4px;
            }
            QStatusBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-top: 1px solid #3c3c3c;
            }
            QMessageBox {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMessageBox QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 创建工具栏
        self._create_tool_bar()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 音轨列表（包含控制和波形）
        self.track_list_widget = TrackListWidget(self.track_manager)
        main_layout.addWidget(self.track_list_widget)
        
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 添加快捷键提示
        shortcut_hint = QLabel("  快捷键: 空格=播放/暂停 | Enter=停止 | Home=跳转开始 | 点击波形=跳转位置 | Ctrl+R=二创  ")
        shortcut_hint.setStyleSheet("color: #888888; font-size: 10px;")
        self.status_bar.addPermanentWidget(shortcut_hint)
        
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
        
        # 二创菜单
        remix_menu = menu_bar.addMenu("二创(&R)")
        
        smart_remix_action = QAction("智能二创(&S)...", self)
        smart_remix_action.setShortcut(QKeySequence("Ctrl+R"))
        smart_remix_action.triggered.connect(self.open_remix_dialog)
        remix_menu.addAction(smart_remix_action)
        
        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_tool_bar(self):
        """创建工具栏"""
        tool_bar = QToolBar("主工具栏")
        tool_bar.setStyleSheet("""
            QToolBar QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QToolBar QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        self.addToolBar(tool_bar)
        
        # 打开按钮
        open_btn = QPushButton("📁 打开音频")
        open_btn.setToolTip("打开音频文件 (Ctrl+O)")
        open_btn.clicked.connect(self.open_audio_file)
        tool_bar.addWidget(open_btn)
        
        tool_bar.addSeparator()
        
        # 播放控制按钮
        play_btn = QPushButton("▶")
        play_btn.setToolTip("播放 (空格)")
        play_btn.clicked.connect(self._toggle_play_pause)
        tool_bar.addWidget(play_btn)
        
        pause_btn = QPushButton("⏸")
        pause_btn.setToolTip("暂停 (空格)")
        pause_btn.clicked.connect(self.player.pause)
        tool_bar.addWidget(pause_btn)
        
        stop_btn = QPushButton("⏹")
        stop_btn.setToolTip("停止 (Enter)")
        stop_btn.clicked.connect(self.player.stop)
        tool_bar.addWidget(stop_btn)
    
    def _connect_signals(self):
        """连接信号"""
        self.track_manager.tracks_updated.connect(self.on_tracks_updated)
        self.track_manager.track_param_changed.connect(self.on_track_param_changed)
        self.player.position_updated.connect(self.track_list_widget.update_playhead)
        self.track_list_widget.seek_requested.connect(self.player.seek)
        
        # 安装全局异常处理器
        CrashProtection.install_global_exception_handler()
        logger.info("崩溃保护已启用")
    
    @CrashProtection.protect_slot("音轨参数更新错误")
    def on_track_param_changed(self, track_id: str, param: str, value):
        """音轨参数变化 - 实时更新播放（带保护）"""
        # 如果正在播放，实时重新混合
        if self.player.is_playing():
            self.player.reload_mix()
            logger.debug(f"实时更新音轨参数: {track_id}.{param} = {value}")
    
    def _setup_shortcuts(self):
        """设置键盘快捷键"""
        # 空格键：播放/暂停
        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.activated.connect(self._toggle_play_pause)
        
        # Enter/Return：停止
        stop_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        stop_shortcut.activated.connect(self.player.stop)
        
        # Home：跳转到开始
        home_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Home), self)
        home_shortcut.activated.connect(lambda: self.player.seek(0))
        
        # Delete：删除选中的音轨（暂时不实现，需要选择逻辑）
        # delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        # delete_shortcut.activated.connect(self._delete_selected_track)
        
        logger.info("键盘快捷键已设置")
    
    def _toggle_play_pause(self):
        """切换播放/暂停状态"""
        if self.player.is_playing():
            # 正在播放，则暂停
            self.player.pause()
            logger.info("暂停播放")
        else:
            # 未播放或已暂停，则播放
            tracks = self.track_manager.get_all_tracks()
            if tracks:
                # 只在首次播放或停止后才重新加载音轨
                if self.player.get_position() == 0:
                    self.player.load_tracks(tracks)
                self.player.play()
                logger.info("开始播放")
    
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
        
        # 显示模型选择对话框
        dialog = ModelSelectionDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        selected_model = dialog.get_selected_model()
        
        logger.info(f"打开音频文件: {file_path}, 使用模型: {selected_model}")
        self.status_bar.showMessage(f"正在分离音频: {Path(file_path).name} (模型: {selected_model})")
        
        # 创建新的分离引擎（使用选择的模型）
        separation_engine = SeparationEngine(model_name=selected_model)
        
        # 创建进度对话框
        progress_dialog = QProgressDialog("正在分离音频...", "取消", 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        
        # 创建分离线程
        self.separation_thread = SeparationThread(separation_engine, file_path)
        
        # 连接信号
        self.separation_thread.progress.connect(lambda p: progress_dialog.setValue(int(p)))
        self.separation_thread.finished.connect(lambda stems: self.on_separation_finished(stems, progress_dialog, selected_model))
        self.separation_thread.error.connect(lambda err: self.on_separation_error(err, progress_dialog))
        progress_dialog.canceled.connect(separation_engine.cancel)
        
        # 启动线程
        self.separation_thread.start()
    
    def on_separation_finished(self, stems: dict, progress_dialog: QProgressDialog, model_name: str):
        """分离完成"""
        progress_dialog.close()
        
        if not stems:
            logger.warning("分离被取消或失败")
            self.status_bar.showMessage("分离已取消")
            return
        
        # 添加分离的音轨
        sample_rate = self.separation_thread.sample_rate
        self.track_manager.add_separated_tracks(stems, sample_rate)
        
        self.status_bar.showMessage(f"分离完成，共 {len(stems)} 个音轨 (模型: {model_name})")
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
            progress_callback=lambda p: progress_dialog.setValue(int(p))
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
            "关于 Hachimi",
            "Hachimi (ハチミ) v1.0\n\n"
            "基于 Demucs 的音频源分离工具\n\n"
            "开源许可证: Apache License 2.0\n"
            "GitHub: https://github.com/ChenXin-2009/hachimi"
        )
    
    def open_remix_dialog(self):
        """打开二创对话框"""
        from src.gui.remix_dialog import RemixDialog
        
        # 检查是否有音轨
        tracks = self.track_manager.get_all_tracks()
        if not tracks:
            QMessageBox.warning(
                self,
                "提示",
                "请先打开音频文件并进行分离！"
            )
            return
        
        dialog = RemixDialog(self.track_manager, self)
        dialog.exec()
    
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
