import subprocess
import threading
import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE, CHANNELS


def _beep(sound: str):
    """异步播放系统音效，不阻塞主流程。"""
    subprocess.Popen(
        ["afplay", f"/System/Library/Sounds/{sound}.aiff"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class Recorder:
    def __init__(self):
        self._frames = []
        self._recording = False
        self._stream = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self._frames = []
            self._recording = True

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()
        _beep("Pop")
        print("[录音中...]")

    def stop(self) -> bytes:
        with self._lock:
            self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = self._frames[:]

        if not frames:
            return b""

        _beep("Tink")

        audio = np.concatenate(frames, axis=0)
        return audio.tobytes()

    def _callback(self, indata, frames, time, status):
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())
