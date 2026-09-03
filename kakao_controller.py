"""
카카오톡 제어 모듈 (pyobjc + AppleScript)
macOS 전용
"""
import subprocess
import time
from typing import Tuple

from debug_log import dlog

# pyobjc imports
try:
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementCopyAttributeValue,
        AXUIElementCopyMultipleAttributeValues,
        AXUIElementSetMessagingTimeout,
        kAXErrorSuccess
    )
    from Cocoa import NSWorkspace
    PYOBJC_AVAILABLE = True
    PYOBJC_IMPORT_ERROR = None
except ImportError as _e:
    PYOBJC_AVAILABLE = False
    PYOBJC_IMPORT_ERROR = str(_e)


MAIN_WINDOW_TITLE = "카카오톡"


def _get_ax_attr(element, attr):
    """AXUIElement 속성 가져오기 (내부용)"""
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == kAXErrorSuccess else None


def _get_kakaotalk_pid():
    """카카오톡 PID 가져오기"""
    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.localizedName() == "카카오톡":
            return app.processIdentifier()
    return None


def _run_applescript(script: str, timeout: int = 120) -> Tuple[bool, str]:
    """AppleScript 실행 (내부용)"""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        dlog(f"AppleScript 실패: {result.stderr.strip()[:100]}")
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        dlog("AppleScript 시간 초과")
        return False, "실행 시간 초과"
    except Exception as e:
        dlog(f"AppleScript 예외: {e}")
        return False, str(e)


def is_kakaotalk_running() -> bool:
    """카카오톡 실행 여부 확인"""
    script = '''
    tell application "System Events"
        return (name of every process) contains "KakaoTalk"
    end tell
    '''
    success, result = _run_applescript(script)
    return success and result == "true"


def activate_kakaotalk() -> bool:
    """카카오톡 앱 활성화"""
    script = 'tell application "KakaoTalk" to activate'
    success, _ = _run_applescript(script)
    return success


def activate_main_window() -> bool:
    """메인 창(친구/대화 목록)을 찾아서 앞으로 가져오기"""
    script = f'''
    tell application "System Events"
        tell process "KakaoTalk"
            set frontmost to true
            repeat with w in windows
                if name of w is "{MAIN_WINDOW_TITLE}" then
                    perform action "AXRaise" of w
                    set focused of w to true
                    return "success"
                end if
            end repeat
            return "not found"
        end tell
    end tell
    '''
    success, result = _run_applescript(script)
    dlog(f"메인 창 활성화: {result if success else '실패'}")
    return success and result == "success"


def get_chat_window_title() -> Tuple[bool, str]:
    """현재 최상위 창 제목 가져오기"""
    script = '''
    tell application "System Events"
        tell process "KakaoTalk"
            return name of window 1
        end tell
    end tell
    '''
    ok, title = _run_applescript(script)
    dlog(f"창 제목 읽기: {title!r}" if ok else "창 제목 읽기 실패")
    return ok, title


def get_last_message() -> Tuple[bool, str]:
    """채팅창에서 마지막 메시지 읽기"""
    if PYOBJC_AVAILABLE:
        ok, val = _get_last_message_pyobjc()
    else:
        ok, val = _get_last_message_applescript()
    dlog(f"마지막 메시지 읽기: ok={ok} {str(val)[:30]!r}")
    return ok, val


def _get_last_message_pyobjc() -> Tuple[bool, str]:
    """pyobjc로 마지막 메시지 읽기"""
    try:
        pid = _get_kakaotalk_pid()
        if not pid:
            return False, ""

        app_ref = AXUIElementCreateApplication(pid)
        windows = _get_ax_attr(app_ref, "AXWindows")
        if not windows:
            return False, ""

        for window in windows:
            title = _get_ax_attr(window, "AXTitle")
            if title == "카카오톡":
                continue

            children = _get_ax_attr(window, "AXChildren") or []
            for child in children:
                if _get_ax_attr(child, "AXRole") != "AXScrollArea":
                    continue
                sub = _get_ax_attr(child, "AXChildren") or []
                for s in sub:
                    if _get_ax_attr(s, "AXRole") != "AXTable":
                        continue

                    rows = _get_ax_attr(s, "AXRows") or []
                    for row in reversed(rows):
                        cells = _get_ax_attr(row, "AXChildren") or []
                        for cell in cells:
                            cc = _get_ax_attr(cell, "AXChildren") or []
                            for c in cc:
                                if _get_ax_attr(c, "AXRole") == "AXTextArea":
                                    value = _get_ax_attr(c, "AXValue")
                                    if value:
                                        return True, value
        return False, ""
    except Exception:
        return False, ""


