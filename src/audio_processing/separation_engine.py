"""
音频分离引擎模块
使用 Demucs 模型进行音频源分离
"""
import torch
import numpy as np
from pathlib import Path
from typing import Dict, Callable, Optional, List
from demucs.pretrained import get_model
from demucs.apply import apply_model
from demucs.audio import AudioFile
import logging
from .audio_loader import AudioLoader

logger = logging.getLogger(__name__)


class SeparationEngine:
    """音频分离引擎，使用 Demucs 模型"""
    
    def __init__(self, model_name: str = "htdemucs"):
        """
        初始化分离引擎
        
        Args:
            model_name: 模型名称（htdemucs, htdemucs_ft, htdemucs_6s）
        """
        self.model_name = model_name
        self.model = None
        self.device = self._detect_device()
        self._cancel_flag = False
        
        logger.info(f"初始化音频分离引擎，模型: {model_name}, 设备: {self.device}")
    
    def _detect_device(self) -> str:
        """
        自动检测可用的计算设备（GPU/CPU）
        
        Returns:
            设备名称（cuda, mps, cpu）
        """
        if torch.cuda.is_available():
            device = "cuda"
            logger.info(f"检测到 CUDA GPU: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            logger.info("检测到 Apple Silicon GPU (MPS)")
        else:
            device = "cpu"
            logger.info("使用 CPU 进行计算")
        
        return device
    
    def _load_model(self):
        """加载 Demucs 模型"""
        if self.model is None:
            try:
                logger.info(f"加载模型: {self.model_name}")
                self.model = get_model(self.model_name)
                self.model.to(self.device)
                self.model.eval()
                logger.info("模型加载成功")
            except Exception as e:
                logger.error(f"模型加载失败: {e}")
                raise RuntimeError(f"无法加载模型 {self.model_name}: {e}")
    
    def separate(
        self, 
        audio_path: str, 
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, np.ndarray]:
        """
        分离音频文件
        
        Args:
            audio_path: 音频文件路径
            progress_callback: 进度回调函数，接收 0-100 的进度值
            
        Returns:
            字典，键为音轨类型（vocals, drums, bass, other），值为音频数据（numpy 数组）
            
        Raises:
            RuntimeError: 分离过程中发生错误
            FileNotFoundError: 音频文件不存在
        """
        self._cancel_flag = False
        
        # 检查文件是否存在
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        logger.info(f"开始分离音频: {audio_path}")
        
        try:
            # 加载模型
            if progress_callback:
                progress_callback(5.0)
            self._load_model()
            
            if self._cancel_flag:
                logger.info("分离操作已取消")
                return {}
            
            # 加载音频（使用新的 AudioLoader）
            if progress_callback:
                progress_callback(10.0)
            
            logger.info("加载音频文件")
            try:
                # 使用 AudioLoader 加载并重采样
                wav, _ = AudioLoader.load(str(audio_path), target_sr=self.model.samplerate)
                
                # 确保声道数匹配
                if wav.shape[0] != self.model.audio_channels:
                    if self.model.audio_channels == 2 and wav.shape[0] == 1:
                        # 单声道转立体声
                        wav = np.repeat(wav, 2, axis=0)
                    elif self.model.audio_channels == 1 and wav.shape[0] == 2:
                        # 立体声转单声道
                        wav = wav.mean(axis=0, keepdims=True)
                
            except Exception as e:
                logger.warning(f"AudioLoader 加载失败，使用备用方法: {e}")
                # 备用方案：使用原始方法
                wav = AudioFile(str(audio_path)).read(
                    streams=0,
                    samplerate=self.model.samplerate,
                    channels=self.model.audio_channels
                )
                if isinstance(wav, torch.Tensor):
                    wav = wav.numpy()
            
            # 转换为 tensor
            wav = torch.from_numpy(wav).to(self.device)
            
            if self._cancel_flag:
                logger.info("分离操作已取消")
                return {}
            
            # 执行分离
            if progress_callback:
                progress_callback(20.0)
            
            logger.info("执行音频分离")
            with torch.no_grad():
                sources = apply_model(
                    self.model,
                    wav[None],
                    device=self.device,
                    progress=True
                )[0]
            
            if self._cancel_flag:
                logger.info("分离操作已取消")
                return {}
            
            # 转换结果
            if progress_callback:
                progress_callback(90.0)
            
            # 获取音轨名称
            source_names = self.model.sources
            
            # 转换为 numpy 数组并组织结果
            result = {}
            for i, name in enumerate(source_names):
                audio_data = sources[i].cpu().numpy()
                result[name] = audio_data
                logger.info(f"分离音轨: {name}, 形状: {audio_data.shape}")
            
            if progress_callback:
                progress_callback(100.0)
            
            logger.info(f"音频分离完成，共 {len(result)} 个音轨")
            return result
            
        except Exception as e:
            logger.error(f"音频分离失败: {e}", exc_info=True)
            raise RuntimeError(f"音频分离失败: {e}")
    
    def cancel(self):
        """取消当前分离操作"""
        logger.info("请求取消分离操作")
        self._cancel_flag = True
    
    def get_available_models(self) -> List[str]:
        """
        获取可用的模型列表
        
        Returns:
            模型名称列表
        """
        # Demucs 常用模型
        models = [
            "htdemucs",      # 4-stem (vocals, drums, bass, other)
            "htdemucs_ft",   # 4-stem fine-tuned
            "htdemucs_6s",   # 6-stem (vocals, drums, bass, other, guitar, piano)
        ]
        return models
    
    def get_sample_rate(self) -> int:
        """
        获取模型的采样率
        
        Returns:
            采样率（Hz）
        """
        if self.model is None:
            self._load_model()
        return self.model.samplerate
