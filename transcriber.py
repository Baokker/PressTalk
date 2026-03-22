"""
语音转录模块
支持三种后端（通过 .env 的 STT_BACKEND 切换）：
  - xfyun:       讯飞实时语音转写大模型 API（需联网）
  - volcengine:  火山引擎豆包 ASR Seed-ASR 2.0（推荐，准确率更高）
  - whisper:     本地 faster-whisper（离线，turbo 模型）
"""

import base64
import gzip
import hashlib
import hmac
import io
import json
import struct
import threading
import time
import uuid
import wave
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import websocket

from config import (
    CHANNELS,
    SAMPLE_RATE,
    STT_BACKEND,
    WHISPER_MODEL,
    XFYUN_APPID,
    XFYUN_API_KEY,
    XFYUN_API_SECRET,
    VOLC_APP_ID,
    VOLC_ACCESS_KEY,
)

XFYUN_WS_URL = "wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1"
CHUNK_SIZE = 1280  # 1280 字节 / 40ms（16kHz 16bit mono）

# ── 火山引擎 ASR 常量 ──────────────────────────────────────────────────────
VOLC_WS_URL     = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
VOLC_RESOURCE_ID = "volc.bigasr.sauc.duration"
VOLC_CHUNK_SIZE  = 5120  # 5120 字节 = 160ms（16kHz 16bit mono）

# 帧头字节 byte1（msg_type<<4 | flags）
_VOLC_FULL_CLIENT   = 0x10  # Full client request, no-flag
_VOLC_AUDIO_MID     = 0x20  # Audio-only, mid-stream
_VOLC_AUDIO_LAST    = 0x22  # Audio-only, last packet
# 帧头字节 byte2（serialization<<4 | compression）
_VOLC_JSON_GZIP     = 0x11  # JSON + gzip
_VOLC_RAW_GZIP      = 0x01  # raw bytes + gzip

# 本地 Whisper 模型（懒加载，首次使用时初始化）
_whisper_model = None
_whisper_lock = threading.Lock()


def transcribe(audio_bytes: bytes) -> str:
    """将 PCM 音频字节转录为文字。"""
    if not audio_bytes:
        return ""
    if STT_BACKEND == "whisper":
        return _transcribe_whisper(audio_bytes)
    if STT_BACKEND == "volcengine":
        return _transcribe_volcengine(audio_bytes)
    return _transcribe_xfyun_llm(audio_bytes)


# ──────────────────────────────────────────────
# 本地 faster-whisper
# ──────────────────────────────────────────────