def _get_last_message_applescript() -> Tuple[bool, str]:
    """AppleScript로 마지막 메시지 읽기 (fallback)"""
    script = '''
    tell application "System Events"
        tell process "KakaoTalk"
            set rowList to every row of table 1 of scroll area 1 of window 1
            set rowCount to count of rowList

            repeat with i from rowCount to 1 by -1
                try
                    set msgValue to value of text area 1 of UI element 1 of row i of table 1 of scroll area 1 of window 1
                    if msgValue is not missing value and msgValue is not "" then
                        return msgValue
                    end if
                end try
            end repeat

            return ""
        end tell
    end tell
    '''
    return _run_applescript(script)


def get_friend_list(progress_callback=None) -> Tuple[bool, any]:
    """친구 목록 전체 가져오기. 실패 시 에러 메시지 반환

    progress_callback: callable(current, total) — 대규모 목록 읽기 진행률 알림 (선택)
    """

    # pyobjc 사용 가능하면 pyobjc로 (빠름, 권한 문제 해결)
    if PYOBJC_AVAILABLE:
        success, result = _get_friend_list_pyobjc(progress_callback)
        if not success:
            # 카카오톡이 목록 갱신 중이면 일시적으로 못 읽을 수 있음 → 1회 재시도
            import time as _time
            _time.sleep(1.0)
            success, result = _get_friend_list_pyobjc(progress_callback)
        return success, result

    # fallback: AppleScript
    return _get_friend_list_applescript()


# 초성 소제목(ㄱ,ㄴ,ㄷ… 헤더)은 친구가 아니므로 제외
_CHOSUNG_HEADERS = set("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ#")


def _mget(el, attrs):
    """여러 속성을 1번의 IPC로 읽기 (행 단위 왕복 횟수 절감)"""
    ret = AXUIElementCopyMultipleAttributeValues(el, attrs, 0, None)
    if ret and len(ret) >= 2 and ret[1] is not None:
        return list(ret[1])
    return [None] * len(attrs)


def _read_row(row):
    """행 → (들여쓰기 레벨, 이름).

    셀 자식 구조가 행 종류마다 다르다:
      - 친구 행(레벨 1): [프로필사진(AXButton), 이름, 상태메시지] → 이름은 두 번째
      - 섹션 헤더(레벨 0): [이름, 개수 배지, 버튼] → 이름은 첫 번째 (개수를 집으면 안 됨)
    레벨에 따라 읽기 순서를 바꿔 호출 수를 줄이되, 실패 시 전체 스캔으로 폴백.
    """
    lvl, cells = _mget(row, ["AXDisclosureLevel", "AXChildren"])
    if not cells:
        return lvl, None
    kids = _mget(cells[0], ["AXChildren"])[0]
    if not kids:
        return lvl, None

    if lvl == 0 or len(kids) == 1:
        order = range(len(kids))
    else:
        order = [1] + [i for i in range(len(kids)) if i != 1]
    for i in order:
        role, value = _mget(kids[i], ["AXRole", "AXValue"])
        if role == "AXStaticText" and isinstance(value, str):
            return lvl, value
    return lvl, None


