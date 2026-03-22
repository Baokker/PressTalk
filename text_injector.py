"""
文字注入模块
流程：pbcopy 写入剪贴板 → osascript 模拟 Cmd+V
用 AppleScript / System Events 执行按键，比 pynput Controller 更可靠，
在 .app bundle 环境下不受 pynput 权限问题影响。
转录文本会留在剪贴板中（方便用户二次使用）。
"""

import subprocess
import time


def inject(text: str):
    """将文字粘贴到当前光标位置。"""
    if not text:
        return

    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    time.sleep(0.1)
    subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to keystroke "v" using command down'],
        check=True,
    )
