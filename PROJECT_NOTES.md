# Speeduino dash: project notes

Wireless dash for a 1961 VW Beetle running a Speeduino (Mega-based v0.4). Two ESP32 nodes
talk over ESP-NOW; nothing has been flashed or run on hardware yet.

## Working across computers (read first)

This project is edited from several computers, each with its own Claude session, so the repo can change between sessions.

- Before doing any work, run `git pull --ff-only`, then re-read this file and `SHOPPING_LIST.md`. Do this again whenever
  `git log` shows commits you didn't make.
- `--ff-only` makes the pull fail instead of creating a merge commit or conflicts. If it refuses, local and remote have both
  moved: stop, tell the user, and decide together whether to merge or rebase. Don't force anything.
- When work changes the project's state (decisions, status, measurements, open questions), update these notes in the same
  commit and push, so the next computer starts from the truth.
- Set the git identity once per machine (`git config --global user.name` / `user.email`) rather than committing with `-c`.

## Architecture

```
Speeduino Serial3 --wire--> [ESP32-C3 "bridge"] ~~ESP-NOW~~> [ESP32 "dash"] --SPI--> round tach + info screen
```

- **Bridge (ESP32-C3):** polls the Speeduino with the 'A' command at 20 Hz, broadcasts a `Telemetry`
  packet (`include/Telemetry.h`). Source: `src/bridge/main.cpp`.
- **Dash (classic ESP32 WROOM-32 DevKitC):** receives packets, draws both screens. Source: `src/dash/main.cpp`.
- `src/display/main.cpp` (`display_rx`) is a serial-only receiver for testing the radio link.

## Build environments (PlatformIO)

| Env | Purpose |
|---|---|
| `bridge_sim`, `bridge_c3_sim` | bridge sends fake data, no ECU needed |
| `bridge_live`, `bridge_c3_live` | bridge reads the Speeduino |
| `display_rx` | serial-print receiver for radio testing |
| `dash_sim` | dash draws fake data locally, no bridge needed |
| `dash` | dash receives from the bridge |

Compiled OK: all of the above. Not flashed, not tested on hardware.

## Hardware plan

- Tach: 2.1" round 360x360 SPI, GC9B72 driver (Estardyn / GoldenMorning, about GBP 5 on AliExpress).
  Active area 52.9 mm, PCB 59.24 x 67.47 mm, 10-pin 2.54 mm header, two ~2 mm holes 23.88 mm apart.
  Driver library: https://github.com/MaliosDark/Arduino_GC9B72 (Arduino_GFX based, 4 commits, untested by us).
  Needs 3.3 V, BL pin must be driven HIGH. Ask the seller for sample code and datasheet.
- Info screen: 2.8" ILI9341 240x320 SPI, non-touch, 3.3 V logic, about 86 x 50 mm.
- Backup tach if the GC9B72 fails: GC9A01 1.28" round (well supported, about 32 mm active).
- Rejected: Waveshare ESP32-S3-Touch-LCD-2.1 (cost, unclear mounting, parallel RGB), Amazon BUAGOUWZ 2.1" (no driver info),
  4" 480x480 Guition panel with a round bezel (size/depth unknown, would need S3 rewrite).
- Mounting: 3D-printed mount later (PETG). Target is a 1961 Beetle glovebox; EMPI C13-3033 listing gives about
  343 mm wide x 127-137 mm tall (aftermarket box, measure the real one, depth unknown).

## Wiring

Bridge (ESP32-C3, Serial1): Speeduino TX3 (pin 14) -> 1k/2k divider -> GPIO4 (RX); GPIO5 (TX) -> Speeduino RX3 (pin 15); common GND.
Speeduino needs Secondary Serial IO enabled in TunerStudio, 115200 baud. Check the v0.4 Serial3 header on your board.

Dash (classic ESP32): SCK 18, MOSI 23, DC 21 shared. Tach: CS 5, RST 22, BL 25. Info: CS 4, RST 27, LED 26.
3V3 + GND to both screens. Both screens share one SPI bus; untested.

Power: switched 12 V -> 1 A fuse -> automotive 12V->5V buck (36 V+ input, TVS + caps on input) -> 5 V pins.
Dash node needs its own 5 V feed. Do not power the ESP32 from the Speeduino 5 V rail. See `SHOPPING_LIST.md`.

## Bridge enclosure (ESP32-C3 + buck converter)

Small two-part box (base + lid, PETG) holding the C3 and the 12V->5V buck with its input filter parts.
Built in Fusion (via the Fusion MCP) from a parametric script; an equivalent OpenSCAD version is kept as a reference.

- `enclosure/BridgeBox/BridgeBox.py` (+ `.manifest`): Fusion script. Install by copying the folder into Fusion's
  `API/Scripts` directory, then Utilities > Scripts and Add-ins > BridgeBox > Run. Dimensions are constants at the top (mm).
- `enclosure/bridge_box.scad`: OpenSCAD equivalent, never rendered (OpenSCAD not installed).
- Default size 96.8 x 38.8 x 22.0 mm base, plus a 4.4 mm lid laid out beside it. Corner M3 posts, C3 on two rails,
  four pads for the buck area, USB-C slot on one end wall, two 8 mm square wire holes (12 V in, ECU serial out) on the other,
  floor vents under the buck, lip on the lid.
- Status: base and lid built and checked in a Fusion screenshot; fit not test-printed. Document not saved, no STL exported.
- Guessed, not measured: C3 board 55 x 26 mm, buck area 25 x 20 mm, 14 mm component height, USB slot centred on the box width.
  Measure the real C3, buck and caps (and check where the C3's USB port sits) and edit the constants before printing.
- Wire holes are bare holes: add grommets or strain relief; the box is not sealed against water.

## Open questions / unverified

1. Realtime byte offsets now match the 61Bug mainController.ini (speeduino 202402; advance is byte 24, TPS byte 25). Still unconfirmed on the wire: whether Serial3 answers the ini's `r` command, and whether it echoes an `r` first (the code tolerates both). The secondary-serial protocol setting in TunerStudio may matter (try msDroid or Generic).
2. AFR is shown as the `afr` channel (byte 10, scale 0.1 in the ini); it only means something if a wideband is wired in.
3. "Head temp" is the Speeduino CLT input; needs a CHT sender wired to it and calibrated in TunerStudio.
4. GC9B72 library on a classic ESP32 (its example is S3), and two screens on one SPI bus.
5. Warning thresholds (head 190/220 C, battery, 5000/5500 rpm shift/redline) are guesses.
6. C3 pins GPIO4/5 depend on which pins your C3 board breaks out.

## Next steps

1. Flash `bridge_c3_sim` and `display_rx` to check the radio link (no screens needed).
2. When screens arrive: flash `dash_sim`, check both screens and the shared SPI bus.
3. Verify ECU byte offsets, wire up the bridge, try `bridge_c3_live` + `dash`.
4. Measure the C3, buck and caps, update `BridgeBox.py`, export STLs and print the bridge box (PETG).
5. Measure the glovebox and the real screens, then design the 3D-printed mount.
