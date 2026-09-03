#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="카카오톡매크로.app"
APP_PATH="$DIR/$APP_NAME"
DEST="/Applications/$APP_NAME"

clear
APP_VERSION="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_PATH/Contents/Info.plist" 2>/dev/null)"
echo "=========================================="
echo "   카카오톡 메시지 발송 프로그램 설치"
[ -n "$APP_VERSION" ] && echo "   (버전 $APP_VERSION)"
echo "=========================================="
echo ""

if [ ! -d "$APP_PATH" ]; then
    echo "❌ 오류: $APP_NAME 을(를) 찾을 수 없습니다."
    echo "   이 스크립트는 앱과 같은 폴더에 있어야 합니다."
    echo ""
    read -p "아무 키나 누르면 종료합니다..." _
    exit 1
fi

# 0. CPU 확인 — 애플 실리콘(M1 이상) 전용
#    lipo 등 개발자 도구를 쓰면 도구 설치 팝업이 떠서 초심자를 혼란시킴 → sysctl(기본 내장)만 사용
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
    echo "❌ 이 앱은 애플 실리콘(M1 이상) 맥 전용입니다."
    echo "   현재 맥은 인텔(Intel) 맥이라 실행할 수 없어요."
    echo "   → 제작자에게 문의하세요."
    echo "   ※ 막히면 같은 폴더의 '클로드와 함께 설치하기.txt'를 열어 안내를 따라주세요."
    echo ""
    read -p "아무 키나 누르면 종료합니다..." _
    exit 1
fi

# 이미 설치된 버전이 있으면 알려주기
OLD_VERSION="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$DEST/Contents/Info.plist" 2>/dev/null)"
if [ -d "$DEST" ]; then
    echo "기존 설치 발견: 버전 ${OLD_VERSION:-알 수 없음} → ${APP_VERSION:-새 버전} 으로 교체합니다."
    echo ""
fi

# 1. 응용 프로그램 폴더로 복사 (기존 버전 있으면 교체)
echo "1. 응용 프로그램 폴더에 복사 중..."
[ -d "$DEST" ] && rm -rf "$DEST"
if ! cp -R "$APP_PATH" /Applications/; then
    echo "   ⚠️ 복사 실패. 수동으로 앱을 Applications 폴더로 옮겨주세요."
    echo "   ※ 막히면 같은 폴더의 '클로드와 함께 설치하기.txt'를 열어 안내를 따라주세요."
    read -p "아무 키나 누르면 종료합니다..." _
    exit 1
fi
echo "   완료!"
echo ""

# 2. 보안 격리(quarantine) 해제 — 이게 없으면 "손상되었음" 오류가 뜸
echo "2. 보안 속성 정리 중..."
if ! xattr -cr "$DEST"; then
    echo "   ⚠️ 보안 속성 제거 실패. 아래 명령을 터미널에 직접 입력해 주세요:"
    echo "      xattr -cr \"$DEST\""
    echo "   ※ 막히면 같은 폴더의 '클로드와 함께 설치하기.txt'를 열어 안내를 따라주세요."
    read -p "아무 키나 누르면 종료합니다..." _
    exit 1
fi
echo "   완료!"
echo ""

# ⚠️ 여기서 codesign 재서명을 하지 말 것!
#    v1.2.0까지는 `codesign --force --deep --sign -` 재서명을 했는데, 이 명령이
#    이 앱 번들 구조에서 크래시(Bus error)하며 서명을 쓰다 만 상태로 남겨
#    설치된 앱을 "손상되었음" 상태로 만드는 원인이었음.
#    서명은 빌드 시점(build.sh)에 완결되므로 설치 시에는 격리 해제만 하면 됨.

echo "=========================================="
echo "   설치 완료!"
echo "=========================================="
echo ""
echo "※ 사용하려면 '손쉬운 사용' 권한이 필요합니다."
echo "  곧 열리는 시스템 설정 창에서"
echo "  '카카오톡매크로'를 켜 주세요."
echo ""
echo "앱 위치: $DEST"
echo ""

# 3. 앱 실행 + 손쉬운 사용 설정 열기
open "$DEST"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
read -p "아무 키나 누르면 종료합니다..." _
