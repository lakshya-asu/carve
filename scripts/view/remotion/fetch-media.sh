#!/usr/bin/env bash
# Fill public/ with the fonts and clips the compositions read. They are copies of files that
# already live elsewhere (docs/videos, the screencast folder, the installed B612 faces), so
# public/ is not committed; run this after a fresh checkout, then render.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
public="$here/public"
mkdir -p "$public"
cp "$HOME/.local/share/fonts/B612-Regular.ttf" "$HOME/.local/share/fonts/B612-Bold.ttf" \
   "$HOME/.local/share/fonts/B612Mono-Regular.ttf" "$public/"
for clip in 05-gripper-jaw-alone 06-gripper-three-finger-alone 07-ur20-jaw-grips-the-shank-from-above \
    08-scara-jaw-grips-the-shank-from-above 09-ur20-three-finger-tries-the-shank-from-above \
    10-scara-three-finger-tries-the-shank-from-above 11-ur20-three-finger-grips-the-trotter-end-on \
    12-scara-three-finger-tries-the-trotter-end-on approach-a-closeup-ur20-tilt0 \
    approach-b-closeup-ur20-tilt0-any-leg13 approach-b-closeup-ur20-tilt0 approach-b-ur20-tilt0-any \
    centre-of-gravity depth-cameras leg-segmentation loin-approach-b-closeup-ur20-tilt0-leg0 \
    reach-scara-leg reach-ur20-leg real-footage-segmentation; do
  cp "$repo/docs/videos/$clip.mp4" "$public/"
done
screencasts="$HOME/Videos/Screencasts"
cp "$screencasts/Screencast from 09-16-2026 03:05:39 AM.webm" "$public/drill-first-touch.webm"
cp "$screencasts/Screencast from 09-16-2026 03:10:48 AM.webm" "$public/drill-close-control.webm"
cp "$screencasts/Screencast from 09-16-2026 03:12:07 AM.webm" "$public/drill-carrying.webm"
echo "public/ filled: $(ls "$public" | wc -l) files"
