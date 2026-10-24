#!/usr/bin/env bash
# docs/assets/*.png 와 demo.gif 를 src/*.html 에서 다시 만든다. 필요: Google Chrome, ffmpeg, python3,
# 설치된 글꼴 Pretendard · Inter (~/Library/Fonts). 사용: docs/assets/src/render.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/.."
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
shot() { # name width height
  local prof; prof="$(mktemp -d)" # 쓰고 버리는 프로필: 실행 중인 내 Chrome을 건드리지 않는다
  "$CHROME" --user-data-dir="$prof" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --window-size="$2,$3" --virtual-time-budget=3000 --screenshot="$OUT/$1.png" "file://$HERE/$1.html" >/dev/null 2>&1 || true
  rm -rf "$prof"
}
shot banner 1280 640; shot pipeline 1600 600
shot before-after 1600 800; shot job-families 1600 1000
# screening-sample.png 는 screening.html 에서 만든다 (파일명이 다름)
cp "$HERE/screening.html" "$HERE/screening-sample.html"; shot screening-sample 1200 1500; rm "$HERE/screening-sample.html"
# demo.gif
TMP="$(mktemp -d)"; N=$(python3 "$HERE/demo.py" "$TMP")
for f in "$TMP"/f*.html; do
  for try in 1 2 3; do # 가끔 헤드리스 크롬이 프레임을 건너뛰므로 재시도
    PROF="$(mktemp -d)"
    "$CHROME" --user-data-dir="$PROF" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
      --window-size=960,540 --screenshot="${f%.html}.png" "file://$f" >/dev/null 2>&1 || true
    rm -rf "$PROF"
    [ -s "${f%.html}.png" ] && break
  done
done
ffmpeg -y -loglevel error -framerate 2.5 -i "$TMP/f%03d.png" -vf "palettegen=max_colors=64" "$TMP/p.png"
ffmpeg -y -loglevel error -framerate 2.5 -i "$TMP/f%03d.png" -i "$TMP/p.png" -lavfi "paletteuse=dither=none" "$OUT/demo.gif"
rm -rf "$TMP"
