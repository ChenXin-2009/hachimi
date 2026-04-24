"""
性能监控工具
"""
import time
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""
    
    # 性能阈值（毫秒）
    WARNING_THRESHOLD_MS = 50
    ERROR_THRESHOLD_MS = 200
    
    @staticmethod
    def measure(func: Callable) -> Callable:
        """
        装饰器：测量函数执行时间
        
        Args:
            func: 要测量的函数
            
        Returns:
            包装后的函数
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            # 根据耗时记录不同级别的日志
            func_name = f"{func.__module__}.{func.__qualname__}"
            
            if elapsed_ms > PerformanceMonitor.ERROR_THRESHOLD_MS:
                logger.error(f"⚠️ {func_name} 耗时过长: {elapsed_ms:.2f}ms")
            elif elapsed_ms > PerformanceMonitor.WARNING_THRESHOLD_MS:
                logger.warning(f"⏱️ {func_name} 耗时: {elapsed_ms:.2f}ms")
            else:
                logger.debug(f"✓ {func_name} 耗时: {elapsed_ms:.2f}ms")
            
            return result
        return wrapper
    
    @staticmethod
    def measure_block(name: str):
        """
        上下文管理器：测量代码块执行时间
        
        Args:
            name: 代码块名称
            
        Example:
            with PerformanceMonitor.measure_block("音频混合"):
                # 执行耗时操作
                pass
        """
        return _PerformanceBlock(name)


class _PerformanceBlock:
    """性能测量代码块"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        
        if elapsed_ms > PerformanceMonitor.ERROR_THRESHOLD_MS:
            logger.error(f"⚠️ {self.name} 耗时过长: {elapsed_ms:.2f}ms")
        elif elapsed_ms > PerformanceMonitor.WARNING_THRESHOLD_MS:
            logger.warning(f"⏱️ {self.name} 耗时: {elapsed_ms:.2f}ms")
        else:
            logger.debug(f"✓ {self.name} 耗时: {elapsed_ms:.2f}ms")


# 便捷函数
def measure_performance(func: Callable) -> Callable:
    """
    装饰器：测量函数性能
    
    Example:
        @measure_performance
        def my_function():
            pass
    """
    return PerformanceMonitor.measure(func)
