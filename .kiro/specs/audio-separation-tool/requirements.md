# 需求文档：音频分离和二创工具

## 简介

本文档定义了一个基于 Python 的本地桌面音频分离和二创工具的需求。该工具类似于 RipX DeepAudio，允许用户导入音频文件，自动分离成不同的音轨（人声、鼓、贝斯、其他乐器等），并支持用户导入自己的音频素材替换原曲中的特定乐器轨道，最终导出混合后的音频文件。

## 术语表

- **Audio_Separation_Engine**：音频源分离引擎，负责将音频文件分离成多个独立音轨
- **Waveform_Editor**：波形编辑器，提供多轨道波形可视化和编辑界面
- **Track_Manager**：音轨管理器，管理分离后的音轨和用户导入的替换音轨
- **Audio_Mixer**：音频混合器，将多个音轨混合成最终输出
- **Project_Manager**：项目管理器，负责保存和加载用户的编辑项目
- **Audio_File**：音频文件，支持的格式包括 MP3、WAV、FLAC、OGG、M4A
- **Separated_Track**：分离音轨，从原始音频中分离出的单一乐器或人声轨道
- **Replacement_Track**：替换音轨，用户导入用于替换原曲中特定乐器的音频素材
- **Stem**：音频干声，指分离后的单一音轨（如人声干声、鼓干声等）
- **Demucs_Model**：Meta 开源的音频源分离深度学习模型
- **GUI_Framework**：图形用户界面框架，使用 PyQt6 或 PySide6

## 需求

### 需求 1：音频文件导入

**用户故事：** 作为用户，我希望能够导入常见格式的音频文件，以便进行后续的分离和编辑操作。

#### 验收标准

1. THE Audio_Separation_Engine SHALL 支持导入 MP3、WAV、FLAC、OGG、M4A 格式的音频文件
2. WHEN 用户选择一个音频文件，THE GUI_Framework SHALL 在 3 秒内显示文件的基本信息（文件名、时长、采样率、比特率）
3. IF 音频文件格式不支持或文件损坏，THEN THE Audio_Separation_Engine SHALL 返回描述性错误消息
4. THE Audio_Separation_Engine SHALL 支持最长 10 分钟的音频文件
5. WHEN 音频文件导入成功，THE Waveform_Editor SHALL 显示原始音频的波形预览

### 需求 2：音频源分离

**用户故事：** 作为音乐爱好者，我希望导入一首歌曲并自动分离出人声、鼓、贝斯等轨道，以便我可以单独听每个乐器的演奏。

#### 验收标准

1. THE Audio_Separation_Engine SHALL 使用 Demucs_Model 将音频分离为至少 4 个 Stem（人声、鼓、贝斯、其他乐器）
2. WHEN 用户启动分离操作，THE GUI_Framework SHALL 显示实时进度指示器（百分比和预计剩余时间）
3. WHEN 分离操作完成，THE Track_Manager SHALL 为每个 Separated_Track 创建独立的音轨条目
4. THE Audio_Separation_Engine SHALL 在分离过程中支持用户取消操作
5. IF 分离过程中发生错误（内存不足、模型加载失败），THEN THE Audio_Separation_Engine SHALL 记录错误日志并通知用户
6. FOR ALL 分离后的 Separated_Track，混合后的音频 SHALL 与原始音频在听感上保持一致（信噪比 > 20dB）

### 需求 3：波形可视化

**用户故事：** 作为音频编辑者，我希望在波形编辑器中可视化查看每个分离的音轨，以便进行精确的时间对齐和音量调整。

#### 验收标准

1. THE Waveform_Editor SHALL 以多轨道布局显示所有 Separated_Track 的波形
2. WHEN 用户缩放时间轴，THE Waveform_Editor SHALL 在 500 毫秒内重新渲染波形
3. THE Waveform_Editor SHALL 支持水平滚动和缩放（最小精度到 10 毫秒）
4. WHEN 用户点击波形上的位置，THE Waveform_Editor SHALL 将播放头移动到该时间点
5. THE Waveform_Editor SHALL 为每个音轨显示音量包络线
6. THE Waveform_Editor SHALL 使用不同颜色区分不同类型的音轨（人声、鼓、贝斯、其他）
7. WHILE 音频播放中，THE Waveform_Editor SHALL 实时更新播放头位置

