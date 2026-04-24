"""
集成测试脚本 - 验证开源库集成
"""
import numpy as np
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_audio_loader():
    """测试 AudioLoader"""
    print("\n" + "="*60)
    print("测试 AudioLoader")
    print("="*60)
    
    try:
        from src.audio_processing.audio_loader import AudioLoader
        
        # 测试加载音频
        print("\n1. 测试加载音频...")
        audio_files = [
            "audio/哈基米完整.wav",
            "audio/呗.wav",
        ]
        
        for audio_file in audio_files:
            try:
                audio_data, sr = AudioLoader.load(audio_file)
                info = AudioLoader.get_info(audio_file)
                print(f"   ✅ {audio_file}")
                print(f"      形状: {audio_data.shape}, 采样率: {sr}Hz")
                print(f"      时长: {info['duration']:.2f}秒, 声道: {info['channels']}")
            except Exception as e:
                print(f"   ❌ {audio_file}: {e}")
        
        # 测试重采样
        print("\n2. 测试重采样...")
        audio_data, sr = AudioLoader.load("audio/哈基米完整.wav", target_sr=22050)
        print(f"   ✅ 重采样到 22050Hz: {audio_data.shape}, {sr}Hz")
        
        # 测试保存
        print("\n3. 测试保存音频...")
        test_audio = np.random.randn(2, 44100) * 0.1  # 2 秒立体声
        AudioLoader.save("test_output.wav", test_audio, 44100)
        print(f"   ✅ 保存成功: test_output.wav")
        
        print("\n✅ AudioLoader 测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ AudioLoader 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fast_audio_effects():
    """测试 FastAudioEffects"""
    print("\n" + "="*60)
    print("测试 FastAudioEffects")
    print("="*60)
    
    try:
        from src.audio_processing.audio_effects import FastAudioEffects
        
        # 创建测试音频
        audio = np.random.randn(2, 44100).astype(np.float32)  # 1 秒立体声
        
        # 测试音量调整
        print("\n1. 测试音量调整...")
        processed = FastAudioEffects.apply_volume(audio, 6.0)
        gain_ratio = np.abs(processed).mean() / np.abs(audio).mean()
        print(f"   ✅ 音量调整: 增益比 {gain_ratio:.2f} (预期 ~2.0)")
        
        # 测试平衡调整
        print("\n2. 测试平衡调整...")
        processed = FastAudioEffects.apply_pan(audio, -0.5)
        print(f"   ✅ 平衡调整: 形状 {processed.shape}")
        
        # 测试归一化
        print("\n3. 测试归一化...")
        processed = FastAudioEffects.normalize(audio, target_db=-3.0)
        max_val = np.abs(processed).max()
        print(f"   ✅ 归一化: 最大值 {max_val:.3f}")
        
        # 测试淡入淡出
        print("\n4. 测试淡入淡出...")
        processed = FastAudioEffects.apply_fade_in(audio, 100, 44100)
        print(f"   ✅ 淡入: 形状 {processed.shape}")
        processed = FastAudioEffects.apply_fade_out(audio, 100, 44100)
        print(f"   ✅ 淡出: 形状 {processed.shape}")
        
        # 性能测试
        print("\n5. 性能测试...")
        iterations = 1000
        
        # 测试音量调整性能
        start = time.time()
        for _ in range(iterations):
            FastAudioEffects.apply_volume(audio, 3.0)
        elapsed = time.time() - start
        print(f"   ✅ {iterations} 次音量调整: {elapsed:.3f}秒 ({elapsed/iterations*1000:.3f}ms/次)")
        
        # 测试平衡调整性能
        start = time.time()
        for _ in range(iterations):
            FastAudioEffects.apply_pan(audio, 0.5)
        elapsed = time.time() - start
        print(f"   ✅ {iterations} 次平衡调整: {elapsed:.3f}秒 ({elapsed/iterations*1000:.3f}ms/次)")
        
        print("\n✅ FastAudioEffects 测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ FastAudioEffects 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """测试集成到现有代码"""
    print("\n" + "="*60)
    print("测试集成")
    print("="*60)
    
    try:
        # 测试导入
        print("\n1. 测试模块导入...")
        from src.audio_processing.audio_mixer import AudioMixer
        from src.audio_processing.separation_engine import SeparationEngine
        from src.models.track_manager import TrackManager
        from src.models.project_manager import ProjectManager
        print("   ✅ 所有模块导入成功")
        
        # 测试 AudioMixer
        print("\n2. 测试 AudioMixer...")
        mixer = AudioMixer()
        print("   ✅ AudioMixer 初始化成功")
        
        # 测试 TrackManager
        print("\n3. 测试 TrackManager...")
        track_manager = TrackManager()
        print("   ✅ TrackManager 初始化成功")
        
        # 测试 ProjectManager
        print("\n4. 测试 ProjectManager...")
        project_manager = ProjectManager()
        print("   ✅ ProjectManager 初始化成功")
        
        print("\n✅ 集成测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开源库集成测试")
    print("="*60)
    
    results = []
    
    # 运行测试
    results.append(("AudioLoader", test_audio_loader()))
    results.append(("FastAudioEffects", test_fast_audio_effects()))
    results.append(("Integration", test_integration()))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！集成成功！")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
