"""
CSV 파일 읽기 모듈
"""
import csv
from dataclasses import dataclass, field
from typing import List, Tuple, Union, Optional


# 헤더 매핑 (다양한 이름 → 표준 필드명)
NAME_ALIASES = ["친구명", "이름", "name", "Name", "받는사람", "수신자"]
MESSAGE_ALIASES = ["메시지", "message", "Message", "내용", "메세지", "문자"]
IMAGE_ALIASES = ["이미지", "image", "Image", "사진", "파일", "file"]


@dataclass
class MessageData:
    """메시지 데이터"""
    name: str
    message: str
    images: List[str] = field(default_factory=list)  # 이미지 경로 목록 (선택, ';' 구분)


@dataclass
class SkippedRow:
    """제외된 행 정보"""
    line: int
    name: str
    message: str
    reason: str


@dataclass
class ReadResult:
    """CSV 읽기 결과"""
    data: List['MessageData']
    skipped_rows: List['SkippedRow']


def _clean_text(text: str) -> str:
    """공백 정리: 앞뒤 공백 제거 + 연속 공백을 하나로 (줄바꿈 유지)"""
    import re
    text = text.strip()
    # 줄바꿈은 유지하고, 같은 줄 내 연속 공백만 하나로
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text


def _find_column(fieldnames: List[str], aliases: List[str]) -> Optional[str]:
    """헤더에서 매칭되는 컬럼명 찾기"""
    for alias in aliases:
        if alias in fieldnames:
            return alias
    return None


def read_csv(file_path: str) -> Tuple[bool, Union[ReadResult, str]]:
    """
    CSV 파일 읽기

    지원하는 헤더:
    - 친구명/이름/name/받는사람/수신자
    - 메시지/message/내용/메세지/문자

    Returns:
        (성공 여부, ReadResult 또는 에러 메시지)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return False, "CSV 파일이 비어있습니다."

            # 헤더 매핑
            name_col = _find_column(reader.fieldnames, NAME_ALIASES)
            message_col = _find_column(reader.fieldnames, MESSAGE_ALIASES)
            image_col = _find_column(reader.fieldnames, IMAGE_ALIASES)  # 선택

            if not name_col:
                return False, f"친구명 컬럼을 찾을 수 없습니다. (지원: {', '.join(NAME_ALIASES)})"
            if not message_col:
                return False, f"메시지 컬럼을 찾을 수 없습니다. (지원: {', '.join(MESSAGE_ALIASES)})"

            data_list = []
            skipped_rows = []

            for i, row in enumerate(reader, start=2):
                name = _clean_text(row.get(name_col, ''))
                message = _clean_text(row.get(message_col, ''))
                image_raw = row.get(image_col, '').strip() if image_col else ""
                # ';' 구분으로 여러 장 지원 (한 장이면 그대로 1개)
                images = [p.strip() for p in image_raw.split(';') if p.strip()]

                # 빈 행 건너뛰기
                if not name and not message:
                    skipped_rows.append(SkippedRow(i, "", "", "빈 행"))
                    continue
                if not name:
                    skipped_rows.append(SkippedRow(i, "", message, "친구명 없음"))
                    continue
                if not message and not images:
                    skipped_rows.append(SkippedRow(i, name, "", "메시지/이미지 없음"))
                    continue

                data_list.append(MessageData(name=name, message=message, images=images))

            if not data_list:
                return False, "CSV 파일에 유효한 데이터가 없습니다."

            return True, ReadResult(data=data_list, skipped_rows=skipped_rows)

    except FileNotFoundError:
        return False, f"파일을 찾을 수 없습니다: {file_path}"
    except UnicodeDecodeError:
        return False, "파일 인코딩 오류 (UTF-8 형식이어야 합니다)"
    except Exception as e:
        return False, f"CSV 읽기 오류: {e}"