### 需求 4：音频播放控制

**用户故事：** 作为用户，我希望能够播放、暂停、停止音频，并控制播放位置，以便预览编辑效果。

#### 验收标准

1. THE Audio_Mixer SHALL 支持播放、暂停、停止操作
2. WHEN 用户点击播放按钮，THE Audio_Mixer SHALL 在 200 毫秒内开始播放音频
3. THE Audio_Mixer SHALL 支持拖动播放头到任意时间位置
4. THE Audio_Mixer SHALL 支持循环播放指定时间范围
5. THE Audio_Mixer SHALL 实时混合所有启用的音轨并输出
6. WHEN 用户调整音轨音量，THE Audio_Mixer SHALL 在 100 毫秒内反映音量变化
7. THE Audio_Mixer SHALL 支持独奏（Solo）和静音（Mute）单个音轨

### 需求 5：音频替换功能

**用户故事：** 作为二创作者，我希望用自己录制的吉他音轨替换原曲中的吉他部分，创作出新的混音版本。

#### 验收标准

1. THE Track_Manager SHALL 允许用户导入 Replacement_Track 替换任意 Separated_Track
2. WHEN 用户导入 Replacement_Track，THE Track_Manager SHALL 验证音频格式和采样率兼容性
3. IF Replacement_Track 的采样率与原始音频不同，THEN THE Track_Manager SHALL 自动重采样到匹配的采样率
4. THE Track_Manager SHALL 允许用户调整 Replacement_Track 的起始时间偏移
5. THE Waveform_Editor SHALL 在波形视图中区分显示 Separated_Track 和 Replacement_Track
6. THE Track_Manager SHALL 允许用户恢复到原始 Separated_Track
7. FOR ALL Replacement_Track，时间对齐精度 SHALL 达到 10 毫秒以内

### 需求 6：音轨编辑操作

**用户故事：** 作为音频编辑者，我希望能够调整每个音轨的音量、平衡和时间偏移，以便创作出理想的混音效果。

#### 验收标准

1. THE Track_Manager SHALL 允许用户调整每个音轨的音量（范围 -60dB 到 +12dB）
2. THE Track_Manager SHALL 允许用户调整每个音轨的左右声道平衡（范围 -100% 到 +100%）
3. THE Track_Manager SHALL 允许用户设置每个音轨的时间偏移（范围 -10 秒到 +10 秒）
4. WHEN 用户调整音轨参数，THE Waveform_Editor SHALL 实时更新视觉反馈
5. THE Track_Manager SHALL 支持撤销和重做操作（至少 50 步历史记录）
6. THE Track_Manager SHALL 允许用户重命名音轨
7. THE Track_Manager SHALL 允许用户删除不需要的音轨

### 需求 7：音频导出

**用户故事：** 作为用户，我希望能够导出最终混合的音频文件，支持常见格式（MP3、WAV、FLAC），以便分享或进一步处理。

#### 验收标准

1. THE Audio_Mixer SHALL 支持导出为 MP3（128-320 kbps）、WAV（16/24 bit）、FLAC 格式
2. WHEN 用户启动导出操作，THE Audio_Mixer SHALL 显示导出进度和预计剩余时间
3. THE Audio_Mixer SHALL 混合所有启用的音轨并应用音量、平衡、时间偏移设置
4. THE Audio_Mixer SHALL 在导出过程中支持用户取消操作
5. WHEN 导出完成，THE Audio_Mixer SHALL 通知用户并提供打开文件位置的选项
6. IF 导出过程中发生错误（磁盘空间不足、写入权限不足），THEN THE Audio_Mixer SHALL 显示描述性错误消息
7. FOR ALL 导出的音频文件，音质 SHALL 保持与预览播放一致（无额外失真或噪声）

### 需求 8：项目保存和加载

**用户故事：** 作为用户，我希望能够保存当前的编辑项目并在以后加载，以便继续未完成的工作。

#### 验收标准

