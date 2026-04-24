"""
测试 FeatureCache 类的功能
"""

import os
import tempfile
import time
import pytest
from src.remix.improved.feature_cache import FeatureCache


def test_init():
    """测试初始化"""
    cache = FeatureCache(max_size=50)
    assert cache.max_size == 50
    assert len(cache.cache) == 0
    assert len(cache.access_order) == 0


def test_generate_key():
    """测试缓存键生成"""
    cache = FeatureCache()
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name
        f.write(b"test data")
    
    try:
        # 生成键
        key1 = cache._generate_key(temp_path)
        assert isinstance(key1, str)
        assert len(key1) == 32  # MD5 哈希长度
        
        # 相同文件应生成相同的键
        key2 = cache._generate_key(temp_path)
        assert key1 == key2
        
        # 修改文件后应生成不同的键
        time.sleep(0.1)
        with open(temp_path, 'a') as f:
            f.write("more data")
        key3 = cache._generate_key(temp_path)
        assert key1 != key3
    finally:
        os.unlink(temp_path)


def test_get_and_set():
    """测试获取和设置缓存"""
    cache = FeatureCache()
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name
        f.write(b"test data")
    
    try:
        # 初始时缓存为空
        assert cache.get(temp_path) is None
        
        # 设置缓存
        features = {'pitch': 440, 'tempo': 120}
        cache.set(temp_path, features)
        
        # 获取缓存
        cached_features = cache.get(temp_path)
        assert cached_features == features
        assert cache.size() == 1
    finally:
        os.unlink(temp_path)


def test_lru_eviction():
    """测试 LRU 淘汰机制"""
    cache = FeatureCache(max_size=3)
    
    # 创建临时文件
    temp_files = []
    for i in range(4):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_files.append(f.name)
            f.write(f"test data {i}".encode())
    
    try:
        # 添加 3 个缓存条目
        for i in range(3):
            cache.set(temp_files[i], {'index': i})
        
        assert cache.size() == 3
        
        # 添加第 4 个条目，应该淘汰第 1 个
        cache.set(temp_files[3], {'index': 3})
        
        assert cache.size() == 3
        assert cache.get(temp_files[0]) is None  # 第 1 个被淘汰
        assert cache.get(temp_files[1]) is not None
        assert cache.get(temp_files[2]) is not None
        assert cache.get(temp_files[3]) is not None
    finally:
        for temp_file in temp_files:
            os.unlink(temp_file)


def test_lru_update_on_access():
    """测试访问时更新 LRU 顺序"""
    cache = FeatureCache(max_size=3)
    
    # 创建临时文件
    temp_files = []
    for i in range(4):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_files.append(f.name)
            f.write(f"test data {i}".encode())
    
    try:
        # 添加 3 个缓存条目
        for i in range(3):
            cache.set(temp_files[i], {'index': i})
        
        # 访问第 1 个条目，更新其访问顺序
        cache.get(temp_files[0])
        
        # 添加第 4 个条目，应该淘汰第 2 个（而不是第 1 个）
        cache.set(temp_files[3], {'index': 3})
        
        assert cache.get(temp_files[0]) is not None  # 第 1 个仍在
        assert cache.get(temp_files[1]) is None  # 第 2 个被淘汰
        assert cache.get(temp_files[2]) is not None
        assert cache.get(temp_files[3]) is not None
    finally:
        for temp_file in temp_files:
            os.unlink(temp_file)


def test_clear():
    """测试清空缓存"""
    cache = FeatureCache()
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name
        f.write(b"test data")
    
    try:
        # 添加缓存
        cache.set(temp_path, {'pitch': 440})
        assert cache.size() == 1
        
        # 清空缓存
        cache.clear()
        assert cache.size() == 0
        assert cache.get(temp_path) is None
    finally:
        os.unlink(temp_path)


def test_remove():
    """测试移除指定缓存"""
    cache = FeatureCache()
    
    # 创建临时文件
    temp_files = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_files.append(f.name)
            f.write(f"test data {i}".encode())
    
    try:
        # 添加缓存
        for i, temp_file in enumerate(temp_files):
            cache.set(temp_file, {'index': i})
        
        assert cache.size() == 3
        
        # 移除第 2 个
        result = cache.remove(temp_files[1])
        assert result is True
        assert cache.size() == 2
        assert cache.get(temp_files[1]) is None
        
        # 尝试移除不存在的条目
        result = cache.remove(temp_files[1])
        assert result is False
    finally:
        for temp_file in temp_files:
            os.unlink(temp_file)


def test_update_existing_key():
    """测试更新已存在的键"""
    cache = FeatureCache()
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name
        f.write(b"test data")
    
    try:
        # 设置初始值
        cache.set(temp_path, {'pitch': 440})
        assert cache.size() == 1
        
        # 更新值
        cache.set(temp_path, {'pitch': 880})
        assert cache.size() == 1  # 大小不变
        
        # 验证值已更新
        cached = cache.get(temp_path)
        assert cached['pitch'] == 880
    finally:
        os.unlink(temp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