def _get_friend_list_pyobjc(progress_callback=None) -> Tuple[bool, any]:
    """pyobjc로 친구 목록 가져오기 (배치 API + 타임아웃 상향 + 재시도)"""
    try:
        pid = _get_kakaotalk_pid()
        if not pid:
            return False, "카카오톡이 실행 중이 아닙니다"

        app_ref = AXUIElementCreateApplication(pid)
        # 카카오톡이 대형 목록 렌더링으로 바쁠 때 개별 호출이 조용히 실패(CannotComplete)
        # 하는 것을 막기 위해 접근성 메시지 타임아웃을 넉넉히 늘린다 (기본 약 6초)
        try:
            AXUIElementSetMessagingTimeout(app_ref, 30.0)
        except Exception:
            pass

        windows = _get_ax_attr(app_ref, "AXWindows")
        if not windows:
            return False, "윈도우를 찾을 수 없습니다"

        rows = []
        for window in windows:
            if _get_ax_attr(window, "AXTitle") != "카카오톡":
                continue
            for child in (_get_ax_attr(window, "AXChildren") or []):
                if _get_ax_attr(child, "AXRole") != "AXScrollArea":
                    continue
                for sub in (_get_ax_attr(child, "AXChildren") or []):
                    if _get_ax_attr(sub, "AXRole") == "AXOutline":
                        rows = _get_ax_attr(sub, "AXRows") or []
                        break
                if rows:
                    break
            if rows:
                break

        if not rows:
            return False, "친구 목록을 찾을 수 없습니다 (카카오톡 메인 창의 친구 탭을 열어주세요)"

        total = len(rows)
        friend_list = []
        in_friend_section = False
        failed_rows = 0

        for i, row in enumerate(rows):
            lvl, name = _read_row(row)
            if lvl is None and name is None:
                # 일시적 실패 가능성 → 한 번 재시도
                lvl, name = _read_row(row)
                if lvl is None and name is None:
                    failed_rows += 1
                    continue

            if lvl == 0:
                # 레벨 0 = 섹션 헤더. '친구' 섹션부터 다음 섹션 전까지가 실제 친구
                in_friend_section = (name is not None and name.strip() == "친구")
                continue

            if in_friend_section and name:
                name = name.strip()
                if name and name not in _CHOSUNG_HEADERS:
                    friend_list.append(name)

            if progress_callback and (i + 1) % 200 == 0:
                progress_callback(i + 1, total)

        if progress_callback:
            progress_callback(total, total)

        dlog(f"친구 목록 파싱: 전체 {total}행 → 친구 {len(friend_list)}명, 읽기실패 {failed_rows}행")
        if friend_list:
            return True, friend_list
        return False, "친구 목록을 찾을 수 없습니다 ('친구' 섹션이 안 보임)"

    except Exception as e:
        dlog(f"친구 목록 pyobjc 예외: {e}")
        return False, f"pyobjc 오류: {str(e)}"


def _get_friend_list_applescript() -> Tuple[bool, any]:
    """AppleScript로 친구 목록 가져오기 (fallback)"""
    script = '''
    tell application "System Events"
        tell process "KakaoTalk"
            tell outline 1 of scroll area 1 of window 1
                set nameList to {}
                repeat with r in rows
                    try
                        set firstName to value of static text 1 of UI element 1 of r
                        set end of nameList to firstName
                    end try
                end repeat
                set AppleScript's text item delimiters to linefeed
                return nameList as text
            end tell
        end tell
    end tell
    '''
    # 대규모 목록(수천 명)에서 AppleScript는 매우 느려 120초를 넘길 수 있음 → 여유 있게
    success, result = _run_applescript(script, timeout=600)
    if not success:
        error_msg = result if result else "알 수 없는 오류"
        return False, error_msg

    if not result:
        return False, "빈 결과"

    all_names = result.split('\n')
    friend_list = []
    in_friend_section = False

    for name in all_names:
        name = name.strip()
        if not name:
            continue

        if name == "친구":
            in_friend_section = True
            continue

        if in_friend_section and name in ("채널", "플러스친구", "오픈채팅"):
            break

        if in_friend_section:
            friend_list.append(name)

    if friend_list:
        return True, friend_list
    return False, "친구 목록을 파싱할 수 없음"


