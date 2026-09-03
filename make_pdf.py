"""
사용설명서 PDF 생성 스크립트
"""
from weasyprint import HTML, CSS
import base64

# 이미지를 base64로 인코딩
with open("kakaotalk_main.png", "rb") as f:
    img_data = base64.b64encode(f.read()).decode()

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{
            text-align: center;
            color: #FEE500;
            background: #3C1E1E;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #3C1E1E;
            border-bottom: 2px solid #FEE500;
            padding-bottom: 5px;
            margin-top: 25px;
        }}
        h3 {{
            color: #555;
            margin-top: 15px;
        }}
        ul {{
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 5px;
        }}
        code {{
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background: #FEE500;
            color: #3C1E1E;
        }}
        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px 15px;
            margin: 15px 0;
        }}
        .screenshot {{
            text-align: center;
            margin: 20px 0;
        }}
        .screenshot img {{
            max-width: 250px;
            border: 1px solid #ddd;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .screenshot-caption {{
            color: #666;
            font-size: 10pt;
            margin-top: 10px;
        }}
        ol {{
            padding-left: 20px;
        }}
        ol li {{
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <h1>카카오톡 매크로 사용 설명서</h1>

    <h2>1. CSV 파일이란?</h2>
    <p>쉼표로 구분된 데이터 파일이에요. 표를 텍스트로 저장한 거라고 생각하면 됩니다.</p>

    <h2>2. 지원하는 헤더 (열 이름)</h2>
    <p><strong>친구명 열</strong> (아무거나 하나 선택)</p>
    <ul>
        <li>친구명, 이름, name, Name, 받는사람, 수신자</li>
    </ul>
    <p><strong>메시지 열</strong> (아무거나 하나 선택)</p>
    <ul>
        <li>메시지, 메세지, message, Message, 내용, 문자</li>
    </ul>

    <h2>3. CSV 만드는 법</h2>

    <h3>Coda.io에서 만들기</h3>
    <ol>
        <li>표(Table) 만들기</li>
        <li>첫 번째 열 이름: <code>친구명</code></li>
        <li>두 번째 열 이름: <code>메시지</code></li>
        <li>데이터 입력</li>
        <li>표 오른쪽 상단 <code>⋯</code> 클릭 → <strong>Export</strong> → <strong>CSV</strong></li>
    </ol>

    <h3>Google Spreadsheet에서 만들기</h3>
    <ol>
        <li>새 스프레드시트 만들기</li>
        <li>A1셀: <code>친구명</code>, B1셀: <code>메시지</code></li>
        <li>2행부터 데이터 입력</li>
        <li><strong>파일</strong> → <strong>다운로드</strong> → <strong>쉼표로 구분된 값(.csv)</strong></li>
    </ol>

    <h2>4. CSV 예시</h2>
    <table>
        <tr>
            <th>친구명</th>
            <th>메시지</th>
        </tr>
        <tr>
            <td>홍길동</td>
            <td>안녕하세요! 내일 회의 참석 부탁드립니다.</td>
        </tr>
        <tr>
            <td>김철수</td>
            <td>생일 축하해요!</td>
        </tr>
    </table>

    <h2>5. 주의사항</h2>

    <div class="warning">
        <strong>친구명은 정확히!</strong><br>
        카카오톡에 저장된 이름과 <strong>글자 하나까지 똑같아야</strong> 합니다.<br>
        공백, 띄어쓰기 주의! 예: "홍길동" ≠ "홍길동 " (뒤에 공백)
    </div>

    <div class="warning">
        <strong>빈 칸은 자동 제외</strong><br>
        친구명이나 메시지가 비어있으면 자동으로 건너뜁니다.<br>
        제외된 항목은 팝업으로 알려드려요.
    </div>

    <div class="warning">
        <strong>카카오톡 메인 창 띄워두기</strong><br>
        프로그램 실행 전 카카오톡을 <strong>친구 목록 화면</strong>으로 띄워두세요.<br>
        아래 이미지처럼 친구 탭이 선택된 상태여야 합니다.
    </div>

    <div class="screenshot">
        <img src="data:image/png;base64,{img_data}" alt="카카오톡 메인 창">
        <div class="screenshot-caption">▲ 이렇게 친구 목록이 보이는 상태로 띄워두세요</div>
    </div>

    <h2>6. 프로그램 사용법</h2>
    <ol>
        <li><strong>카카오톡 먼저 실행</strong> (친구 목록 창 열어두기)</li>
        <li><strong>카카오톡매크로.app</strong> 실행</li>
        <li><strong>CSV 파일 선택</strong> 클릭</li>
        <li>미리보기에서 확인</li>
        <li><strong>발송 시작</strong> 클릭</li>
        <li>중간에 멈추려면 <strong>중지</strong> 클릭</li>
    </ol>

    <h2>7. 문제 해결</h2>
    <table>
        <tr>
            <th>증상</th>
            <th>해결 방법</th>
        </tr>
        <tr>
            <td>카카오톡이 실행 중이 아닙니다</td>
            <td>카카오톡 앱 먼저 실행</td>
        </tr>
        <tr>
            <td>친구를 못 찾음</td>
            <td>이름이 정확한지 확인</td>
        </tr>
        <tr>
            <td>CSV 읽기 오류</td>
            <td>UTF-8 인코딩 확인</td>
        </tr>
    </table>
</body>
</html>
"""

# PDF 생성
HTML(string=html_content).write_pdf("사용설명서.pdf")
print("PDF 생성 완료: 사용설명서.pdf")
