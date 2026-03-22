import os
from dotenv import load_dotenv

load_dotenv()

XFYUN_APPID = os.getenv("XFYUN_APPID", "")
XFYUN_API_KEY = os.getenv("XFYUN_API_KEY", "")
XFYUN_API_SECRET = os.getenv("XFYUN_API_SECRET", "")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

VOLC_APP_ID     = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")

STT_BACKEND = os.getenv("STT_BACKEND", "xfyun")   # "xfyun" / "whisper" / "volcengine"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "turbo")  # tiny/base/small/medium/turbo/large-v3

# 录音参数
SAMPLE_RATE = 16000
CHANNELS = 1
