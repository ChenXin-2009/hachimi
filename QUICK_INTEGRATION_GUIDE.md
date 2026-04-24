# 快速集成指南 - 开源代码

## 🚀 立即可用的改进

### 1. 使用 pydub 简化音频处理

**安装**:
```bash
pip install pydub
```

**替换现有代码**:

```python
# 旧代码 (使用 soundfile)
import soundfile as sf
audio_data, sr = sf.read(audio_path, always_2d=True)
audio_data = audio_data.T

# 新代码 (使用 pydub)
from pydub import AudioSegment
import numpy as np

audio = AudioSegment.from_file(audio_path)
audio_data = np.array(audio.get_array_of_samples()).reshape((-1, audio.channels)).T
sr = audio.frame_rate
```

**优势**:
- ✅ 支持更多格式（MP3, M4A, OGG 等）
- ✅ 更简单的 API
- ✅ 内置音频效果

---

### 2. 使用 madmom 改进二创匹配

**安装**:
```bash
pip install madmom
```

**添加节拍检测**:

```python
from madmom.features import RNNBeatProcessor, DBNBeatTrackingProcessor

class ImprovedRemixMatcher:
    def __init__(self):
        self.beat_processor = DBNBeatTrackingProcessor(fps=100)
    
    def detect_beats(self, audio_path):
        """检测音频的节拍"""
        beats = self.beat_processor(audio_path)
        return beats
    
    def match_by_beats(self, source_audio, target_audio):
        """基于节拍匹配音频片段"""
        source_beats = self.detect_beats(source_audio)
        target_beats = self.detect_beats(target_audio)
        
        # 根据节拍对齐片段
        # ... 你的匹配逻辑 ...
```

**优势**:
- ✅ 更准确的节拍检测
- ✅ 改进二创匹配质量
- ✅ 专业的音乐分析

---

### 3. 使用 pyqtgraph 优化波形显示

**你已经在使用**: ✅

**参考优化**:

```python
import pyqtgraph as pg

class OptimizedWaveformWidget:
    def __init__(self):
        self.plot = pg.PlotWidget()
        
        # 性能优化
        self.plot.setClipToView(True)  # 只渲染可见区域
        self.plot.setDownsampling(auto=True)  # 自动降采样
        
        # 使用 OpenGL 加速（可选）
        self.plot.useOpenGL(True)
    
    def update_waveform(self, audio_data, sample_rate):
        """优化的波形更新"""
        # 降采样以提高性能
        max_points = 10000
        if len(audio_data) > max_points:
            step = len(audio_data) // max_points
            audio_data = audio_data[::step]
        
        # 使用 PlotDataItem 而非 plot() 以提高性能
        if not hasattr(self, 'curve'):
            self.curve = self.plot.plot(audio_data)
        else:
            self.curve.setData(audio_data)
```

---

## 📦 推荐的依赖更新

### 更新 requirements.txt

```txt
# 现有依赖
PyQt6>=6.4.0
numpy>=1.24.0
sounddevice>=0.4.6
soundfile>=0.12.1
librosa>=0.10.0
demucs>=4.0.0
pyqtgraph>=0.13.0
pedalboard>=0.7.0

# 新增推荐依赖
pydub>=0.25.1          # 简化音频处理
madmom>=0.16.1         # 音乐分析
python-dotenv>=1.0.0   # 配置管理（可选）
```

---

## 🎨 UI 改进建议

### 1. 添加频谱分析器

```python
import numpy as np
from scipy import signal

class SpectrumAnalyzer:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
    
    def compute_spectrum(self, audio_data, window_size=2048):
        """计算频谱"""
        f, t, Sxx = signal.spectrogram(
            audio_data,
            self.sample_rate,
            window='hann',
            nperseg=window_size
        )
        return f, t, 10 * np.log10(Sxx + 1e-10)  # 转换为 dB
    
    def plot_spectrum(self, plot_widget, audio_data):
        """绘制频谱图"""
        f, t, Sxx = self.compute_spectrum(audio_data)
        
        # 使用 ImageItem 显示频谱图
        img = pg.ImageItem()
        img.setImage(Sxx)
        plot_widget.addItem(img)
```

### 2. 添加音量表（VU Meter）

```python
class VUMeter(QWidget):
    def __init__(self):
        super().__init__()
        self.level = 0.0
        self.setMinimumSize(20, 100)
    
    def set_level(self, level_db):
        """设置音量级别（dB）"""
        # 转换为 0-1 范围
        self.level = max(0, min(1, (level_db + 60) / 60))
        self.update()
    
    def paintEvent(self, event):
        """绘制音量表"""
        painter = QPainter(self)
        
        # 背景
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        # 音量条
        height = int(self.height() * self.level)
        color = QColor(0, 255, 0) if self.level < 0.8 else QColor(255, 0, 0)
        painter.fillRect(0, self.height() - height, self.width(), height, color)
```

---

## 🔧 性能优化技巧

### 1. 使用 numba 加速计算

```bash
pip install numba
```