def get_search_result() -> Tuple[bool, any]:
    """검색 결과 목록 가져오기 (검색창에 입력된 상태에서 호출)"""
    if not PYOBJC_AVAILABLE:
        return False, "pyobjc가 설치되어 있지 않습니다"

    try:
        pid = _get_kakaotalk_pid()
        if not pid:
            return False, "카카오톡이 실행 중이 아닙니다"

        app_ref = AXUIElementCreateApplication(pid)
        windows = _get_ax_attr(app_ref, "AXWindows")

        if not windows:
            return False, "윈도우를 찾을 수 없습니다"

        names = []

        for window in windows:
            title = _get_ax_attr(window, "AXTitle")
            if title != "카카오톡":
                continue

            children = _get_ax_attr(window, "AXChildren") or []

            for child in children:
                if _get_ax_attr(child, "AXRole") != "AXScrollArea":
                    continue

                sub = _get_ax_attr(child, "AXChildren") or []
                for s in sub:
                    if _get_ax_attr(s, "AXRole") != "AXOutline":
                        continue

                    rows = _get_ax_attr(s, "AXRows") or []

                    for row in rows:
                        cells = _get_ax_attr(row, "AXChildren") or []
                        if not cells:
                            continue

                        texts = _get_ax_attr(cells[0], "AXChildren") or []
                        for txt in texts:
                            if _get_ax_attr(txt, "AXRole") == "AXStaticText":
                                value = _get_ax_attr(txt, "AXValue")
                                if value:
                                    names.append(value)
                                break

        if names:
            return True, names
        return False, "검색 결과가 없습니다"

    except Exception as e:
        return False, f"오류: {str(e)}"


def list_windows_debug() -> list:
    """현재 카카오톡 창들의 (제목, 서브롤) 목록 — 전송 확인 창 미감지 시 진단용"""
    result = []
    try:
        pid = _get_kakaotalk_pid()
        if not pid:
            return result
        app_ref = AXUIElementCreateApplication(pid)
        for w in (_get_ax_attr(app_ref, "AXWindows") or []):
            title = _get_ax_attr(w, "AXTitle") or ""
            subrole = _get_ax_attr(w, "AXSubrole") or "?"
            has_sheet = bool(_get_ax_attr(w, "AXSheets"))
            result.append((title, subrole, "시트있음" if has_sheet else ""))
    except Exception:
        pass
    return result


def window_snapshot() -> list:
    """현재 카카오톡 창 목록의 스냅샷 (정렬된 (제목, 서브롤, 시트여부) 목록).
    붙여넣기 전에 찍어두고, 이후와 비교해 '새 창이 생겼는지'로 전송 확인 창을 감지한다."""
    return sorted(list_windows_debug())


def new_windows_since(before: list) -> list:
    """before 스냅샷 이후 새로 생긴 창 목록 (같은 제목 창이 늘어난 경우도 포함)"""
    now = list_windows_debug()
    remaining = list(before)
    added = []
    for w in now:
        if w in remaining:
            remaining.remove(w)
        else:
            added.append(w)
    return added


def has_file_send_dialog(before: list = None) -> bool:
    """파일/이미지 '전송 확인' 대화상자가 떠 있는지.

    카카오톡의 전송 확인 창은 시트가 아닌 일반 창으로 뜰 수 있어서 창 종류로는 못 잡는다
    (v1.2.4에서 이 때문에 감지 실패 → 중복 전송 사고). 그래서 구조에 의존하지 않고
    '붙여넣기 전 스냅샷(before) 대비 새 창이 생겼는가'를 1순위 기준으로 쓴다.
    """
    if not PYOBJC_AVAILABLE:
        return False
    try:
        if before is not None and new_windows_since(before):
            return True
        pid = _get_kakaotalk_pid()
        if not pid:
            return False
        app_ref = AXUIElementCreateApplication(pid)
        for w in (_get_ax_attr(app_ref, "AXWindows") or []):
            if _get_ax_attr(w, "AXSheets"):
                return True
            if _get_ax_attr(w, "AXSubrole") in ("AXDialog", "AXSystemDialog"):
                return True
        return False
    except Exception:
        return False


