#!/usr/bin/env bash
# Build the nano 7G 1.0.4 AirPods-fix firmware from YOUR stock IPSW.
# No Apple material is shipped; this patches your own firmware locally.
#
#   release/build.sh --ipsw /path/iPod_1.0.4_37A40005.ipsw --out ./Firmware-nano7-btfix.MSE
#   release/build.sh --ipsw /path/iPod_1.0.4_37A40005.ipsw --out ./Firmware-stock.MSE --stock
#
# Produces a flashable Firmware.MSE. Runs on Linux or macOS (flashing needs Linux; see install.sh).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Pinned upstream the patch applies against.
UNTETHER_URL="https://github.com/olievans123/nano7-untethered.git"
UNTETHER_COMMIT="7a0f097650f50cf2fbd244984e340db8c04827e3"

IPSW=""; OUT=""; STOCK=0
while [[ $# -gt 0 ]]; do case "$1" in
  --ipsw) IPSW=$2; shift 2;;
  --out)  OUT=$2;  shift 2;;
  --stock) STOCK=1; shift;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done
[[ -n $IPSW && -n $OUT ]] || { echo "usage: $0 --ipsw <ipsw> --out <mse> [--stock]" >&2; exit 2; }
[[ -f $IPSW ]] || { echo "no such IPSW: $IPSW" >&2; exit 1; }

say(){ printf '\033[1;36m>> %s\033[0m\n' "$*"; }

# ---- stock: just extract Firmware.MSE, no patching ----
if [[ $STOCK == 1 ]]; then
  say "extracting stock Firmware.MSE"
  python3 - "$IPSW" "$OUT" <<'PY'
import sys, zipfile
open(sys.argv[2],"wb").write(zipfile.ZipFile(sys.argv[1]).read("Firmware.MSE"))
print("wrote", sys.argv[2])
PY
  exit 0
fi

# ---- deps ----
need(){ command -v "$1" >/dev/null || { echo "MISSING: $1  ($2)" >&2; MISS=1; }; }
MISS=0
need git "git"; need cargo "rust toolchain (https://rustup.rs)"; need unzip "unzip"
need fontforge "fontforge (dnf install fontforge / brew install fontforge)"
need python3 "python3"
OBJCOPY=$(command -v arm-none-eabi-objcopy || true)
[[ -z $OBJCOPY ]] && for d in /opt/homebrew/Cellar/arm-none-eabi-binutils/*/bin /usr/bin; do
  [[ -x $d/arm-none-eabi-objcopy ]] && OBJCOPY=$d/arm-none-eabi-objcopy && break; done
[[ -n $OBJCOPY ]] || { echo "MISSING: arm-none-eabi-objcopy (arm-none-eabi-binutils)" >&2; MISS=1; }
[[ $MISS == 0 ]] || { echo "install the missing dependencies and re-run." >&2; exit 1; }
export PATH="$(dirname "$OBJCOPY"):$PATH"
rustup target add thumbv6m-none-eabi >/dev/null 2>&1 || true

BUILD="$REPO/.build"; mkdir -p "$BUILD"

# ---- python venv for fonttools/pyfatfs (py3.12 works; 3.14 breaks 'fs') ----
VENV="$BUILD/venv"
if [[ ! -x $VENV/bin/python ]]; then
  PY=python3; command -v python3.12 >/dev/null && PY=python3.12
  say "creating python venv ($PY)"
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" -q install "setuptools<81" pyfatfs fonttools fs
fi

# ---- upstream + our patch ----
SRC="$BUILD/nano7-untethered"
if [[ ! -d $SRC ]]; then
  say "cloning upstream nano7-untethered @ ${UNTETHER_COMMIT:0:12}"
  git clone -q "$UNTETHER_URL" "$SRC"
  git -C "$SRC" checkout -q "$UNTETHER_COMMIT"
  say "applying ipod_sun_nano7_104.patch"
  git -C "$SRC" apply "$REPO/src/ipod_sun_nano7_104.patch"
fi
TOOL="$SRC/untether/ipod_sun_untethered"

# ---- carrier font from YOUR firmware ----
say "extracting Helvetica from your IPSW and building the CFF carrier"
"$VENV/bin/python" "$REPO/src/tools/extract_font.py" "$IPSW" "$BUILD/Helvetica.ttf"
bash "$REPO/src/tools/make_helvetica_carrier.sh" "$BUILD/Helvetica.ttf" "$BUILD/Helvetica_cff.otf"

# ---- firmware input ----
python3 - "$IPSW" "$TOOL/Firmware-37A40005.MSE" <<'PY'
import sys, zipfile
open(sys.argv[2],"wb").write(zipfile.ZipFile(sys.argv[1]).read("Firmware.MSE"))
PY
rm -f "$TOOL/Firmware-37A40005-patched.MSE" "$TOOL/Firmware-37A40005-repack.MSE"

# ---- build + run ----
say "building ipod_sun"
( cd "$TOOL" && cargo build --release )
say "repacking firmware with the BT fix + Helvetica carrier"
( cd "$TOOL" && NANO7_CFF_CARRIER="$BUILD/Helvetica_cff.otf" PYTHON="$VENV/bin/python" \
    ./target/release/ipod_sun --device nano7-104 --bt-patch )
cp "$TOOL/Firmware-37A40005-repack.MSE" "$OUT"
say "DONE -> $OUT"
echo "   flash it from Linux:  sudo release/install.sh --mse \"$OUT\""
