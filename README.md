# Hachimi (ハチミ)

一个基于 Python 的本地桌面音频分离和二创工具，类似于 RipX DeepAudio。使用 Meta 开源的 Demucs 模型进行高质量音频源分离。

![项目状态](https://img.shields.io/badge/状态-MVP完成-green)
![Python版本](https://img.shields.io/badge/Python-3.8+-blue)
![许可证](https://img.shields.io/badge/许可证-Apache%202.0-blue)

## 🚀 最新更新 (2026-04-24)

### 性能优化与开源库集成

- ⚡ **音频处理速度提升 900-1800 倍** - 使用 numba JIT 编译加速
- 📦 **支持更多格式** - MP3, M4A, OGG, FLAC 等 20+ 种音频格式
- 🛡️ **更高稳定性** - 多层备用方案，快速操作不再崩溃
- 📝 **代码更简洁** - 减少 30-85% 代码量，更易维护

**详细信息**: 
- 集成总结: [`INTEGRATION_SUMMARY.md`](INTEGRATION_SUMMARY.md)
- 前后对比: [`BEFORE_AFTER_COMPARISON.md`](BEFORE_AFTER_COMPARISON.md)
- 完整报告: [`INTEGRATION_COMPLETE.md`](INTEGRATION_COMPLETE.md)

---

## ✨ 功能特性

- 🎵 **多模型音频分离**：支持 3 种 Demucs 模型
  - `htdemucs` - 4音轨（vocals, drums, bass, other）
  - `htdemucs_ft` - 4音轨微调版
  - `htdemucs_6s` - 6音轨（vocals, drums, bass, other, guitar, piano）**默认**
- 🎚️ **音轨控制**：独立的音量、静音、独奏控制
- 🎨 **多轨道波形可视化**：直观的波形编辑界面
- 🔄 **智能二创功能** ⭐ **新功能**
  - 自动检测音频片段
  - 智能匹配原曲音轨
  - 自动调整音高
  - 一键生成二创音频
- 💾 **项目管理**：保存和加载编辑项目
- 🎧 **实时播放预览**：即时听到编辑效果，支持进度跳转
- 📤 **多格式导出**：支持 MP3、WAV、FLAC 格式
- ⚡ **GPU 加速**：自动检测并使用 CUDA/MPS GPU

## 🖼️ 界面预览

```
┌─────────────────────────────────────────────────────┐
│  文件  编辑  帮助                    [打开] [播放]   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁  Vocals (人声)                    │
│  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁  Drums (鼓)                       │
│  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁  Bass (贝斯)                      │
│  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁  Other (其他)                     │
│                                                     │
├─────────────────────────────────────────────────────┤
│  [播放] [暂停] [停止]     00:00 / 03:45  ━━━━━━━━  │
└─────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 系统要求

**最低配置**：
- Python 3.8+
- 4GB RAM
- Windows 10+

**推荐配置**：
- Python 3.8+
- 8GB RAM
- NVIDIA GPU（支持 CUDA）
- Windows 10+

### 安装

1. 克隆仓库：
```bash
git clone https://github.com/ChenXin-2009/hachimi.git
cd hachimi
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

**注意**：首次运行时会自动下载 Demucs 模型（约 2GB），请确保网络连接正常。

### 运行

```bash
python main.py
```

### 基本使用

1. **打开音频**：点击"打开音频"按钮，选择音频文件
2. **选择模型**：在弹出的对话框中选择分离模型
   - **htdemucs**：标准版，速度快，适合大多数音乐
   - **htdemucs_ft**：微调版，质量更高
   - **htdemucs_6s**：6音轨版，可分离吉他和钢琴（速度较慢）
3. **等待分离**：自动分离音频为多个音轨（显示进度）
4. **调整音轨**：使用音轨控制面板
   - **M** 按钮：静音/取消静音
   - **S** 按钮：独奏（只播放该音轨）
   - 滑块：调整音量（-60dB 到 +12dB）
   - 🗑 按钮：删除音轨
5. **播放预览**：使用播放控制按钮预听效果，点击进度条可跳转
6. **导出音频**：点击"文件 → 导出音频"保存结果

详细使用说明请查看 [快速入门指南](docs/QUICKSTART.md)。

## 📊 技术栈

- **编程语言**：Python 3.8+
- **GUI 框架**：PyQt6
- **音频分离**：Demucs (Meta 开源)
- **波形可视化**：PyQtGraph
- **音频处理**：Pedalboard (Spotify), PyDub, soundfile, librosa
- **深度学习**：PyTorch
- **音频播放**：sounddevice

## 📁 项目结构

```
hachimi/
├── src/
│   ├── audio_processing/    # 音频处理模块
│   ├── gui/                  # GUI 组件
│   ├── models/               # 数据模型
│   └── utils/                # 工具函数
├── tests/                    # 测试文件
├── docs/                     # 文档
├── main.py                   # 主入口
└── requirements.txt          # 依赖列表
```

## 🎯 开发状态

### ✅ 已完成（MVP）
- [x] 多模型音频源分离（htdemucs, htdemucs_ft, htdemucs_6s）
- [x] 模型选择对话框
- [x] 多轨道波形可视化
- [x] 音轨控制面板（音量、静音、独奏、删除）
- [x] 音频播放控制（播放、暂停、停止、进度跳转）
- [x] 音频混合和导出
- [x] 项目保存/加载
- [x] GPU 加速支持
- [x] 撤销/重做功能
- [x] 深色主题 UI

### 🚧 进行中
- [ ] 音轨替换功能 GUI
- [ ] 设置对话框

### 📋 计划中
- [ ] 批量处理
- [ ] 音效处理（EQ、混响、压缩器）
- [ ] 帮助文档和教程
- [ ] 跨平台支持（macOS, Linux）

详细开发状态请查看 [开发状态文档](docs/DEVELOPMENT_STATUS.md)。

## 📈 性能表现

### 音频分离速度（3 分钟音频）
- **GPU（NVIDIA RTX 3060）**：约 2 分钟
- **CPU（Intel i7）**：约 10 分钟

### 内存使用
- **分离过程**：2-3GB
- **波形显示**：200-500MB

## 🔧 开发

### 运行测试
```bash
pytest tests/
```

### 代码风格
遵循 PEP 8 规范。

## 📚 文档

- [快速入门指南](docs/QUICKSTART.md)
- [开发状态](docs/DEVELOPMENT_STATUS.md)
- [项目总结](docs/SUMMARY.md)
- [需求文档](.kiro/specs/audio-separation-tool/requirements.md)
- [设计文档](.kiro/specs/audio-separation-tool/design.md)
- [任务清单](.kiro/specs/audio-separation-tool/tasks.md)

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 Apache License 2.0 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [Demucs](https://github.com/facebookresearch/demucs) - Meta 开源的音频分离模型
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - 强大的 Python GUI 框架
- [PyQtGraph](https://www.pyqtgraph.org/) - 高性能科学绘图库
- [Pedalboard](https://github.com/spotify/pedalboard) - Spotify 开源的音频处理库

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 [Issue](https://github.com/ChenXin-2009/hachimi/issues)
- GitHub: [@ChenXin-2009](https://github.com/ChenXin-2009)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
