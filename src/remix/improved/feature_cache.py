"""
特征缓存管理器

本模块提供特征缓存功能，避免重复计算音频特征，提高处理效率。

使用 LRU（最近最少使用）策略管理缓存，缓存键基于文件路径和修改时间的哈希。
"""

import hashlib
import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureCache:
    """
    特征缓存管理器
    
    使用 LRU 策略管理音频特征缓存，避免重复计算。
    
    Attributes:
        max_size: 最大缓存条目数
        cache: 缓存字典
        access_order: 访问顺序列表（用于 LRU）
    
    Example:
        >>> cache = FeatureCache(max_size=100)
        >>> features = cache.get('/path/to/audio.wav')
        >>> if features is None:
        ...     features = extract_features(audio)
        ...     cache.set('/path/to/audio.wav', features)
    """
    
    def __init__(self, max_size: int = 100):
        """
        初始化特征缓存
        
        Args:
            max_size: 最大缓存条目数，默认 100
        """
        self.max_size = max_size
        self.cache: Dict[str, Dict] = {}
        self.access_order: list = []
        logger.info(f"初始化特征缓存，最大容量: {max_size}")
    
    def _generate_key(self, audio_path: str) -> str:
        """
        生成缓存键
        
        基于文件路径和修改时间生成唯一的哈希键，确保文件修改后缓存失效。
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            缓存键（MD5 哈希字符串）
        """
        try:
            # 获取文件修改时间
            mtime = os.path.getmtime(audio_path)
            # 组合路径和修改时间
            key_str = f"{audio_path}_{mtime}"
            # 生成 MD5 哈希
            return hashlib.md5(key_str.encode()).hexdigest()
        except OSError as e:
            logger.warning(f"无法获取文件修改时间: {audio_path}, 错误: {e}")
            # 如果无法获取修改时间，仅使用路径
            return hashlib.md5(audio_path.encode()).hexdigest()
    
    def get(self, audio_path: str) -> Optional[Dict]:
        """
        获取缓存的特征
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            特征字典，如果缓存不存在则返回 None
        """
        key = self._generate_key(audio_path)
        
        if key in self.cache:
            # 更新访问顺序（LRU）
            self.access_order.remove(key)
            self.access_order.append(key)
            logger.debug(f"缓存命中: {audio_path}")
            return self.cache[key]
        
        logger.debug(f"缓存未命中: {audio_path}")
        return None
    
    def set(self, audio_path: str, features: Dict):
        """
        设置缓存
        
        如果缓存已满，删除最久未使用的条目（LRU 策略）。
        
        Args:
            audio_path: 音频文件路径
            features: 特征字典
        """
        key = self._generate_key(audio_path)
        
        # 如果缓存已满，删除最久未使用的条目
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]
            logger.debug(f"缓存已满，删除最久未使用的条目")
        
        # 如果键已存在，先从访问顺序中移除
        if key in self.access_order:
            self.access_order.remove(key)
        
        # 添加到缓存
        self.cache[key] = features
        self.access_order.append(key)
        logger.debug(f"缓存已更新: {audio_path}")
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.access_order.clear()
        logger.info("缓存已清空")
    
    def size(self) -> int:
        """
        获取当前缓存大小
        
        Returns:
            缓存中的条目数
        """
        return len(self.cache)
    
    def remove(self, audio_path: str) -> bool:
        """
        移除指定路径的缓存
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            是否成功移除
        """
        key = self._generate_key(audio_path)
        
        if key in self.cache:
            del self.cache[key]
            self.access_order.remove(key)
            logger.debug(f"缓存已移除: {audio_path}")
            return True
        
        return False