1. THE Project_Manager SHALL 支持将当前项目保存为项目文件（包含所有音轨、参数设置、分离结果）
2. THE Project_Manager SHALL 支持加载已保存的项目文件
3. WHEN 用户保存项目，THE Project_Manager SHALL 保存所有 Separated_Track 和 Replacement_Track 的引用路径
4. WHEN 用户加载项目，THE Project_Manager SHALL 验证所有音频文件路径是否有效
5. IF 项目文件中引用的音频文件缺失，THEN THE Project_Manager SHALL 提示用户重新定位文件
6. THE Project_Manager SHALL 在用户关闭应用前提示保存未保存的更改
7. THE Project_Manager SHALL 使用结构化格式（JSON 或 XML）存储项目元数据

### 需求 9：用户界面响应性

**用户故事：** 作为用户，我希望应用程序界面流畅响应，不会因为后台处理而卡顿。

#### 验收标准

1. THE GUI_Framework SHALL 在独立线程中执行音频分离操作，避免阻塞主界面
2. THE GUI_Framework SHALL 在独立线程中执行音频导出操作，避免阻塞主界面
3. WHEN 执行耗时操作时，THE GUI_Framework SHALL 保持界面响应用户输入
4. THE Waveform_Editor SHALL 在 16 毫秒内完成单帧渲染（60 FPS）
5. THE GUI_Framework SHALL 在用户操作后 100 毫秒内提供视觉反馈
6. THE GUI_Framework SHALL 使用进度条或加载动画指示后台操作状态

### 需求 10：错误处理和日志记录

**用户故事：** 作为开发者，我希望应用程序能够记录详细的错误日志，以便诊断和修复问题。

#### 验收标准

1. THE Audio_Separation_Engine SHALL 记录所有错误和警告到日志文件
2. THE Audio_Separation_Engine SHALL 在日志中包含时间戳、错误级别、错误消息、堆栈跟踪
3. WHEN 发生致命错误，THE Audio_Separation_Engine SHALL 显示用户友好的错误对话框
4. THE Audio_Separation_Engine SHALL 将日志文件保存在用户可访问的位置（应用数据目录）
5. THE Audio_Separation_Engine SHALL 支持配置日志级别（DEBUG、INFO、WARNING、ERROR）
6. THE Audio_Separation_Engine SHALL 自动轮转日志文件（单个文件最大 10MB，保留最近 5 个文件）

### 需求 11：性能要求

**用户故事：** 作为用户，我希望应用程序能够在合理时间内处理音频文件，不会消耗过多系统资源。

#### 验收标准

1. WHEN 处理 3 分钟的音频文件，THE Audio_Separation_Engine SHALL 在配备 NVIDIA GPU 的系统上 2 分钟内完成分离
2. WHEN 处理 3 分钟的音频文件，THE Audio_Separation_Engine SHALL 在仅使用 CPU 的系统上 10 分钟内完成分离
3. THE Audio_Separation_Engine SHALL 在分离过程中使用不超过 4GB 内存
4. THE Waveform_Editor SHALL 在显示 5 分钟音频的波形时使用不超过 500MB 内存
5. THE Audio_Mixer SHALL 在播放时保持 CPU 使用率低于 30%（单核）
6. THE Audio_Separation_Engine SHALL 自动检测并使用可用的 GPU 加速（CUDA 或 MPS）

### 需求 12：模型管理

**用户故事：** 作为用户，我希望应用程序能够自动下载和管理音频分离模型，无需手动配置。

#### 验收标准

1. WHEN 首次启动应用，THE Audio_Separation_Engine SHALL 检查 Demucs_Model 是否已下载
2. IF Demucs_Model 未下载，THEN THE Audio_Separation_Engine SHALL 提示用户并自动下载模型文件
3. THE Audio_Separation_Engine SHALL 在下载模型时显示下载进度和速度
4. THE Audio_Separation_Engine SHALL 将模型文件缓存在本地目录（用户数据目录）
5. THE Audio_Separation_Engine SHALL 支持用户选择不同的模型版本（htdemucs、htdemucs_ft、htdemucs_6s）
6. THE Audio_Separation_Engine SHALL 验证下载的模型文件完整性（校验和验证）

### 需求 13：批量处理

**用户故事：** 作为用户，我希望能够批量处理多个音频文件，以便提高工作效率。

#### 验收标准

