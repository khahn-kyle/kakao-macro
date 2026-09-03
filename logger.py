"""
발송 결과 로깅 모듈
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class SendResult:
    """발송 결과"""
    name: str
    message: str
    success: bool
    reason: str = ""


@dataclass
class Logger:
    """발송 결과 로거"""
    results: List[SendResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def log_success(self, name: str, message: str) -> None:
        """성공 기록"""
        self.results.append(SendResult(name, message, success=True))
        print(f"  [성공] {name}")

    def log_failure(self, name: str, message: str, reason: str) -> None:
        """실패 기록"""
        self.results.append(SendResult(name, message, success=False, reason=reason))
        print(f"  [실패] {name} - {reason}")

    def print_report(self) -> None:
        """최종 리포트 출력"""
        elapsed = datetime.now() - self.start_time
        success_count = sum(1 for r in self.results if r.success)
        failure_count = len(self.results) - success_count

        print("\n" + "=" * 50)
        print("발송 결과 리포트")
        print("=" * 50)
        print(f"총 발송 시도: {len(self.results)}건")
        print(f"성공: {success_count}건")
        print(f"실패: {failure_count}건")
        print(f"소요 시간: {elapsed.total_seconds():.1f}초")

        if failure_count > 0:
            print("\n[실패 목록]")
            for r in self.results:
                if not r.success:
                    print(f"  - {r.name}: {r.reason}")

        print("=" * 50)
