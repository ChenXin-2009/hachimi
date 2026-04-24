# 音频编辑器性能优化方案

## 问题分析

当前程序在快速开关轨道时出现延迟和未响应的问题，主要原因：

### 1. **实时重新混音开销过大**
- 每次切换静音/独奏状态都会触发 `reload_mix()`
- `reload_mix()` 会重新混合所有音轨的完整音频数据
- 没有防抖（debounce）机制，快速操作会导致大量重复计算

### 2. **UI 更新阻塞主线程**
- 音频处理在主线程执行
- 波形渲染和音频混合同步进行
- 没有使用后台线程处理耗时操作

### 3. **缺少缓存机制**
- 每次都重新应用音轨效果（音量、平衡等）
- 没有缓存处理后的音频数据

### 4. **波形渲染效率低**
- 每次更新都重新绘制完整波形
- 没有使用视口裁剪优化

## 开源软件参考方案

### Audacity 的优化策略
1. **延迟更新（Deferred Updates）**: 使用定时器批量处理 UI 更新
2. **后台线程**: 音频处理在独立线程执行
3. **块缓存（Block Cache）**: 音频数据分块存储和处理
4. **视图优化**: 只渲染可见区域的波形

### 其他 DAW 软件的通用做法
1. **防抖/节流**: 限制高频操作的执行频率
2. **异步混音**: 使用线程池处理音频混合
3. **增量更新**: 只更新变化的部分
4. **音频缓冲区管理**: 使用环形缓冲区减少内存分配

## 优化方案

### 方案 1: 添加防抖机制（立即实施）

**优先级**: 🔴 高
**难度**: 简单
**效果**: 显著减少重复计算

在 `TrackManager` 中添加防抖定时器：

```python
class TrackManager:
    def __init__(self):
        # ... 现有代码 ...
        self._reload_timer = QTimer()
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._do_reload_mix)
        self._reload_debounce_ms = 150  # 150ms 防抖延迟
    
    def update_track_param(self, track_id: str, param: str, value):
        # ... 更新参数 ...
        
        # 使用防抖延迟重新混音
        self._reload_timer.start(self._reload_debounce_ms)
    
    def _do_reload_mix(self):
        """实际执行重新混音"""
        if self.audio_player:
            self.audio_player.reload_mix()
```

### 方案 2: 异步音频处理（推荐）

**优先级**: 🔴 高
**难度**: 中等
**效果**: 防止 UI 冻结

使用 QThreadPool 在后台线程处理音频混合：

```python
from PyQt6.QtCore import QRunnable, QThreadPool

class MixAudioTask(QRunnable):
    def __init__(self, mixer, tracks, callback):
        super().__init__()
        self.mixer = mixer
        self.tracks = tracks
        self.callback = callback
    
    def run(self):
        mixed_audio = self.mixer.mix_tracks(self.tracks)
        self.callback(mixed_audio)

class AudioPlayer:
    def __init__(self):
        # ... 现有代码 ...
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)
    
    def reload_mix_async(self):
        """异步重新混音"""
        task = MixAudioTask(self.mixer, self._tracks, self._on_mix_complete)
        self.thread_pool.start(task)
    
    def _on_mix_complete(self, mixed_audio):
        """混音完成回调"""
        self._mixed_audio = mixed_audio
```

### 方案 3: 音频效果缓存

**优先级**: 🟡 中
**难度**: 中等
**效果**: 减少重复计算

缓存每个音轨处理后的音频：

```python
class Track:
    def __init__(self):
        # ... 现有代码 ...
        self._processed_cache = None
        self._cache_params = None
    
    def get_processed_audio(self, mixer):
        """获取处理后的音频（带缓存）"""
        current_params = (self.volume_db, self.pan, self.time_offset_ms)
        
        if self._processed_cache is not None and self._cache_params == current_params:
            return self._processed_cache
        
        # 重新处理
        self._processed_cache = mixer.apply_track_effects(self)
        self._cache_params = current_params
        return self._processed_cache
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._processed_cache = None
        self._cache_params = None
```

### 方案 4: 智能混音策略

**优先级**: 🟡 中
**难度**: 简单
**效果**: 减少不必要的混音

只在播放时才实时混音，暂停时延迟混音：

