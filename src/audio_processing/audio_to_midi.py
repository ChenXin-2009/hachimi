"""
音频转MIDI模块
使用 Basic Pitch 和 CREPE 进行音频到MIDI的转换
"""
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import logging

logger = logging.getLogger(__name__)


class AudioToMidiConverter:
    """音频转MIDI转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.basic_pitch_model = None
        self.backend = None
        self._init_backend()
    
    def _init_backend(self):
        """初始化后端（延迟加载）"""
        try:
            # 尝试导入 Basic Pitch
            import basic_pitch
            from basic_pitch.inference import predict, Model
            from basic_pitch import ICASSP_2022_MODEL_PATH
            
            self.backend = 'basic_pitch'
            self.basic_pitch_model = Model(ICASSP_2022_MODEL_PATH)
            logger.info("Basic Pitch 后端初始化成功")
            
        except ImportError:
            logger.warning("Basic Pitch 未安装，音频转MIDI功能不可用")
            logger.info("请运行: pip install basic-pitch")
            self.backend = None
    
    def is_available(self) -> bool:
        """检查转换器是否可用"""
        return self.backend is not None
    
    def convert(
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
        minimum_note_length: float = 127.70,
        minimum_frequency: float = 65.41,
        maximum_frequency: float = 2093.00,
        multiple_pitch_bends: bool = False,
        melodia_trick: bool = True,
    ) -> Tuple[Optional[object], Optional[List[Dict]], str]:
        """
        将音频转换为MIDI
        
        Args:
            audio_path: 输入音频文件路径
            output_path: 输出MIDI文件路径（可选）
            onset_threshold: 音符起始阈值 (0-1)
            frame_threshold: 帧阈值 (0-1)
            minimum_note_length: 最小音符长度（毫秒）
            minimum_frequency: 最小频率（Hz）
            maximum_frequency: 最大频率（Hz）
            multiple_pitch_bends: 是否支持多个音高弯曲
            melodia_trick: 是否使用melodia技巧改善单音检测
            
        Returns:
            (midi_data, note_events, message)
            - midi_data: MIDI数据对象
            - note_events: 音符事件列表
            - message: 状态消息
        """
        if not self.is_available():
            return None, None, "音频转MIDI功能不可用，请安装 basic-pitch"
        
        try:
            from basic_pitch.inference import predict
            
            logger.info(f"开始转换音频: {audio_path}")
            
            # 执行转换
            model_output, midi_data, note_events = predict(
                audio_path,
                self.basic_pitch_model,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                minimum_note_length=minimum_note_length,
                minimum_frequency=minimum_frequency,
                maximum_frequency=maximum_frequency,
                multiple_pitch_bends=multiple_pitch_bends,
                melodia_trick=melodia_trick,
            )
            
            # 后处理：合并过短的音符片段
            note_events = self._merge_short_notes(note_events)
            
            # 保存MIDI文件
            if output_path:
                midi_data.write(output_path)
                logger.info(f"MIDI文件已保存: {output_path}")
            
            num_notes = len(note_events)
            logger.info(f"转换完成，检测到 {num_notes} 个音符")
            
            return midi_data, note_events, f"成功转换，检测到 {num_notes} 个音符"
            
        except Exception as e:
            error_msg = f"音频转MIDI转换失败: {e}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg
    
    def _merge_short_notes(
        self,
        note_events: List[Dict],
        min_gap: float = 0.05
    ) -> List[Dict]:
        """
        合并时间间隔很短的相同音高音符
        
        Args:
            note_events: 音符事件列表
            min_gap: 最小间隔时间（秒），小于此值的相同音高音符将被合并
            
        Returns:
            合并后的音符事件列表
        """
        if not note_events:
            return note_events
        
        # 按起始时间排序
        sorted_events = sorted(note_events, key=lambda x: x['start_time_seconds'])
        
        merged = []
        for event in sorted_events:
            if merged and \
               event['pitch_midi'] == merged[-1]['pitch_midi'] and \
               event['start_time_seconds'] - merged[-1]['end_time_seconds'] < min_gap:
                # 合并音符
                merged[-1]['end_time_seconds'] = event['end_time_seconds']
                merged[-1]['duration_seconds'] = (
                    merged[-1]['end_time_seconds'] - merged[-1]['start_time_seconds']
                )
            else:
                merged.append(event.copy())
        
        logger.info(f"音符合并: {len(note_events)} -> {len(merged)}")
        return merged
    
    def convert_with_crepe(
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        model_capacity: str = 'full',
        viterbi: bool = True,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], str]:
        """
        使用CREPE进行音高检测（单音）
        
        Args:
            audio_path: 输入音频文件路径
            output_path: 输出CSV文件路径（可选）
            model_capacity: 模型容量 ('tiny', 'small', 'medium', 'large', 'full')
            viterbi: 是否使用维特比解码
            
        Returns:
            (time, frequency, message)
            - time: 时间数组
            - frequency: 频率数组
            - message: 状态消息
        """
        try:
            import crepe
            import librosa
            
            logger.info(f"使用CREPE进行音高检测: {audio_path}")
            
            # 加载音频
            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            
            # CREPE音高检测
            time, frequency, confidence, activation = crepe.predict(
                audio,
                sr,
                model_capacity=model_capacity,
                viterbi=viterbi,
                step_size=10,  # 10ms步长
            )
            
            # 保存结果
            if output_path:
                np.savetxt(
                    output_path,
                    np.column_stack([time, frequency, confidence]),
                    delimiter=',',
                    header='time,frequency,confidence',
                    comments=''
                )
                logger.info(f"音高数据已保存: {output_path}")
            
            logger.info(f"CREPE检测完成，检测到 {len(time)} 个时间点")
            
            return time, frequency, f"CREPE检测完成"
            
        except ImportError:
            error_msg = "CREPE未安装，请运行: pip install crepe"
            logger.error(error_msg)
            return None, None, error_msg
        except Exception as e:
            error_msg = f"CREPE音高检测失败: {e}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg


# 全局单例
_converter = None


def get_converter() -> AudioToMidiConverter:
    """获取全局转换器实例"""
    global _converter
    if _converter is None:
        _converter = AudioToMidiConverter()
    return _converter
