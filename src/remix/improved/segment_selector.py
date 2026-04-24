"""
片段选择器模块

负责智能选择最合适的素材片段，包括：
- 综合匹配分数计算（音高、节奏、音色、响度）
- 最佳片段选择
- 重复避免机制
- 子片段提取

需求: 5.1, 5.2
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

from src.remix.segment_detector import Segment

logger = logging.getLogger(__name__)


class SegmentSelector:
    """
    片段选择器
    
    智能选择最合适的素材片段，综合考虑多个维度的相似度
    """
    
    def __init__(self, 
                 pitch_weight: float = 0.4,
                 rhythm_weight: float = 0.3,
                 timbre_weight: float = 0.2,
                 loudness_weight: float = 0.1,
                 min_score: float = 0.6,
                 max_repeat: int = 3):
        """
        初始化片段选择器
        
        Args:
            pitch_weight: 音高匹配权重，默认 0.4 (40%)
            rhythm_weight: 节奏匹配权重，默认 0.3 (30%)
            timbre_weight: 音色匹配权重，默认 0.2 (20%)
            loudness_weight: 响度匹配权重，默认 0.1 (10%)
            min_score: 最小匹配分数阈值，默认 0.6
            max_repeat: 最大重复次数，默认 3
            
        需求: 5.2
        """
        self.pitch_weight = pitch_weight
        self.rhythm_weight = rhythm_weight
        self.timbre_weight = timbre_weight
        self.loudness_weight = loudness_weight
        self.min_score = min_score
        self.max_repeat = max_repeat
        
        # 验证权重总和为 1.0
        total_weight = pitch_weight + rhythm_weight + timbre_weight + loudness_weight
        if not np.isclose(total_weight, 1.0):
            logger.warning(f"权重总和不为 1.0: {total_weight:.3f}，将自动归一化")
            self.pitch_weight /= total_weight
            self.rhythm_weight /= total_weight
            self.timbre_weight /= total_weight
            self.loudness_weight /= total_weight
        
        logger.info(f"SegmentSelector 初始化: pitch={self.pitch_weight:.2f}, "
                   f"rhythm={self.rhythm_weight:.2f}, timbre={self.timbre_weight:.2f}, "
                   f"loudness={self.loudness_weight:.2f}, min_score={self.min_score:.2f}, "
                   f"max_repeat={self.max_repeat}")
    
    def calculate_match_score(self, 
                             segment: Segment, 
                             target_features: Dict) -> float:
        """
        计算匹配分数
        
        综合考虑音高、节奏、音色、响度相似度，计算综合匹配分数。
        
        Args:
            segment: 素材片段
            target_features: 目标位置的特征字典，包含：
                - 'pitch': 目标音高（Hz）
                - 'tempo': 目标速度（BPM）
                - 'mfcc': 目标 MFCC 特征
                - 'rms': 目标响度（RMS）
            
        Returns:
            匹配分数（0-1），1 表示完全匹配
            
        需求: 5.1
        """
        # 计算各维度相似度
        pitch_sim = self._calculate_pitch_similarity(segment, target_features)
        rhythm_sim = self._calculate_rhythm_similarity(segment, target_features)
        timbre_sim = self._calculate_timbre_similarity(segment, target_features)
        loudness_sim = self._calculate_loudness_similarity(segment, target_features)
        
        # 综合评分
        score = (self.pitch_weight * pitch_sim +
                self.rhythm_weight * rhythm_sim +
                self.timbre_weight * timbre_sim +
                self.loudness_weight * loudness_sim)
        
        logger.debug(f"片段 '{segment.name}' 匹配分数: {score:.3f} "
                    f"(pitch={pitch_sim:.3f}, rhythm={rhythm_sim:.3f}, "
                    f"timbre={timbre_sim:.3f}, loudness={loudness_sim:.3f})")
        
        return float(score)
    
    def _calculate_pitch_similarity(self, 
                                   segment: Segment, 
                                   target_features: Dict) -> float:
        """
        计算音高相似度
        
        基于半音差异计算相似度，差异越小相似度越高。
        
        Args:
            segment: 素材片段
            target_features: 目标特征字典
            
        Returns:
            音高相似度（0-1）
        """
        # 获取片段音高和目标音高
        source_pitch = segment.pitch if hasattr(segment, 'pitch') and segment.pitch else 0
        target_pitch = target_features.get('pitch', 0)
        
        # 如果任一音高无效，返回 0
        if source_pitch <= 0 or target_pitch <= 0:
            return 0.0
        
        # 计算半音差异
        # semitone_diff = 12 * log2(f2 / f1)
        semitone_diff = abs(12 * np.log2(target_pitch / source_pitch))
        
        # 转换为相似度（0-1）
        # 差异 0 半音 -> 相似度 1.0
        # 差异 12 半音（1 个八度）-> 相似度 0.0
        similarity = max(0.0, 1.0 - semitone_diff / 12.0)
        
        return similarity
    
    def _calculate_rhythm_similarity(self, 
                                    segment: Segment, 
                                    target_features: Dict) -> float:
        """
        计算节奏相似度
        
        基于速度（BPM）比例计算相似度。
        
        Args:
            segment: 素材片段
            target_features: 目标特征字典
            
        Returns:
            节奏相似度（0-1）
        """
        # 获取片段速度和目标速度
        source_tempo = getattr(segment, 'tempo', None)
        target_tempo = target_features.get('tempo', None)
        
        # 如果任一速度无效，返回中等相似度
        if source_tempo is None or target_tempo is None or source_tempo <= 0 or target_tempo <= 0:
            return 0.5
        
        # 计算速度比例
        tempo_ratio = min(source_tempo, target_tempo) / max(source_tempo, target_tempo)
        
        return tempo_ratio
    
    def _calculate_timbre_similarity(self, 
                                    segment: Segment, 
                                    target_features: Dict) -> float:
        """
        计算音色相似度
        
        使用余弦相似度比较 MFCC 特征。
        
        Args:
            segment: 素材片段
            target_features: 目标特征字典
            
        Returns:
            音色相似度（0-1）
        """
        # 获取片段 MFCC 和目标 MFCC
        source_mfcc = getattr(segment, 'mfcc', None)
        target_mfcc = target_features.get('mfcc', None)
        
        # 如果任一 MFCC 无效，返回中等相似度
        if source_mfcc is None or target_mfcc is None:
            return 0.5
        
        try:
            # 时间平均
            if len(source_mfcc.shape) == 2:
                source_mfcc_mean = np.mean(source_mfcc, axis=1)
            else:
                source_mfcc_mean = source_mfcc
            
            if len(target_mfcc.shape) == 2:
                target_mfcc_mean = np.mean(target_mfcc, axis=1)
            else:
                target_mfcc_mean = target_mfcc
            
            # 余弦相似度
            dot_product = np.dot(source_mfcc_mean, target_mfcc_mean)
            norm1 = np.linalg.norm(source_mfcc_mean)
            norm2 = np.linalg.norm(target_mfcc_mean)
            
            # 避免除以零
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            cosine_similarity = dot_product / (norm1 * norm2)
            
            # 归一化到 0-1
            normalized_similarity = (cosine_similarity + 1) / 2
            
            return float(np.clip(normalized_similarity, 0.0, 1.0))
            
        except Exception as e:
            logger.warning(f"音色相似度计算失败: {e}")
            return 0.5
    
    def _calculate_loudness_similarity(self, 
                                      segment: Segment, 
                                      target_features: Dict) -> float:
        """
        计算响度相似度
        
        基于 RMS 响度比例计算相似度。
        
        Args:
            segment: 素材片段
            target_features: 目标特征字典
            
        Returns:
            响度相似度（0-1）
        """
        # 获取片段响度和目标响度
        source_rms = getattr(segment, 'energy', None)
        target_rms = target_features.get('rms', None)
        
        # 如果任一响度无效，返回中等相似度
        if source_rms is None or target_rms is None or source_rms <= 0 or target_rms <= 0:
            return 0.5
        
        # 计算响度比例
        loudness_ratio = min(source_rms, target_rms) / max(source_rms, target_rms)
        
        return loudness_ratio
    
    def select_best_segment(self, 
                           segments: List[Segment], 
                           target_features: Dict,
                           used_segments: List[int]) -> Optional[Segment]:
        """
        选择最佳匹配片段
        
        从素材片段列表中选择最匹配的片段，同时避免过度重复使用同一片段。
        
        Args:
            segments: 素材片段列表
            target_features: 目标位置的特征
            used_segments: 已使用片段的索引列表
            
        Returns:
            最佳匹配片段或 None（如果没有合适的片段）
            
        需求: 5.3
        """
        if not segments:
            logger.warning("片段列表为空")
            return None
        
        # 统计使用次数
        usage_count = {}
        for idx in used_segments:
            usage_count[idx] = usage_count.get(idx, 0) + 1
        
        # 计算每个片段的调整后分数
        candidates = []
        for i, segment in enumerate(segments):
            # 计算基础匹配分数
            base_score = self.calculate_match_score(segment, target_features)
            
            # 根据使用次数降低分数
            repeat_count = usage_count.get(i, 0)
            if repeat_count >= self.max_repeat:
                logger.debug(f"片段 {i} '{segment.name}' 已达到最大重复次数 {self.max_repeat}，跳过")
                continue  # 跳过已达到最大重复次数的片段
            
            # 重复惩罚：使用次数越多，惩罚越大
            repeat_penalty = 1.0 - (repeat_count / self.max_repeat) * 0.5
            adjusted_score = base_score * repeat_penalty
            
            candidates.append((i, segment, adjusted_score))
            logger.debug(f"片段 {i} '{segment.name}': base_score={base_score:.3f}, "
                        f"repeat_count={repeat_count}, adjusted_score={adjusted_score:.3f}")
        
        if not candidates:
            logger.warning("没有可用的候选片段")
            return None
        
        # 选择分数最高的片段
        candidates.sort(key=lambda x: x[2], reverse=True)
        best_idx, best_segment, best_score = candidates[0]
        
        # 检查是否达到最小分数阈值
        if best_score < self.min_score:
            logger.warning(f"最佳片段分数 {best_score:.3f} 低于阈值 {self.min_score:.3f}")
            return None
        
        logger.info(f"选择片段 {best_idx} '{best_segment.name}'，分数: {best_score:.3f}")
        return best_segment
    
    def extract_sub_segment(self, 
                           segment: Segment, 
                           target_duration: float) -> Segment:
        """
        从片段中提取子片段（滑动窗口）
        
        使用滑动窗口在片段中寻找最匹配的子片段。
        
        Args:
            segment: 原始片段
            target_duration: 目标时长（秒）
            
        Returns:
            子片段
            
        需求: 5.4
        """
        sr = segment.sample_rate
        window_size = int(target_duration * sr)
        
        # 如果片段比目标时长短，直接返回原片段
        if len(segment.audio_data) <= window_size:
            logger.debug(f"片段 '{segment.name}' 短于目标时长，返回原片段")
            return segment
        
        # 滑动窗口步长为窗口的 1/4
        step_size = max(1, window_size // 4)
        
        best_score = -1
        best_start = 0
        
        # 滑动窗口寻找最佳子片段
        for start in range(0, len(segment.audio_data) - window_size + 1, step_size):
            sub_audio = segment.audio_data[start:start + window_size]
            
            # 计算子片段的能量（作为简单的质量指标）
            energy = np.sqrt(np.mean(sub_audio ** 2))
            
            if energy > best_score:
                best_score = energy
                best_start = start
        
        # 创建子片段
        sub_audio = segment.audio_data[best_start:best_start + window_size]
        sub_start_time = segment.start_time + (best_start / sr)
        sub_end_time = sub_start_time + target_duration
        
        sub_segment = Segment(
            start_time=sub_start_time,
            end_time=sub_end_time,
            audio_data=sub_audio,
            sample_rate=sr,
            name=f"{segment.name}_sub"
        )
        
        # 复制原片段的特征
        if hasattr(segment, 'pitch'):
            sub_segment.pitch = segment.pitch
        if hasattr(segment, 'energy'):
            sub_segment.energy = segment.energy
        if hasattr(segment, 'tempo'):
            sub_segment.tempo = segment.tempo
        if hasattr(segment, 'mfcc'):
            sub_segment.mfcc = segment.mfcc
        
        logger.debug(f"从片段 '{segment.name}' 提取子片段: "
                    f"[{sub_start_time:.3f}s, {sub_end_time:.3f}s]")
        
        return sub_segment
