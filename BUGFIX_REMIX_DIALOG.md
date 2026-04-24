# RemixDialog 按钮引用错误修复

## 🐛 问题描述

在 `src/gui/remix_dialog.py` 中，播放控制按钮（`play_segment_btn`, `play_all_btn`, `stop_btn`）被注释掉了，但代码中仍然在引用这些按钮，导致 `AttributeError`。

### 错误信息

```
AttributeError: 'RemixDialog' object has no attribute 'play_segment_btn'
```

### 触发场景

1. 点击波形图选择片段时
2. 在片段列表中点击项目时
3. 删除片段时
4. 播放音频时

---

## ✅ 修复方案

添加了按钮存在性检查，确保代码在按钮不存在时不会崩溃。

### 修改的方法

1. **`_update_play_segment_button()`**
   ```python
   def _update_play_segment_button(self):
       """更新播放片段按钮状态"""
       # 检查按钮是否存在（可能被注释掉了）
       if not hasattr(self, 'play_segment_btn'):
           return
       
       self.play_segment_btn.setEnabled(...)
   ```

2. **`_play_all()`**
   ```python
   self.is_playing = True
   if hasattr(self, 'play_all_btn'):
       self.play_all_btn.setText("⏹ 停止")
   if hasattr(self, 'stop_btn'):
       self.stop_btn.setEnabled(True)
   ```

3. **`_play_selected_segment()`**
   ```python
   self.is_playing = True
   if hasattr(self, 'play_segment_btn'):
       self.play_segment_btn.setText("⏹ 停止")
   if hasattr(self, 'stop_btn'):
       self.stop_btn.setEnabled(True)
   ```

4. **`_stop_playback()`**
   ```python
   self.is_playing = False
   
   # 更新按钮状态
   if hasattr(self, 'play_all_btn'):
       self.play_all_btn.setText("▶ 播放全部")
   if hasattr(self, 'play_segment_btn'):
       self.play_segment_btn.setText("▶ 播放片段")
   if hasattr(self, 'stop_btn'):
       self.stop_btn.setEnabled(False)
   ```

---

## 🎯 修复效果

- ✅ 不再抛出 `AttributeError`
- ✅ 程序可以正常运行
- ✅ 如果将来取消注释播放按钮，代码仍然可以正常工作
- ✅ 向后兼容

---

## 📝 注意事项

### 为什么播放按钮被注释掉？

根据代码注释：
```python
# 播放控制（暂时禁用，避免崩溃）
```

可能是因为播放功能在某些情况下会导致崩溃，所以暂时禁用了。

### 如何恢复播放功能？

如果想恢复播放功能，只需取消注释以下代码：

```python
# 在 _init_sample_tab() 方法中
self.play_all_btn = QPushButton("▶ 播放全部")
self.play_all_btn.clicked.connect(self._play_all)
self.play_all_btn.setEnabled(False)
toolbar.addWidget(self.play_all_btn)

self.play_segment_btn = QPushButton("▶ 播放片段")
self.play_segment_btn.clicked.connect(self._play_selected_segment)
self.play_segment_btn.setEnabled(False)
toolbar.addWidget(self.play_segment_btn)

self.stop_btn = QPushButton("⏹ 停止")
self.stop_btn.clicked.connect(self._stop_playback)
self.stop_btn.setEnabled(False)
toolbar.addWidget(self.stop_btn)
```

由于我们添加了 `hasattr()` 检查，取消注释后代码会自动启用按钮功能。

---

## ✅ 测试

修复后，以下操作不再报错：

1. ✅ 点击波形图选择片段
2. ✅ 在片段列表中点击项目
3. ✅ 删除片段
4. ✅ 导入素材音频

---

## 📊 修改摘要

| 文件 | 修改内容 | 行数 |
|------|---------|------|
| `src/gui/remix_dialog.py` | 添加按钮存在性检查 | 4 处 |

---

**修复完成！程序现在可以正常运行，不会因为缺少播放按钮而崩溃。** ✅
