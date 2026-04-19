"""
二创生成器 - 将片段插入到音轨生成二创音频
"""
import numpy as np
import logging
from typing import List, Dict
from src.models.track import Track
from src.remix.matcher import MatchPoint
from src.remix.pitch_shifter import PitchShifter

logger = logging.getLogger(__name__)


class RemixGenerator:
    """二创生成器"""
    
    def __init__(self):
        self.pitch_shifter = PitchShifter()
        self.fade_duration = 0.01  # 淡入淡出时长（秒）
    
    def generate_remix_for_all_tracks(self, tracks: List[Track], segments: List, 
                                     full_replace: bool = True) -> List[Track]:
        """
        为所有音轨生成二创版本 - 用素材片段完全替换整个音轨
        
        Args:
            tracks: 原始音轨列表
            segments: 素材片段列表
            full_replace: True=完全替换整个音轨，False=在匹配点插入
            
        Returns:
            新的音轨列表
        """
        logger.info(f"为 {len(tracks)} 个音轨生成二创版本（完全替换模式）")
        
        remix_tracks = []
        for track in tracks:
            if full_replace:
                remix_track = self.generate_full_replacement_remix(track, segments)
            else:
                # 保留旧的插入模式（暂时不用）
                remix_track = track
            remix_tracks.append(remix_track)
        
        return remix_tracks
    
    def generate_full_replacement_remix(self, track: Track, segments: List) -> Track:
        """
        用素材片段完全替换整个音轨，智能选取最匹配的部分
        
        改进策略：
        1. 分析原音轨的音高、响度、节奏
        2. 对于每个位置，从素材中智能选取最匹配的片段
        3. 不是直接用整个片段，而是从片段中提取最匹配的部分
        4. 精确匹配音高和响度
        
        Args:
            track: 原始音轨
            segments: 素材片段列表
            
        Returns:
            新的音轨
        """
        logger.info(f"用素材片段完全替换音轨: {track.name}")
        
        try:
            if not segments:
                logger.warning("没有素材片段，返回静音")
                return Track(
                    name=f"{track.name}_remix",
                    audio_data=np.zeros_like(track.audio_data),
                    sample_rate=track.sample_rate,
                    track_type="remix",
                    source_type=track.source_type
                )
            
            import librosa
            
            sr = track.sample_rate
            audio = track.audio_data[0]  # 使用第一个声道
            
            # 分析原音轨
            logger.info("分析原音轨特征...")
            
            # 1. 提取音高轮廓
            hop_length = 512
            try:
                pitches, magnitudes = librosa.piptrack(
                    y=audio,
                    sr=sr,
                    fmin=50,
                    fmax=2000,
                    hop_length=hop_length
                )
                
                pitch_contour = []
                for t in range(pitches.shape[1]):
                    index = magnitudes[:, t].argmax()
                    pitch = pitches[index, t]
                    pitch_contour.append(pitch if pitch > 0 else 0)
                pitch_contour = np.array(pitch_contour)
            except Exception as e:
                logger.error(f"音高分析失败: {e}")
                pitch_contour = np.zeros(len(audio) // hop_length)
            
            # 2. 提取响度包络（RMS）
            try:
                rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
            except Exception as e:
                logger.error(f"响度分析失败: {e}")
                rms = np.ones(len(pitch_contour))
            
            # 3. 检测节拍
            try:
                tempo, beats = librosa.beat.beat_track(y=audio, sr=sr, hop_length=hop_length)
                beat_frames = librosa.util.fix_frames(beats, x_min=0, x_max=len(pitch_contour))
            except Exception as e:
                logger.warning(f"节拍检测失败: {e}")
                beat_frames = np.arange(0, len(pitch_contour), len(pitch_contour) // 100)
            
            # 归一化响度
            rms_max = np.max(rms)
            if rms_max > 0:
                rms_normalized = rms / rms_max
            else:
                rms_normalized = np.ones_like(rms)
            
            logger.info(f"分析完成: {len(pitch_contour)} 帧, {len(beat_frames)} 个节拍点")
            
            # 创建结果音频
            result_audio = []
            total_samples = track.audio_data.shape[1]
            
            logger.info("开始智能匹配和拼接...")
            
            # 在节拍点位置进行匹配
            for i, beat_frame in enumerate(beat_frames):
                try:
                    if beat_frame >= len(pitch_contour):
                        break
                    
                    # 获取当前位置的特征
                    target_pitch = pitch_contour[beat_frame]
                    target_loudness = rms_normalized[beat_frame]
                    
                    # 如果响度太小，跳过
                    if target_loudness < 0.05:
                        # 计算到下一个节拍的时长
                        if i + 1 < len(beat_frames):
                            next_beat = beat_frames[i + 1]
                            silence_length = (next_beat - beat_frame) * hop_length
                        else:
                            silence_length = hop_length * 2
                        
                        result_audio.append(np.zeros(min(silence_length, total_samples - len(np.concatenate(result_audio)) if result_audio else total_samples)))
                        continue
                    
                    # 计算需要的片段长度（到下一个节拍）
                    if i + 1 < len(beat_frames):
                        next_beat = beat_frames[i + 1]
                        target_length_frames = next_beat - beat_frame
                    else:
                        target_length_frames = 20  # 默认长度
                    
                    target_length_samples = target_length_frames * hop_length
                    
                    # 从素材中智能选取最匹配的部分
                    matched_audio = self._extract_best_match(
                        segments,
                        target_pitch,
                        target_loudness,
                        target_length_samples,
                        sr
                    )
                    
                    if matched_audio is not None and len(matched_audio) > 0:
                        result_audio.append(matched_audio)
                    else:
                        # 如果没有匹配，添加静音
                        result_audio.append(np.zeros(target_length_samples))
                    
                    # 进度日志
                    if i % 50 == 0:
                        progress = i / len(beat_frames) * 100
                        logger.debug(f"匹配进度: {progress:.1f}%")
                        
                except Exception as e:
                    logger.error(f"处理节拍点 {i} 时出错: {e}")
                    continue
            
            if not result_audio:
                logger.warning("没有生成任何音频，返回静音")
                return Track(
                    name=f"{track.name}_remix",
                    audio_data=np.zeros_like(track.audio_data),
                    sample_rate=track.sample_rate,
                    track_type="remix",
                    source_type=track.source_type
                )
            
            # 合并所有片段
            logger.info("合并所有片段...")
            result_audio = np.concatenate(result_audio)
            
            # 裁剪或填充到原始长度
            if len(result_audio) > total_samples:
                result_audio = result_audio[:total_samples]
            elif len(result_audio) < total_samples:
                padding = np.zeros(total_samples - len(result_audio))
                result_audio = np.concatenate([result_audio, padding])
            
            # 归一化，避免削波
            max_val = np.max(np.abs(result_audio))
            if max_val > 0.95:
                result_audio = result_audio * (0.95 / max_val)
            
            # 转换为多声道格式
            num_channels = track.audio_data.shape[0]
            result_audio_multi = np.tile(result_audio, (num_channels, 1))
            
            # 创建新音轨
            remix_track = Track(
                name=f"{track.name}_remix",
                audio_data=result_audio_multi,
                sample_rate=sr,
                track_type="remix",
                source_type=track.source_type
            )
            
            logger.info(f"音轨 {track.name} 二创完成")
            return remix_track
            
        except Exception as e:
            logger.error(f"生成二创音轨失败: {e}", exc_info=True)
            return Track(
                name=f"{track.name}_remix_error",
                audio_data=np.zeros_like(track.audio_data),
                sample_rate=track.sample_rate,
                track_type="remix",
                source_type=track.source_type
            )
    
    def _extract_best_match(self, segments: List, target_pitch: float, 
                           target_loudness: float, target_length: int, sr: int) -> np.ndarray:
        """
        从素材片段中智能提取最匹配的部分
        
        Args:
            segments: 素材片段列表
            target_pitch: 目标音高（Hz）
            target_loudness: 目标响度（0-1）
            target_length: 目标长度（采样点数）
            sr: 采样率
            
        Returns:
            匹配的音频片段
        """
        try:
            import librosa
            
            best_segment = None
            best_score = -1
            best_start_idx = 0
            
            # 遍历所有片段，找到最匹配的部分
            for segment in segments:
                if segment.audio_data is None or len(segment.audio_data) == 0:
                    continue
                
                # 如果片段太短，跳过
                if len(segment.audio_data) < target_length // 2:
                    continue
                
                # 在片段中滑动窗口，找最匹配的位置
                window_size = min(target_length, len(segment.audio_data))
                step = max(1, window_size // 4)  # 步长为窗口的1/4
                
                for start_idx in range(0, len(segment.audio_data) - window_size + 1, step):
                    window_audio = segment.audio_data[start_idx:start_idx + window_size]
                    
                    # 计算窗口的特征
                    try:
                        # 音高
                        pitches, magnitudes = librosa.piptrack(
                            y=window_audio,
                            sr=segment.sample_rate,
                            fmin=50,
                            fmax=2000
                        )
                        
                        if pitches.shape[1] > 0:
                            pitch_values = []
                            for t in range(pitches.shape[1]):
                                idx = magnitudes[:, t].argmax()
                                p = pitches[idx, t]
                                if p > 0:
                                    pitch_values.append(p)
                            
                            window_pitch = np.median(pitch_values) if pitch_values else 0
                        else:
                            window_pitch = 0
                        
                        # 响度
                        window_loudness = np.sqrt(np.mean(window_audio ** 2))
                        
                        # 计算匹配分数
                        score = 0
                        
                        # 音高匹配（权重 0.6）
                        if target_pitch > 0 and window_pitch > 0:
                            pitch_diff = abs(12 * np.log2(window_pitch / target_pitch))
                            pitch_score = max(0, 1 - pitch_diff / 12)  # 差异越小分数越高
                            score += pitch_score * 0.6
                        
                        # 响度匹配（权重 0.4）
                        if window_loudness > 0:
                            loudness_ratio = min(window_loudness, target_loudness) / max(window_loudness, target_loudness)
                            score += loudness_ratio * 0.4
                        
                        # 更新最佳匹配
                        if score > best_score:
                            best_score = score
                            best_segment = segment
                            best_start_idx = start_idx
                            
                    except Exception as e:
                        continue
            
            if best_segment is None:
                return None
            
            # 提取最佳匹配的部分
            window_size = min(target_length, len(best_segment.audio_data) - best_start_idx)
            matched_audio = best_segment.audio_data[best_start_idx:best_start_idx + window_size].copy()
            
            # 调整音高
            if target_pitch > 0 and best_segment.pitch > 0:
                # 重新计算这部分的音高
                try:
                    pitches, magnitudes = librosa.piptrack(
                        y=matched_audio,
                        sr=best_segment.sample_rate,
                        fmin=50,
                        fmax=2000
                    )
                    
                    pitch_values = []
                    for t in range(pitches.shape[1]):
                        idx = magnitudes[:, t].argmax()
                        p = pitches[idx, t]
                        if p > 0:
                            pitch_values.append(p)
                    
                    actual_pitch = np.median(pitch_values) if pitch_values else best_segment.pitch
                    
                    if actual_pitch > 0:
                        pitch_shift = 12 * np.log2(target_pitch / actual_pitch)
                        pitch_shift = np.clip(pitch_shift, -12, 12)
                        
                        matched_audio = self.pitch_shifter.shift_pitch(
                            matched_audio,
                            best_segment.sample_rate,
                            pitch_shift
                        )
                except Exception as e:
                    logger.debug(f"音高调整失败: {e}")
            
            # 重采样
            if best_segment.sample_rate != sr:
                matched_audio = librosa.resample(
                    matched_audio,
                    orig_sr=best_segment.sample_rate,
                    target_sr=sr
                )
            
            # 调整响度
            current_loudness = np.sqrt(np.mean(matched_audio ** 2))
            if current_loudness > 0:
                matched_audio = matched_audio * (target_loudness / current_loudness)
            
            # 调整长度
            if len(matched_audio) > target_length:
                matched_audio = matched_audio[:target_length]
            elif len(matched_audio) < target_length:
                padding = np.zeros(target_length - len(matched_audio))
                matched_audio = np.concatenate([matched_audio, padding])
            
            # 淡入淡出
            fade_samples = min(int(0.005 * sr), len(matched_audio) // 4)
            if fade_samples > 0:
                matched_audio = self.pitch_shifter.apply_fade(
                    matched_audio,
                    fade_in_samples=fade_samples,
                    fade_out_samples=fade_samples
                )
            
            return matched_audio
            
        except Exception as e:
            logger.error(f"提取匹配片段失败: {e}")
            return None
        """
        用素材片段完全替换整个音轨，同时保持原曲的音量和动态特性
        
        策略：
        1. 分析原音轨的音高轮廓和音量包络
        2. 遍历整个音轨，每个位置选择最匹配的素材片段
        3. 调整片段音高以匹配原音轨
        4. 应用原音轨的音量包络到生成的音频
        5. 拼接所有片段形成完整的二创音轨
        
        Args:
            track: 原始音轨
            segments: 素材片段列表
            
        Returns:
            新的音轨
        """
        logger.info(f"用素材片段完全替换音轨: {track.name}")
        
        try:
            if not segments:
                logger.warning("没有素材片段，返回静音")
                return Track(
                    name=f"{track.name}_remix",
                    audio_data=np.zeros_like(track.audio_data),
                    sample_rate=track.sample_rate,
                    track_type="remix",
                    source_type=track.source_type
                )
            
            import librosa
            
            sr = track.sample_rate
            audio = track.audio_data[0]  # 使用第一个声道
            
            # 提取原音轨的音高轮廓
            logger.info("分析原音轨音高...")
            try:
                pitches, magnitudes = librosa.piptrack(
                    y=audio,
                    sr=sr,
                    fmin=50,
                    fmax=2000,
                    hop_length=512
                )
            except Exception as e:
                logger.error(f"音高分析失败: {e}")
                pitches = np.zeros((1, len(audio) // 512))
                magnitudes = np.zeros_like(pitches)
            
            # 提取每个时间帧的主要音高
            pitch_contour = []
            for t in range(pitches.shape[1]):
                try:
                    index = magnitudes[:, t].argmax()
                    pitch = pitches[index, t]
                    pitch_contour.append(pitch if pitch > 0 else 0)
                except Exception as e:
                    pitch_contour.append(0)
            
            pitch_contour = np.array(pitch_contour)
            
            # 提取原音轨的音量包络（RMS能量）
            logger.info("分析原音轨音量包络...")
            try:
                rms = librosa.feature.rms(y=audio, hop_length=512)[0]
            except Exception as e:
                logger.error(f"音量分析失败: {e}")
                rms = np.ones(len(pitch_contour))
            
            # 归一化音量包络到 0-1 范围
            rms_max = np.max(rms)
            if rms_max > 0:
                rms_normalized = rms / rms_max
            else:
                rms_normalized = np.ones_like(rms)
            
            # 计算每帧对应的时间和采样位置
            hop_length = 512
            
            # 创建结果音频
            result_audio = []
            current_sample = 0
            total_samples = track.audio_data.shape[1]
            
            logger.info(f"开始拼接片段，总时长: {total_samples/sr:.2f}秒")
            
            # 遍历整个音轨，用片段填充
            segment_index = 0
            max_iterations = total_samples // 100  # 防止无限循环
            iteration = 0
            
            while current_sample < total_samples and iteration < max_iterations:
                iteration += 1
                
                try:
                    # 获取当前位置的音高和音量
                    current_time = current_sample / sr
                    frame_idx = int(current_time * sr / hop_length)
                    
                    if frame_idx >= len(pitch_contour):
                        break
                    
                    target_pitch = pitch_contour[frame_idx]
                    target_volume = rms_normalized[frame_idx] if frame_idx < len(rms_normalized) else 1.0
                    
                    # 如果音量太小（接近静音），跳过或使用静音
                    if target_volume < 0.01:
                        # 添加短暂静音
                        silence_length = min(hop_length, total_samples - current_sample)
                        result_audio.append(np.zeros(silence_length))
                        current_sample += silence_length
                        continue
                    
                    # 选择最匹配的片段
                    if target_pitch > 0:
                        best_segment = self._select_best_segment(segments, target_pitch)
                    else:
                        # 如果没有音高（静音或噪音），循环使用片段
                        best_segment = segments[segment_index % len(segments)]
                        segment_index += 1
                    
                    if best_segment is None or best_segment.audio_data is None or len(best_segment.audio_data) == 0:
                        logger.warning("片段无效，跳过")
                        current_sample += hop_length
                        continue
                    
                    # 计算需要的音高调整
                    if target_pitch > 0 and best_segment.pitch > 0:
                        pitch_shift = 12 * np.log2(target_pitch / best_segment.pitch)
                        # 限制音高调整范围，避免过度失真
                        pitch_shift = np.clip(pitch_shift, -12, 12)  # 限制在±1个八度
                    else:
                        pitch_shift = 0
                    
                    # 调整音高
                    shifted_audio = self.pitch_shifter.shift_pitch(
                        best_segment.audio_data,
                        best_segment.sample_rate,
                        pitch_shift
                    )
                    
                    if shifted_audio is None or len(shifted_audio) == 0:
                        logger.warning("音高调整失败，使用原片段")
                        shifted_audio = best_segment.audio_data
                    
                    # 重采样到目标采样率
                    if best_segment.sample_rate != sr:
                        shifted_audio = librosa.resample(
                            shifted_audio,
                            orig_sr=best_segment.sample_rate,
                            target_sr=sr
                        )
                    
                    # 应用原音轨的音量（保持动态）
                    shifted_audio = shifted_audio * target_volume
                    
                    # 应用淡入淡出（避免爆音）
                    fade_samples = min(int(0.005 * sr), len(shifted_audio) // 4)  # 5ms 或片段的1/4
                    if fade_samples > 0:
                        shifted_audio = self.pitch_shifter.apply_fade(
                            shifted_audio,
                            fade_in_samples=fade_samples,
                            fade_out_samples=fade_samples
                        )
                    
                    # 添加到结果
                    result_audio.append(shifted_audio)
                    current_sample += len(shifted_audio)
                    
                    # 进度日志
                    if len(result_audio) % 100 == 0:
                        progress = current_sample / total_samples * 100
                        logger.debug(f"拼接进度: {progress:.1f}%")
                        
                except Exception as e:
                    logger.error(f"处理片段时出错: {e}", exc_info=True)
                    # 跳过这个片段，继续处理
                    current_sample += hop_length
                    continue
            
            if not result_audio:
                logger.warning("没有生成任何音频，返回静音")
                return Track(
                    name=f"{track.name}_remix",
                    audio_data=np.zeros_like(track.audio_data),
                    sample_rate=track.sample_rate,
                    track_type="remix",
                    source_type=track.source_type
                )
            
            # 合并所有片段
            logger.info("合并所有片段...")
            result_audio = np.concatenate(result_audio)
            
            # 裁剪或填充到原始长度
            if len(result_audio) > total_samples:
                result_audio = result_audio[:total_samples]
            elif len(result_audio) < total_samples:
                # 填充静音
                padding = np.zeros(total_samples - len(result_audio))
                result_audio = np.concatenate([result_audio, padding])
            
            # 应用原音轨的整体音量包络（更精细的控制）
            logger.info("应用原音轨音量包络...")
            try:
                # 将帧级别的RMS插值到采样级别
                rms_interpolated = np.interp(
                    np.arange(len(result_audio)),
                    np.arange(len(rms_normalized)) * hop_length,
                    rms_normalized
                )
                
                # 应用音量包络
                result_audio = result_audio * rms_interpolated
            except Exception as e:
                logger.warning(f"应用音量包络失败: {e}")
            
            # 归一化到合理范围，避免削波
            max_val = np.max(np.abs(result_audio))
            if max_val > 0.95:
                result_audio = result_audio * (0.95 / max_val)
            
            # 转换为多声道格式
            num_channels = track.audio_data.shape[0]
            result_audio_multi = np.tile(result_audio, (num_channels, 1))
            
            # 创建新音轨
            remix_track = Track(
                name=f"{track.name}_remix",
                audio_data=result_audio_multi,
                sample_rate=sr,
                track_type="remix",
                source_type=track.source_type
            )
            
            logger.info(f"音轨 {track.name} 二创完成")
            return remix_track
            
        except Exception as e:
            logger.error(f"生成二创音轨失败: {e}", exc_info=True)
            # 返回静音轨道而不是崩溃
            return Track(
                name=f"{track.name}_remix_error",
                audio_data=np.zeros_like(track.audio_data),
                sample_rate=track.sample_rate,
                track_type="remix",
                source_type=track.source_type
            )
    
    def _select_best_segment(self, segments: List, target_pitch: float):
        """
        选择最匹配目标音高的片段
        
        Args:
            segments: 片段列表
            target_pitch: 目标音高（Hz）
            
        Returns:
            最佳匹配的片段
        """
        if not segments:
            return None
        
        best_segment = segments[0]
        min_diff = float('inf')
        
        for segment in segments:
            if segment.pitch > 0:
                # 计算音高差异（半音）
                pitch_diff = abs(12 * np.log2(target_pitch / segment.pitch))
                if pitch_diff < min_diff:
                    min_diff = pitch_diff
                    best_segment = segment
        
        return best_segment
    
    def generate_remix(self, track: Track, match_points: List[MatchPoint], 
                      replace_mode: bool = True) -> Track:
        """
        生成单个音轨的二创版本
        
        Args:
            track: 原始音轨
            match_points: 匹配点列表
            replace_mode: True=完全替换，False=混合
            
        Returns:
            新的音轨
        """
        logger.info(f"生成音轨 {track.name} 的二创版本")
        
        # 复制原音轨数据
        result_audio = track.audio_data.copy()
        sr = track.sample_rate
        
        # 计算淡入淡出采样数
        fade_samples = int(self.fade_duration * sr)
        
        # 插入每个片段
        for i, match in enumerate(match_points):
            logger.debug(f"插入片段 {i+1}/{len(match_points)}: {match}")
            
            # 调整音高
            shifted_audio = self.pitch_shifter.shift_pitch(
                match.segment.audio_data,
                match.segment.sample_rate,
                match.pitch_shift
            )
            
            # 重采样到目标采样率（如果需要）
            if match.segment.sample_rate != sr:
                import librosa
                shifted_audio = librosa.resample(
                    shifted_audio,
                    orig_sr=match.segment.sample_rate,
                    target_sr=sr
                )
            
            # 应用淡入淡出
            shifted_audio = self.pitch_shifter.apply_fade(
                shifted_audio,
                fade_in_samples=fade_samples,
                fade_out_samples=fade_samples
            )
            
            # 计算插入位置（采样点）
            insert_pos = int(match.position * sr)
            segment_length = len(shifted_audio)
            
            # 检查边界
            if insert_pos + segment_length > result_audio.shape[1]:
                segment_length = result_audio.shape[1] - insert_pos
                shifted_audio = shifted_audio[:segment_length]
            
            if insert_pos < 0:
                continue
            
            # 替换或混合音频
            for ch in range(result_audio.shape[0]):
                if replace_mode:
                    # 完全替换模式
                    result_audio[ch, insert_pos:insert_pos+segment_length] = shifted_audio[:len(result_audio[ch, insert_pos:insert_pos+segment_length])]
                else:
                    # 混合模式
                    original = result_audio[ch, insert_pos:insert_pos+segment_length]
                    mixed = original * 0.3 + shifted_audio[:len(original)] * 0.7
                    result_audio[ch, insert_pos:insert_pos+segment_length] = mixed
        
        # 创建新音轨
        remix_track = Track(
            name=f"{track.name}_remix",
            audio_data=result_audio,
            sample_rate=sr,
            track_type="remix",
            source_type=track.source_type
        )
        
        logger.info(f"音轨 {track.name} 二创完成")
        return remix_track
    
    def preview_segment(self, match_point: MatchPoint) -> np.ndarray:
        """
        预览单个片段（调整音高后）
        
        Args:
            match_point: 匹配点
            
        Returns:
            处理后的音频数据
        """
        shifted_audio = self.pitch_shifter.shift_pitch(
            match_point.segment.audio_data,
            match_point.segment.sample_rate,
            match_point.pitch_shift
        )
        
        return shifted_audio
