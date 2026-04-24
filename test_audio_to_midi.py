"""
音频转MIDI功能测试脚本
"""
import sys
from pathlib import Path

def test_import():
    """测试模块导入"""
    print("测试模块导入...")
    try:
        from src.audio_processing.audio_to_midi import AudioToMidiConverter, get_converter
        print("✅ audio_to_midi 模块导入成功")
        
        from src.gui.midi_dialog import MidiDialog, MidiConversionThread
        print("✅ midi_dialog 模块导入成功")
        
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_converter_init():
    """测试转换器初始化"""
    print("\n测试转换器初始化...")
    try:
        from src.audio_processing.audio_to_midi import get_converter
        
        converter = get_converter()
        print(f"✅ 转换器初始化成功")
        print(f"   后端: {converter.backend}")
        print(f"   可用: {converter.is_available()}")
        
        if not converter.is_available():
            print("⚠️  Basic Pitch 未安装，请运行: pip install basic-pitch")
        
        return True
    except Exception as e:
        print(f"❌ 转换器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_merge_notes():
    """测试音符合并功能"""
    print("\n测试音符合并功能...")
    try:
        from src.audio_processing.audio_to_midi import AudioToMidiConverter
        
        converter = AudioToMidiConverter()
        
        # 模拟音符事件
        note_events = [
            {'pitch_midi': 60, 'start_time_seconds': 0.0, 'end_time_seconds': 0.5, 'duration_seconds': 0.5},
            {'pitch_midi': 60, 'start_time_seconds': 0.52, 'end_time_seconds': 1.0, 'duration_seconds': 0.48},  # 应该被合并
            {'pitch_midi': 62, 'start_time_seconds': 1.0, 'end_time_seconds': 1.5, 'duration_seconds': 0.5},
            {'pitch_midi': 60, 'start_time_seconds': 2.0, 'end_time_seconds': 2.5, 'duration_seconds': 0.5},  # 不应该被合并
        ]
        
        merged = converter._merge_short_notes(note_events, min_gap=0.05)
        
        print(f"   原始音符数: {len(note_events)}")
        print(f"   合并后音符数: {len(merged)}")
        
        if len(merged) == 3:  # 应该从4个合并为3个
            print("✅ 音符合并功能正常")
            return True
        else:
            print(f"❌ 音符合并结果不符合预期，期望3个，实际{len(merged)}个")
            return False
            
    except Exception as e:
        print(f"❌ 音符合并测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gui_integration():
    """测试GUI集成"""
    print("\n测试GUI集成...")
    try:
        from PyQt6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow
        
        # 创建应用（不显示窗口）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        window = MainWindow()
        
        # 检查菜单是否存在
        menu_bar = window.menuBar()
        tools_menu = None
        for action in menu_bar.actions():
            if "工具" in action.text():
                tools_menu = action.menu()
                break
        
        if tools_menu:
            # 检查音频转MIDI菜单项
            has_midi_action = False
            for action in tools_menu.actions():
                if "MIDI" in action.text():
                    has_midi_action = True
                    break
            
            if has_midi_action:
                print("✅ GUI集成成功，菜单项已添加")
                return True
            else:
                print("❌ 未找到音频转MIDI菜单项")
                return False
        else:
            print("❌ 未找到工具菜单")
            return False
            
    except Exception as e:
        print(f"❌ GUI集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("音频转MIDI功能集成测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("模块导入", test_import()))
    results.append(("转换器初始化", test_converter_init()))
    results.append(("音符合并", test_merge_notes()))
    results.append(("GUI集成", test_gui_integration()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！音频转MIDI功能集成成功！")
        print("\n下一步:")
        print("1. 安装依赖: pip install basic-pitch")
        print("2. 运行程序: python main.py")
        print("3. 打开音频文件并分离")
        print("4. 点击 工具 → 音频转MIDI")
        print("5. 查看文档: docs/AUDIO_TO_MIDI_GUIDE.md")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
