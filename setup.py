"""
py2app 打包配置
用法：python setup.py py2app
输出：dist/VoiceInput.app
"""

import sys
# modulegraph 扫描 numpy/openai 等复杂包的 AST 时会爆栈，调高限制
sys.setrecursionlimit(10000)

from setuptools import setup

APP = ["app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "VoiceInput",
        "CFBundleDisplayName": "VoiceInput",
        "CFBundleIdentifier": "com.yourname.voiceinput",
        "CFBundleVersion": "1.0.0",
        "LSUIElement": True,  # 不在 Dock 显示，只在菜单栏
        "NSMicrophoneUsageDescription": "语音输入需要麦克风权限",
        "NSAppleEventsUsageDescription": "文字注入需要辅助功能权限",
    },
    "packages": [
        "websocket",
        "pynput",
        "rumps",
        "openai",
        "sounddevice",
        "numpy",
        "scipy",
        "pyperclip",
        "dotenv",
    ],
    "includes": [
        "config",
        "transcriber",
        "recorder",
        "formatter",
        "hotkey_listener",
        "text_injector",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
