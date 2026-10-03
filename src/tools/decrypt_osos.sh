#!/usr/bin/env bash
# REFERENCE ARTIFACT from the original research (NOT part of the build/install flow).
# Shows how the osos partition was decrypted on macOS with wInd3x for reverse engineering
# (see docs/HOW_IT_WORKS.md section 2). Paths below are from the original project tree and are
# illustrative; adapt them. Decryption is NOT needed to build or use the fix.
# Decrypt the 1.1.2 osos on-device (RAM-only; no NAND writes) for side-by-side
# RE against the already-decrypted 1.0.4 osos.
#
# Physical step (yours): connect the nano with a USB-A -> Lightning cable (USB-C to Lightning did
# not work), then enter DFU: hold Home + Sleep/Wake together until the screen goes black and
# STAYS black (~10s). Do not let go early. Then run this script (no sudo needed for
# wInd3x; sudo is only used to pause Apple's auto-updater daemons).
#
# This script:
#   1. SIGSTOPs MobileDeviceUpdater / AMPDevicesAgent / AMPDeviceDiscoveryAgent so macOS
#      cannot push WTF to the DFU nano (which would move PID 0x1234 -> 0x1249 and kill the
#      exploit window).
#   2. Waits for the bootrom DFU device (05ac:1234) to appear.
#   3. Runs wInd3x decrypt with a recovery file (resumable; decrypt is slow, ~16 min).
#   4. SIGCONTs the daemons on exit, always.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WIND3X="$ROOT/tools/bin/wInd3x-nano7"
IN="$ROOT/fw/1.1.2/parts/osos_0.bin"
OUT="$ROOT/fw/1.1.2/dec/osos.dec.img1"
REC="$ROOT/fw/1.1.2/dec/osos_decrypt.recovery"
DAEMONS=(MobileDeviceUpdater AMPDevicesAgent AMPDeviceDiscoveryAgent)

mkdir -p "$(dirname "$OUT")"
[[ -x $WIND3X ]] || { echo "missing $WIND3X" >&2; exit 1; }
[[ -f $IN ]] || { echo "missing input $IN" >&2; exit 1; }

resume_daemons() { for d in "${DAEMONS[@]}"; do sudo pkill -CONT -x "$d" 2>/dev/null; done; }
trap resume_daemons EXIT

echo ">> pausing Apple device daemons (needs sudo once)"
for d in "${DAEMONS[@]}"; do sudo pkill -STOP -x "$d" 2>/dev/null; done

echo ">> waiting for bootrom DFU (05ac:1234); put the nano in DFU now"
for i in $(seq 1 60); do
  if system_profiler SPUSBDataType 2>/dev/null | grep -q "0x1234"; then found=1; break; fi
  # also catch it via ioreg (devices behind hubs can reorder idVendor/idProduct)
  if ioreg -p IOUSB -l 2>/dev/null | grep -q '"idProduct" = 4660'; then found=1; break; fi
  sleep 1
done
[[ ${found:-} == 1 ]] || { echo "DFU device not seen in 60s; aborting (daemons resumed)"; exit 2; }
echo ">> DFU device detected"

echo ">> decrypting (this is slow, ~16 min; resumable via $REC)"
"$WIND3X" decrypt --recovery "$REC" "$IN" "$OUT"
rc=$?
if [[ $rc == 0 ]]; then
  echo ">> done: $OUT"
  shasum -a 256 "$OUT"
else
  echo ">> wInd3x exited $rc; re-run this script to resume from $REC" >&2
fi
exit $rc
