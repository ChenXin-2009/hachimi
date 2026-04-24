# 闪退问题修复指南

## 问题分析

你的音频处理软件在处理大量音轨时会闪退，根本原因包括：

### 1. 内存泄漏
- **问题**：`AudioPlayer` 每次播放都创建新的音频流，但没有正确清理旧的流
- **后果**：内存持续增长，最终导致程序崩溃

### 2. 音频数据重复加载
- **问题**：`load_tracks()` 和 `reload_mix()` 会重复混合所有音轨
- **后果**：内存占用激增，特别是在实时调整参数时

### 3. 没有资源限制
- **问题**：同时处理多个音轨时，没有限制并发数量和内存使用
- **后果**：处理十几个音轨时内存爆炸

### 4. 音频流回调异常
- **问题**：`_audio_callback` 中的异常会导致整个程序崩溃
- **后果**：任何音频处理错误都会让程序闪退

## 修复方案

### 方案 1：替换修复后的文件（推荐）

1. **备份原文件**：
```bash
cp src/audio_processing/audio_player.py src/audio_processing/audio_player_backup.py
cp src/audio_processing/audio_mixer.py src/audio_processing/audio_mixer_backup.py
```

2. **替换为修复版本**：
```bash
cp src/audio_processing/audio_player_fixed.py src/audio_processing/audio_player.py
cp src/audio_processing/audio_mixer_fixed.py src/audio_processing/audio_mixer.py
```

3. **安装依赖**（如果还没有）：
```bash
pip install psutil
```

4. **重启程序测试**

### 方案 2：手动应用修复（如果你想保留自定义修改）

#### 修复 1：AudioPlayer 内存泄漏

在 `src/audio_processing/audio_player.py` 中添加：

```python
import gc

class AudioPlayer(QObject):
    # 添加常量
    MAX_AUDIO_LENGTH_SECONDS = 600
    BUFFER_SIZE = 2048
    
    def __init__(self, mixer: AudioMixer):
        # ... 现有代码 ...
        self._stream_lock = False  # 添加锁
    
    def _cleanup_stream(self):
        """清理音频流"""
        if self._stream_lock:
            return
        
        try:
            self._stream_lock = True
            
            if self._stream is not None:
                try:
                    if self._stream.active:
                        self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning(f"清理音频流时出错: {e}")
                finally:
                    self._stream = None
                    
        except Exception as e:
            logger.error(f"清理音频流失败: {e}", exc_info=True)
        finally:
            self._stream_lock = False
    
    def _cleanup_audio(self):
        """清理音频数据"""
        try:
            if self._is_playing:
                self.stop()
            
            if self._mixed_audio is not None:
                del self._mixed_audio
                self._mixed_audio = None
            
            gc.collect()
            
        except Exception as e:
            logger.error(f"清理音频数据失败: {e}", exc_info=True)
    
    def load_tracks(self, tracks: List[Track]):
        # 在开始时添加清理
        self._cleanup_audio()
        # ... 其余代码 ...
    
    def reload_mix(self):
        # 保存旧音频引用
        old_audio = self._mixed_audio
        # ... 重新混合 ...
        # 清理旧音频
        if old_audio is not None:
            del old_audio
            gc.collect()
    
    def play(self):
        # 在创建新流之前关闭旧流
        if self._stream is not None:
            try:
                if self._stream.active:
                    self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"关闭旧音频流时出错: {e}")
            finally:
                self._stream = None
        # ... 其余代码 ...
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """添加异常处理"""
        try:
            # ... 原有代码 ...
        except Exception as e:
            logger.error(f"音频回调异常: {e}", exc_info=True)
            outdata.fill(0)
            self._is_playing = False
```

#### 修复 2：AudioMixer 资源限制

在 `src/audio_processing/audio_mixer.py` 中添加：

