"""
Hachimi (ハチミ) - 音频分离和二创工具
主入口文件
"""
import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from src.utils.logger import setup_logger
from src.gui.main_window import MainWindow
from src.utils.crash_protection import CrashProtection

# 设置日志
logger = setup_logger()


def exception_hook(exctype, value, tb):
    """全局异常处理器（增强版）"""
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    logger.critical(f"未捕获的异常:\n{error_msg}")
    
    # 显示友好的错误对话框
    try:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)  # 使用警告图标而非严重错误
        msg.setWindowTitle("程序遇到问题")
        msg.setText("程序遇到了一个错误，但将尝试继续运行")
        msg.setInformativeText(
            f"{exctype.__name__}: {value}\n\n"
            f"建议：\n"
            f"• 保存当前工作\n"
            f"• 如果问题持续，请重启程序\n"
            f"• 详细错误信息已记录到日志文件"
        )
        msg.setDetailedText(error_msg)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    except:
        # 如果连对话框都无法显示，至少打印到控制台
        print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)
    
    # 不调用默认的异常处理，让程序继续运行
    # sys.__excepthook__(exctype, value, tb)


def main():
    """主函数"""
    # 设置全局异常处理
    sys.excepthook = exception_hook
    
    logger.info("Hachimi 启动")
    logger.info("崩溃保护已启用 - 程序将尝试从错误中恢复")
    
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Hachimi")
        app.setOrganizationName("Hachimi")
        
        # 安装全局异常处理器
        CrashProtection.install_global_exception_handler()
        
        # PyQt6 默认启用高DPI支持，不需要手动设置
        
        # 创建并显示主窗口
        main_window = MainWindow()
        main_window.show()
        
        logger.info("应用程序初始化完成")
        
        return app.exec()
        
    except Exception as e:
        logger.critical(f"应用程序启动失败: {e}", exc_info=True)
        try:
            QMessageBox.critical(None, "启动失败", f"应用程序启动失败：\n{e}")
        except:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
