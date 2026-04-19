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

# 设置日志
logger = setup_logger()


def exception_hook(exctype, value, tb):
    """全局异常处理器"""
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    logger.critical(f"未捕获的异常:\n{error_msg}")
    
    # 显示错误对话框
    try:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("程序错误")
        msg.setText("程序遇到了一个错误")
        msg.setInformativeText(f"{exctype.__name__}: {value}")
        msg.setDetailedText(error_msg)
        msg.exec()
    except:
        pass
    
    # 调用默认的异常处理
    sys.__excepthook__(exctype, value, tb)


def main():
    """主函数"""
    # 设置全局异常处理
    sys.excepthook = exception_hook
    
    logger.info("Hachimi 启动")
    
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Hachimi")
        app.setOrganizationName("Hachimi")
        
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
