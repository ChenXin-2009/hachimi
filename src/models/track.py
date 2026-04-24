"""
音轨数据模型
"""
from dataclasses import dataclass, field
import numpy as np
from typing import Optional
import uuid


@dataclass
class Track:
    """音轨数据类"""
    
    # 基本信息
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    audio_data: Optional[np.ndarray] = None
    sample_rate: int = 44100
    track_type: str = "separated"  # "separated" 或 "replacement"
    source_type: str = "other"  # "vocals", "drums", "bass", "other", "guitar", "piano"
    
    # 可调参数
    volume_db: float = 0.0  # -60 到 +12 dB
    pan: float = 0.0  # -1.0 (左) 到 +1.0 (右)
    time_offset_ms: float = 0.0  # -10000 到 +10000 毫秒
    muted: bool = False
    solo: bool = False
    
    # 性能优化：音频效果缓存
    _processed_cache: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _cache_params: Optional[tuple] = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.name:
            self.name = self.source_type.capitalize()
        
        # 初始化缓存
        self._processed_cache = None
        self._cache_params = None
    
    def get_cache_key(self) -> tuple:
        """获取缓存键（基于影响音频处理的参数）"""
        return (self.volume_db, self.pan, self.time_offset_ms)
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._processed_cache = None
        self._cache_params = None
    
    def get_processed_audio(self, mixer) -> Optional[np.ndarray]:
        """
        获取处理后的音频（带缓存）
        
        Args:
            mixer: AudioMixer 实例
            
        Returns:
            处理后的音频数据
        """
        current_params = self.get_cache_key()
        
        # 检查缓存是否有效
        if self._processed_cache is not None and self._cache_params == current_params:
            return self._processed_cache
        
        # 重新处理音频
        self._processed_cache = mixer.apply_track_effects(self)
        self._cache_params = current_params
        
        return self._processed_cache
    
    def get_duration_ms(self) -> float:
        """
        获取音轨时长（毫秒）
        
        Returns:
            时长（毫秒）
        """
        if self.audio_data is None:
            return 0.0
        
        # audio_data 形状: (channels, samples)
        num_samples = self.audio_data.shape[-1]
        duration_seconds = num_samples / self.sample_rate
        return duration_seconds * 1000.0
    
    def clone(self) -> 'Track':
        """
        克隆音轨（深拷贝）
        
        Returns:
            新的音轨实例
        """
        cloned = Track(
            id=self.id,
            name=self.name,
            audio_data=self.audio_data.copy() if self.audio_data is not None else None,
            sample_rate=self.sample_rate,
            track_type=self.track_type,
            source_type=self.source_type,
            volume_db=self.volume_db,
            pan=self.pan,
            time_offset_ms=self.time_offset_ms,
            muted=self.muted,
            solo=self.solo
        )
        # 不复制缓存，让新实例重新计算
        return cloned