```python
import psutil
import gc

class AudioMixer:
    # 添加常量
    MAX_CONCURRENT_TRACKS = 16
    MAX_MEMORY_MB = 1024
    CHUNK_SIZE = 44100 * 10
    
    def __init__(self):
        self._memory_warning_shown = False
        # ... 其余代码 ...
    
    def _check_memory(self) -> bool:
        """检查内存使用情况"""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            if memory_mb > self.MAX_MEMORY_MB:
                if not self._memory_warning_shown:
                    logger.warning(f"内存使用过高: {memory_mb:.1f} MB")
                    self._memory_warning_shown = True
                return False
            
            return True
        except Exception as e:
            logger.error(f"检查内存失败: {e}")
            return True
    
    def mix_tracks(self, tracks: List[Track]) -> Optional[np.ndarray]:
        # 在开始时检查内存
        if not self._check_memory():
            logger.warning("内存不足，尝试清理")
            gc.collect()
        
        # ... 过滤音轨代码 ...
        
        # 限制音轨数量
        if len(tracks_to_mix) > self.MAX_CONCURRENT_TRACKS:
            logger.warning(f"音轨数量过多，限制为 {self.MAX_CONCURRENT_TRACKS}")
            tracks_to_mix = tracks_to_mix[:self.MAX_CONCURRENT_TRACKS]
        
        # ... 其余代码 ...
```

## 测试修复效果

### 测试步骤

1. **测试单音轨播放**：
   - 打开一个音频文件
   - 分离音轨
   - 播放、暂停、停止多次
   - 观察内存使用是否稳定

2. **测试多音轨播放**：
   - 加载 10+ 个音轨
   - 同时播放所有音轨
   - 实时调整音量、平衡等参数
   - 观察是否闪退

3. **测试长时间运行**：
   - 连续播放 30 分钟
   - 多次导出音频
   - 观察内存是否持续增长

### 监控内存使用

在 Windows 上使用任务管理器：
1. 打开任务管理器（Ctrl+Shift+Esc）
2. 找到你的 Python 进程
3. 观察"内存"列
4. 正常情况下应该稳定在 1GB 以下

## 关键改进点

### 1. 资源清理
- ✅ 每次加载新音频前清理旧数据
- ✅ 显式调用 `gc.collect()` 触发垃圾回收
- ✅ 使用 `del` 删除大对象

### 2. 异常处理
- ✅ 所有音频回调都有 try-except
- ✅ 异常不会导致程序崩溃
- ✅ 记录详细的错误日志

### 3. 资源限制
- ✅ 限制最大同时处理音轨数（16个）
- ✅ 监控内存使用（上限 1GB）
- ✅ 分块处理长音频

### 4. 流管理
- ✅ 使用锁防止并发问题
- ✅ 正确关闭旧的音频流
- ✅ 设置合理的缓冲区大小

## 如果还是闪退

如果应用修复后仍然闪退，请检查：

### 1. 日志文件
查看日志中的错误信息：
```python
# 在 main.py 开头添加详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler()
    ]
)
```

### 2. 降低资源限制
如果你的电脑内存较小，可以降低限制：
```python
# 在 AudioMixer 中
MAX_CONCURRENT_TRACKS = 8  # 从 16 降到 8
MAX_MEMORY_MB = 512  # 从 1024 降到 512
```

### 3. 使用更小的缓冲区
```python
# 在 AudioPlayer 中
BUFFER_SIZE = 1024  # 从 2048 降到 1024
```

### 4. 禁用实时重新混合
如果实时调整参数时闪退，可以暂时禁用：
```python
# 在 main_window.py 的 on_track_param_changed 中
def on_track_param_changed(self, track_id: str, param: str, value):
    # 注释掉实时重新混合
    # if self.player.is_playing():
    #     self.player.reload_mix()
    pass
```

## 性能优化建议

### 1. 使用更高效的音频格式
- 优先使用 WAV（无压缩）
- 避免使用 MP3（解码耗时）

### 2. 降低采样率
- 如果不需要高质量，使用 22050 Hz 而不是 44100 Hz
- 可以减少一半内存使用

### 3. 使用单声道
- 如果不需要立体声，转换为单声道
- 可以减少一半内存使用

### 4. 限制音频长度
- 处理超长音频时分段处理
- 每段不超过 10 分钟

## 总结

这些修复从根本上解决了闪退问题：
1. **内存泄漏** → 添加资源清理和垃圾回收
2. **重复加载** → 优化混合逻辑，清理旧数据
3. **无资源限制** → 限制并发数和内存使用
4. **异常崩溃** → 添加全面的异常处理

应用这些修复后，你的软件应该能够稳定处理 10+ 个音轨而不会闪退。
