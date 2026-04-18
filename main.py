"""
Hachimi (ハチミ) - 音频分离和二创工具
主入口文件
"""
import sys
from PyQt6.QtWidgets import QApplication
from src.utils.logger import setup_logger
from src.gui.main_window import MainWindow

# 设置日志
logger = setup_logger()


def main():
    """主函数"""
    logger.info("Hachimi 启动")
    
    app = QApplication(sys.argv)
    app.setApplicationName("Hachimi")
    app.setOrganizationName("Hachimi")
    
    # 创建并显示主窗口
    main_window = MainWindow()
    main_window.show()
    
    logger.info("应用程序初始化完成")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
