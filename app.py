#!/usr/bin/env python3
"""
macOS 菜单栏入口
运行方式：python app.py
程序常驻菜单栏，不显示 Dock 图标（LSUIElement=True 打包后生效）。
"""

import subprocess
import sys
import threading

import rumps

from config import VOLC_APP_ID, VOLC_ACCESS_KEY, DEEPSEEK_API_KEY
from hotkey_listener import HotkeyListener
from formatter import format_smart
from transcriber import warmup

# 菜单栏状态图标（纯 Unicode 文字符号，避免 emoji 在菜单栏被裁剪）
_ICONS = {
    "idle":         "●",
    "recording":    "◉",
    "transcribing": "◌",
    "done":         "✓",
}

# 系统设置深链接
_PERM_URLS = {
    "辅助功能":  "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "输入监控":  "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "麦克风":    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


def _open_pref(url: str):
    subprocess.run(["open", url], check=False)


class VoiceInputApp(rumps.App):
    def __init__(self):
        super().__init__(_ICONS["idle"], quit_button=None)

        self._count = 0
        self._count_item = rumps.MenuItem("今日转录：0 次", callback=None)
        self._smart_item = rumps.MenuItem(
            "智能整理（右 Command）",
            callback=self._toggle_smart,
        )
        self._smart_item.state = bool(DEEPSEEK_API_KEY)  # 有 Key 则默认开启

        # 权限设置子菜单
        perm_menu = rumps.MenuItem("权限设置")
        for name, url in _PERM_URLS.items():
            item = rumps.MenuItem(f"前往 → {name}", callback=lambda _, u=url: _open_pref(u))
            perm_menu.add(item)

        self.menu = [
            self._count_item,
            None,
            self._smart_item,
            None,
            rumps.MenuItem("设置", callback=self._open_settings),
            perm_menu,
            None,
            rumps.MenuItem("退出", callback=self._quit),
        ]

        formatter = format_smart if (DEEPSEEK_API_KEY and self._smart_item.state) else None
        self._listener = HotkeyListener(
            formatter=formatter,
            on_state_change=self._on_state,
        )
        threading.Thread(target=self._listener.start, daemon=True).start()
        warmup()

        # 首次运行（无 API Key）自动打开设置窗口
        if not VOLC_APP_ID or not VOLC_ACCESS_KEY:
            threading.Timer(0.5, lambda: self._open_settings(None)).start()

    # ── 状态回调 ──────────────────────────────────────────────────────────────

    def _on_state(self, state: str):
        self.title = _ICONS.get(state, _ICONS["idle"])
        if state == "done":
            self._count += 1
            self._count_item.title = f"今日转录：{self._count} 次"
            threading.Timer(0.8, self._reset_icon).start()
        elif state == "idle":
            self.title = _ICONS["idle"]

    def _reset_icon(self):
        self.title = _ICONS["idle"]

    # ── 菜单回调 ──────────────────────────────────────────────────────────────

    def _toggle_smart(self, sender):
        if not DEEPSEEK_API_KEY:
            rumps.alert(
                title="未配置 DeepSeek API Key",
                message="请打开「设置」填写 DEEPSEEK_API_KEY 后重启应用。",
            )
            return
        sender.state = not sender.state
        self._listener._formatter = format_smart if sender.state else None

    def _open_settings(self, _):
        import os
        subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), "settings_window.py")],
            close_fds=True,
        )

    def _quit(self, _):
        rumps.quit_application()


def _is_accessibility_trusted() -> bool:
    try:
        import ctypes
        lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return lib.AXIsProcessTrusted()
    except Exception:
        return True  # 无法检测时放行


if __name__ == "__main__":
    # 辅助功能检查：未授权时弹窗提示，附带跳转按钮
    if not _is_accessibility_trusted():
        response = rumps.alert(
            title="需要辅助功能权限",
            message=(
                "文字注入功能需要辅助功能权限。\n\n"
                "请点击「前往授权」跳转到系统设置，\n"
                "将 VoiceInput 加入列表并勾选，然后重新启动应用。\n\n"
                "同时请确认已授予【输入监控】和【麦克风】权限。"
            ),
            ok="前往授权",
            cancel="稍后再说",
        )
        if response == 1:  # OK button
            _open_pref(_PERM_URLS["辅助功能"])

    VoiceInputApp().run()
