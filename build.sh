#!/bin/bash
# 카카오톡매크로 빌드 + 배포 DMG 생성
# - 버전은 version.py에서 자동으로 읽음 (spec이 Info.plist에 주입)
# - 서명 규칙 (중요!):
#   * PyInstaller가 각 바이너리를 ad-hoc 서명 → 실행에는 이것으로 충분
#   * 번들 봉인은 "안쪽(프레임워크) → 바깥쪽(앱)" 순서로 개별 서명
#   * ⚠️ codesign --deep 절대 금지: 이 번들 구조에서 Bus error로 크래시하며
#     서명을 쓰다 만 상태(.cstemp 잔여물)로 앱을 손상시킴 (v1.2.0 "손상되었음" 사고 원인)
#   * 빌드 후 Info.plist를 PlistBuddy로 수정하는 것도 금지 (서명 깨짐)
# 사용법: ./build.sh
set -e

cd "$(dirname "$0")"

VERSION="$(python3 -c "from version import APP_VERSION; print(APP_VERSION)")"
APP="dist/카카오톡매크로.app"
DIST_DIR="dist/dmg_staging"   # DMG에 들어갈 내용물. 매 빌드마다 새로 만든다(저장소에 없어도 동작)
EXE="$APP/Contents/MacOS/카카오톡매크로"

DMG="dist/카카오톡매크로_설치_v${VERSION}.dmg"

echo "=========================================="
echo " 카카오톡매크로 v${VERSION} 빌드"
echo "=========================================="

echo ""
echo "[1/5] PyInstaller 빌드 (spec 기반)..."
python3 -m PyInstaller --clean -y "카카오톡매크로.spec" >/dev/null 2>&1
echo "      완료"

echo "[2/5] 서명 검증..."
# 서명은 PyInstaller가 빌드 중 각 바이너리에 넣은 ad-hoc 그대로 둔다.
# ⚠️ 여기서 번들 봉인(codesign --force --sign - 앱)을 추가하지 말 것:
#    이 번들에선 봉인이 메인 실행파일을 자기 자신 안에 기록하는 모순이 생겨
#    만들자마자 "sealed resource is missing or invalid"로 깨진다.
#    격리 해제(설치 시 xattr -cr)만 되면 개별 서명만으로 정상 실행됨 — 검증 완료.
# ⚠️ codesign --deep 은 크래시(Bus error)로 앱을 손상시키므로 절대 금지 (v1.2.0 사고 원인)
find "$APP" -name "*.cstemp" -delete
# 실행파일에 서명이 존재하는지만 확인 (Apple Silicon은 무서명 바이너리 실행 거부).
# --verify 는 쓰지 않는다: PyInstaller 산출물은 "봉인 명시+봉인 파일 없음" 상태라
# --verify 가 항상 실패하지만 실행에는 문제없음 — 실행 가능 여부는 아래 스모크 테스트가 판정.
codesign -dv "$EXE" 2>/dev/null || { echo "      ❌ 실행파일에 서명이 없음"; exit 1; }
BUILT_VER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
if [ "$BUILT_VER" != "$VERSION" ]; then
  echo "      ❌ 버전 불일치: $BUILT_VER != $VERSION"; exit 1
fi
echo "      완료 (실행파일 서명 유효, v$BUILT_VER)"

echo "[3/5] 기동 스모크 테스트 (창이 3초간 떴다 사라집니다)..."
if [ -n "${SKIP_SMOKE:-}" ]; then
  echo "      생략 (SKIP_SMOKE 설정됨 — CI 등 GUI 없는 환경)"
else
"$EXE" >/dev/null 2>&1 &
SMOKE_PID=$!
sleep 3
if kill -0 "$SMOKE_PID" 2>/dev/null; then
  kill "$SMOKE_PID" 2>/dev/null || true
  echo "      완료 (앱 정상 기동)"
else
  echo "      ❌ 앱이 3초 안에 죽음 — 빌드 불량이므로 배포 중단"
  exit 1
fi
fi

echo "[4/5] 배포 폴더 앱 교체..."
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
cp -R "$APP" "$DIST_DIR/"
cp 설치하기.command "$DIST_DIR/설치하기.command"   # 설치 스크립트 원본은 저장소 루트
cp "클로드와 함께 설치하기.txt" "$DIST_DIR/"
chmod +x "$DIST_DIR/설치하기.command"
# 사용설명서: PDF가 있으면 그걸, 없으면 HTML을 동봉 (PDF는 make_pdf.py로 생성, weasyprint 필요)
if [ -f 사용설명서.pdf ]; then
  cp 사용설명서.pdf "$DIST_DIR/"
else
  cp 사용설명서.html "$DIST_DIR/사용설명서.html"
fi
echo "      완료"

echo "[5/5] DMG 생성..."
rm -f "$DMG"
hdiutil create -volname "카카오톡매크로 설치" -srcfolder "$DIST_DIR" -ov -format UDZO "$DMG" >/dev/null
echo "      완료"

echo ""
echo "=========================================="
echo " ✅ 빌드 완료: $DMG"
echo "=========================================="
