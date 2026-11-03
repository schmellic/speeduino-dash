# Speeduino dash: project notes

Wireless dash for a 1961 VW Beetle running a Speeduino (Mega-based v0.4). Two ESP32 nodes
talk over ESP-NOW; the radio link is verified on the bench (simulated data), nothing else has run on hardware yet.

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

Compiled OK: all of the above. Hardware-tested so far: `bridge_c3_sim` on the C3 (native USB, `/dev/ttyACM0`, flags OK) and
`display_rx` on the classic ESP32 (CH340, `/dev/ttyUSB0`). The ESP-NOW link works: the receiver printed the simulated
rpm/map/clt/iat/batt values. Not yet tested: the 'no data' stale case, range, the ECU link, any screens.

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

Bridge (ESP32-C3 SuperMini, Serial1): Speeduino TX3 (pin 14) -> 1k resistor -> GPIO4 (RX, right header), with a 2k resistor from
that junction to GND; GPIO5 (TX, left header) -> Speeduino RX3 (pin 15) direct. The buck's 5 V goes to the C3 5V pin and its GND
joins the Speeduino GND wire at the C3's single GND header pin. Do not power from the buck and USB at the same time.
SuperMini pin order (USB at top): left 5,6,7,8(LED),9(BOOT),10,20,21; right 5V,GND,3V3,4,3,2,1,0. Matches the user's board.
Speeduino needs Secondary Serial IO enabled in TunerStudio, 115200 baud. Check the v0.4 Serial3 header on your board.

Bridge board (built 2026-11-02): 40x60 mm perfboard with the C3, the 12V->5V buck, the 1k/2k divider and two 2-way screw terminals
(one beside the buck, one top-left). With USB-C facing right the C3 pins read: top row 21,20,10,9,8,7,6,5; bottom row 0,1,2,3,4,3V3,GND,5V.
Terminals (photo, component side, board upright with USB-C facing right): the one beside the buck is the 12 V input, right screw 12 V+, left screw 12 V-.
Resistors: R1 (vertical, beside the C3, near the top-left terminal) is the 1k; R2 (horizontal, under the C3's bottom pins) is the 2k.
Top-left terminal (board's viewpoint, confirmed by continuity): A1 (upper) = C3 RX, reads 1k to GPIO4, so it goes to Speeduino TX3 (pin 14); A2 (lower) = C3 TX, wired to GPIO5, so it goes to Speeduino RX3 (pin 15).
The user continuity-checked the board (resistor values, GPIO4 divider, GPIO5 line, buck 5V/GND to the C3, no shorts) and reports it all
checks out. Only two serial terminal screws, so there is no dedicated ground wire to the Speeduino: in the car the grounds are shared
through the chassis, but on the bench the ECU ground must be joined to the board's ground by hand. The solder side is coated in green
resin, so the wiring can't be inspected by eye. Not yet tested powered or connected to the ECU.

Dash (classic ESP32): SCK 18, MOSI 23, DC 21 shared. Tach: CS 5, RST 22, BL 25. Info: CS 4, RST 27, LED 26.
3V3 + GND to both screens. Both screens share one SPI bus; untested.

Power: switched 12 V -> 1 A fuse -> automotive 12V->5V buck (36 V+ input, TVS + caps on input) -> 5 V pins.
Dash node needs its own 5 V feed. Do not power the ESP32 from the Speeduino 5 V rail. See `SHOPPING_LIST.md`.

## Reference images (`docs/`)

- `docs/wiring.svg`: wiring between the Speeduino v0.4.4d, the bridge board (terminals A1/A2, B1/B2, R1 1k, R2 2k, C3, buck) and the 12 V feed.
- `docs/bridge_board_labelled.jpg`: photo of the built bridge board with A1/A2, B1/B2, R1/R2 and the C3 pins labelled.
- `docs/speeduino_solder_points.png`: photo of the Speeduino shield marking where to solder D14 (TX3), D15 (RX3) and GND (J6),
  plus the D21 continuity-check pads. Positions are derived from the board layout; confirm with the D21 beep test before soldering.

## Bridge enclosure

Fit-and-forget two-part box (base + lid, PETG) around the built bridge board (40 x 60 mm perfboard, see Wiring). Decisions (user, 2026-11-03):
board on standoffs; no access to the screw terminals or the C3's USB-C once the lid is on (flash and test before closing it).
Built in Fusion (via the Fusion MCP) from a parametric script.

- `enclosure/BridgeBox/BridgeBox.py` (+ `.manifest`): Fusion script, constants at the top (mm). Install by copying the folder into
  Fusion's `API/Scripts` directory, then Utilities > Scripts and Add-ins > BridgeBox > Run. `build_all()` makes a new design with both bodies.
- Design: 81.0 x 48.0 x 24.1 mm base plus a 2.0 mm lid (laid out beside it, with a locating lip). Four corner standoffs (5 mm tall, 5.6 mm dia)
  at the board's four mounting holes (all four are 2 mm in from the board edges, confirmed by the user; the bottom-right one only looks hidden
  behind terminal B in the photo because of the camera angle), each with a 1.6 mm pilot hole for an M2 self-tapping screw. Four M3 lid posts in
  the box corners (2.6 mm pilot, 3.4 mm clearance holes in the lid). Two 12 x 6 mm wire
  windows aligned with the terminals' wire entries, which face outwards (user, 2026-11-03): B (12 V, buck end) in the +X end wall, A (ECU serial,
  C3 end) in the low-Y side wall, so the wires go straight into the blocks. Board orientation in the box: B end at +X, terminal A on the low-Y
  side, C3's USB-C toward the high-Y side. The terminal screws face up, so the lid still has to come off to tighten them.
  No USB slot, no vents.