def _get_whisper_model():
    """懒加载 Whisper 模型（只初始化一次）。"""
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            print(f"[加载 Whisper 模型 {WHISPER_MODEL}，首次需下载，请稍候...]")
            _whisper_model = WhisperModel(
                WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
            )
            print("[Whisper 模型已就绪]")
    return _whisper_model


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """将原始 PCM 包装为 WAV，供 faster-whisper 读取。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    buf.seek(0)
    return buf


def _transcribe_whisper(pcm_bytes: bytes) -> str:
    """用本地 faster-whisper 转录，中文优先。"""
    model = _get_whisper_model()
    wav_buf = _pcm_to_wav(pcm_bytes)
    segments, _ = model.transcribe(
        wav_buf,
        language="zh",
        beam_size=1,
        vad_filter=True,  # 过滤静音段，减少幻觉
    )
    return "".join(seg.text for seg in segments).strip()


# ──────────────────────────────────────────────
# 讯飞实时语音转写大模型
# ──────────────────────────────────────────────

def _build_url(session_id: str) -> str:
    """
    按文档要求构建鉴权 URL：
    1. 收集所有参数（不含 signature），按 key 字母序排序
    2. 每个 key/value 分别 URL 编码后拼成 baseString
    3. HmacSHA1(baseString, APISecret) 再 Base64 → signature
    """
    tz_cst = timezone(timedelta(hours=8))
    utc_str = datetime.now(tz=tz_cst).strftime("%Y-%m-%dT%H:%M:%S+0800")

    params = {
        "appId": XFYUN_APPID,
        "accessKeyId": XFYUN_API_KEY,
        "uuid": session_id,
        "utc": utc_str,
        "audio_encode": "pcm_s16le",
        "lang": "autodialect",
        "samplerate": str(SAMPLE_RATE),
    }

    sorted_keys = sorted(params.keys())
    base_string = "&".join(
        f"{quote(k, safe='')}={quote(str(params[k]), safe='')}"
        for k in sorted_keys
    )

    sig = base64.b64encode(
        hmac.new(
            XFYUN_API_SECRET.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    params["signature"] = sig

    query = "&".join(
        f"{quote(k, safe='')}={quote(str(v), safe='')}"
        for k, v in params.items()
    )
    return f"{XFYUN_WS_URL}?{query}"


def _transcribe_xfyun_llm(pcm_bytes: bytes) -> str:
    """调用讯飞实时语音转写大模型 API，返回识别文本。"""
    session_id = str(uuid.uuid4())
    result_segments: dict = {}  # seg_id -> text
    done_event = threading.Event()
    error_holder = []

    def on_message(ws, message):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        if data.get("msg_type") == "error" or "code" in data:
            desc = data.get("desc") or data.get("message") or str(data)
            error_holder.append(desc)
            done_event.set()
            return

        payload = data.get("data", {})
        ls = payload.get("ls", False)
        seg_id = payload.get("seg_id", 0)
        st = payload.get("cn", {}).get("st", {})
        result_type = st.get("type", "0")

        if result_type == "0":
            words = ""
            for ws_item in st.get("rt", []):
                for cw_item in ws_item.get("ws", []):
                    for cw in cw_item.get("cw", []):
                        words += cw.get("w", "")
            if words:
                result_segments[seg_id] = words

        if ls:
            done_event.set()

    def on_error(ws, error):
        error_holder.append(str(error))
        done_event.set()

    def on_close(ws, code, msg):
        done_event.set()

    def on_open(ws):
        threading.Thread(
            target=_send_audio,
            args=(ws, pcm_bytes, session_id),
            daemon=True,
        ).start()

    url = _build_url(session_id)
    ws_app = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    ws_thread = threading.Thread(
        target=ws_app.run_forever,
        kwargs={"ping_interval": 0},
        daemon=True,
    )
    ws_thread.start()

    print("[转录中...]")
    done_event.wait(timeout=30)
    ws_app.close()

    if error_holder:
        raise RuntimeError(f"讯飞 STT 错误: {error_holder[0]}")

    text = "".join(result_segments[k] for k in sorted(result_segments))
    return text.rstrip("。")


def _send_audio(ws, pcm_bytes: bytes, session_id: str):
    """尽快分帧发送 PCM 音频（去掉等待延迟），发完后发结束帧。"""
    offset = 0
    total = len(pcm_bytes)

    while offset < total:
        chunk = pcm_bytes[offset: offset + CHUNK_SIZE]
        ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)
        offset += CHUNK_SIZE

    ws.send(json.dumps({"end": True, "sessionId": session_id}))


# ──────────────────────────────────────────────
# 火山引擎豆包 ASR（Seed-ASR 2.0，enable_nonstream）
# ──────────────────────────────────────────────

def _volc_build_frame(byte1: int, byte2: int, payload: bytes) -> bytes:
    """拼装火山引擎二进制帧：4字节头 + 4字节长度（大端）+ payload。"""
    header = bytes([0x11, byte1, byte2, 0x00])
    return header + struct.pack(">I", len(payload)) + payload


def _volc_parse_response(data: bytes) -> dict:
    """解析服务器二进制帧，返回 JSON dict；错误帧直接 raise。"""
    msg_type = (data[1] >> 4) & 0x0F
    compress  = data[2] & 0x0F

    if msg_type == 0x0F:  # 错误帧：[4头][4 error_code][4 msg_size][msg]
        code = struct.unpack(">I", data[4:8])[0]
        size = struct.unpack(">I", data[8:12])[0]
        msg  = data[12:12 + size].decode("utf-8", errors="replace")
        raise RuntimeError(f"火山引擎 ASR 服务端错误 {code}: {msg}")

    payload_size = struct.unpack(">I", data[4:8])[0]
    raw = data[8:8 + payload_size]
    if compress == 0x01:
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _transcribe_volcengine(pcm_bytes: bytes) -> str:
    """调用火山引擎豆包 ASR（enable_nonstream=True），返回识别文本。"""
    result_holder = []
    done_event    = threading.Event()
    error_holder  = []

    def on_open(ws):
        threading.Thread(
            target=_volc_send_audio,
            args=(ws, pcm_bytes),
            daemon=True,
        ).start()

    def on_message(ws, message):
        try:
            resp = _volc_parse_response(message)
        except RuntimeError as e:
            error_holder.append(str(e))
            done_event.set()
            return

        code = resp.get("code", 1000)
        if code != 1000:
            error_holder.append(f"code={code} {resp.get('message', '')}")
            done_event.set()
            return

        # sequence < 0 表示终态帧
        if resp.get("sequence", 0) < 0:
            text = resp.get("result", {}).get("text", "")
            result_holder.append(text)
            done_event.set()

    def on_error(ws, error):
        error_holder.append(str(error))
        done_event.set()

    def on_close(ws, code, msg):
        done_event.set()

    headers = {
        "X-Api-App-Key":     VOLC_APP_ID,
        "X-Api-Access-Key":  VOLC_ACCESS_KEY,
        "X-Api-Resource-Id": VOLC_RESOURCE_ID,
    }
    ws_app = websocket.WebSocketApp(
        VOLC_WS_URL,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws_thread = threading.Thread(
        target=ws_app.run_forever,
        kwargs={"ping_interval": 0},
        daemon=True,
    )
    ws_thread.start()

    print("[转录中...]")
    done_event.wait(timeout=30)
    ws_app.close()

    if error_holder:
        raise RuntimeError(f"火山引擎 STT 错误: {error_holder[0]}")

    return result_holder[0].strip() if result_holder else ""


def _volc_send_audio(ws, pcm_bytes: bytes):
    """发送首帧 JSON 配置，再分块发送音频，最后发末尾帧。"""
    # 首帧：JSON 配置（gzip 压缩）
    params = {
        "app": {
            "appid":   VOLC_APP_ID,
            "token":   VOLC_ACCESS_KEY,
            "cluster": "volcasr",
        },
        "user": {"uid": str(uuid.uuid4())},
        "audio": {
            "format":      "pcm",
            "sample_rate": SAMPLE_RATE,
            "bits":        16,
            "channel":     CHANNELS,
            "codec":       "raw",
        },
        "request": {
            "reqid":            str(uuid.uuid4()),
            "sequence":         1,
            "nbest":            1,
            "show_utterances":  False,
            "result_type":      "full",
            "enable_nonstream": True,
        },
    }
    payload = gzip.compress(json.dumps(params, ensure_ascii=False).encode("utf-8"))
    ws.send(_volc_build_frame(_VOLC_FULL_CLIENT, _VOLC_JSON_GZIP, payload),
            opcode=websocket.ABNF.OPCODE_BINARY)

    # 音频帧
    offset = 0
    total  = len(pcm_bytes)
    while offset < total:
        chunk   = pcm_bytes[offset:offset + VOLC_CHUNK_SIZE]
        offset += VOLC_CHUNK_SIZE
        is_last = (offset >= total)
        byte1   = _VOLC_AUDIO_LAST if is_last else _VOLC_AUDIO_MID
        ws.send(_volc_build_frame(byte1, _VOLC_RAW_GZIP, gzip.compress(chunk)),
                opcode=websocket.ABNF.OPCODE_BINARY)

    # 如果音频为空，补发一个空末尾帧
    if total == 0:
        ws.send(_volc_build_frame(_VOLC_AUDIO_LAST, _VOLC_RAW_GZIP, gzip.compress(b"")),
                opcode=websocket.ABNF.OPCODE_BINARY)
