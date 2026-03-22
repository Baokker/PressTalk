# my-voice-input

macOS 语音输入工具，按住右 Option 键说话，松开后自动转录并输入到当前光标位置。

## 功能

- **按住右 Option**：开始录音
- **松开右 Option**：停止录音，转录，自动粘贴到光标位置
- 支持两种转录后端：讯飞实时语音转写大模型（联网）/ 本地 faster-whisper（离线）

## 环境要求

- macOS（已在 Apple Silicon 上测试）
- Python 3.9+

## 安装

**1. 安装依赖**

```bash
pip3 install -r requirements.txt
```

如需使用本地 Whisper：

```bash
pip3 install faster-whisper
```

**2. 配置 API Key**

```bash
cp .env.example .env
```

用编辑器打开 `.env`，填入讯飞 API 信息：

```
XFYUN_APPID=你的AppID
XFYUN_API_KEY=你的APIKey（accessKeyId）
XFYUN_API_SECRET=你的APISecret（accessKeySecret）
```

在[讯飞控制台](https://console.xfyun.cn/) → 你的应用 → **实时语音转写大模型** 中获取。

**3. 授予 macOS 权限（必须）**

程序需要两个系统权限：

| 权限 | 位置 | 用途 |
|------|------|------|
| 输入监控 | 系统设置 → 隐私与安全性 → 输入监控 | 监听右 Option 按键 |
| 辅助功能 | 系统设置 → 隐私与安全性 → 辅助功能 | 模拟 Cmd+V 粘贴文字 |

将你的终端（Terminal / iTerm2）加入上述两个列表并勾选。

## 运行

```bash
python3 main.py
```

## 切换到本地 Whisper（离线模式）

在 `.env` 中设置：

```
STT_BACKEND=whisper
WHISPER_MODEL=turbo   # 推荐，~1.6GB，中文质量好；可选 tiny/base/small/medium/large-v3
```

首次运行会自动下载模型文件。

## 文件结构

```
├── main.py              # 入口
├── hotkey_listener.py   # 右 Option 键监听，串联录音→转录→注入
├── recorder.py          # 麦克风录音（sounddevice）
├── transcriber.py       # 语音转录（讯飞 API / 本地 Whisper）
├── text_injector.py     # 文字注入（pbcopy + pynput Cmd+V）
├── config.py            # 配置加载
├── requirements.txt     # 依赖清单
└── .env.example         # 环境变量模板
```
