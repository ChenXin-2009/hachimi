"""
智能匹配引擎 - 将素材片段匹配到原曲音轨
"""
import numpy as np
import librosa
from typing import List, Tuple
import logging
from src.models.track import Track
from src.remix.segment_detector import Segment

logger = logging.getLogger(__name__)


class MatchPoint:
    """匹配点"""
    
    def __init__(self, position: float, segment: Segment, confidence: float, 
                 pitch_shift: float = 0.0):
        self.position = position  # 插入位置（秒）
        self.segment = segment  # 要插入的片段
        self.confidence = confidence  # 匹配置信度 (0-1)
        self.pitch_shift = pitch_shift  # 需要调整的半音数
    
    def __repr__(self):
        return f"MatchPoint(pos={self.position:.2f}s, segment={self.segment.name}, conf={self.confidence:.2f}, shift={self.pitch_shift:+.1f})"


class RemixMatcher:
    """智能匹配引擎"""
    
    def __init__(self):
        self.pitch_tolerance = 2.0  # 音高容差（半音）
        self.min_confidence = 0.3  # 最小置信度
    
    def analyze_track(self, track: Track) -> dict:
        """
        分析音轨特征
        
        Args:
            track: 音轨对象
            
        Returns:
            特征字典
        """
        logger.info(f"分析音轨: {track.name}")
        
        # 使用第一个声道
        audio = track.audio_data[0]
        sr = track.sample_rate
        
        # 提取音高轮廓
        pitches, magnitudes = librosa.piptrack(
            y=audio,
            sr=sr,
            fmin=50,
            fmax=2000
        )
        
        # 提取每个时间点的主要音高
        pitch_contour = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            pitch_contour.append(pitch)
        
        pitch_contour = np.array(pitch_contour)
        
        # 检测节拍
        tempo, beats = librosa.beat.beat_track(y=audio, sr=sr)
        beat_times = librosa.frames_to_time(beats, sr=sr)
        
        # 计算能量包络
        rms = librosa.feature.rms(y=audio)[0]
        
        # 确保 tempo 是 Python float
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo.item()) if tempo.size == 1 else float(tempo[0])
        else:
            tempo = float(tempo)
        
        features = {
            'pitch_contour': pitch_contour,
            'beat_times': beat_times,
            'tempo': tempo,
            'energy': rms,
            'sample_rate': sr,
            'hop_length': 512  # librosa 默认
        }
        
        logger.info(f"音轨分析完成: tempo={tempo:.1f} BPM, beats={len(beat_times)}")
        return features
    
    def find_match_points(self, track: Track, segments: List[Segment], 
                         max_matches: int = 50) -> List[MatchPoint]:
        """
        找到所有可能的匹配点
        
        Args:
            track: 目标音轨
            segments: 素材片段列表
            max_matches: 最大匹配数量
            
        Returns:
            匹配点列表（按置信度排序）
        """
        logger.info(f"开始匹配 {len(segments)} 个片段到音轨 {track.name}")
        
        # 分析音轨
        features = self.analyze_track(track)
        
        all_matches = []
        
        # 对每个片段找匹配点
        for segment in segments:
            matches = self._find_matches_for_segment(segment, features, track)
            all_matches.extend(matches)
        
        # 按置信度排序
        all_matches.sort(key=lambda m: m.confidence, reverse=True)
        
        # 限制数量
        all_matches = all_matches[:max_matches]
        
        logger.info(f"找到 {len(all_matches)} 个匹配点")
        return all_matches
    
    def _find_matches_for_segment(self, segment: Segment, features: dict, 
                                  track: Track) -> List[MatchPoint]:
        """为单个片段找匹配点"""
        matches = []
        
        pitch_contour = features['pitch_contour']
        beat_times = features['beat_times']
        sr = features['sample_rate']
        hop_length = features['hop_length']
        
        # 在节拍点附近搜索
        for beat_time in beat_times:
            # 获取该位置的音高
            frame_idx = int(beat_time * sr / hop_length)
            if frame_idx >= len(pitch_contour):
                continue
            
            target_pitch = pitch_contour[frame_idx]
            
            if target_pitch == 0 or segment.pitch == 0:
                continue
            
            # 计算音高差异（半音）
            pitch_diff = 12 * np.log2(target_pitch / segment.pitch)
            
            # 如果音高差异在容差范围内
            if abs(pitch_diff) <= self.pitch_tolerance * 2:  # 放宽一点
                # 计算置信度
                pitch_similarity = 1.0 - abs(pitch_diff) / 12.0
                pitch_similarity = max(0, pitch_similarity)
                
                # 简单的置信度计算
                confidence = pitch_similarity * 0.8 + 0.2  # 基础分
                
                if confidence >= self.min_confidence:
                    match = MatchPoint(
                        position=beat_time,
                        segment=segment,
                        confidence=confidence,
                        pitch_shift=pitch_diff
                    )
                    matches.append(match)
        
        return matches
    
    def auto_arrange(self, track: Track, segments: List[Segment], 
                    density: float = 0.5) -> List[MatchPoint]:
        """
        自动编排 - 智能分布片段
        
        Args:
            track: 目标音轨
            segments: 素材片段列表
            density: 密度 (0-1)，控制插入频率
            
        Returns:
            最终的匹配点列表
        """
        logger.info(f"自动编排: density={density}")
        
        # 找到所有可能的匹配点
        all_matches = self.find_match_points(track, segments, max_matches=200)
        
        # 根据密度筛选
        target_count = int(len(all_matches) * density)
        
        # 选择分布均匀的匹配点
        selected_matches = self._select_distributed_matches(all_matches, target_count)
        
        logger.info(f"自动编排完成: 选择了 {len(selected_matches)} 个匹配点")
        return selected_matches
    
    def _select_distributed_matches(self, matches: List[MatchPoint], 
                                    target_count: int) -> List[MatchPoint]:
        """选择分布均匀的匹配点"""
        if len(matches) <= target_count:
            return matches
        
        # 按位置排序
        sorted_matches = sorted(matches, key=lambda m: m.position)
        
        # 均匀采样
        step = len(sorted_matches) / target_count
        selected = []
        
        for i in range(target_count):
            idx = int(i * step)
            selected.append(sorted_matches[idx])
        
        return selected
