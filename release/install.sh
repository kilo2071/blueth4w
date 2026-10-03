#!/usr/bin/env bash
# Flash a built nano 7G firmware MSE over DFU. LINUX ONLY (macOS cannot flash the recovery
# stage; see docs/HOW_IT_WORKS.md section 8). Tested on Fedora, x86-64.
#
#   sudo release/install.sh --mse ./Firmware-nano7-btfix.MSE
#
# Put the nano in DFU first: hold Home + Sleep/Wake ~10s until the screen is black and STAYS
# black; `lsusb` should list 05ac:1234. Use a USB-A to Lightning cable (USB-C to Lightning did not work).
#
# To revert: build a stock MSE (release/build.sh --stock) and flash that the same way.
set -euo pipefail
WIND3X_URL="https://github.com/freemyipod/wInd3x.git"
WIND3X_COMMIT="7c7c4d83c8b923f29e7559585b2cdbbf4e028045"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

MSE=""
while [[ $# -gt 0 ]]; do case "$1" in
  --mse) MSE=$2; shift 2;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done
[[ -n $MSE && -f $MSE ]] || { echo "usage: sudo $0 --mse <Firmware.MSE>" >&2; exit 2; }
[[ $(uname -s) == Linux ]] || { echo "flashing must run on Linux (not $(uname -s))." >&2; exit 1; }

# ---- wInd3x: use a provided binary, or build from source (needs go) ----
W="${WIND3X:-}"
if [[ -z $W ]]; then
  BUILD="$REPO/.build"; mkdir -p "$BUILD"
  W="$BUILD/wInd3x"
  if [[ ! -x $W ]]; then
    command -v go >/dev/null || { echo "need 'go' to build wInd3x, or set WIND3X=/path/to/wInd3x" >&2; exit 1; }
    command -v git >/dev/null || { echo "need git" >&2; exit 1; }
    echo ">> building wInd3x @ ${WIND3X_COMMIT:0:12}"
    rm -rf "$BUILD/wInd3x-src"
    git clone -q "$WIND3X_URL" "$BUILD/wInd3x-src"
    git -C "$BUILD/wInd3x-src" checkout -q "$WIND3X_COMMIT"
    ( cd "$BUILD/wInd3x-src" && go build -o "$W" ./cmd/wInd3x )
  fi
fi

command -v lsusb >/dev/null && { lsusb | grep -q "05ac:1234" || {
  echo "nano not in DFU (need 05ac:1234 in lsusb). Enter DFU and retry." >&2; exit 1; }; }

echo ">> flashing $MSE  (non-full restore: your music/data partition is preserved)"
"$W" restore --firmware "$MSE"
echo ">> done. The nano should restart. Connect your AirPods and play."
