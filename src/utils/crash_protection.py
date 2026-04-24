"""
崩溃保护和异常处理工具
"""
import sys
import logging
import traceback
from functools import wraps
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import QTimer

logger = logging.getLogger(__name__)


class CrashProtection:
    """崩溃保护器"""
    
    @staticmethod
    def safe_execute(func, error_title="错误", show_dialog=True):
        """
        安全执行函数，捕获异常并显示友好提示
        
        Args:
            func: 要执行的函数
            error_title: 错误对话框标题
            show_dialog: 是否显示错误对话框
            
        Returns:
            函数执行结果，如果出错则返回 None
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"执行 {func.__name__} 时出错: {e}", exc_info=True)
                
                if show_dialog:
                    error_msg = f"操作失败：{str(e)}\n\n程序将继续运行。"
                    
                    # 使用 QTimer 延迟显示对话框，避免阻塞
                    QTimer.singleShot(0, lambda: QMessageBox.warning(
                        None,
                        error_title,
                        error_msg
                    ))
                
                return None
        return wrapper
    
    @staticmethod
    def protect_slot(error_title="错误"):
        """
        装饰器：保护 Qt 槽函数
        
        Example:
            @CrashProtection.protect_slot("音轨操作错误")
            def on_button_clicked(self):
                # 可能出错的代码
                pass
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"槽函数 {func.__name__} 出错: {e}", exc_info=True)
                    
                    error_msg = (
                        f"操作失败：{str(e)}\n\n"
                        f"程序将继续运行。如果问题持续，请重启程序。"
                    )
                    
                    # 延迟显示对话框
                    QTimer.singleShot(0, lambda: QMessageBox.warning(
                        None,
                        error_title,
                        error_msg
                    ))
                    
                    return None
            return wrapper
        return decorator
    
    @staticmethod
    def install_global_exception_handler():
        """安装全局异常处理器"""
        def exception_hook(exc_type, exc_value, exc_traceback):
            """全局异常钩子"""
            # 记录异常
            logger.critical(
                "未捕获的异常",
                exc_info=(exc_type, exc_value, exc_traceback)
            )
            
            # 格式化异常信息
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            tb_text = ''.join(tb_lines)
            
            # 显示错误对话框
            error_msg = (
                f"程序遇到未处理的错误：\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"程序将尝试继续运行。\n"
                f"如果问题持续，请保存工作并重启程序。\n\n"
                f"详细信息已记录到日志文件。"
            )
            
            try:
                QMessageBox.critical(
                    None,
                    "严重错误",
                    error_msg
                )
            except:
                # 如果连对话框都无法显示，至少打印到控制台
                print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)
                print(tb_text, file=sys.stderr)
        
        # 安装异常钩子
        sys.excepthook = exception_hook
        logger.info("全局异常处理器已安装")


class OperationThrottler:
    """操作节流器 - 限制高频操作"""
    
    def __init__(self, min_interval_ms=50):
        """
        Args:
            min_interval_ms: 最小操作间隔（毫秒）
        """
        self.min_interval_ms = min_interval_ms
        self.last_execution = {}
        self.pending_timers = {}
    
    def throttle(self, key: str, func, *args, **kwargs):
        """
        节流执行函数
        
        Args:
            key: 操作标识符
            func: 要执行的函数
            *args, **kwargs: 函数参数
        """
        import time
        
        current_time = time.time() * 1000  # 转换为毫秒
        last_time = self.last_execution.get(key, 0)
        
        elapsed = current_time - last_time
        
        if elapsed >= self.min_interval_ms:
            # 可以立即执行
            self.last_execution[key] = current_time
            
            # 取消待执行的定时器
            if key in self.pending_timers:
                self.pending_timers[key].stop()
                del self.pending_timers[key]
            
            # 执行函数
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"节流执行失败: {e}", exc_info=True)
        else:
            # 需要延迟执行
            delay = int(self.min_interval_ms - elapsed)
            
            # 取消之前的定时器
            if key in self.pending_timers:
                self.pending_timers[key].stop()
            
            # 创建新的定时器
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._execute_delayed(key, func, *args, **kwargs))
            timer.start(delay)
            
            self.pending_timers[key] = timer
    
    def _execute_delayed(self, key: str, func, *args, **kwargs):
        """延迟执行"""
        import time
        
        self.last_execution[key] = time.time() * 1000
        
        if key in self.pending_timers:
            del self.pending_timers[key]
        
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"延迟执行失败: {e}", exc_info=True)


# 全局节流器实例
global_throttler = OperationThrottler(min_interval_ms=100)


def throttle_operation(key: str):
    """
    装饰器：节流操作
    
    Example:
        @throttle_operation("reload_mix")
        def reload_mix(self):
            # 高频操作
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global_throttler.throttle(key, func, *args, **kwargs)
        return wrapper
    return decorator
