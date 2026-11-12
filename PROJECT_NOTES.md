# Speeduino dash: project notes

Wireless dash for a 1961 VW Beetle running a Speeduino (Mega-based v0.4). Two ESP32 nodes
talk over ESP-NOW; the radio link is verified on the bench (simulated data) and the round tach draws on the classic ESP32 (`dash_sim`, 2026-11-10).

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
| `dash_sim` | dash draws fake data locally, no bridge needed; builds with `-DINFO_SCREEN=0` so it only drives the tach |
| `dash` | dash receives from the bridge |
| `tach_test` | round tach bring-up: tries hardware SPI at 1/4/10 MHz and software SPI, solid colour fills (LED blinks announce each) |
| `pin_test` | holds each tach signal pin high in turn (LED blinks 1-6: RST, CS, DC, SCL, SDA, BL) so a multimeter can check the wires |

Compiled OK: all of the above. Hardware-tested so far: `bridge_c3_sim` on the C3 (native USB, `/dev/ttyACM0`, flags OK) and
`display_rx` on the classic ESP32 (CH340, `/dev/ttyUSB0`). The ESP-NOW link works: the receiver printed the simulated
rpm/map/clt/iat/batt values. Also hardware-tested: `dash_sim` on the classic ESP32 drives the GC9B72 round tach (needle sweep and digits work, no leftover trail), with the info screen not connected. Wireless dash verified 2026-11-10: `bridge_c3_sim` on the C3 (powered separately, away from the computer) drives `dash` on the classic ESP32 over ESP-NOW and the tach ring and digits follow the simulated rpm (the sim sweeps 100-5900 rpm so all three colour zones show; `dash` was flashed with `PLATFORMIO_BUILD_FLAGS="-DINFO_SCREEN=0"` because the info screen is not connected). The 'no data' case also works (power the C3 off: ring clears and the centre shows the dim bar within about half a second; powering it back on recovers by itself, no reset). Info screen verified 2026-11-12: `dash_sim` (both screens, shared SCK/MOSI/DC on a breadboard) drives the round tach and the 2x3 info grid together with no problems on the shared SPI bus. Not yet tested: range, the ECU link, `dash` with both screens over the wireless link.

## Tach design and drawing notes (GC9B72, 2026-11-10)

