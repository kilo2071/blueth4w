#!/usr/bin/env bash
# Convert the device's TrueType Helvetica.ttf into a CFF OpenType carrier for the
# exploit font, so the system UI keeps rendering real Helvetica. Needs FontForge.
#
#   make_helvetica_carrier.sh <Helvetica.ttf> <out Helvetica_cff.otf>
#
# The carrier is derived from Apple's font; keep it local (do not commit/redistribute).
set -euo pipefail
IN=${1:?usage: make_helvetica_carrier.sh <Helvetica.ttf> <out.otf>}
OUT=${2:?usage: make_helvetica_carrier.sh <Helvetica.ttf> <out.otf>}
command -v fontforge >/dev/null || { echo "need fontforge (brew install fontforge / dnf install fontforge)" >&2; exit 1; }
fontforge -lang=py -c "import fontforge; f=fontforge.open('$IN'); f.generate('$OUT', flags=('opentype',))" 2>/dev/null
echo "wrote $OUT"
