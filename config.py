import os
from pathlib import Path
from dotenv import load_dotenv

# 先找脚本同目录的 .env（.app bundle 里的 Resources 目录）
# 再 fallback 到 CWD（命令行开发模式）
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv()  # fallback

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

VOLC_APP_ID     = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")

# 录音参数
SAMPLE_RATE = 16000
CHANNELS = 1