- Design (user choice, modelled on the Audi R8 virtual cockpit, kept clean): numerals 0-6 on a dark ring that lights in 60 blocks of
  100 rpm (dial to 6000 rpm), green below 4500, orange 4500-5400, red from 5400 (the Beetle's redline, per the user), with a dim red redline band always
  visible, fine ticks outside the ring (every 250 rpm), and a big centre RPM readout (red at the redline) with a small "RPM" label. No needle. The
  tach shows nothing else: head temp, battery and the rest belong on the info screen. With no data it shows a dim bar and clears the ring.
  Layout chosen with the user from an interactive preview: ring 50 px thick (r 116-166), 10 px gap to the centre, 2 px centre outline
  (r 104-105), numerals 0-6, green/orange/red scheme. These are constants at the top of the tach section in `src/dash/main.cpp`
  (`RPM_MAX`, `RING_IN/OUT`, `SEG_RPM`, `RPM_SHIFT`, `RPM_REDLINE`), so a different look is a small edit.
  Mockups were compared in chat (classic dial, arc sweep, retro cream, shift ring, R8 variants); the lit-ring R8 style won.
- Fonts: U8g2 fonts via `olikraus/U8g2` (lib_deps on `dash` and `dash_sim`): `u8g2_font_logisoso58_tn` for the centre digits,
  `u8g2_font_helvB24_tn` for the numerals, `u8g2_font_helvB10_tr` for the label. U8g2 fonts print transparently, so the digit area is
  cleared with a rectangle first.
- There is no frame buffer (360x360x16 bit is too big for the classic ESP32), so only the blocks that change are redrawn.
  The library's `fillTriangle` leaves stray pixels beyond thin tips, so shapes that get redrawn use our own scanline `fillQuad`.
  Clearing a block to its exact shape left stray pixels at the gaps, so changed blocks and their neighbours are cleared slightly wider
  (0.4 degrees, 1 px radially), redrawn, and the numerals are put back on top.
- The earlier needle design suffered a dotted trail: erasing with a grown copy of the needle leaves almost no margin at the tip
  (it tapers to the same point). If a needle is ever wanted again, erase with a constant-width strip, not a grown copy.
- Tried and not needed: tach SPI at 10 MHz, and forcing the driver to resend the address window every write. 20 MHz with the stock driver is fine.
- `INFO_SCREEN` (default 1) in `src/dash/main.cpp`: set to 0 to leave the info screen alone while it is not connected; it also
  silences the boot warnings about SPI pins 18/23 being set up twice. `dash_sim` currently builds with it 0. Turn it back on (or remove
  the flag) when the ILI9341 is connected, and check the shared SPI bus then.
- Bring-up envs `tach_test` and `pin_test` are kept for diagnosing a new screen or wiring.

## Hardware plan

- Tach: 2.1" round 360x360 SPI, GC9B72 driver (Estardyn / GoldenMorning, about GBP 5 on AliExpress).
  Active area 52.9 mm, PCB 59.24 x 67.47 mm, 10-pin 2.54 mm header, two ~2 mm holes 23.88 mm apart.
  Driver library: https://github.com/MaliosDark/Arduino_GC9B72 (Arduino_GFX based, 4 commits, untested by us).
  Needs 3.3 V, BL pin must be driven HIGH. Ask the seller for sample code and datasheet.
- Info screen: 2.8" ILI9341 240x320 SPI, non-touch, 3.3 V logic, about 86 x 50 mm. Needs `ips=true` (colour inversion) in the `Arduino_ILI9341` constructor or black and white swap.
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

Dash (classic ESP32): SCL(clock) 18, SDA(data/MOSI) 23, DC 21 shared. The tach's pads are labelled SCL and SDA on the board (not SCK/MOSI): SCL = clock = GPIO18, SDA = data = GPIO23. They were crossed once during bring-up and the screen stayed blank, so check these first if it ever goes dark. Tach: CS 5, RST 22, BL 25. Info: CS 4, RST 27, LED 26.
3V3 + GND to both screens. The tach is verified working on this wiring. Both screens share one SPI bus; the info screen is verified working on the same bus (2026-11-12). With `INFO_SCREEN=1` and only the tach connected, serial prints harmless boot warnings (SPI pins 18/23 set up twice).

Power: switched 12 V -> 1 A fuse -> automotive 12V->5V buck (36 V+ input, TVS + caps on input) -> 5 V pins.
Dash node needs its own 5 V feed. Do not power the ESP32 from the Speeduino 5 V rail. See `SHOPPING_LIST.md`.

## Reference images (`docs/`)

- `docs/wiring.svg`: wiring between the Speeduino v0.4.4d, the bridge board (terminals A1/A2, B1/B2, R1 1k, R2 2k, C3, buck) and the 12 V feed.
- `docs/bridge_board_labelled.jpg`: photo of the built bridge board with A1/A2, B1/B2, R1/R2 and the C3 pins labelled.
- `docs/speeduino_solder_points.png`: photo of the Speeduino shield marking where to solder D14 (TX3), D15 (RX3) and GND (J6),
  plus the D21 continuity-check pads. Positions are derived from the board layout; confirm with the D21 beep test before soldering.

## Boards in use (2026-11-10)

- Two ESP32-C3 SuperMinis exist. One is mounted on the bridge board and was flashed with `bridge_c3_live` (user-confirmed); it has no
  OTA, so reflashing it needs its USB-C. The other is the bench C3 and currently runs `bridge_c3_sim`. Don't assume which one is plugged
  into the computer: check what it prints on `/dev/ttyACM0` (`rpm=... link=1` sweeping = sim; `link=0` = live with no ECU).
- The live firmware has never talked to the Speeduino, so if the in-car link fails, the dash only shows the "no data" bar and nothing
  wireless says why. Offered and declined for now: a boot-time Wi-Fi OTA window plus a raw-byte debug readout in the bridge firmware.
  Revisit if the ECU test fails and the mounted C3 has to be opened up anyway.

## Bridge enclosure

Fit-and-forget two-part box (base + lid) around the built bridge board (40 x 60 mm perfboard, see Wiring). Decisions (user, 2026-11-03):
board on standoffs; no access to the C3's USB-C once the lid is on (flash and test before closing it); the terminal screws need the lid off; lid is a push (friction) fit for now (2026-11-03).
Built in Fusion (via the Fusion MCP) from a parametric script.

- `enclosure/BridgeBox/BridgeBox.py` (+ `.manifest`): Fusion script, constants at the top (mm). Install by copying the folder into
  Fusion's `API/Scripts` directory, then Utilities > Scripts and Add-ins > BridgeBox > Run. `build_all()` makes a new design with both bodies.
- Design: 69.5 x 48.0 x 24.1 mm base (friction mode; the screws mode is 81 mm long because the posts need room) plus a 2.0 mm lid (laid out beside it, with a locating lip). Four corner standoffs (5 mm tall, 5.6 mm dia)
  at the board's four mounting holes (all four are 2 mm in from the board edges, confirmed by the user; the bottom-right one only looks hidden
  behind terminal B in the photo because of the camera angle), each with a 1.9 mm pilot hole for an M2 machine screw to cut its own thread (the user has machine screws, not self-tapping; a 1.6 mm hole printed too small). Lid: `LID_MODE = 'friction'` (default) makes a 3 mm deep lip with 0.15 mm clearance per side (`LIP_TOL`) that
  pushes into the box, with no screws and no corner posts; `LID_MODE = 'screws'` brings back four M3 corner posts (2.6 mm pilot, 3.4 mm lid holes).
  Tune `LIP_TOL` after a test fit (tighter if the lid is loose, looser if it won't go in). The lid is 5.0 mm tall in friction mode (2 mm plate + 3 mm lip).
  With no corner posts the board sits with 2.5 mm clearance at the C3 end and 3 mm at terminal B's end (`END_GAP_C3`, `END_GAP_B`; terminal B is flush
  with the board edge, per the user). Heat: C3 plus buck estimated under 0.5 W total (not measured), so the box air should run only a few degrees above
  ambient; the real heat risk to PLA is the car's cabin temperature.
  Snap-fit hooks for a later PETG version were discussed (hooks crack in PLA) but not built. Two 12 x 6 mm wire
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
- Material: the user only has PLA for now. PLA softens at about 55-60 C and a parked car's cabin can exceed that, so treat a PLA box as a fit test
  and print the car version in PETG (or ASA/ABS) before it lives in the car. Same STLs, same settings; the walls were tuned for a 0.4 mm nozzle.
