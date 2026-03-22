"""
py2app 打包配置
用法：python setup.py py2app
输出：dist/VoiceInput.app
"""

import os
import shutil
import sys
import zipfile

# modulegraph 扫描 numpy/openai 等复杂包的 AST 时会爆栈，调高限制
sys.setrecursionlimit(10000)

from setuptools import setup

APP = ["app.py"]
DATA_FILES = [
    ("", [".env"]),  # 打包进 Resources 根目录，供 config.py 的 load_dotenv 读取
]
OPTIONS = {
    "argv_emulation": False,
    "frameworks": [
        "/opt/anaconda3/lib/libffi.8.dylib",
        "/opt/anaconda3/lib/libssl.3.dylib",
        "/opt/anaconda3/lib/libcrypto.3.dylib",
    ],
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
        "_sounddevice_data",
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


def patch_sounddevice():
    """
    py2app 把 _sounddevice_data 压缩进了 python313.zip，
    但 sounddevice 需要在运行时 dlopen libportaudio.dylib，不能在 zip 里。
    构建完成后把它从 zip 解压出来放到 Resources 目录。
    """
    res = "dist/VoiceInput.app/Contents/Resources"
    zip_path = os.path.join(res, "lib", "python313.zip")
    if not os.path.exists(zip_path):
        return

    extract_prefix = "_sounddevice_data"
    extracted = False
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [n for n in zf.namelist() if n.startswith(extract_prefix)]
        if names:
            zf.extractall(res, members=names)
            extracted = True

    if extracted:
        # 从 zip 里删除这些条目
        tmp = zip_path + ".tmp"
        with zipfile.ZipFile(zip_path, "r") as zin, \
             zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if not item.filename.startswith(extract_prefix):
                    zout.writestr(item, zin.read(item.filename))
        os.replace(tmp, zip_path)
        print(f"[patch] _sounddevice_data 已从 zip 解压到 {res}")


if "py2app" in sys.argv:
    import atexit
    atexit.register(patch_sounddevice)