```python
class AudioPlayer:
    def reload_mix(self):
        """重新混合音轨"""
        if self._is_playing:
            # 播放中：立即混音（或使用异步）
            self.reload_mix_async()
        else:
            # 暂停中：标记需要混音，播放时再执行
            self._needs_remix = True
    
    def play(self):
        if self._needs_remix:
            self.reload_mix_async()
            self._needs_remix = False
        # ... 继续播放 ...
```

### 方案 5: 波形渲染优化

**优先级**: 🟢 低
**难度**: 中等
**效果**: 提升视觉响应速度

使用视口裁剪和 LOD（细节层次）：

```python
class TrackRowWidget:
    def update_waveform(self, viewport_only=True):
        """更新波形显示"""
        if viewport_only:
            # 只渲染可见区域
            x_range = self.waveform_plot.viewRange()[0]
            start_sample = int(x_range[0] * self.track.sample_rate)
            end_sample = int(x_range[1] * self.track.sample_rate)
            
            # 根据缩放级别调整采样密度
            if self.zoom_level < 1.0:
                # 缩小时：更稀疏的采样
                step = max(1, int(1.0 / self.zoom_level))
            else:
                # 放大时：更密集的采样
                step = 1
            
            # 只处理可见部分
            visible_audio = self.track.audio_data[0][start_sample:end_sample:step]
            # ... 渲染 ...
```

### 方案 6: 内存池和对象复用

**优先级**: 🟢 低
**难度**: 高
**效果**: 减少 GC 压力

使用 numpy 的预分配缓冲区：

```python
class AudioMixer:
    def __init__(self):
        self._mix_buffer = None
        self._buffer_size = 0
    
    def mix_tracks(self, tracks):
        # 计算所需缓冲区大小
        max_length = max(t.audio_data.shape[1] for t in tracks)
        
        # 复用或扩展缓冲区
        if self._mix_buffer is None or self._buffer_size < max_length:
            self._mix_buffer = np.zeros((2, max_length))
            self._buffer_size = max_length
        else:
            # 清零现有缓冲区
            self._mix_buffer[:, :max_length] = 0
        
        # 在缓冲区中混音
        for track in tracks:
            # ... 混音逻辑 ...
        
        return self._mix_buffer[:, :max_length]
```

## 实施优先级

### 第一阶段（立即实施）
1. ✅ 添加防抖机制（方案 1）
2. ✅ 异步音频处理（方案 2）
3. ✅ 智能混音策略（方案 4）

**预期效果**: 解决 90% 的卡顿问题

### 第二阶段（后续优化）
4. 音频效果缓存（方案 3）
5. 波形渲染优化（方案 5）

**预期效果**: 进一步提升响应速度

### 第三阶段（高级优化）
6. 内存池和对象复用（方案 6）

**预期效果**: 降低内存占用和 GC 延迟

## 性能监控

添加性能监控代码：

```python
import time
import logging

class PerformanceMonitor:
    @staticmethod
    def measure(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            
            if elapsed > 50:  # 超过 50ms 记录警告
                logging.warning(f"{func.__name__} took {elapsed:.2f}ms")
            
            return result
        return wrapper

# 使用示例
@PerformanceMonitor.measure
def mix_tracks(self, tracks):
    # ... 混音逻辑 ...
```

## 参考资源

1. **Audacity 源码**: https://github.com/audacity/audacity
   - 查看 `src/AudioIO.cpp` 了解音频流处理
   - 查看 `src/TrackPanel.cpp` 了解 UI 更新策略

2. **PyQt 多线程最佳实践**: https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/

3. **实时音频处理优化**: https://acestudio.ai/blog/multi-threaded-audio-processing/

4. **防抖/节流工具**: https://pyapp-kit.github.io/superqt/utilities/throttling/

## 测试建议

1. **压力测试**: 创建 10+ 音轨，快速切换静音/独奏
2. **性能分析**: 使用 `cProfile` 找出瓶颈
3. **内存监控**: 使用 `memory_profiler` 检查内存泄漏
4. **响应时间**: 测量从点击到 UI 更新的延迟

```bash
# 性能分析
python -m cProfile -o profile.stats main.py

# 内存分析
python -m memory_profiler main.py
```
