"""
热键监听模块
  - 按住右 Option，说话，松开 → 转录并注入文字（普通模式）
  - 按住右 Command，说话，松开 → 转录 + 智能整理（需配置 DEEPSEEK_API_KEY）
无需 Karabiner，不影响其他按键原有功能。
"""

import threading
from pynput import keyboard

from recorder import Recorder
from transcriber import transcribe
from text_injector import inject

# 监听的两个 PTT 键
_PTT_KEYS = {keyboard.Key.alt_r, keyboard.Key.cmd_r}


class HotkeyListener:
    def __init__(self, formatter=None):
        """
        formatter: 可选，接收转录文本并返回整理后文本的函数（智能整理模式）
        """
        self._recorder = Recorder()
        self._formatter = formatter
        self._active_key = None   # 当前按住的 PTT 键
        self._listener = None
        self._processing = False
        self._lock = threading.Lock()

    def start(self):
        print("语音输入已启动。")
        print("  【右 Option】按住说话，松开 → 转录并输入")
        if self._formatter:
            print("  【右 Command】按住说话，松开 → 转录 + 智能整理")
        print("按 Ctrl+C 退出。\n")
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        self._listener.join()

    def _on_press(self, key):
        if key not in _PTT_KEYS:
            return
        with self._lock:
            if self._active_key is not None or self._processing:
                return
            self._active_key = key
        self._recorder.start()

    def _on_release(self, key):
        if key not in _PTT_KEYS:
            return
        with self._lock:
            if self._active_key != key:
                return
            smart_mode = (key == keyboard.Key.cmd_r)
            self._active_key = None
            self._processing = True

        audio = self._recorder.stop()

        # 在独立线程处理，不阻塞监听
        threading.Thread(
            target=self._process,
            args=(audio, smart_mode),
            daemon=True,
        ).start()

    def _process(self, audio: bytes, smart_mode: bool):
        try:
            text = transcribe(audio)

            if not text.strip():
                print("[未识别到有效语音]")
                return

            if smart_mode and self._formatter:
                print(f"[原文] {text[:80]}{'...' if len(text) > 80 else ''}")
                print("[整理中...]")
                text = self._formatter(text)
                print(f"[整理后] {text[:80]}{'...' if len(text) > 80 else ''}")
            else:
                print(f"[识别结果] {text[:80]}{'...' if len(text) > 80 else ''}")
            inject(text)
        except Exception as e:
            print(f"[错误] {e}")
        finally:
            with self._lock:
                self._processing = False
