"""
文字注入模块
流程：pbcopy 写入剪贴板 → pynput 模拟 Cmd+V → pbcopy 恢复剪贴板
pynput 已有辅助功能权限（热键监听在同一进程），Cmd+V 可靠。
"""

import subprocess
import time

from pynput.keyboard import Controller, Key

_keyboard = Controller()


def inject(text: str):
    """将文字粘贴到当前光标位置。"""
    if not text:
        return

    # 用 pbcopy 保存/恢复剪贴板（比 pyperclip 更直接）
    original = subprocess.run(["pbpaste"], capture_output=True).stdout

    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        time.sleep(0.1)

        # pynput 在同一进程内已有辅助功能权限，Cmd+V 可靠
        with _keyboard.pressed(Key.cmd):
            _keyboard.press("v")
            _keyboard.release("v")

        time.sleep(0.15)
    finally:
        if original:
            time.sleep(0.05)
            subprocess.run(["pbcopy"], input=original)