- STLs of the current design (base and lid) are in `enclosure/stl/` (exported from Fusion with the medium mesh setting). Not printed yet.
  Regenerate them after any change to `BridgeBox.py`.
- The wire windows are open slots: use sleeving or sealant around the wires if dust or moisture is a concern; the box is not sealed against water.
- The earlier OpenSCAD version was removed (it modelled a bare C3 plus a separate buck, and was never rendered).

## Open questions / unverified

1. Realtime byte offsets now match the 61Bug mainController.ini (speeduino 202402; advance is byte 24, TPS byte 25). Still unconfirmed on the wire: whether Serial3 answers the ini's `r` command, and whether it echoes an `r` first (the code tolerates both). The secondary-serial protocol setting in TunerStudio may matter (try msDroid or Generic).
2. AFR is shown as the `afr` channel (byte 10, scale 0.1 in the ini); it only means something if a wideband is wired in.
3. "Head temp" is the Speeduino CLT input; needs a CHT sender wired to it and calibrated in TunerStudio.
4. ~~GC9B72 library on a classic ESP32~~ works (2026-11-10, tach only). Still open: two screens on one SPI bus.
5. Warning thresholds: redline 5400 rpm and orange from 4500 rpm are set by the user; head 190/220 C and the battery limits are still guesses.
6. Serial3 on the user's Speeduino v0.4.4d: the schematic shows J2 "HC-05 Bluetooth" is Serial0 (D1/D0, shared with USB, 2k/1k divider), NOT Serial3, so don't use it. The Mega is soldered under the shield, so the shield's holes are the Mega's pin positions. From the board photo (USB/power jack at the top = Mega rotated 90 degrees clockwise), the right-hand column of holes carries the Mega's top header; its lowest group of 8 holes, just above the double row, is the communication header: from the bottom up 21,20,19,18,17,16,15,14. So D15 (RX3) is the 2nd hole from the top of that group and D14 (TX3) the top one. Derived from the photo and the standard Mega layout, NOT yet confirmed on the board: check by continuity that the bottom hole of that group beeps to the J5 pad labelled D21. The J6 pads labelled GND sit beside the group. `bridge_c3_live` is flashed; the C3 reports link=0 until the board is connected to the ECU.

