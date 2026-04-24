"""
音频转MIDI对话框
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QGroupBox, QSlider, QCheckBox, QComboBox,
    QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
import logging

from src.audio_processing.audio_to_midi import get_converter

logger = logging.getLogger(__name__)


class MidiConversionThread(QThread):
    """MIDI转换线程"""
    
    progress = pyqtSignal(str)  # 进度消息
    finished = pyqtSignal(object, list, str)  # (midi_data, note_events, message)
    error = pyqtSignal(str)
    
    def __init__(
        self,
        audio_path: str,
        output_path: str,
        params: dict
    ):
        super().__init__()
        self.audio_path = audio_path
        self.output_path = output_path
        self.params = params
        self._is_running = True
    
    def run(self):
        """执行转换"""
        try:
            self.progress.emit("正在初始化转换器...")
            converter = get_converter()
            
            if not converter.is_available():
                self.error.emit("转换器不可用，请安装 basic-pitch")
                return
            
            self.progress.emit("正在分析音频...")
            
            midi_data, note_events, message = converter.convert(
                self.audio_path,
                self.output_path,
                **self.params
            )
            
            if midi_data is None:
                self.error.emit(message)
            else:
                self.finished.emit(midi_data, note_events, message)
                
        except Exception as e:
            logger.error(f"转换线程错误: {e}", exc_info=True)
            self.error.emit(f"转换失败: {e}")
    
    def stop(self):
        """停止转换"""
        self._is_running = False


class MidiDialog(QDialog):
    """音频转MIDI对话框"""
    
    def __init__(self, audio_path: str, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.conversion_thread = None
        self.midi_data = None
        self.note_events = None
        
        self.setWindowTitle("音频转MIDI")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        
        self._init_ui()
        self._check_availability()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 文件信息
        info_group = QGroupBox("文件信息")
        info_layout = QVBoxLayout()
        
        self.file_label = QLabel(f"音频文件: {Path(self.audio_path).name}")
        info_layout.addWidget(self.file_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 转换参数
        params_group = QGroupBox("转换参数")
        params_layout = QVBoxLayout()
        
        # 音符起始阈值
        onset_layout = QHBoxLayout()
        onset_layout.addWidget(QLabel("音符起始阈值:"))
        self.onset_slider = QSlider(Qt.Orientation.Horizontal)
        self.onset_slider.setMinimum(0)
        self.onset_slider.setMaximum(100)
        self.onset_slider.setValue(50)
        self.onset_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.onset_slider.setTickInterval(10)
        self.onset_value = QLabel("0.50")
        self.onset_slider.valueChanged.connect(
            lambda v: self.onset_value.setText(f"{v/100:.2f}")
        )
        onset_layout.addWidget(self.onset_slider)
        onset_layout.addWidget(self.onset_value)
        params_layout.addLayout(onset_layout)
        
        # 帧阈值
        frame_layout = QHBoxLayout()
        frame_layout.addWidget(QLabel("帧阈值:"))
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(100)
        self.frame_slider.setValue(30)
        self.frame_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.frame_slider.setTickInterval(10)
        self.frame_value = QLabel("0.30")
        self.frame_slider.valueChanged.connect(
            lambda v: self.frame_value.setText(f"{v/100:.2f}")
        )
        frame_layout.addWidget(self.frame_slider)
        frame_layout.addWidget(self.frame_value)
        params_layout.addLayout(frame_layout)
        
        # 最小音符长度
        note_length_layout = QHBoxLayout()
        note_length_layout.addWidget(QLabel("最小音符长度 (ms):"))
        self.note_length_spin = QDoubleSpinBox()
        self.note_length_spin.setMinimum(10.0)
        self.note_length_spin.setMaximum(1000.0)
        self.note_length_spin.setValue(127.70)
        self.note_length_spin.setSingleStep(10.0)
        note_length_layout.addWidget(self.note_length_spin)
        note_length_layout.addStretch()
        params_layout.addLayout(note_length_layout)
        
        # 频率范围
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("频率范围 (Hz):"))
        self.min_freq_spin = QDoubleSpinBox()
        self.min_freq_spin.setMinimum(20.0)
        self.min_freq_spin.setMaximum(2000.0)
        self.min_freq_spin.setValue(65.41)
        self.min_freq_spin.setSingleStep(10.0)
        freq_layout.addWidget(self.min_freq_spin)
        freq_layout.addWidget(QLabel("-"))
        self.max_freq_spin = QDoubleSpinBox()
        self.max_freq_spin.setMinimum(100.0)
        self.max_freq_spin.setMaximum(5000.0)
        self.max_freq_spin.setValue(2093.00)
        self.max_freq_spin.setSingleStep(100.0)
        freq_layout.addWidget(self.max_freq_spin)
        params_layout.addLayout(freq_layout)
        
        # 高级选项
        self.melodia_check = QCheckBox("使用Melodia技巧（改善单音检测）")
        self.melodia_check.setChecked(True)
        params_layout.addWidget(self.melodia_check)
        
        self.pitch_bend_check = QCheckBox("支持多个音高弯曲")
        self.pitch_bend_check.setChecked(False)
        params_layout.addWidget(self.pitch_bend_check)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # 提示信息
        tip_label = QLabel(
            "💡 提示：\n"
            "• 音符起始阈值：较高值会减少误检，但可能漏掉轻音\n"
            "• 帧阈值：较高值会使音符更短，较低值会使音符更长\n"
            "• 最小音符长度：过滤掉过短的音符片段"
        )
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(tip_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.clicked.connect(self._on_convert)
        button_layout.addWidget(self.convert_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _check_availability(self):
        """检查转换器可用性"""
        converter = get_converter()
        if not converter.is_available():
            self.status_label.setText(
                "⚠️ Basic Pitch 未安装\n"
                "请运行: pip install basic-pitch"
            )
            self.status_label.setStyleSheet("color: orange;")
            self.convert_btn.setEnabled(False)
    
    def _on_convert(self):
        """开始转换"""
        # 选择输出文件
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存MIDI文件",
            str(Path(self.audio_path).with_suffix('.mid')),
            "MIDI文件 (*.mid *.midi)"
        )
        
        if not output_path:
            return
        
        # 收集参数
        params = {
            'onset_threshold': self.onset_slider.value() / 100.0,
            'frame_threshold': self.frame_slider.value() / 100.0,
            'minimum_note_length': self.note_length_spin.value(),
            'minimum_frequency': self.min_freq_spin.value(),
            'maximum_frequency': self.max_freq_spin.value(),
            'melodia_trick': self.melodia_check.isChecked(),
            'multiple_pitch_bends': self.pitch_bend_check.isChecked(),
        }
        
        # 禁用控件
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 启动转换线程
        self.conversion_thread = MidiConversionThread(
            self.audio_path,
            output_path,
            params
        )
        self.conversion_thread.progress.connect(self._on_progress)
        self.conversion_thread.finished.connect(self._on_finished)
        self.conversion_thread.error.connect(self._on_error)
        self.conversion_thread.start()
    
    def _on_progress(self, message: str):
        """更新进度"""
        self.status_label.setText(message)
    
    def _on_finished(self, midi_data, note_events, message):
        """转换完成"""
        self.midi_data = midi_data
        self.note_events = note_events
        
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"✅ {message}")
        self.status_label.setStyleSheet("color: green;")
        
        QMessageBox.information(
            self,
            "转换完成",
            f"{message}\n\nMIDI文件已保存"
        )
        
        self.accept()
    
    def _on_error(self, error_msg: str):
        """转换错误"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ {error_msg}")
        self.status_label.setStyleSheet("color: red;")
        self.convert_btn.setEnabled(True)
        
        QMessageBox.critical(self, "转换失败", error_msg)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.conversion_thread.wait()
        event.accept()