def is_accessibility_trusted() -> bool:
    """이 프로세스에 손쉬운 사용 권한이 실제로 유효한지 (토글이 켜져 보여도 무효일 수 있음)"""
    try:
        from ApplicationServices import AXIsProcessTrusted
        trusted = bool(AXIsProcessTrusted())
        dlog(f"손쉬운 사용 권한 유효: {trusted}")
        return trusted
    except Exception as e:
        # 판단 불가 시 흐름을 막지 않는다
        dlog(f"권한 확인 불가(통과 처리): {e}")
        return True


def get_focused_element_role() -> str:
    """카카오톡에서 현재 포커스된 UI 요소의 역할(AXTextArea 등). 확인 불가 시 ''"""
    try:
        pid = _get_kakaotalk_pid()
        if not pid:
            return ""
        app_ref = AXUIElementCreateApplication(pid)
        el = _get_ax_attr(app_ref, "AXFocusedUIElement")
        if el is None:
            return ""
        return _get_ax_attr(el, "AXRole") or ""
    except Exception:
        return ""


def wait_for_input_focus(timeout: float = 2.0) -> bool:
    """채팅 입력창(텍스트 영역)에 포커스가 잡힐 때까지 대기.

    Cmd+V가 입력창 준비 전에 도착하면 조용히 무시된다(파일 묶음 붙여넣기 시 전송 확인 창이
    안 뜨는 증상). 클릭 후 고정 0.1초에 기대지 말고 포커스를 실제로 확인한 뒤 붙여넣는다.
    확인되면 True, 시간 초과면 0.5초 더 기다린 뒤 False(진행은 한다).
    """
    if not PYOBJC_AVAILABLE:
        time.sleep(0.5)
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        role = get_focused_element_role()
        if role in ("AXTextArea", "AXTextField"):
            dlog(f"입력창 포커스 확인: {role}")
            return True
        time.sleep(0.15)
    dlog(f"입력창 포커스 미확인(마지막 역할: {get_focused_element_role()!r}) → 0.5초 추가 대기 후 진행")
    time.sleep(0.5)
    return False


# ---------- 전송 확인 창(모달) 감지 ----------
# 실측(2026-09-03, 프로브): 카톡이 파일/이미지 전송 확인 창을 띄우면 앱이 모달 상태로 들어가
# 접근성 트리가 통째로 비어버린다 — AXWindows 0개, AXChildren 0개, System Events는 -1719.
# 창이 '추가'되는 게 아니라 창 목록이 '소등'되는 것이 신호다. 확인 창이 닫히면 즉시 복구된다.

def _app_ref(timeout: float = 1.0):
    pid = _get_kakaotalk_pid()
    if not pid:
        return None
    ref = AXUIElementCreateApplication(pid)
    try:
        AXUIElementSetMessagingTimeout(ref, timeout)
    except Exception:
        pass
    return ref


def is_send_dialog_up(app_ref=None) -> bool:
    """전송 확인 창(모달)이 떠 있는지 — 접근성 창 목록이 비어 있으면 True"""
    if not PYOBJC_AVAILABLE:
        return False
    ref = app_ref or _app_ref()
    if ref is None:
        return False
    return not (_get_ax_attr(ref, "AXWindows") or [])


def wait_send_dialog(appear: bool, timeout: float) -> float:
    """appear=True면 확인 창이 뜰 때까지, False면 닫힐 때까지 대기.
    걸린 초를 반환, 시간 초과면 -1. 대기 중 어떤 키 입력도 보내지 않는다."""
    ref = _app_ref()
    if ref is None:
        return -1.0
    t0 = time.time()
    while time.time() - t0 < timeout:
        if is_send_dialog_up(ref) == appear:
            return time.time() - t0
        time.sleep(0.25)
    return -1.0
