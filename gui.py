"""
카카오톡 메시지 발송 GUI (PyQt6)
"""
import sys
import threading
import time
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QTextEdit,
    QProgressBar, QFileDialog, QHeaderView, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

import platform

from csv_reader import read_csv, MessageData, ReadResult, SkippedRow
from version import APP_VERSION
from debug_log import dlog, get_debug_log

if platform.system() == "Darwin":
    from kakao_controller import (
        is_kakaotalk_running, activate_kakaotalk, activate_main_window,
        get_chat_window_title, get_last_message, get_friend_list, get_search_result
    )
    from input_controller import (
        paste_text, paste_image, paste_files, press_enter, press_down,
        open_search, click_chat_input, close_chat_window
    )
else:
    from kakao_controller_win import (
        is_kakaotalk_running, activate_kakaotalk, activate_main_window,
        get_chat_window_title, get_last_message, get_friend_list, get_search_result
    )
    from input_controller_win import (
        paste_text, paste_image, paste_files, press_enter, press_down,
        open_search, click_chat_input, close_chat_window
    )


# 설정
DELAY_BETWEEN_MESSAGES = 0.3
DELAY_AFTER_SEND = 0.5
# 이미지/파일 전송 확인 창: 카톡이 창을 띄우면 접근성 트리가 통째로 비는(모달) 것을 신호로 삼아
# "뜰 때까지 대기 → Enter → 닫힐 때까지 대기"로 처리한다 (기기 속도 무관). 대기 중 키 입력 금지 —
# 창이 뜨기 전의 Enter는 준비 중인 첨부를 취소시킨다(v1.2.5특/1.2.7 사고).
DIALOG_APPEAR_TIMEOUT = 25.0   # 확인 창(소등)이 뜰 때까지 최대 대기(초). 초과 = 이 방은 붙여넣기 미지원
DIALOG_SETTLE = 1.0            # 소등 후 첫 Enter까지 여유(초)
DIALOG_SECOND_ENTER = 2.5      # 첫 Enter 뒤 보험 Enter까지 간격(초): 로딩 중 무시됐을 때 대비, 이미 보내졌으면 무해
DIALOG_AFTER_SEND = 2.0        # 보험 Enter 뒤 다음 단계까지 여유(초). 점등은 기다리지 않는다(30초+ 걸릴 수 있음)
VERIFY_TIMEOUT = 20.0          # 메시지 전송 후 마지막 메시지 읽기(검증) 재시도 한도(초)
MAIN_WINDOW_TITLE = "카카오톡"


class WorkerSignals(QObject):
    """스레드 시그널"""
    progress = pyqtSignal(int, int)  # current, total
    log = pyqtSignal(str)
    finished = pyqtSignal(int, int)  # success, fail


