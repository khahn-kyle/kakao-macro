"""
입력 제어 모듈 (AppleScript + pyautogui)
macOS 전용
"""
import time
import subprocess
import os
import pyautogui
import pyperclip

from debug_log import dlog

# pyobjc imports for image clipboard
try:
    from Cocoa import NSPasteboard, NSURL
    from AppKit import NSImage
    PYOBJC_AVAILABLE = True
    PYOBJC_IMPORT_ERROR = None
except ImportError as _e:
    PYOBJC_AVAILABLE = False
    PYOBJC_IMPORT_ERROR = str(_e)


# pyautogui 설정
pyautogui.FAILSAFE = True  # 마우스를 모서리로 이동하면 중단
pyautogui.PAUSE = 0.1

# 키 코드 매핑 (macOS)
KEY_CODES = {
    'a': 0, 's': 1, 'd': 2, 'f': 3,
    'v': 9, 'w': 13,
    'enter': 36, 'escape': 53,
    'down': 125, 'up': 126,
}


def _run_applescript(script: str) -> bool:
    """AppleScript 실행 (내부용)"""
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def _key_code(code: int, modifier: str = None) -> None:
    """키 코드 입력 (내부용)"""
    if modifier:
        script = f'tell application "System Events" to key code {code} using {modifier} down'
    else:
        script = f'tell application "System Events" to key code {code}'
    ok = _run_applescript(script)
    dlog(f"키입력 code={code}{'+' + modifier if modifier else ''} → {'OK' if ok else '실패'}")
    time.sleep(0.05)


def paste_text(text: str) -> None:
    """클립보드 복사 후 붙여넣기 (Cmd+V)"""
    dlog(f"텍스트 복사→붙여넣기 ({len(text)}자): {text[:20]!r}…")
    pyperclip.copy(text)
    time.sleep(0.05)
    _key_code(KEY_CODES['v'], 'command')
    time.sleep(0.1)


def paste_image(image_path: str) -> bool:
    """이미지를 클립보드에 복사 후 붙여넣기 (Cmd+V)"""
    if not PYOBJC_AVAILABLE:
        return False

    if not os.path.exists(image_path):
        return False

    image = NSImage.alloc().initWithContentsOfFile_(image_path)
    if not image:
        dlog(f"이미지 로드 실패: {image_path}")
        return False

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    success = pb.writeObjects_([image])
    dlog(f"이미지 클립보드 복사: {os.path.basename(image_path)} → {bool(success)}")

    if success:
        time.sleep(0.05)
        _key_code(KEY_CODES['v'], 'command')
        time.sleep(0.1)

    return success


def paste_files(paths: list) -> bool:
    """파일 여러 개를 클립보드에 복사 후 붙여넣기 (Cmd+V).

    카카오톡이 파일 첨부(드래그앤드롭과 동일) 경로로 받아서
    전송 확인 창에 n개가 한꺼번에 첨부된다. 이후 Enter로 전송.
    """
    if not PYOBJC_AVAILABLE:
        return False

    urls = [
        NSURL.fileURLWithPath_(os.path.abspath(p))
        for p in paths
        if os.path.exists(p)
    ]
    if not urls:
        return False

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    success = pb.writeObjects_(urls)
    dlog(f"파일 {len(urls)}개 클립보드 복사 → {bool(success)}")

    if success:
        time.sleep(0.05)
        _key_code(KEY_CODES['v'], 'command')
        time.sleep(0.1)

    return bool(success)


def press_enter() -> None:
    """Enter 키"""
    _key_code(KEY_CODES['enter'])


def press_down() -> None:
    """아래 방향키"""
    _key_code(KEY_CODES['down'])


def open_search() -> None:
    """검색창 열기 (Cmd+F)"""
    _key_code(KEY_CODES['f'], 'command')
    time.sleep(0.2)


def close_chat_window() -> None:
    """채팅창 닫기 (Cmd+W)"""
    _key_code(KEY_CODES['w'], 'command')
    time.sleep(0.2)


def click_chat_input() -> None:
    """채팅 입력창 클릭 (창 하단 중앙)"""
    script = '''
    tell application "System Events"
        tell process "KakaoTalk"
            set winPos to position of window 1
            set winSize to size of window 1
            set x to (item 1 of winPos) as integer
            set y to (item 2 of winPos) as integer
            set w to (item 1 of winSize) as integer
            set h to (item 2 of winSize) as integer
            return (x as string) & " " & (y as string) & " " & (w as string) & " " & (h as string)
        end tell
    end tell
    '''
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        parts = result.stdout.strip().split()
        x, y = int(parts[0]), int(parts[1])
        width, height = int(parts[2]), int(parts[3])

        # 입력창: 창 하단 중앙
        input_x = x + width // 2
        input_y = y + height - 50

        dlog(f"입력창 클릭: ({input_x},{input_y}) 창={width}x{height}")
        pyautogui.click(input_x, input_y)
        time.sleep(0.1)
    else:
        dlog(f"입력창 클릭 실패(창 위치 읽기 불가): {result.stderr.strip()[:80]}")
