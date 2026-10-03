#!/usr/bin/env python3
"""Extract /Resources/Fonts/Helvetica.ttf from a stock nano 7G 1.0.4 IPSW (or Firmware.MSE),
so it can be converted into the CFF exploit carrier (see make_helvetica_carrier.sh).

Usage:
    extract_font.py <iPod_1.0.4_37A40005.ipsw | Firmware.MSE> <out Helvetica.ttf>

Needs: pyfatfs, fs (pip install "setuptools<81" pyfatfs). No Apple material is redistributed;
this reads your own firmware file.
"""
import sys, io, zipfile, struct, warnings
warnings.filterwarnings("ignore")


def load_mse(path):
    if path.lower().endswith(".ipsw"):
        with zipfile.ZipFile(path) as z:
            return z.read("Firmware.MSE")
    return open(path, "rb").read()


def find_rsrc_fat(mse):
    # MSE: ]ih[ header at 0x100, 40-byte partition directory entries at 0x5000.
    assert mse[0x100:0x104] == b"]ih[", "not a Firmware.MSE (missing ]ih[ header)"
    off = 0x5000
    while off + 40 <= len(mse):
        name = mse[off + 4:off + 8][::-1]  # type tag, byte-reversed
        if name == b"\x00\x00\x00\x00":
            break
        dev_off = struct.unpack_from("<I", mse, off + 12)[0]
        length = struct.unpack_from("<I", mse, off + 16)[0]
        if name == b"rsrc":
            body = mse[dev_off + 0x1000: dev_off + 0x1000 + length]
            # rsrc is an IMG1 (format 04, plaintext); FAT body starts at +0x400.
            assert body[:7] == b"87402.0", "rsrc is not a plaintext IMG1"
            return body[0x400:]
        off += 40
    raise SystemExit("rsrc partition not found in MSE")


def main():
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    fat = find_rsrc_fat(load_mse(sys.argv[1]))
    tmp = "/tmp/_nano7_rsrc.fat"
    open(tmp, "wb").write(fat)
    from pyfatfs.PyFatFS import PyFatFS
    f = PyFatFS(tmp, read_only=True)
    data = f.openbin("/Resources/Fonts/Helvetica.ttf", "rb").read()
    f.close()
    open(sys.argv[2], "wb").write(data)
    print("wrote %s (%d bytes, sfnt tag %s)" % (sys.argv[2], len(data), data[:4].hex()))


if __name__ == "__main__":
    main()