1. WHERE 批量处理功能启用，THE Audio_Separation_Engine SHALL 允许用户添加多个音频文件到处理队列
2. WHERE 批量处理功能启用，THE Audio_Separation_Engine SHALL 按顺序处理队列中的所有文件
3. WHERE 批量处理功能启用，THE GUI_Framework SHALL 显示整体进度和当前处理的文件
4. WHERE 批量处理功能启用，THE Audio_Separation_Engine SHALL 在处理完成后自动导出所有分离的音轨
5. WHERE 批量处理功能启用，THE Audio_Separation_Engine SHALL 允许用户暂停和恢复批量处理
6. WHERE 批量处理功能启用，IF 某个文件处理失败，THEN THE Audio_Separation_Engine SHALL 记录错误并继续处理下一个文件

### 需求 14：音效处理

**用户故事：** 作为音频编辑者，我希望能够对音轨应用基本的音效处理（EQ、混响等），以便改善音质。

#### 验收标准

1. WHERE 音效处理功能启用，THE Track_Manager SHALL 支持对每个音轨应用均衡器（EQ）
2. WHERE 音效处理功能启用，THE Track_Manager SHALL 支持对每个音轨应用混响效果
3. WHERE 音效处理功能启用，THE Track_Manager SHALL 支持对每个音轨应用压缩器
4. WHERE 音效处理功能启用，THE Waveform_Editor SHALL 实时预览音效处理效果
5. WHERE 音效处理功能启用，THE Track_Manager SHALL 允许用户保存和加载音效预设
6. WHERE 音效处理功能启用，THE Audio_Mixer SHALL 在导出时应用所有音效处理

### 需求 15：键盘快捷键

**用户故事：** 作为高级用户，我希望能够使用键盘快捷键执行常用操作，以便提高工作效率。

#### 验收标准

1. THE GUI_Framework SHALL 支持空格键播放/暂停音频
2. THE GUI_Framework SHALL 支持 Ctrl+Z 撤销和 Ctrl+Y 重做
3. THE GUI_Framework SHALL 支持 Ctrl+S 保存项目
4. THE GUI_Framework SHALL 支持 Ctrl+O 打开音频文件
5. THE GUI_Framework SHALL 支持 Ctrl+E 导出音频
6. THE GUI_Framework SHALL 支持 Delete 键删除选中的音轨
7. THE GUI_Framework SHALL 支持 M 键切换选中音轨的静音状态
8. THE GUI_Framework SHALL 支持 S 键切换选中音轨的独奏状态
9. THE GUI_Framework SHALL 在帮助菜单中显示所有可用的键盘快捷键

### 需求 16：配置和偏好设置

**用户故事：** 作为用户，我希望能够自定义应用程序的行为和外观，以便适应我的工作习惯。

#### 验收标准

1. THE GUI_Framework SHALL 提供设置对话框供用户配置应用程序
2. THE GUI_Framework SHALL 允许用户选择默认的音频导出格式和质量
3. THE GUI_Framework SHALL 允许用户选择默认的分离模型版本
4. THE GUI_Framework SHALL 允许用户配置临时文件存储位置
5. THE GUI_Framework SHALL 允许用户选择界面主题（浅色/深色）
6. THE GUI_Framework SHALL 允许用户配置是否使用 GPU 加速
7. THE GUI_Framework SHALL 将用户设置持久化保存到配置文件
8. WHEN 应用启动，THE GUI_Framework SHALL 加载用户的偏好设置

### 需求 17：帮助和文档

**用户故事：** 作为新用户，我希望能够访问帮助文档和教程，以便快速学习如何使用应用程序。

#### 验收标准

1. THE GUI_Framework SHALL 提供帮助菜单访问用户文档
2. THE GUI_Framework SHALL 在首次启动时显示快速入门向导
3. THE GUI_Framework SHALL 提供工具提示（Tooltip）解释界面元素的功能
4. THE GUI_Framework SHALL 在帮助菜单中提供关于对话框显示版本信息和开源许可证
5. THE GUI_Framework SHALL 提供示例项目文件供用户学习

### 需求 18：开源许可证合规

**用户故事：** 作为开源项目维护者，我希望确保应用程序遵守所有依赖库的开源许可证要求。

#### 验收标准

1. THE Audio_Separation_Engine SHALL 在应用程序中包含所有依赖库的许可证声明
2. THE Audio_Separation_Engine SHALL 使用与依赖库兼容的开源许可证（MIT 或 Apache 2.0）
3. THE GUI_Framework SHALL 在关于对话框中显示第三方库的许可证信息
4. THE Audio_Separation_Engine SHALL 在源代码仓库中包含 LICENSE 文件
5. THE Audio_Separation_Engine SHALL 在源代码仓库中包含 NOTICE 文件列出所有第三方依赖

