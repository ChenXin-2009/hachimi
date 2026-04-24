"""
性能测试脚本 - 测试快速开关轨道的性能
"""
import sys
import time
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.models.track import Track
from src.models.track_manager import TrackManager
from src.audio_processing.audio_mixer import AudioMixer
from src.audio_processing.audio_player import AudioPlayer
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_tracks(num_tracks: int = 5) -> list:
    """创建测试音轨"""
    tracks = []
    sample_rate = 44100
    duration_s = 10  # 10 秒
    num_samples = int(sample_rate * duration_s)
    
    track_types = ["vocals", "drums", "bass", "other", "guitar"]
    
    for i in range(num_tracks):
        # 生成随机音频数据
        audio_data = np.random.randn(2, num_samples) * 0.1
        
        track = Track(
            name=f"Track {i+1}",
            audio_data=audio_data,
            sample_rate=sample_rate,
            source_type=track_types[i % len(track_types)]
        )
        tracks.append(track)
    
    return tracks


def test_rapid_mute_toggle():
    """测试快速切换静音"""
    logger.info("=" * 60)
    logger.info("测试 1: 快速切换静音（模拟用户快速操作）")
    logger.info("=" * 60)
    
    # 创建测试环境
    app = QApplication(sys.argv)
    
    track_manager = TrackManager()
    mixer = AudioMixer()
    player = AudioPlayer(mixer)
    
    # 创建测试音轨
    tracks = create_test_tracks(5)
    
    # 添加到管理器
    for track in tracks:
        track_manager._tracks[track.id] = track
        track_manager._track_order.append(track.id)
    
    # 加载到播放器
    player.load_tracks(tracks)
    
    # 测试：快速切换静音 20 次
    logger.info("开始快速切换静音 20 次...")
    start_time = time.perf_counter()
    
    for i in range(20):
        track_id = tracks[i % len(tracks)].id
        # 切换静音状态
        track_manager.update_track_param(track_id, "muted", i % 2 == 0)
        # 触发重新混音
        player.reload_mix()
    
    # 等待所有操作完成
    QTimer.singleShot(2000, app.quit)
    app.exec()
    
    elapsed = time.perf_counter() - start_time
    logger.info(f"✓ 完成 20 次切换，总耗时: {elapsed:.2f}秒")
    logger.info(f"✓ 平均每次: {elapsed/20*1000:.2f}ms")
    
    if elapsed < 2.0:
        logger.info("✅ 性能测试通过！响应速度良好")
    else:
        logger.warning("⚠️ 性能需要优化，响应时间过长")


def test_volume_adjustment():
    """测试快速调整音量"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 快速调整音量（模拟拖动滑块）")
    logger.info("=" * 60)
    
    app = QApplication(sys.argv)
    
    track_manager = TrackManager()
    mixer = AudioMixer()
    player = AudioPlayer(mixer)
    
    tracks = create_test_tracks(5)
    
    for track in tracks:
        track_manager._tracks[track.id] = track
        track_manager._track_order.append(track.id)
    
    player.load_tracks(tracks)
    
    # 测试：快速调整音量 50 次
    logger.info("开始快速调整音量 50 次...")
    start_time = time.perf_counter()
    
    track_id = tracks[0].id
    for i in range(50):
        volume = -20 + (i % 40)  # -20 到 +20 dB
        track_manager.update_track_param(track_id, "volume_db", float(volume))
        player.reload_mix()
    
    # 等待防抖完成
    QTimer.singleShot(500, app.quit)
    app.exec()
    
    elapsed = time.perf_counter() - start_time
    logger.info(f"✓ 完成 50 次调整，总耗时: {elapsed:.2f}秒")
    logger.info(f"✓ 平均每次: {elapsed/50*1000:.2f}ms")
    
    if elapsed < 1.0:
        logger.info("✅ 防抖机制工作正常！")
    else:
        logger.warning("⚠️ 防抖可能需要调整")


def test_cache_effectiveness():
    """测试缓存效果"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 音频效果缓存测试")
    logger.info("=" * 60)
    
    mixer = AudioMixer()
    track = create_test_tracks(1)[0]
    
    # 第一次处理（无缓存）
    logger.info("第一次处理（无缓存）...")
    start = time.perf_counter()
    result1 = track.get_processed_audio(mixer)
    time1 = (time.perf_counter() - start) * 1000
    logger.info(f"✓ 耗时: {time1:.2f}ms")
    
    # 第二次处理（使用缓存）
    logger.info("第二次处理（使用缓存）...")
    start = time.perf_counter()
    result2 = track.get_processed_audio(mixer)
    time2 = (time.perf_counter() - start) * 1000
    logger.info(f"✓ 耗时: {time2:.2f}ms")
    
    # 验证结果一致
    if np.array_equal(result1, result2):
        logger.info("✓ 缓存结果正确")
    else:
        logger.error("✗ 缓存结果不一致！")
    
    # 计算加速比
    speedup = time1 / time2 if time2 > 0 else float('inf')
    logger.info(f"✓ 缓存加速比: {speedup:.1f}x")
    
    if speedup > 10:
        logger.info("✅ 缓存效果显著！")
    elif speedup > 2:
        logger.info("✅ 缓存有效")
    else:
        logger.warning("⚠️ 缓存效果不明显")
    
    # 修改参数后缓存失效
    logger.info("\n修改参数后重新处理...")
    track.volume_db = -10.0
    start = time.perf_counter()
    result3 = track.get_processed_audio(mixer)
    time3 = (time.perf_counter() - start) * 1000
    logger.info(f"✓ 耗时: {time3:.2f}ms")
    
    if not np.array_equal(result1, result3):
        logger.info("✓ 缓存正确失效")
    else:
        logger.error("✗ 缓存未正确失效！")


def main():
    """运行所有测试"""
    logger.info("开始性能测试...")
    logger.info("测试环境: 5 个音轨，每个 10 秒，44.1kHz")
    
    try:
        test_cache_effectiveness()
        test_rapid_mute_toggle()
        test_volume_adjustment()
        
        logger.info("\n" + "=" * 60)
        logger.info("所有测试完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
