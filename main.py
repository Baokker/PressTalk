#!/usr/bin/env python3
"""
macOS 语音输入工具
用法：python main.py
"""

import sys
from config import (
    XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET,
    VOLC_APP_ID, VOLC_ACCESS_KEY,
    STT_BACKEND, DEEPSEEK_API_KEY,
)
from hotkey_listener import HotkeyListener
from formatter import format_smart


def check_accessibility():
    """检查辅助功能权限（文字注入需要）。"""
    try:
        import ctypes
        app_services = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        trusted = app_services.AXIsProcessTrusted()
        if not trusted:
            print("=" * 60)
            print("[权限缺失] 辅助功能（Accessibility）未授权！")
            print("文字注入功能将无法工作。")
            print()
            print("请前往：系统设置 → 隐私与安全性 → 辅助功能")
            print("将【终端】（Terminal / iTerm2）加入列表并勾选。")
            print("添加后重新运行程序。")
            print("=" * 60)
            sys.exit(1)
    except Exception:
        pass  # 无法检测时跳过，不阻断运行


def check_config():
    if STT_BACKEND == "xfyun":
        missing = []
        if not XFYUN_APPID:
            missing.append("XFYUN_APPID")
        if not XFYUN_API_KEY:
            missing.append("XFYUN_API_KEY")
        if not XFYUN_API_SECRET:
            missing.append("XFYUN_API_SECRET")
        if missing:
            print(f"[错误] 缺少配置项：{', '.join(missing)}")
            print("请将 .env.example 复制为 .env 并填写 API 信息。")
            sys.exit(1)
    elif STT_BACKEND == "volcengine":
        missing = []
        if not VOLC_APP_ID:
            missing.append("VOLC_APP_ID")
        if not VOLC_ACCESS_KEY:
            missing.append("VOLC_ACCESS_KEY")
        if missing:
            print(f"[错误] 缺少配置项：{', '.join(missing)}")
            print("请在 .env 中填写火山引擎 ASR 的 AppID 和 Access Token。")
            sys.exit(1)


def main():
    check_accessibility()
    check_config()
    if not DEEPSEEK_API_KEY:
        print("[提示] 未配置 DEEPSEEK_API_KEY，右 Option + Space 智能整理功能不可用。")
        formatter = None
    else:
        formatter = format_smart
    listener = HotkeyListener(formatter=formatter)
    try:
        listener.start()
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