### 需求 19：跨平台兼容性

**用户故事：** 作为 Windows 用户，我希望应用程序能够在 Windows 10 及以上版本稳定运行。

#### 验收标准

1. THE Audio_Separation_Engine SHALL 在 Windows 10 及以上版本上运行
2. THE GUI_Framework SHALL 使用原生 Windows 风格的界面元素
3. THE Audio_Separation_Engine SHALL 支持 Windows 文件路径格式（包括 Unicode 字符）
4. THE Audio_Separation_Engine SHALL 在 Windows 开始菜单中创建应用程序快捷方式
5. THE Audio_Separation_Engine SHALL 关联支持的音频文件格式（可选）
6. THE Audio_Separation_Engine SHALL 在 Windows 任务栏中显示应用程序图标和进度

### 需求 20：数据安全和隐私

**用户故事：** 作为用户，我希望我的音频文件和项目数据保持私密和安全。

#### 验收标准

1. THE Audio_Separation_Engine SHALL 仅在本地处理音频文件，不上传到任何远程服务器
2. THE Project_Manager SHALL 将所有项目数据存储在用户本地文件系统
3. THE Audio_Separation_Engine SHALL 在用户关闭项目时清理临时文件
4. THE Audio_Separation_Engine SHALL 不收集或传输任何用户数据或使用统计信息
5. THE Audio_Separation_Engine SHALL 在用户手动删除时完全移除缓存的模型文件

## 优先级分类

### P0（必须有）
- 需求 1：音频文件导入
- 需求 2：音频源分离
- 需求 3：波形可视化
- 需求 4：音频播放控制
- 需求 7：音频导出
- 需求 10：错误处理和日志记录
- 需求 11：性能要求
- 需求 12：模型管理

### P1（应该有）
- 需求 5：音频替换功能
- 需求 6：音轨编辑操作
- 需求 8：项目保存和加载
- 需求 9：用户界面响应性
- 需求 15：键盘快捷键
- 需求 16：配置和偏好设置
- 需求 19：跨平台兼容性
- 需求 20：数据安全和隐私

### P2（可以有）
- 需求 13：批量处理
- 需求 14：音效处理
- 需求 17：帮助和文档
- 需求 18：开源许可证合规

## 技术约束

1. **编程语言**：Python 3.8 及以上版本
2. **音频分离模型**：Demucs（Meta 开源）或 Spleeter（Deezer 开源）
3. **GUI 框架**：PyQt6 或 PySide6
4. **音频处理库**：Pedalboard（Spotify）、PyDub、soundfile、librosa
5. **波形可视化**：PyQtGraph
6. **操作系统**：Windows 10 及以上版本（主要支持）
7. **硬件要求**：
   - 最低：4GB RAM，双核 CPU
   - 推荐：8GB RAM，四核 CPU，NVIDIA GPU（支持 CUDA）

## 非功能性需求总结

1. **性能**：处理 3-5 分钟的歌曲应在合理时间内完成（GPU：2 分钟，CPU：10 分钟）
2. **可用性**：界面直观，类似专业音频编辑软件（参考 Audacity、RipX）
3. **可靠性**：应用程序应稳定运行，不会因为常见操作而崩溃
4. **可维护性**：代码模块化，遵循 SOLID 原则，便于后续扩展
5. **可扩展性**：支持添加新的分离模型、音效插件、导出格式
6. **安全性**：本地处理，不上传用户数据，保护用户隐私

## 技术风险

1. **音频分离质量**：Demucs 模型的分离质量取决于音频类型和复杂度，某些音乐可能分离效果不佳
2. **性能优化**：实时波形渲染和音频播放需要仔细优化以避免卡顿
3. **内存管理**：处理大文件时需要有效管理内存，避免内存溢出
4. **时间同步**：音频替换时的时间对齐精度需要达到毫秒级
5. **GPU 兼容性**：不同 GPU 型号对 CUDA 的支持程度不同，需要充分测试
6. **依赖库版本**：PyTorch、Demucs 等库的版本兼容性需要仔细管理
