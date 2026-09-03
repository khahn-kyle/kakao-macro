"""
카카오톡 자동 메시지 전송 매크로 (macOS)
사용법: python main.py <csv_file>
"""
import sys
import time
from typing import Tuple, List

from csv_reader import read_csv, MessageData
from kakao_controller import (
    is_kakaotalk_running,
    activate_kakaotalk,
    activate_main_window,
    get_chat_window_title,
    get_last_message,
)
from input_controller import (
    paste_text,
    press_enter,
    press_down,
    open_search,
    click_chat_input,
    close_chat_window,
)
from logger import Logger


# 설정
DELAY_BETWEEN_MESSAGES = 1.0  # 메시지 간 대기 시간 (초)
DELAY_AFTER_SEND = 0.5        # 전송 후 확인 대기 시간 (초)
MAIN_WINDOW_TITLE = "카카오톡"  # 메인 창 제목


def find_and_verify_chat(target_name: str) -> Tuple[bool, str]:
    """
    채팅방 검색 및 수신자 검증

    Returns:
        (성공 여부, 실패 시 사유)
    """
    # 메인 창 활성화
    if not activate_main_window():
        return False, "메인 창을 찾을 수 없음"
    time.sleep(0.3)

    # 검색창 열기 및 이름 입력
    open_search()
    time.sleep(0.2)
    paste_text(target_name)
    time.sleep(0.3)

    # 검색 결과 첫 번째 항목 선택
    press_down()
    time.sleep(0.1)
    press_down()
    time.sleep(0.1)
    press_enter()
    time.sleep(0.3)

    # 수신자 검증 루프
    previous_title = None

    while True:
        success, current_title = get_chat_window_title()

        if not success:
            return False, "채팅창 제목 읽기 실패"

        # 메인 창 그대로면 검색 결과 없음
        if current_title == MAIN_WINDOW_TITLE:
            return False, "검색 결과 없음"

        # 정확히 일치하면 성공
        if current_title == target_name:
            return True, ""

        # 직전과 같으면 검색 결과 소진
        if current_title == previous_title:
            close_chat_window()
            return False, f"일치하는 채팅방 없음 (마지막: {current_title})"

        # 다음 검색 결과로 이동
        previous_title = current_title
        close_chat_window()
        time.sleep(0.1)
        press_down()
        time.sleep(0.1)
        press_enter()
        time.sleep(0.3)


def send_and_verify(message: str) -> Tuple[bool, str]:
    """
    메시지 전송 및 발송 확인

    Returns:
        (성공 여부, 실패 시 사유)
    """
    # 입력창 포커스
    click_chat_input()
    time.sleep(0.1)

    # 메시지 전송
    paste_text(message)
    time.sleep(0.1)
    press_enter()
    time.sleep(DELAY_AFTER_SEND)

    # 발송 확인
    success, last_message = get_last_message()

    if not success:
        return False, "메시지 확인 실패"

    if last_message == message:
        return True, ""
    else:
        return False, f"메시지 불일치 (기대: {message[:20]}...)"


def process_message(data: MessageData, logger: Logger) -> None:
    """단일 메시지 처리"""
    print(f"\n처리 중: {data.name}")

    # 1. 채팅방 찾기
    success, reason = find_and_verify_chat(data.name)
    if not success:
        logger.log_failure(data.name, data.message, reason)
        return

    # 2. 메시지 전송
    success, reason = send_and_verify(data.message)
    if success:
        logger.log_success(data.name, data.message)
    else:
        logger.log_failure(data.name, data.message, reason)

    # 3. 채팅창 닫기
    close_chat_window()


def main():
    if len(sys.argv) < 2:
        print("사용법: python main.py <csv_file>")
        print("예시: python main.py data.csv")
        sys.exit(1)

    csv_file = sys.argv[1]

    # CSV 읽기
    print(f"CSV 파일 읽는 중: {csv_file}")
    success, result = read_csv(csv_file)

    if not success:
        print(f"오류: {result}")
        sys.exit(1)

    data_list: List[MessageData] = result
    print(f"총 {len(data_list)}건의 메시지를 발송합니다.\n")

    # 카카오톡 확인
    if not is_kakaotalk_running():
        print("오류: 카카오톡이 실행 중이 아닙니다.")
        sys.exit(1)

    activate_kakaotalk()
    time.sleep(0.5)

    # 발송 시작
    print("=" * 50)
    print("발송 시작")
    print("=" * 50)

    logger = Logger()

    for i, data in enumerate(data_list, start=1):
        print(f"\n[{i}/{len(data_list)}]", end="")
        process_message(data, logger)

        if i < len(data_list):
            time.sleep(DELAY_BETWEEN_MESSAGES)

    logger.print_report()


if __name__ == "__main__":
    main()
