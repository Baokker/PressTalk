#!/usr/bin/env python3
"""
macOS 菜单栏入口
运行方式：python app.py
程序常驻菜单栏，不显示 Dock 图标（LSUIElement=True 打包后生效）。
"""

import sys
import threading

import rumps

from config import VOLC_APP_ID, VOLC_ACCESS_KEY, DEEPSEEK_API_KEY
from hotkey_listener import HotkeyListener
from formatter import format_smart
from transcriber import warmup
from main import check_accessibility, check_config

# 菜单栏状态图标
_ICONS = {
    "idle":         "🎙",
    "recording":    "🔴",
    "transcribing": "⏳",
    "done":         "✓",
}


class VoiceInputApp(rumps.App):
    def __init__(self):
        super().__init__(_ICONS["idle"], quit_button=None)

        self._count = 0
        self._count_item = rumps.MenuItem(f"今日转录：0 次", callback=None)
        self._smart_item = rumps.MenuItem(
            "智能整理（右 Command）",
            callback=self._toggle_smart,
        )
        self._smart_item.state = bool(DEEPSEEK_API_KEY)  # 有 Key 则默认开启

        self.menu = [
            self._count_item,
            None,  # 分隔线
            self._smart_item,
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

    # ── 状态回调 ──────────────────────────────────────────────────────────────

    def _on_state(self, state: str):
        self.title = _ICONS.get(state, _ICONS["idle"])
        if state == "done":
            self._count += 1
            self._count_item.title = f"今日转录：{self._count} 次"
            # 0.8s 后恢复待机图标
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
                message="请在 .env 中填写 DEEPSEEK_API_KEY 后重启应用。",
            )
            return
        sender.state = not sender.state
        self._listener._formatter = format_smart if sender.state else None

    def _quit(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    check_accessibility()
    check_config()
    VoiceInputApp().run()
