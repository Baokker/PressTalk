"""
可视化设置窗口（tkinter）
在独立子进程中运行（app.py 通过 subprocess.Popen 调用）。
也可直接运行：python3 settings_window.py
"""

import ctypes
import ctypes.util
import os
import subprocess
import tkinter as tk
import tkinter.messagebox as msgbox
import webbrowser
from pathlib import Path

# .env 文件路径（与本文件同目录）
_ENV_PATH = Path(__file__).parent / ".env"

# 权限深链接
_PERM_URLS = {
    "辅助功能": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "输入监控": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "麦克风":   "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


# ── 权限检测 ──────────────────────────────────────────────────────────────────

def _check_accessibility() -> str:
    try:
        lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return "✓ 已授权" if lib.AXIsProcessTrusted() else "✗ 未授权"
    except Exception:
        return "? 检测失败"


def _check_input_monitoring() -> str:
    try:
        iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
        iokit.IOHIDCheckAccess.restype = ctypes.c_uint32
        status = iokit.IOHIDCheckAccess(1)  # 1 = kIOHIDRequestTypeListenEvent
        return {0: "✓ 已授权", 1: "✗ 未授权", 2: "? 未确定"}.get(status, "? 未知")
    except Exception:
        return "? 检测失败"


def _check_microphone() -> str:
    try:
        # 优先用 pyobjc（若已安装）
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio  # type: ignore
        status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
        return {0: "? 未确定", 1: "✗ 受限", 2: "✗ 未授权", 3: "✓ 已授权"}.get(status, "? 未知")
    except ImportError:
        pass
    try:
        # fallback：纯 ctypes ObjC runtime
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AVFoundation.framework/AVFoundation")
        objc.objc_getClass.restype    = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype     = ctypes.c_long

        NSString   = objc.objc_getClass(b"NSString")
        sel_str    = objc.sel_registerName(b"stringWithUTF8String:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        audio_type = objc.objc_msgSend(NSString, sel_str, b"soun")

        AVCaptureDevice = objc.objc_getClass(b"AVCaptureDevice")
        sel_auth = objc.sel_registerName(b"authorizationStatusForMediaType:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        status = objc.objc_msgSend(AVCaptureDevice, sel_auth, audio_type)
        return {0: "? 未确定", 1: "✗ 受限", 2: "✗ 未授权", 3: "✓ 已授权"}.get(status, "? 未知")
    except Exception:
        return "? 检测失败"


# ── .env 读写 ─────────────────────────────────────────────────────────────────

def _read_env() -> dict:
    vals = {"VOLC_APP_ID": "", "VOLC_ACCESS_KEY": "", "DEEPSEEK_API_KEY": ""}
    if not _ENV_PATH.exists():
        return vals
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k in vals:
            vals[k] = v.strip().strip('"').strip("'")
    return vals


def _write_env(updates: dict):
    lines = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        k = stripped.split("=", 1)[0].strip()
        if k in updates:
            new_lines.append(f"{k}={updates[k]}")
            written.add(k)
        else:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in written:
            new_lines.append(f"{k}={v}")
    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ── 窗口 ─────────────────────────────────────────────────────────────────────

def open_settings():
    root = tk.Tk()
    _build_window(root)
    root.mainloop()


def _build_window(root: tk.Tk):
    root.title("VoiceInput 设置")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    pad = {"padx": 12, "pady": 4}
    current = _read_env()

    # ── 火山引擎 ─────────────────────────────────────────────────────────────
    tk.Label(root, text="火山引擎配置", font=("", 13, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(14, 2))

    tk.Label(root, text="App ID:").grid(row=1, column=0, sticky="e", **pad)
    volc_id = tk.Entry(root, width=36)
    volc_id.insert(0, current["VOLC_APP_ID"])
    volc_id.grid(row=1, column=1, **pad)

    tk.Label(root, text="Access Key:").grid(row=2, column=0, sticky="e", **pad)
    volc_key = tk.Entry(root, width=36, show="•")
    volc_key.insert(0, current["VOLC_ACCESS_KEY"])
    volc_key.grid(row=2, column=1, **pad)

    # App ID 和 Access Key 可在同一页面获取，只需一个按钮
    tk.Button(root, text="前往控制台获取 →",
              command=lambda: webbrowser.open("https://console.volcengine.com/speech/service/10038")
              ).grid(row=1, column=2, rowspan=2, **pad)

    # ── DeepSeek ─────────────────────────────────────────────────────────────
    tk.Label(root, text="DeepSeek 配置（可选）", font=("", 13, "bold")).grid(
        row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 2))

    tk.Label(root, text="API Key:").grid(row=4, column=0, sticky="e", **pad)
    ds_key = tk.Entry(root, width=36, show="•")
    ds_key.insert(0, current["DEEPSEEK_API_KEY"])
    ds_key.grid(row=4, column=1, **pad)
    tk.Button(root, text="获取 →",
              command=lambda: webbrowser.open("https://platform.deepseek.com/api_keys")
              ).grid(row=4, column=2, **pad)

    # ── 权限状态 ──────────────────────────────────────────────────────────────
    tk.Label(root, text="权限状态", font=("", 13, "bold")).grid(
        row=5, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 2))

    perms = [
        ("辅助功能", _check_accessibility(),    "辅助功能"),
        ("输入监控", _check_input_monitoring(), "输入监控"),
        ("麦克风",   _check_microphone(),       "麦克风"),
    ]
    for i, (name, status, url_key) in enumerate(perms):
        row = 6 + i
        tk.Label(root, text=f"{name}:").grid(row=row, column=0, sticky="e", **pad)
        color = "green" if status.startswith("✓") else ("red" if status.startswith("✗") else "orange")
        tk.Label(root, text=status, fg=color).grid(row=row, column=1, sticky="w", **pad)
        tk.Button(root, text="前往系统设置",
                  command=lambda u=_PERM_URLS[url_key]: subprocess.run(["open", u], check=False)
                  ).grid(row=row, column=2, **pad)

    # ── 使用说明 ──────────────────────────────────────────────────────────────
    tk.Label(root, text="使用说明", font=("", 13, "bold")).grid(
        row=9, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 2))
    tk.Label(root,
             text="右 Option：按住说话，松开后转录并注入文字\n"
                  "右 Command：同上，转录后再由 DeepSeek 智能整理",
             justify="left", fg="#444").grid(
        row=10, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 8))

    # ── 分隔线 ────────────────────────────────────────────────────────────────
    tk.Frame(root, height=1, bg="#ccc").grid(
        row=11, column=0, columnspan=3, sticky="ew", padx=12, pady=6)

    # ── 按钮 ──────────────────────────────────────────────────────────────────
    btn_frame = tk.Frame(root)
    btn_frame.grid(row=12, column=0, columnspan=3, pady=(4, 12))

    def _test():
        btn_test.config(state="disabled", text="连接中…")
        import threading
        def _run():
            try:
                import socket
                s = socket.create_connection(("openspeech.bytedance.com", 443), timeout=5)
                s.close()
                root.after(0, lambda: (
                    btn_test.config(state="normal", text="测试连接"),
                    msgbox.showinfo("连接成功", "火山引擎服务器连接正常！", parent=root),
                ))
            except Exception as e:
                root.after(0, lambda: (
                    btn_test.config(state="normal", text="测试连接"),
                    msgbox.showerror("连接失败", str(e), parent=root),
                ))
        threading.Thread(target=_run, daemon=True).start()

    def _save():
        _write_env({
            "VOLC_APP_ID":      volc_id.get().strip(),
            "VOLC_ACCESS_KEY":  volc_key.get().strip(),
            "DEEPSEEK_API_KEY": ds_key.get().strip(),
        })
        msgbox.showinfo("已保存", "配置已保存。\n请重启 VoiceInput 以生效。", parent=root)

    btn_test = tk.Button(btn_frame, text="测试连接", width=12, command=_test)
    btn_test.pack(side="left", padx=8)
    tk.Button(btn_frame, text="保存", width=12, command=_save).pack(side="left", padx=8)
    tk.Button(btn_frame, text="关闭", width=12, command=root.destroy).pack(side="left", padx=8)


if __name__ == "__main__":
    open_settings()
