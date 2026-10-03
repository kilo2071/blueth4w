# How it works

This is the full technical account: the bug, how it was found, the fix, and how the fix is
delivered and made persistent on firmware 1.0.4.

## 1. The symptom

On a stock iPod nano 7G, AirPods Pro 2 / Pro 3 pair successfully and the stem controls work
(play/pause/skip via AVRCP), but **no audio ever plays**. AirPods Pro 1, AirPods Max, and various
non-Apple earbuds work fine. Apple support blamed a Bluetooth-version incompatibility, which is
wrong. Bluetooth 5.x is backward compatible with the nano's 4.0. Pairing and control work; only
the audio *stream* fails. So the fault is in A2DP stream handling, not pairing.

## 2. Getting at the firmware (on a Mac)

The nano's OS lives in the `osos` partition of the firmware (`Firmware.MSE` inside the IPSW), and
it is **encrypted** (IMG1 format 3). It can be decrypted on-device with the nano's own AES engine:

- [`wInd3x`](https://github.com/freemyipod/wInd3x) (freemyipod) uses the nano 7G bootrom exploit
  (`S5Late`) and works on macOS. `wInd3x decrypt <img1> <out>` decrypts an IMG1 using the device
  in DFU mode. **RAM-only, nothing is written to the iPod**.
- macOS tip: Apple's device daemons (`MobileDeviceUpdater`, `AMPDevicesAgent`,
  `AMPDeviceDiscoveryAgent`) will grab a DFU nano within seconds; `SIGSTOP` them before entering
  DFU and `SIGCONT` after. DFU was only reachable with a USB-A to Lightning cable (a USB-C to
  Lightning cable did not work).

The decrypted `osos` (load base `0x08000000`) is a Pixo/RTXC-based RTOS with rich debug strings and
C++ symbols. Its Bluetooth host stack is **Open Interface BLUEmagic** with an Apple C++ layer
(`BT::A2dpStreamConfig`, `OI_AVDTP_*`, etc.).

## 3. Finding the bug

Loaded into Ghidra, the A2DP send path was traced. Codecs offered: SBC only (two endpoints, 44.1
and 48 kHz, 16 blocks × 8 subbands). The RTP packet builder and the per-packet timestamp update
were the suspects (newer earbuds use the RTP timestamp to drive their jitter buffer; if it's
nonsense they mute; older ones ignore it).

The timestamp update, in the send loop (`FUN_082b2994`, around `0x082b2bc6`), is:

```
vmla.f64  d0, d8, d1      ; timestamp += d8 * frames
```

where `d8` is computed earlier as a division (`vdiv.f64 d8, d0, d1`). Working out the operands,
**`d8` is the duration of one SBC frame in milliseconds** (≈ 2.9025 = 128 samples ÷ 44100 Hz).
So the firmware advances the RTP timestamp by *milliseconds* per frame.

**A2DP requires the RTP timestamp in audio samples.** Each SBC frame here is 16 × 8 = **128
samples**, so the correct step is `timestamp += 128 * frames`. The firmware's value is ~44× too
small. AirPods Pro 2/3 reject the resulting stream and stay silent; older earbuds ignore the field.