class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.data_list: List[MessageData] = []
        self.is_sending = False
        self.stop_requested = False
        self.signals = WorkerSignals()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setWindowTitle(f"카카오톡 메시지 발송 v{APP_VERSION}")
        self.setGeometry(100, 100, 650, 750)
        self.setMinimumSize(550, 650)

        # 중앙 위젯
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # === 파일 선택 ===
        file_layout = QHBoxLayout()
        self.file_btn = QPushButton("CSV 파일 선택")
        self.file_btn.setFixedWidth(120)
        self.file_btn.clicked.connect(self._select_file)
        self.file_label = QLabel("선택된 파일 없음")
        file_layout.addWidget(self.file_btn)
        file_layout.addWidget(self.file_label, 1)
        layout.addLayout(file_layout)

        # === 친구 목록 가져오기 ===
        friend_layout = QHBoxLayout()

        self.friend_btn = QPushButton("친구 목록 가져오기")
        self.friend_btn.setFixedHeight(35)
        self.friend_btn.clicked.connect(self._get_friend_list)
        friend_layout.addWidget(self.friend_btn)

        self.search_btn = QPushButton("검색 결과 가져오기")
        self.search_btn.setFixedHeight(35)
        self.search_btn.clicked.connect(self._get_search_result)
        friend_layout.addWidget(self.search_btn)

        layout.addLayout(friend_layout)

        # === 총 인원수 ===
        self.count_label = QLabel("총 0명")
        self.count_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # === 미리보기 ===
        layout.addWidget(QLabel("<b>미리보기</b>"))

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(3)
        self.preview_table.setHorizontalHeaderLabels(["이름", "메시지", "이미지"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview_table, 1)

        # === 진행률 ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("대기 중")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)

        # === 발송 버튼 ===
        self.send_btn = QPushButton("발송 시작")
        self.send_btn.setFixedHeight(45)
        self.send_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.send_btn.clicked.connect(self._start_sending)
        layout.addWidget(self.send_btn)

        # === 로그 (+ 진단 리포트 버튼) ===
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>로그</b>"))
        log_header.addStretch()
        self.report_btn = QPushButton("🩺 진단 리포트 복사")
        self.report_btn.setToolTip("오류 문의 시 이 버튼을 누르고, 복사된 내용을 클로드(또는 개발자)에게 그대로 붙여넣으세요")
        self.report_btn.clicked.connect(self._copy_diagnosis_report)
        log_header.addWidget(self.report_btn)
        layout.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)

    def _connect_signals(self):
        self.signals.progress.connect(self._update_progress)
        self.signals.log.connect(self._add_log)
        self.signals.finished.connect(self._sending_complete)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "CSV 파일 선택", "", "CSV files (*.csv);;All files (*.*)"
        )

        if not file_path:
            return

        success, result = read_csv(file_path)

        if not success:
            self._add_log(f"오류: {result}")
            return

        self.data_list = result.data
        self.file_label.setText(file_path.split("/")[-1])
        self._update_preview()
        self._update_count()

        log_msg = f"파일 로드 완료: {len(self.data_list)}명"
        if result.skipped_rows:
            log_msg += f" (제외: {len(result.skipped_rows)}행)"
            self._show_skipped_popup(result.skipped_rows)
        self._add_log(log_msg)

    def _get_friend_list(self):
        """친구 목록 가져와서 클립보드에 저장"""
        if not is_kakaotalk_running():
            self._add_log("오류: 카카오톡이 실행 중이 아닙니다.")
            return

        if not self._check_accessibility():
            return

        from kakao_controller import PYOBJC_AVAILABLE, PYOBJC_IMPORT_ERROR
        if PYOBJC_AVAILABLE:
            self._add_log("친구 목록 가져오는 중... (고속 엔진)")
        else:
            self._add_log(f"친구 목록 가져오는 중... (⚠ 호환 모드 — 대규모 목록은 수 분 걸릴 수 있음)")
            self._add_log(f"  호환 모드 원인: {PYOBJC_IMPORT_ERROR}")
        self.friend_btn.setEnabled(False)

        def fetch():
            activate_kakaotalk()
            time.sleep(0.3)

            def on_progress(cur, total):
                self.signals.log.emit(f"  … 목록 읽는 중 {cur}/{total}")

            success, friends = get_friend_list(progress_callback=on_progress)

            if success and isinstance(friends, list):
                import pyperclip
                pyperclip.copy('\n'.join(friends))
                self.signals.log.emit(f"✓ 친구 목록 {len(friends)}명 클립보드에 저장 완료!")
            else:
                error_msg = friends if isinstance(friends, str) else "알 수 없는 오류"
                self.signals.log.emit(f"✗ 친구 목록을 가져올 수 없습니다.\n  → {error_msg}")

            # 버튼 다시 활성화 (메인 스레드에서)
            self.friend_btn.setEnabled(True)

        threading.Thread(target=fetch, daemon=True).start()

    def _get_search_result(self):
        """검색 결과 가져와서 클립보드에 저장"""
        if not is_kakaotalk_running():
            self._add_log("오류: 카카오톡이 실행 중이 아닙니다.")
            return

        self._add_log("검색 결과 가져오는 중...")
        self.search_btn.setEnabled(False)

        def fetch():
            activate_kakaotalk()
            time.sleep(0.3)
            success, names = get_search_result()

            if success and isinstance(names, list):
                import pyperclip
                pyperclip.copy('\n'.join(names))
                self.signals.log.emit(f"✓ 검색 결과 {len(names)}명 클립보드에 저장 완료!")
            else:
                error_msg = names if isinstance(names, str) else "알 수 없는 오류"
                self.signals.log.emit(f"✗ 검색 결과를 가져올 수 없습니다.\n  → {error_msg}")

            self.search_btn.setEnabled(True)

        threading.Thread(target=fetch, daemon=True).start()

    def _update_preview(self):
        self.preview_table.setRowCount(len(self.data_list))

        import os
        for i, data in enumerate(self.data_list):
            self.preview_table.setItem(i, 0, QTableWidgetItem(data.name))
            msg_preview = data.message[:40] + "..." if len(data.message) > 40 else data.message
            self.preview_table.setItem(i, 1, QTableWidgetItem(msg_preview))

            # 이미지 장수 표시 (없는 파일은 경고)
            if data.images:
                missing = sum(1 for p in data.images if not os.path.exists(p))
                img_text = f"{len(data.images)}장"
                if missing:
                    img_text += f" (⚠ {missing}장 없음)"
            else:
                img_text = "-"
            item = QTableWidgetItem(img_text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_table.setItem(i, 2, item)

    def _update_count(self):
        count = len(self.data_list)
        self.count_label.setText(f"총 {count}명")

    def _show_skipped_popup(self, skipped_rows: list):
        """제외된 행 팝업 표시"""
        dialog = QDialog(self)
        dialog.setWindowTitle("제외된 행")
        dialog.setMinimumSize(400, 300)

        layout = QVBoxLayout(dialog)

        # 안내 문구
        label = QLabel(f"⚠ {len(skipped_rows)}개 행이 제외되었습니다:")
        label.setStyleSheet("font-weight: bold; color: #ff6b6b;")
        layout.addWidget(label)

        # 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["줄", "친구명", "메시지", "사유"])
        table.setRowCount(len(skipped_rows))
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for i, row in enumerate(skipped_rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.line)))
            table.setItem(i, 1, QTableWidgetItem(row.name or "(없음)"))
            table.setItem(i, 2, QTableWidgetItem(row.message or "(없음)"))
            table.setItem(i, 3, QTableWidgetItem(row.reason))

        layout.addWidget(table)

        # 확인 버튼
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn.accepted.connect(dialog.accept)
        layout.addWidget(btn)

        dialog.exec()

    def _check_accessibility(self) -> bool:
        """손쉬운 사용 권한이 유효한지 확인. 무효면 안내 후 False"""
        if platform.system() != "Darwin":
            return True
        from kakao_controller import is_accessibility_trusted
        if is_accessibility_trusted():
            return True
        self._add_log("⚠ 손쉬운 사용 권한이 없거나 무효 상태입니다 (앱 업데이트 후엔 토글이 켜져 있어도 무효일 수 있어요).")
        self._add_log("  → 시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용에서")
        self._add_log("     '카카오톡매크로'를 'ㅡ'로 완전히 제거한 뒤 '+'로 다시 추가해 주세요. (설정 창을 엽니다)")
        import subprocess
        subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
        return False

    def _copy_diagnosis_report(self):
        """환경 정보 + 화면 로그 + 백그라운드 상세 로그를 클립보드와 파일로 저장"""
        import os
        import datetime
        lines = [
            "===== 카카오톡매크로 진단 리포트 =====",
            "",
            "[클로드에게] 이 텍스트는 macOS용 '카카오톡매크로' 앱(카카오톡 자동 메시지 발송 도구)이",
            "자동 생성한 진단 리포트입니다. 붙여넣은 사용자는 개발 지식이 없는 비개발자입니다.",
            "- 아래 환경 정보와 로그를 근거로 문제 원인을 진단해 주세요.",
            "- 해결 방법은 한 번에 한 단계씩, 처음 맥을 쓰는 사람도 따라할 수 있게 안내해 주세요.",
            "- 터미널 명령이 필요하면 복사-붙여넣기만 하면 되는 형태로 제시해 주세요.",
            "- 자주 있는 원인:",
            "  1) 손쉬운 사용 권한 무효 — 앱 업데이트 후엔 토글이 켜져 보여도 무효.",
            "     시스템 설정→개인정보 보호 및 보안→손쉬운 사용에서 'ㅡ'로 제거 후 '+'로 재추가해야 함",
            "  2) CSV 문제 — 이미지 여러 장 구분자는 세미콜론(;), 경로는 절대경로 권장, UTF-8 인코딩",
            "  3) 특정 채팅방이 파일 붙여넣기를 안 받음(채널/오픈채팅 등) — 앱이 자동으로 한 장씩 전환함",
            "- 앱 자체의 버그로 판단되면 '이 리포트를 프로그램 제작자에게 그대로 전달하세요'라고 안내해 주세요.",
            "",
            f"시각: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
            f"앱 버전: {APP_VERSION}",
            f"macOS: {platform.mac_ver()[0]} ({platform.machine()})",
        ]
        try:
            from kakao_controller import (
                PYOBJC_AVAILABLE as KC_PYOBJC, PYOBJC_IMPORT_ERROR as KC_ERR,
                is_accessibility_trusted, list_windows_debug,
            )
            from input_controller import PYOBJC_AVAILABLE as IC_PYOBJC, PYOBJC_IMPORT_ERROR as IC_ERR
            lines += [
                f"카카오톡 실행 중: {is_kakaotalk_running()}",
                f"손쉬운 사용 권한 유효: {is_accessibility_trusted()}",
                f"pyobjc(카톡 제어): {'OK' if KC_PYOBJC else f'불가 - {KC_ERR}'}",
                f"pyobjc(입력 제어): {'OK' if IC_PYOBJC else f'불가 - {IC_ERR}'}",
                f"카카오톡 창 상태: {list_windows_debug()}",
            ]
        except ImportError as e:
            lines.append(f"(환경 정보 수집 실패: {e})")
        lines += [
            f"로드된 CSV: {len(self.data_list)}명",
            "",
            "----- 화면 로그 -----",
            self.log_text.toPlainText(),
            "",
            "----- 백그라운드 상세 로그 -----",
            get_debug_log(),
        ]
        report = "\n".join(lines)

        import pyperclip
        pyperclip.copy(report)
        saved = ""
        try:
            path = os.path.expanduser("~/Desktop/카카오톡매크로_진단리포트.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            saved = f"\n  파일로도 저장됨: {path}"
        except OSError:
            pass
        self._add_log(f"🩺 진단 리포트를 클립보드에 복사했습니다.{saved}\n  → 클로드(또는 개발자)에게 그대로 붙여넣으면 됩니다.")

    def _confirm_send_dialog(self):
        """붙여넣기 직후 호출. 실측(2026-09-03, 3회) 기반 규칙:
        - 확인 창이 뜨면 카톡 접근성 트리가 소등(AXWindows 응답 없음)된다 → 뜰 때까지 키 입력 금지
          (소등 전의 Enter는 준비 중인 첨부를 취소시킨다 — v1.2.5특/1.2.7 사고)
        - 소등 뒤의 Enter는 안전: 로딩 중이면 무시, 준비되면 전송, 이미 보내졌으면 빈 입력창이라 무해
        - 점등(복구)은 전송 뒤에도 30초+ 늦을 수 있으므로 기다리지 않는다"""
        from kakao_controller import wait_send_dialog
        t_up = wait_send_dialog(appear=True, timeout=DIALOG_APPEAR_TIMEOUT)
        if t_up < 0:
            dlog(f"전송 확인 창이 {DIALOG_APPEAR_TIMEOUT:.0f}초 안에 뜨지 않음 (접근성 창 목록이 계속 살아있음)")
            return False, f"확인 창이 {DIALOG_APPEAR_TIMEOUT:.0f}초 안에 뜨지 않음"
        dlog(f"전송 확인 창 감지(소등) +{t_up:.1f}s → {DIALOG_SETTLE}s 후 Enter")
        time.sleep(DIALOG_SETTLE)
        press_enter()
        time.sleep(DIALOG_SECOND_ENTER)
        press_enter()   # 보험
        time.sleep(DIALOG_AFTER_SEND)
        dlog("확인 창 Enter 2회 완료 → 다음 단계")
        return True, f"창 +{t_up:.1f}s 감지, Enter 2회"

    def _pyobjc_hint(self) -> str:
        """이미지 복사 실패가 pyobjc import 문제면 원인 힌트 반환"""
        try:
            from input_controller import PYOBJC_AVAILABLE, PYOBJC_IMPORT_ERROR
            if not PYOBJC_AVAILABLE:
                return f" (원인: pyobjc 사용 불가 — {PYOBJC_IMPORT_ERROR})"
        except ImportError:
            pass
        return ""

    def _add_log(self, message: str):
        self.log_text.append(message)

    def _update_progress(self, current: int, total: int):
        progress = int(current / total * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{current}/{total} ({progress}%)")

    def _start_sending(self):
        # 발송 중이면 중지 요청
        if self.is_sending:
            self.stop_requested = True
            self.send_btn.setEnabled(False)
            self.send_btn.setText("중지 중...")
            self._add_log("중지 요청됨. 현재 작업 완료 후 중지됩니다.")
            return

        if not self.data_list:
            self._add_log("오류: CSV 파일을 먼저 선택하세요.")
            return

        if not is_kakaotalk_running():
            self._add_log("오류: 카카오톡이 실행 중이 아닙니다.")
            return

        if not self._check_accessibility():
            return

        self.is_sending = True
        self.stop_requested = False
        self.send_btn.setText("중지")
        self.send_btn.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #ff6b6b; color: white;")

        threading.Thread(target=self._send_messages, daemon=True).start()

    def _send_messages(self):
        activate_kakaotalk()
        time.sleep(0.5)

        total = len(self.data_list)
        success_count = 0
        fail_count = 0

        for i, data in enumerate(self.data_list):
            # 중지 요청 확인
            if self.stop_requested:
                self.signals.log.emit(f"\n⚠ 사용자 요청으로 중지됨 ({i}/{total})")
                break

            self.signals.progress.emit(i + 1, total)
            dlog(f"=== [{i + 1}/{total}] {data.name} 처리 시작 (이미지 {len(data.images)}장) ===")

            success, reason = self._find_and_verify_chat(data.name)
            if not success:
                fail_count += 1
                self.signals.log.emit(f"✗ {data.name} - {reason}")
                continue

            success, reason = self._send_and_verify(data.message, data.images)
            if success:
                success_count += 1
                img_info = f" (이미지 {len(data.images)}장 포함)" if data.images else ""
                self.signals.log.emit(f"✓ {data.name} - 성공{img_info}")
            else:
                fail_count += 1
                self.signals.log.emit(f"✗ {data.name} - {reason}")

            close_chat_window()

            if i < total - 1:
                time.sleep(DELAY_BETWEEN_MESSAGES)

        self.signals.finished.emit(success_count, fail_count)

    def _find_and_verify_chat(self, target_name: str):
        if not activate_main_window():
            return False, "메인 창을 찾을 수 없음"
        time.sleep(0.3)

        open_search()
        time.sleep(0.2)
        paste_text(target_name)
        time.sleep(0.3)

        press_down()
        time.sleep(0.1)
        press_down()
        time.sleep(0.1)
        press_enter()
        time.sleep(0.3)

        previous_title = None

        while True:
            success, current_title = get_chat_window_title()

            if not success:
                return False, "채팅창 제목 읽기 실패"

            if current_title == MAIN_WINDOW_TITLE:
                return False, "검색 결과 없음"

            if current_title == target_name:
                return True, ""

            if current_title == previous_title:
                close_chat_window()
                return False, "일치하는 채팅방 없음"

            previous_title = current_title
            close_chat_window()
            time.sleep(0.1)
            press_down()
            time.sleep(0.1)
            press_enter()
            time.sleep(0.3)

    def _send_and_verify(self, message: str, images: list = None):
        click_chat_input()
        time.sleep(0.2)
        if platform.system() == "Darwin":
            # 붙여넣기 전에 입력창 포커스를 실제로 확인 (고정 대기에 기대면 기기에 따라 Cmd+V가 씹힘)
            from kakao_controller import wait_for_input_focus
            wait_for_input_focus()

        # 이미지가 있으면 먼저 전송 — 각 단계 결과를 로그에 정직하게 남긴다
        import os
        valid_images = [p for p in (images or []) if os.path.exists(p)]
        missing = [p for p in (images or []) if not os.path.exists(p)]
        if missing:
            self.signals.log.emit(f"  ⚠ 이미지 파일 없음({len(missing)}장): " + ", ".join(missing))

        if valid_images:
            from kakao_controller import is_send_dialog_up
            if is_send_dialog_up():
                self.signals.log.emit("  ✗ 카카오톡에 다른 확인 창/팝업이 떠 있어 이미지를 붙여넣을 수 없음")
                return False, "카카오톡이 모달 상태(다른 창이 떠 있음)"
            n = len(valid_images)
            if n == 1:
                pasted = paste_image(valid_images[0])       # 이미지 데이터 붙여넣기
                how = "이미지 1장"
            else:
                pasted = paste_files(valid_images)          # 파일 묶음 붙여넣기 → 확인 창에 n장
                how = f"이미지 {n}장 묶음"
            if not pasted:
                self.signals.log.emit(f"  ✗ {how} 클립보드 복사 실패{self._pyobjc_hint()}")
                return False, "이미지 클립보드 복사 실패"
            self.signals.log.emit(f"  · {how} 붙여넣기 → 전송 확인 창 대기…")
            ok, detail = self._confirm_send_dialog()
            if ok:
                self.signals.log.emit(f"  · {how} 전송 완료 ({detail})")
            else:
                self.signals.log.emit(f"  ⚠ {how} 전송 실패: {detail}")
                if n > 1:
                    self.signals.log.emit("    (이 방이 파일 붙여넣기를 안 받는 경우일 수 있음 — 메시지는 계속 보냄)")
                if not message:
                    return False, detail

        # 메시지 전송
        if message:
            paste_text(message)
            time.sleep(0.1)
            press_enter()
            time.sleep(DELAY_AFTER_SEND)

            # 이미지 전송 직후엔 카톡 접근성이 한동안(기기에 따라 8~40초) 응답하지 않을 수 있어
            # 마지막 메시지 읽기를 점등될 때까지 재시도한다. 끝내 못 읽으면 실패가 아니라 '확인 불가'로
            # 처리한다 — 실제로는 전송된 경우가 대부분이라 실패로 세면 재발송(중복) 사고가 난다.
            success, last_message = get_last_message()
            t_verify = time.time()
            while not success and time.time() - t_verify < VERIFY_TIMEOUT:
                time.sleep(1.0)
                success, last_message = get_last_message()
            if not success:
                dlog(f"전송 확인 불가: {VERIFY_TIMEOUT:.0f}초 동안 카톡 접근성 응답 없음 (전송은 됐을 가능성 높음)")
                self.signals.log.emit("  ⚠ 전송 확인 불가 (카톡이 한동안 응답 없음) — 전송은 된 것으로 처리")
                return True, ""

            # 카카오톡이 긴 메시지를 잘라서 표시하므로 앞부분만 비교
            if message.startswith(last_message) or last_message.startswith(message) or last_message == message:
                return True, ""
            else:
                return False, "메시지 불일치"

        return True, ""

    def _sending_complete(self, success: int, fail: int):
        stopped = self.stop_requested
        self.is_sending = False
        self.stop_requested = False
        self.send_btn.setEnabled(True)
        self.send_btn.setText("발송 시작")
        self.send_btn.setStyleSheet("font-size: 16px; font-weight: bold;")

        status = "중지됨" if stopped else "완료"
        self.progress_label.setText(f"{status}! 성공: {success}건, 실패: {fail}건")
        self._add_log(f"\n===== 발송 {status} =====")
        self._add_log(f"성공: {success}건")
        self._add_log(f"실패: {fail}건")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())
