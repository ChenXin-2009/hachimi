"""
音频分离工具使用示例

这个脚本演示了如何使用核心 API 进行音频分离和处理（不使用 GUI）
"""
import sys
from pathlib import Path
from src.audio_processing.separation_engine import SeparationEngine
from src.audio_processing.audio_mixer import AudioMixer
from src.models.track import Track
from src.models.track_manager import TrackManager
from src.utils.logger import setup_logger

# 设置日志
logger = setup_logger()


def progress_callback(progress: float):
    """进度回调函数"""
    print(f"\r进度: {progress:.1f}%", end="", flush=True)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法: python example_usage.py <音频文件路径>")
        print("示例: python example_usage.py test.mp3")
        return
    
    audio_path = sys.argv[1]
    
    if not Path(audio_path).exists():
        print(f"错误：文件不存在 - {audio_path}")
        return
    
    print("=" * 60)
    print("音频分离工具 - 命令行示例")
    print("=" * 60)
    print()
    
    # 1. 创建分离引擎
    print("1. 初始化音频分离引擎...")
    engine = SeparationEngine(model_name="htdemucs")
    print(f"   设备: {engine.device}")
    print(f"   模型: {engine.model_name}")
    print()
    
    # 2. 分离音频
    print(f"2. 分离音频: {Path(audio_path).name}")
    print("   这可能需要几分钟，请耐心等待...")
    
    try:
        stems = engine.separate(audio_path, progress_callback=progress_callback)
        print()  # 换行
        print(f"   ✓ 分离完成！共 {len(stems)} 个音轨")
        print()
    except Exception as e:
        print(f"\n   ✗ 分离失败: {e}")
        return
    
    # 3. 创建音轨管理器
    print("3. 创建音轨管理器...")
    track_manager = TrackManager()
    sample_rate = engine.get_sample_rate()
    track_manager.add_separated_tracks(stems, sample_rate)
    
    tracks = track_manager.get_all_tracks()
    print(f"   ✓ 已添加 {len(tracks)} 个音轨:")
    for track in tracks:
        duration = track.get_duration_ms() / 1000.0
        print(f"      - {track.name}: {duration:.2f} 秒")
    print()
    
    # 4. 调整音轨参数（示例）
    print("4. 调整音轨参数...")
    if tracks:
        # 降低人声音量
        vocals_track = next((t for t in tracks if t.source_type == "vocals"), None)
        if vocals_track:
            track_manager.update_track_param(vocals_track.id, "volume_db", -6.0)
            print(f"   ✓ 人声音量降低 6dB")
        
        # 增强鼓的音量
        drums_track = next((t for t in tracks if t.source_type == "drums"), None)
        if drums_track:
            track_manager.update_track_param(drums_track.id, "volume_db", 3.0)
            print(f"   ✓ 鼓音量增加 3dB")
    print()
    
    # 5. 混合和导出
    print("5. 混合音轨并导出...")
    mixer = AudioMixer()
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # 导出混合音频
    output_path = output_dir / f"{Path(audio_path).stem}_mixed.wav"
    
    success = mixer.export(
        tracks,
        str(output_path),
        format="wav",
        quality="high",
        progress_callback=progress_callback
    )
    
    print()  # 换行
    if success:
        print(f"   ✓ 导出成功: {output_path}")
    else:
        print(f"   ✗ 导出失败")
    print()
    
    # 6. 导出单独的音轨
    print("6. 导出单独的音轨...")
    for track in tracks:
        track_output = output_dir / f"{Path(audio_path).stem}_{track.source_type}.wav"
        
        # 创建只包含这个音轨的列表
        single_track_list = [track]
        
        success = mixer.export(
            single_track_list,
            str(track_output),
            format="wav",
            quality="high"
        )
        
        if success:
            print(f"   ✓ {track.name}: {track_output}")
        else:
            print(f"   ✗ {track.name}: 导出失败")
    print()
    
    print("=" * 60)
    print("完成！所有文件已保存到 output/ 目录")
    print("=" * 60)


if __name__ == "__main__":
    main()
