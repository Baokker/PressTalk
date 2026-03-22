"""
热键监听模块
监听右 Option 键（alt_r）：
  - 按下右 Option：开始录音
  - 松开右 Option：停止录音，触发转录+注入
  - 按下右 Option + Space（同时）：触发智能整理模式
无需 Karabiner，不影响 Fn 键原有功能。
"""

import threading
from pynput import keyboard

from recorder import Recorder
from transcriber import transcribe
from text_injector import inject


class HotkeyListener:
    def __init__(self, formatter=None):
        """
        formatter: 可选，接收转录文本并返回整理后文本的函数（Phase 2）
        """
        self._recorder = Recorder()
        self._formatter = formatter
        self._ptt_pressed = False
        self._space_pressed = False
        self._listener = None
        self._processing = False
        self._lock = threading.Lock()

    def start(self):
        print("语音输入已启动。按住【右 Option】开始录音，松开后自动转录并输入。")
        print("按 Ctrl+C 退出。\n")
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        self._listener.join()

    def _on_press(self, key):
        if key == keyboard.Key.alt_r:
            with self._lock:
                if self._ptt_pressed or self._processing:
                    return
                self._ptt_pressed = True
            self._recorder.start()

        elif key == keyboard.Key.space:
            with self._lock:
                self._space_pressed = True

    def _on_release(self, key):
        if key == keyboard.Key.alt_r:
            with self._lock:
                if not self._ptt_pressed:
                    return
                self._ptt_pressed = False
                smart_mode = self._space_pressed
                self._processing = True

            audio = self._recorder.stop()

            # 在独立线程处理，不阻塞监听
            threading.Thread(
                target=self._process,
                args=(audio, smart_mode),
                daemon=True,
            ).start()

        elif key == keyboard.Key.space:
            with self._lock:
                self._space_pressed = False

    def _process(self, audio: bytes, smart_mode: bool):
        try:
            text = transcribe(audio)

            if not text.strip():
                print("[未识别到有效语音]")
                return

            if smart_mode and self._formatter:
                print("[整理中...]")
                text = self._formatter(text)

            print(f"[识别结果] {text[:80]}{'...' if len(text) > 80 else ''}")
            inject(text)
        except Exception as e:
            print(f"[错误] {e}")
        finally:
            with self._lock:
                self._processing = False