The lead for this came from gabew100's **VitaBtFix**, which fixes the identical symptom on the PS
Vita (a matching A2DP RTP-timestamp bug in Sony's stack). On the hunch that the nano had the same
class of bug, I went looking and found it. Only afterward did I learn of Merquice's **NanoBtFix**,
which had independently found and published the same root cause for the nano on firmware 1.1.2 about
nine days earlier (credit to them for being first to publish it for this device). The original byte
block is byte-identical between 1.0.4 and 1.1.2 (just at a slightly different address), which
cross-validates the analysis in both directions.

## 4. The fix

`d8` is **also** used for send pacing (`vmul.f64 d0, d9, d8` earlier in the function), so it must
not be changed. Only the timestamp calculation is rewritten (28 bytes at `0x082b2bb6`) from the
floating-point block to a pure-integer one:

```
ldr   r0, [r1, #4]          ; r0 = timestamp
add.w r0, r0, ip, lsl #7    ; r0 += frames * 128     (ip already holds the frame count)
str   r0, [r1, #4]          ; store
nop * 10                    ; pad to the original length
```

Original bytes @ `0x082b2bb6`:
`01ee10ca91ed010ab8ee400bb8ee411b08ee010bbceec00b81ed010a`
Patched bytes: `486800ebcc10486000bf00bf00bf00bf00bf00bf00bf00bf00bf00bf`

`r1` (the RTP state pointer) and `ip` (frame count) are already set up by the preceding
instructions, so the patch needs nothing else.

## 5. Getting the patch onto the nano

The nano 7G font exploit (CUB3D's `ipod_sun`) works by making the firmware parse a malformed CFF
(Type 2 charstring) font. A charstring in the font's **`space` glyph** overflows the CFF decoder's
`buildchar` state and turns the font decoder into an **arbitrary memory-write primitive**. The
exploit is triggered simply by the firmware rendering that glyph.

To run on 1.0.4 (the exploit's published constants are for 1.1.2), the exploit's stack-frame
offsets and a few function addresses had to be re-derived. The two firmware versions turned out to
be almost identical here: `cff_slot_load` is structurally the same, so every frame offset is
unchanged and only three absolute addresses shift by −4:

| | 1.1.2 (published) | 1.0.4 (this project) |
|---|---|---|
| `cff_slot_load` | `0x0813a3f4` | `0x0813a3f0` |
| CFF decoder | `0x081889ac` | `0x081889a8` |
| overwrite target (SCSI handler) | `0x0819c458` | `0x0819c454` |
| nothrow allocator | `0x0842b440` | `0x0842b440` (same) |
| frame offsets (LR 151, charstring 132, …) | n/a | unchanged |

(These were derived with `src/tools/cff_frame.py` against both decrypted images and validated by
reproducing every known 1.1.2 constant first.)

## 6. Making it persistent and standalone

The firmware's resource partition (`rsrc`, a plaintext FAT16 image) contains
`/Resources/Fonts/Helvetica.ttf`. blueth4w replaces that font with the exploit font. Because the exploit
lives in the (invisible) `space` glyph, **it re-runs every time any text with a space is rendered**
(including at boot, on the home screen).

The payload (`src/payload_bt_patch.rs`) uses the exploit's write primitive to write the 28-byte
patch into the A2DP send loop. This happens at boot, before any audio stream exists, so the write
lands cleanly. Re-writing the same bytes on later renders is harmless (identical bytes). No host,
no manual step. The iPod fixes its own Bluetooth on every power-on.

**Important design note (a bug I hit):** the exploit's "set write base" can only be used **once**
per charstring. An early version also tried to write a debug stub to a second address: the second
base-switch silently wrote to the wrong place and dumped the stub *into the BT send loop*,
corrupting it and crashing on playback. The shipping payload writes exactly one region (the patch).

## 7. Keeping the fonts intact

A raw exploit font replaces Helvetica with the exploit's carrier glyphs, which makes system
subtitles (e.g. "7 ALBUMS", the Now-Playing title) render in a wrong, rounded font. The
`ipod_sun` build supports a custom carrier via the `NANO7_CFF_CARRIER` environment variable.

The carrier is generated from the device's **own** Helvetica.ttf: it's a TrueType font, converted
to a CFF OpenType carrier with FontForge (`src/tools/make_helvetica_carrier.sh`). The exploit is
injected only into that carrier's `space` glyph, so all visible glyphs are real Helvetica and the
UI looks normal. (The carrier is derived from Apple's font and is therefore **not** committed; the
build regenerates it from your IPSW.)

## 8. Why flashing needs Linux

The repacked firmware is flashed with `wInd3x restore --firmware` over DFU. This is **not possible
on macOS**: the restore walks the device through recovery/disk mode, where a macOS kernel driver
claims the USB interface, and libusb cannot detach it (`LIBUSB_ERROR_ACCESS`). The bootrom-DFU
stage works on macOS (that's how decryption runs there), but the recovery stage does not. On Linux
libusb detaches the driver and the restore completes. Everything else (decryption, analysis,
building the image) can be done on a Mac; only the flash needs Linux.

## 9. What is and isn't changed on the device

- Changed: only the `rsrc` (resource) partition: one format byte and one font file.
- Unchanged: the `osos` OS image and every other partition are **byte-identical to stock**.
- Not touched: your music/data partition (a non-full restore preserves it). HFS+ is fine.
- Recoverable: the nano's bootrom exploit is always reachable from DFU, so you can reflash stock
  firmware if anything goes wrong.

## Appendix: addresses and bytes (1.0.4 / 37A40005)

- BT patch site: `0x082b2bb6`, 28 bytes (see §4).
- Aligned write block (what the boot payload writes): base `0x082b2bb4`, 8 little-endian words:
  `0x68484925 0x10cceb00 0xbf006048 0xbf00bf00 0xbf00bf00 0xbf00bf00 0xbf00bf00 0xf8d4bf00`
- Exploit config: `cff_slot_load 0x0813a3f0`, CFF decoder `0x081889a8`,
  `BUILDCHAR_OVERWRITE_ADDR 0x0819c454`, allocator `0x0842b440`; `OFFSET_LR 151`,
  `OFFSET_CHARSTRING_PTR 132`, `OFFSET_BUILDCHAR_LEN_PTR 120`.
- rsrc exploit trigger: the sole `"87402.0"` + `0x04` signature in `Firmware.MSE` is flipped to
  `0x03` so the resource IMG1 is parsed by the vulnerable path.
