#!/usr/bin/env bash
# Genera fixtures 100% sintéticos con FFmpeg (nada de medios privados).
# Uso: bash make_fixtures.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="$HERE/fixtures"
mkdir -p "$FIX"
FIXW="$(cygpath -m "$FIX")"   # C:/... nativo: ffmpeg.exe no entiende /c/...

echo "[1/4] clipA.mp4 (testsrc2 720p30, 8s, tono 440Hz)"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=size=1280x720:rate=30:duration=8" \
  -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=8" \
  -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -shortest "$FIXW/clipA.mp4"

echo "[2/4] clipB.mp4 (smptebars 720p30, 8s, tono 660Hz)"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "smptebars=size=1280x720:rate=30:duration=8" \
  -f lavfi -i "sine=frequency=660:sample_rate=48000:duration=8" \
  -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -shortest "$FIXW/clipB.mp4"

echo "[3/4] logo.png (PNG sintético con drawtext)"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=black@0.0:s=240x90:d=1,format=rgba" \
  -vf "drawtext=text='SPIKE F1':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.55:boxborderw=8" \
  -frames:v 1 "$FIXW/logo.png"

echo "[4/4] checksums + ffprobe"
sha256sum "$FIX"/* | tee "$FIX/SHA256SUMS.txt"
ffprobe -v error -show_entries format=filename,duration,size,bit_rate -of csv=p=0 "$FIXW/clipA.mp4"
ffprobe -v error -show_entries format=filename,duration,size,bit_rate -of csv=p=0 "$FIXW/clipB.mp4"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate -of csv=p=0 "$FIXW/clipA.mp4"