- Status: built; checked by point-containment tests in Fusion (standoffs, pilot holes, wire holes, posts, lid holes) and body volumes, and the
  exported STLs were rendered in matplotlib (Fusion's own viewport screenshots come out washed out under Wine). Not saved, no STL committed,
  not printed.
- Measured by the user: tallest part is about 12 mm above the board, so `COMP_H = 14` stays (2 mm headroom).
- Wall thicknesses are tuned for a 0.4 mm nozzle at 0.2 mm layers (multiples of the line width): walls and lid 2.0 mm (5 lines), floor 1.6 mm
  (8 layers), screw columns have a 2.0-2.2 mm wall around the pilot holes. Print with at least 3-4 perimeters and about 25% gyroid infill;
  the standoffs and posts come out solid.
- Confirmed by the user: 5 mm standoffs are enough under the board, and M2 screws suit the corner holes.
- Measured by the user (calipers, 2026-11-03): board 1.5 mm thick; terminal blocks 10 mm wide; terminal A centre 14 mm from the board's C3 end;
  terminal B centre 31 mm across from the board's left (low-Y) edge; wire entry centre 4.5 mm above the board surface. The 12 x 6 mm windows use
  these values (`TERM_*`, `SLOT_*`, `ENTRY_Z` in `BridgeBox.py`). Not measured: the wire-entry opening size (12 x 6 mm window is a guess that suits
  wire up to about 2.5 mm^2 with insulation) and B's entry height (assumed the same as A's). Terminal B's window clears the nearby lid post.
- STLs of the current design (base and lid) are in `enclosure/stl/` (exported from Fusion with the medium mesh setting). Not printed yet.
  Regenerate them after any change to `BridgeBox.py`.
- The wire windows are open slots: use sleeving or sealant around the wires if dust or moisture is a concern; the box is not sealed against water.
- The earlier OpenSCAD version was removed (it modelled a bare C3 plus a separate buck, and was never rendered).

## Open questions / unverified

1. Realtime byte offsets now match the 61Bug mainController.ini (speeduino 202402; advance is byte 24, TPS byte 25). Still unconfirmed on the wire: whether Serial3 answers the ini's `r` command, and whether it echoes an `r` first (the code tolerates both). The secondary-serial protocol setting in TunerStudio may matter (try msDroid or Generic).
2. AFR is shown as the `afr` channel (byte 10, scale 0.1 in the ini); it only means something if a wideband is wired in.
3. "Head temp" is the Speeduino CLT input; needs a CHT sender wired to it and calibrated in TunerStudio.
4. GC9B72 library on a classic ESP32 (its example is S3), and two screens on one SPI bus.
5. Warning thresholds (head 190/220 C, battery, 5000/5500 rpm shift/redline) are guesses.
6. Serial3 on the user's Speeduino v0.4.4d: the schematic shows J2 "HC-05 Bluetooth" is Serial0 (D1/D0, shared with USB, 2k/1k divider), NOT Serial3, so don't use it. The Mega is soldered under the shield, so the shield's holes are the Mega's pin positions. From the board photo (USB/power jack at the top = Mega rotated 90 degrees clockwise), the right-hand column of holes carries the Mega's top header; its lowest group of 8 holes, just above the double row, is the communication header: from the bottom up 21,20,19,18,17,16,15,14. So D15 (RX3) is the 2nd hole from the top of that group and D14 (TX3) the top one. Derived from the photo and the standard Mega layout, NOT yet confirmed on the board: check by continuity that the bottom hole of that group beeps to the J5 pad labelled D21. The J6 pads labelled GND sit beside the group. `bridge_c3_live` is flashed; the C3 reports link=0 until the board is connected to the ECU.

## Next steps

1. ~~Check the radio link~~ done 2026-11-02. Optional: unplug the C3 and confirm the receiver prints `no data`.
2. When screens arrive: flash `dash_sim`, check both screens and the shared SPI bus.
3. Enclosure for the bridge board is designed (see Bridge enclosure; measure the board and print it). Solder the
   bridge wires to the Speeduino (D14 -> A1, D15 -> A2, J6 GND -> B1; run the D21 continuity check first). Then test in the car with
   `bridge_c3_live` on the C3 and `display_rx` on the classic ESP32 plugged into a laptop (it prints `no data` until real values arrive).
   TunerStudio needs Secondary Serial IO enabled at 115200, burned, then power-cycled. Then verify the ECU byte offsets and try `dash`.
4. Measure the bridge board height, update `BridgeBox.py` if needed, export STLs and print the box (PETG). Close the lid only after the in-car test.
5. Measure the glovebox and the real screens, then design the 3D-printed mount.
