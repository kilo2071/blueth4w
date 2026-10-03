# Building, flashing, and reverting

The repo ships **no firmware**. You build the patched firmware from your own stock
`iPod_1.0.4_37A40005.ipsw`, then flash it from Linux.

## Dependencies

**Build** (Linux or macOS):
- `git`, `unzip`
- Rust toolchain (https://rustup.rs); the build adds the `thumbv6m-none-eabi` target itself
- `arm-none-eabi-binutils` (for `arm-none-eabi-objcopy`)
  - Fedora: `sudo dnf install arm-none-eabi-binutils-cs`
  - macOS: `brew install arm-none-eabi-binutils` (the script finds it in the Cellar if not linked)
- `fontforge`
  - Fedora: `sudo dnf install fontforge` · macOS: `brew install fontforge`
- `python3` (3.12 recommended; **3.14 breaks the `fs` library** the font tools use; the build
  prefers `python3.12` if present and makes its own venv)

**Flash** (Linux only, x86-64; Fedora tested):
- `sudo dnf install libusbx usbutils`
- Either `go` (the installer builds `wInd3x` from source) or a prebuilt `wInd3x` (set
  `WIND3X=/path/to/wInd3x`)

## Build

```sh
release/build.sh --ipsw /path/to/iPod_1.0.4_37A40005.ipsw --out ./Firmware-nano7-btfix.MSE
```

What it does (all local; see `release/build.sh`): clones the pinned upstream `nano7-untethered`,
applies `src/ipod_sun_nano7_104.patch`, extracts your firmware's Helvetica and converts it to the
CFF carrier with FontForge (so system fonts stay correct; the font comes from your IPSW, so no
Helvetica needs to be installed on the build machine, only the FontForge program), builds the `ipod_sun` tool, and repacks the firmware
with the boot-time BT patch. Output is a flashable `Firmware.MSE`. Only the resource partition
differs from stock; the OS image is byte-identical.

Intermediate files land in `.build/` (gitignored). A matching stock image, for reverting:

```sh
release/build.sh --ipsw /path/to/iPod_1.0.4_37A40005.ipsw --out ./Firmware-stock.MSE --stock
```

## Flash (Linux)

1. Put the nano in **DFU**: hold **Home + Sleep/Wake** ~10 s until the screen goes black and
   **stays** black. `lsusb` should show `05ac:1234`. (Use a **USB-A to Lightning** cable; a USB-C
   to Lightning cable did not work for me. A black screen that then shows the Apple logo means it
   rebooted, try again.)
2. ```sh
   sudo release/install.sh --mse ./Firmware-nano7-btfix.MSE
   ```
   This is a **non-full** restore, so your music/data partition is left alone.
3. The nano reboots. Connect AirPods Pro 2/3 and play. Audio works, and persists across reboots.

## Revert to stock

Build a stock MSE (`--stock` above) and flash it the same way from DFU:

```sh
sudo release/install.sh --mse ./Firmware-stock.MSE
```

The nano's bootrom exploit is always reachable from DFU, so the device stays recoverable even if a
flash goes wrong. You can also restore via Finder/iTunes on a Mac/PC for stock 1.0.4.

## Optional: the SCSI debug tool

`release/bt_patch_scsi.py` is only for a *debug* build of the firmware that installs an on-device
read/write/execute SCSI stub (not the shipping build). It can read device memory and apply/revert
the RAM patch by hand. The shipping firmware does not include the stub (that stub, mis-delivered,
was the cause of an early crash, see HOW_IT_WORKS §6), so this tool is for development only.

## Why flashing is Linux-only

macOS cannot complete the restore: at the recovery/disk stage a macOS kernel driver claims the
USB interface and libusb can't detach it. The bootrom-DFU stage works on macOS (decryption/analysis
can be done there), but the flash itself must run on Linux. See HOW_IT_WORKS §8.