## Next steps

1. ~~Check the radio link~~ done 2026-11-02; the no-data case was confirmed on the dash on 2026-11-10.
2. ~~Round tach on `dash_sim`~~ works (2026-11-10). Info screen and shared SPI bus checked and working (2026-11-12). Optional: judge brightness/colours, test `dash` with the bridge (`bridge_c3_sim` on the C3).
3. Enclosure for the bridge board is designed (see Bridge enclosure; measure the board and print it). Solder the
   bridge wires to the Speeduino (D14 -> A1, D15 -> A2, J6 GND -> B1; run the D21 continuity check first). Then test in the car with
   `bridge_c3_live` on the C3 and `display_rx` on the classic ESP32 plugged into a laptop (it prints `no data` until real values arrive).
   TunerStudio needs Secondary Serial IO enabled at 115200, burned, then power-cycled. Then verify the ECU byte offsets and try `dash`.
4. Measure the bridge board height, update `BridgeBox.py` if needed, export STLs and print the box (PETG). Close the lid only after the in-car test.
5. Measure the glovebox and the real screens, then design the 3D-printed mount.

## Info screen design (2026-11-12)
Same design language as the tach: black ground, dark rounded panels (`C_BAND`), rim-grey labels, U8g2 fonts (helvB10 labels, logisoso20 values),
a status stripe on each panel's left edge (green normal, orange warning, red danger). 2 columns x 4 rows, grouped by purpose:
head temp | peak head, throttle (with a bar) | MAP, AFR | advance, intake | battery. Peak head is the highest head temp since power-on (kept
on screen, dimmed, if data drops out). Head temp warns at 190 C and goes red at 220 C (`HEAD_WARN_C`, `HEAD_DANGER_C`, still guesses); battery is orange
below 12.5 V and red below 11.5 V or above 15 V. Lambda and an ECU-link panel were tried and dropped (AFR already shows the mixture).
Ideas needing bridge changes: injector duty, AFR target, VE, engine status. Verified on hardware with `dash_sim`.

## OTA update of the dash (2026-11-12)
The dash runs its own Wi-Fi access point for the first 2 minutes after power-on (`SpeeduinoDash`, channel 1; it stays up while a client is connected or an
update is running, then shuts off so ESP-NOW has the radio). The Wi-Fi password is not in the repo: it lives in `src/dash/secrets.h` (git-ignored; copy
`secrets.example.h` and set your own, 8+ characters). Without that file the build uses the placeholder `change-me-123`, which would then be the Wi-Fi password.
**On a new computer, if `src/dash/secrets.h` is missing, ask the user for the dash Wi-Fi password and create the file with it before building the dash.** Two ways to update, no login beyond joining the network:
- Browser: join the network, open `http://192.168.4.1` in Chrome or Safari (not the captive-portal sign-in sheet, whose file picker often does nothing),
  choose `.pio/build/dash/firmware.bin`, press Update. A DNS catch-all makes phones treat it as a captive portal.
- PlatformIO: join the network, then `pio run -e dash_ota -t upload` (ArduinoOTA to 192.168.4.1).
Firmware is about 1.1 MB, 84% of the 1.31 MB OTA slot. The first OTA-capable build had to go on over USB. Upload page confirmed working from a phone.
Not yet checked: that ESP-NOW telemetry keeps arriving after the access point shuts off (watch the screens for 3 minutes with the test C3 sending).
The bridge C3 (mounted in the car) has no OTA yet; it would need the same treatment.
