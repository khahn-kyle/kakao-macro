"""백그라운드 상세 로그 — 진단 리포트용 링버퍼 (스레드 안전)"""
import threading
import time
from collections import deque

_LOCK = threading.Lock()
_BUF = deque(maxlen=3000)


def dlog(msg: str) -> None:
    """상세 로그 한 줄 기록 (화면 로그와 별개, 진단 리포트에 포함됨)"""
    ts = time.strftime("%H:%M:%S")
    with _LOCK:
        _BUF.append(f"[{ts}] {msg}")


def get_debug_log() -> str:
    """지금까지의 상세 로그 전체를 문자열로"""
    with _LOCK:
        return "\n".join(_BUF)
