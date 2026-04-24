"""
音色匹配器模块

该模块负责分析和匹配音频的音色特征，包括：
- MFCC（梅尔频率倒谱系数）提取
- 频谱质心提取
- 音色相似度计算

需求: 3.1, 3.2
"""

import numpy as np
import librosa
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TimbreMatcher:
    """
    音色匹配器
    
    使用 MFCC 和频谱质心分析音频的音色特征，用于匹配相似音色的素材片段。
    """
    
    def __init__(self, n_mfcc: int = 13):
        """
        初始化音色匹配器
        
        Args:
            n_mfcc: MFCC 系数数量，默认为 13 维
        """
        self.n_mfcc = n_mfcc
        logger.info(f"TimbreMatcher 初始化完成，MFCC 维度: {n_mfcc}")
    
    def extract_mfcc(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        提取 MFCC 特征
        
        使用 librosa.feature.mfcc 提取音频的梅尔频率倒谱系数，
        这些系数能够表示音色的特征。
        
        Args:
            audio: 音频数据（numpy 数组）
            sr: 采样率
            
        Returns:
            MFCC 特征矩阵（n_mfcc × n_frames）
            
        Raises:
            ValueError: 如果音频数据为空或无效
        """
        if audio is None or len(audio) == 0:
            raise ValueError("音频数据为空")
        
        try:
            # 使用 librosa 提取 MFCC 特征
            mfcc = librosa.feature.mfcc(
                y=audio,
                sr=sr,
                n_mfcc=self.n_mfcc
            )
            
            logger.debug(f"MFCC 提取成功，形状: {mfcc.shape}")
            return mfcc
            
        except Exception as e:
            logger.error(f"MFCC 提取失败: {e}")
            raise
    
    def extract_spectral_centroid(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        提取频谱质心
        
        使用 librosa.feature.spectral_centroid 计算频谱质心，
        该特征表示音色的明亮度（频率重心位置）。
        
        Args:
            audio: 音频数据（numpy 数组）
            sr: 采样率
            
        Returns:
            频谱质心数组（1 × n_frames）
            
        Raises:
            ValueError: 如果音频数据为空或无效
        """
        if audio is None or len(audio) == 0:
            raise ValueError("音频数据为空")
        
        try:
            # 使用 librosa 提取频谱质心
            spectral_centroid = librosa.feature.spectral_centroid(
                y=audio,
                sr=sr
            )
            
            logger.debug(f"频谱质心提取成功，形状: {spectral_centroid.shape}")
            return spectral_centroid
            
        except Exception as e:
            logger.error(f"频谱质心提取失败: {e}")
            raise
    
    def calculate_timbre_similarity(self, mfcc1: np.ndarray, mfcc2: np.ndarray) -> float:
        """
        计算音色相似度
        
        使用余弦相似度比较两个 MFCC 特征矩阵。通过时间平均处理变化的音色，
        然后计算两个平均 MFCC 向量之间的余弦相似度。
        
        Args:
            mfcc1: 第一个音频的 MFCC 特征矩阵（n_mfcc × n_frames）
            mfcc2: 第二个音频的 MFCC 特征矩阵（n_mfcc × n_frames）
            
        Returns:
            相似度分数（0-1），1 表示完全相似，0 表示完全不同
            
        Raises:
            ValueError: 如果 MFCC 数据为空或维度不匹配
        """
        if mfcc1 is None or mfcc2 is None:
            raise ValueError("MFCC 数据为空")
        
        if len(mfcc1.shape) != 2 or len(mfcc2.shape) != 2:
            raise ValueError("MFCC 数据必须是二维数组")
        
        if mfcc1.shape[0] != mfcc2.shape[0]:
            raise ValueError(f"MFCC 维度不匹配: {mfcc1.shape[0]} vs {mfcc2.shape[0]}")
        
        try:
            # 时间平均：计算每个 MFCC 系数在时间轴上的平均值
            # 这样可以处理变化的音色，得到一个代表性的音色特征向量
            mfcc1_mean = np.mean(mfcc1, axis=1)  # 形状: (n_mfcc,)
            mfcc2_mean = np.mean(mfcc2, axis=1)  # 形状: (n_mfcc,)
            
            # 计算余弦相似度
            # cosine_similarity = (A · B) / (||A|| * ||B||)
            dot_product = np.dot(mfcc1_mean, mfcc2_mean)
            norm1 = np.linalg.norm(mfcc1_mean)
            norm2 = np.linalg.norm(mfcc2_mean)
            
            # 避免除以零
            if norm1 == 0 or norm2 == 0:
                logger.warning("MFCC 向量范数为零，返回相似度 0")
                return 0.0
            
            cosine_similarity = dot_product / (norm1 * norm2)
            
            # 余弦相似度范围是 [-1, 1]，归一化到 [0, 1]
            # -1 表示完全相反，0 表示正交，1 表示完全相同
            normalized_similarity = (cosine_similarity + 1) / 2
            
            # 确保结果在 [0, 1] 范围内（处理浮点误差）
            normalized_similarity = np.clip(normalized_similarity, 0.0, 1.0)
            
            logger.debug(f"音色相似度计算成功: {normalized_similarity:.4f}")
            return float(normalized_similarity)
            
        except Exception as e:
            logger.error(f"音色相似度计算失败: {e}")
            raise
