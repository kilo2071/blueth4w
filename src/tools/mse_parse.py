#!/usr/bin/env python3
"""List / extract partitions from an iPod Firmware.MSE (classic ]ih[ layout).
Directory at 0x5000, 40-byte entries: dev, type (byte-reversed tags), id, devOffset,
length, loadAddr, entryOffset, checksum, version, loadAddr2."""
import struct, sys, os

def entries(data, base=0x5000):
    off = base
    while True:
        e = data[off:off+40]
        dev = e[0:4][::-1].decode('latin1')
        if dev not in ('NAND', 'ATA!', 'FLSH'):
            break
        typ = e[4:8][::-1].decode('latin1')
        f = struct.unpack('<8I', e[8:40])
        yield dict(dev=dev, type=typ, id=f[0], off=f[1], len=f[2], addr=f[3],
                   entry=f[4], cksum=f[5], ver=f[6], load=f[7])
        off += 40

if __name__ == '__main__':
    path = sys.argv[1]; outdir = sys.argv[2] if len(sys.argv) > 2 else None
    data = open(path, 'rb').read()
    for p in entries(data):
        start = p['off'] + 0x1000   # devOffset is relative to 0x1000 in .MSE files
        blob = data[start:start+p['len']]
        print(f"{p['dev']} {p['type']} id={p['id']:#x} off={p['off']:#010x} len={p['len']:#010x} "
              f"addr={p['addr']:#010x} entry={p['entry']:#x} ver={p['ver']:#x} head={blob[:8].hex()}")
        if outdir:
            os.makedirs(outdir, exist_ok=True)
            open(os.path.join(outdir, f"{p['type']}_{p['id']:x}.bin"), 'wb').write(blob)
