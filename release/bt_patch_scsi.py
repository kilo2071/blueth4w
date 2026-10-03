#!/usr/bin/env python3
"""Drive the iPod nano 7G RWX SCSI stub (installed by the 1.0.4 exploit font) from Linux,
and apply the AirPods A2DP RTP-timestamp fix. Uses sg_raw (sg3-utils).

The stub (overwritten SCSI handler at 0x0819c454) takes a vendor CDB:
    C6 96 <subcmd> <addr b3 b2 b1 b0>   ; subcmd 1=write512, 2=read512, 3=exec, 4=VROM
Data phase is always 512 bytes.

Usage (run as root; find the iPod's /dev/sgN with `lsscsi -g` or `sg_scan -i`):
    sudo ./bt_patch_scsi.py /dev/sgN test          # read 0x08000000, expect 09 00 00 EB
    sudo ./bt_patch_scsi.py /dev/sgN read  0x082b2b80
    sudo ./bt_patch_scsi.py /dev/sgN patch          # apply the BT fix (read-modify-write + verify)
    sudo ./bt_patch_scsi.py /dev/sgN unpatch        # restore the original bytes
"""
import subprocess, sys, tempfile, os

BASE        = 0x082b2b80                 # 512-aligned block covering the patch site
OFF         = 0x082b2bb6 - BASE          # 0x36
ORIG = bytes.fromhex("01ee10ca91ed010ab8ee400bb8ee411b08ee010bbceec00b81ed010a")
PATCH= bytes.fromhex("486800ebcc10486000bf00bf00bf00bf00bf00bf00bf00bf00bf00bf")
assert len(ORIG) == len(PATCH) == 28

def cdb(sub, addr):
    return ["%02x" % sub] + ["%02x" % b for b in [0x96]] + \
           ["%02x" % ((addr >> s) & 0xff) for s in (24, 16, 8, 0)]

def read512(dev, addr):
    with tempfile.NamedTemporaryFile(delete=False) as f: out = f.name
    try:
        c = ["sg_raw", "-r", "512", "-o", out, dev, "c6", "96", "02"] + \
            ["%02x" % ((addr >> s) & 0xff) for s in (24, 16, 8, 0)]
        subprocess.run(c, check=True, capture_output=True)
        return open(out, "rb").read()
    finally:
        os.unlink(out)

def write512(dev, addr, data):
    assert len(data) == 512
    with tempfile.NamedTemporaryFile(delete=False) as f: inp = f.name; f.write(data)
    try:
        c = ["sg_raw", "-s", "512", "-i", inp, dev, "c6", "96", "01"] + \
            ["%02x" % ((addr >> s) & 0xff) for s in (24, 16, 8, 0)]
        subprocess.run(c, check=True, capture_output=True)
    finally:
        os.unlink(inp)

def do_patch(dev, new28):
    blk = bytearray(read512(dev, BASE))
    cur = bytes(blk[OFF:OFF+28])
    want = ORIG if new28 == PATCH else PATCH
    if cur == new28:
        print("already in the target state; nothing to do."); return
    if cur != want:
        print("REFUSING: bytes at 0x%08x are neither original nor patched:" % (BASE+OFF))
        print("  found:", cur.hex()); print("  origExpected:", want.hex())
        sys.exit(2)
    blk[OFF:OFF+28] = new28
    write512(dev, BASE, bytes(blk))
    back = read512(dev, BASE)[OFF:OFF+28]
    if back != new28:
        print("WRITE VERIFY FAILED:", back.hex()); sys.exit(3)
    print("OK: wrote and verified 28 bytes at 0x%08x" % (BASE+OFF))
    print("note: if audio was already streaming, reconnect the AirPods so the patched path runs.")

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    dev, cmd = sys.argv[1], sys.argv[2]
    if cmd == "test":
        # Canary = the patch site itself (stable .text), not 0x08000000 (live RTOS data).
        cur = bytes(read512(dev, BASE)[OFF:OFF+28])
        print("bytes @0x%08x: %s" % (BASE+OFF, cur.hex()))
        if cur == ORIG:
            print("EXPLOIT OK: stub works and the BT patch site is unpatched (ready to patch).")
        elif cur == PATCH:
            print("EXPLOIT OK: the BT patch is already applied.")
        else:
            print("stub responded but the patch site doesn't match the expected code.")
            print("  expected:", ORIG.hex())
    elif cmd == "read":
        addr = int(sys.argv[3], 0); print("%08x:" % addr, read512(dev, addr)[:64].hex())
    elif cmd == "patch":   do_patch(dev, PATCH)
    elif cmd == "unpatch": do_patch(dev, ORIG)
    else: print(__doc__); sys.exit(1)

if __name__ == "__main__":
    main()