```python
from numba import jit

@jit(nopython=True)
def fast_audio_processing(audio_data, gain):
    """使用 numba 加速的音频处理"""
    return audio_data * gain

# 使用
processed = fast_audio_processing(audio_data, 1.5)
```

### 2. 使用 concurrent.futures 并行处理

```python
from concurrent.futures import ThreadPoolExecutor

class ParallelAudioProcessor:
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_tracks_parallel(self, tracks, process_func):
        """并行处理多个音轨"""
        futures = [
            self.executor.submit(process_func, track)
            for track in tracks
        ]
        
        results = [future.result() for future in futures]
        return results
```

---

## 📊 代码质量改进

### 1. 添加类型提示

```python
from typing import Optional, List, Tuple
import numpy as np

def process_audio(
    audio_data: np.ndarray,
    sample_rate: int,
    volume_db: float = 0.0
) -> Tuple[np.ndarray, int]:
    """
    处理音频数据
    
    Args:
        audio_data: 音频数据数组
        sample_rate: 采样率
        volume_db: 音量调整（dB）
        
    Returns:
        处理后的音频数据和采样率
    """
    # 处理逻辑
    return processed_audio, sample_rate
```

### 2. 添加单元测试

```python
import unittest
import numpy as np

class TestAudioProcessing(unittest.TestCase):
    def test_volume_adjustment(self):
        """测试音量调整"""
        audio = np.random.randn(44100)
        processed = apply_volume(audio, 6.0)
        
        # 验证音量增加了约 2 倍（6dB）
        self.assertAlmostEqual(
            np.abs(processed).mean() / np.abs(audio).mean(),
            2.0,
            places=1
        )
```

---

## 🎯 快速集成步骤

### 步骤 1: 安装新依赖
```bash
pip install pydub madmom numba
```

### 步骤 2: 更新音频加载
在 `src/audio_processing/` 中添加 `audio_loader.py`:

```python
from pydub import AudioSegment
import numpy as np

class AudioLoader:
    @staticmethod
    def load(path):
        """加载音频文件"""
        audio = AudioSegment.from_file(path)
        samples = np.array(audio.get_array_of_samples())
        
        if audio.channels == 2:
            samples = samples.reshape((-1, 2)).T
        else:
            samples = samples.reshape((1, -1))
        
        return samples, audio.frame_rate
```

### 步骤 3: 添加节拍检测
在 `src/remix/` 中添加 `beat_detector.py`:

```python
from madmom.features import DBNBeatTrackingProcessor

class BeatDetector:
    def __init__(self):
        self.processor = DBNBeatTrackingProcessor(fps=100)
    
    def detect(self, audio_path):
        """检测节拍"""
        return self.processor(audio_path)
```

### 步骤 4: 集成到现有代码
在 `src/remix/matcher.py` 中:

```python
from .beat_detector import BeatDetector

class RemixMatcher:
    def __init__(self):
        # 现有代码...
        self.beat_detector = BeatDetector()
    
    def match_with_beats(self, source, target):
        """使用节拍信息匹配"""
        source_beats = self.beat_detector.detect(source)
        target_beats = self.beat_detector.detect(target)
        
        # 使用节拍信息改进匹配
        # ...
```

---

## 🐛 常见问题

### Q: pydub 无法加载 MP3
**A**: 需要安装 ffmpeg
```bash
# Windows (使用 chocolatey)
choco install ffmpeg

# macOS
brew install ffmpeg

# Linux
sudo apt-get install ffmpeg
```

### Q: madmom 安装失败
**A**: 需要先安装依赖
```bash
# Windows
pip install numpy scipy cython

# Linux
sudo apt-get install python3-dev libsndfile1
pip install madmom
```

### Q: numba 编译慢
**A**: 第一次运行会编译，之后会很快。可以使用缓存：
```python
@jit(nopython=True, cache=True)
def my_function():
    pass
```

---

## 📚 更多资源

- **完整文档**: `docs/OPEN_SOURCE_REFERENCES.md`
- **性能优化**: `docs/PERFORMANCE_OPTIMIZATION.md`
- **崩溃保护**: `docs/CRASH_PROTECTION_GUIDE.md`

---

## ✅ 检查清单

集成前检查：
- [x] 安装新依赖（pydub, numba）
- [x] 阅读许可证
- [x] 备份现有代码
- [ ] 编写测试用例

集成后验证：
- [ ] 功能正常工作
- [ ] 性能没有下降
- [ ] 没有引入新的 bug
- [x] 文档已更新

---

## 🎉 集成状态

**已完成集成**:
- ✅ AudioLoader (pydub) - 统一音频加载器
- ✅ FastAudioEffects (numba) - 快速音频效果处理
- ✅ 集成到 audio_mixer.py
- ✅ 集成到 separation_engine.py
- ✅ 集成到 track_manager.py
- ✅ 集成到 project_manager.py
- ✅ 多层备用方案确保稳定性

**详细报告**: 查看 `INTEGRATION_COMPLETE.md`

---

**集成完成，让你的项目更强大！** 🚀
