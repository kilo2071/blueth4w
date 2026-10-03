# blueth4w

Get modern AirPods to play audio on an iPod nano 7th generation (2012, A1446) running stock
firmware 1.0.4.

On a stock nano 7G, AirPods Pro 2 and Pro 3 pair and the stem controls work, but no audio plays.
blueth4w patches the iPod's Bluetooth A2DP stack to fix this. Once installed, the fix applies
itself at every boot, so no computer is needed to use it.

The bug: the firmware advances the audio stream's RTP timestamp in milliseconds instead of
samples, which newer earbuds reject, so they stay silent. The fix is a 28-byte patch. See
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) for details.

---

## ⚠️ READ THIS FIRST: use at your own risk

- **Use at your own risk.** This modifies iPod firmware over DFU. Modifying firmware *can
  permanently brick a device.* You are responsible for anything that happens to your iPod.
- **Only for the iPod nano 7th generation (A1446), the 2012 model, on firmware 1.0.4.** I developed and tested it on exactly that. Do **not** use it on any other iPod, or on the 2015
  refresh / firmware 1.1.2 (for 1.1.2 see NanoBtFix instead, credits below).
- **I only tested it with an HFS+ (Mac-formatted) iPod.** The fix lives entirely in the firmware
  resource partition and does not touch your music/data partition, so HFS+ is fine, but I haven't
  tested FAT32.
- **I built it on macOS and flashed it from Linux (Fedora).** The flash step *must* run on Linux
  (macOS cannot complete it; see the docs). Building should also work entirely on Linux, but I
  haven't tried that, so your mileage may vary. Any x86-64 Linux should work for flashing; I only
  used Fedora.
- **I confirmed it works with AirPods Pro 2 and AirPods Pro 3.** Other models that were already
  silent may improve too, but are unconfirmed. (AirPods Pro 1, AirPods Max, and many non-Apple
  buds always worked and are unaffected.)
- **This was made with AI** (Claude), driven by my testing on my own hardware. It is not an
  official or widely-tested release. Treat it as experimental.
- **Again: use at your own risk.** If it bricks, you reflash stock firmware yourself (the project
  includes that path, and the nano's bootrom is always recoverable from DFU, but no guarantees).

This repository ships **no Apple firmware**. You build the patched firmware from your *own* copy
of the stock 1.0.4 IPSW. Nothing here redistributes Apple's code.

---

## What you need

- An **iPod nano 7G (A1446), 2012, on firmware 1.0.4**.
- Your own **`iPod_1.0.4_37A40005.ipsw`** (from an archive / your own device backup, not provided).
- An **x86-64 Linux machine** for flashing (Fedora tested), and a **USB-A to Lightning** cable
  (a USB-C to Lightning cable did not work for me).
- Build dependencies (Linux or macOS to build; Linux to flash). See [docs/BUILDING.md](docs/BUILDING.md).

## Quick start

```sh
# 1. Build the patched firmware from YOUR stock IPSW (produces a .MSE):
release/build.sh --ipsw /path/to/iPod_1.0.4_37A40005.ipsw --out ./Firmware-nano7-btfix.MSE

# 2. Put the nano in DFU: hold Home + Sleep/Wake ~10s until the screen is black and STAYS black
#    (`lsusb` should show 05ac:1234), then on Linux:
sudo release/install.sh --mse ./Firmware-nano7-btfix.MSE          # flash the fix
#    (to revert: build a stock MSE from the IPSW and: sudo release/install.sh --mse <stock>.MSE)

# 3. The nano reboots. Connect your AirPods Pro 2/3 and play. Audio works, and survives reboots.
```

Full build/flash detail, dependencies, and how to revert: [docs/BUILDING.md](docs/BUILDING.md).

## How it works (short version)

1. A font-parsing exploit (CUB3D's `ipod_sun`, extended here to 1.0.4) gives code/memory-write
   access on the nano.
2. blueth4w repacks the firmware's resource partition so that, at every boot, a 28-byte patch is written
   into the A2DP send loop, changing the RTP timestamp step from milliseconds to samples.
3. The exploit normally mangles system fonts, so the carrier font is rebuilt from the device's own
   Helvetica so the UI looks normal.

Only the resource partition is changed; the OS image is byte-identical to stock.

## Credits and prior work

The idea came from the PS Vita. gabew100's [VitaBtFix](https://github.com/gabew100/VitaBtFix) fixes
the exact same symptom on a jailbroken Vita (pairs, controls work, but no audio) by correcting an
A2DP RTP-timestamp bug in Sony's Bluetooth stack. On a hunch that the nano 7G had the same class of
bug, I went looking in the 1.0.4 firmware, found it, and got the fix working.

Only afterward did I find [NanoBtFix](https://github.com/Merquice/NanoBtFix) by Merquice, which had
independently found and published the same root cause for the nano on firmware **1.1.2**, about nine
days earlier. Credit to them for being first to publish it for this device; I reached it on my own,
from the Vita lead, and did not know about their project until mine was already working.

None of this would exist without the exploit and tooling groundwork from the wider scene:

- **gabew100**, [`VitaBtFix`](https://github.com/gabew100/VitaBtFix): the PS Vita fix that showed
  this class of bug (and its fix) exists, and sparked the hunch for the nano.
- **CUB3D**, [`ipod_sun`](https://github.com/CUB3D/ipod_sun): the nano 7G CFF font exploit that
  everything here builds on.
- **olievans123**, [`nano7-untethered`](https://github.com/olievans123/nano7-untethered): the
  firmware-repack / payload framework and the CFF carrier mechanism.
- **freemyipod**, [`wInd3x`](https://github.com/freemyipod/wInd3x): the bootrom DFU exploit,
  decryptor, and flasher.
- **Merquice**, [`NanoBtFix`](https://github.com/Merquice/NanoBtFix): independent, earlier
  publication of the same root cause for the nano (firmware **1.1.2**, installed via NanoApps).

**What blueth4w actually adds** (and all it claims as original): porting the fix to the
**1.0.4 / 2012** firmware, making it **apply itself at boot** with no computer attached, and
**rebuilding the exploit font from the device's own Helvetica** so the system fonts stay correct.
The analysis of the bug, the exploit, and the flashing tools are other people's work; this stands
entirely on top of them.

## License

The original code here (the payload, the patch, the tools, the scripts) is MIT, see [LICENSE](LICENSE).
Third-party components keep their own licenses and are **not** vendored here; the build fetches them.
No Apple material is included or redistributed.
