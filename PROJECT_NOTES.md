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
Top-left terminal (board's viewpoint, confirmed by continuity): the upper screw (labelled TX3 in; formerly A1) = C3 RX, reads 1k to GPIO4, so it goes to Speeduino TX3 (pin 14); the lower screw (RX3 out; formerly A2) = C3 TX, wired to GPIO5, so it goes to Speeduino RX3 (pin 15).
The user continuity-checked the board (resistor values, GPIO4 divider, GPIO5 line, buck 5V/GND to the C3, no shorts) and reports it all
checks out. Only two serial terminal screws, so there is no dedicated ground wire to the Speeduino: in the car the grounds are shared
through the chassis, but on the bench the ECU ground must be joined to the board's ground by hand. The solder side is coated in green
resin, so the wiring can't be inspected by eye. Not yet tested powered or connected to the ECU.

Dash (classic ESP32): SCL(clock) 18, SDA(data/MOSI) 23, DC 21 shared. The tach's pads are labelled SCL and SDA on the board (not SCK/MOSI): SCL = clock = GPIO18, SDA = data = GPIO23. They were crossed once during bring-up and the screen stayed blank, so check these first if it ever goes dark. Tach: CS 5, RST 22, BL 25. Info: CS 4, RST 27, LED 26.
3V3 + GND to both screens. The tach is verified working on this wiring. Both screens share one SPI bus; the info screen is verified working on the same bus (2026-11-12). With `INFO_SCREEN=1` and only the tach connected, serial prints harmless boot warnings (SPI pins 18/23 set up twice).

Power: switched 12 V -> 1 A fuse -> automotive 12V->5V buck (36 V+ input, TVS + caps on input) -> 5 V pins.
Dash node needs its own 5 V feed. Do not power the ESP32 from the Speeduino 5 V rail. See `SHOPPING_LIST.md`.

## Reference images (`docs/`)

- `docs/wiring.svg`: wiring between the Speeduino v0.4.4d, the bridge board (terminals TX3 in / RX3 out / 12 V - / 12 V +, R1 1k, R2 2k, C3, buck) and the 12 V feed.
- `docs/bridge_board_labelled.jpg`: photo of the built bridge board with the terminals labelled by function (Speeduino TX3 pin 14, Speeduino RX3 pin 15, 12 V -, 12 V +; these were A1, A2, B1, B2 before 2026-11-16), R1/R2 and the C3 pins.
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
- Status: built and printed; checked by point-containment tests in Fusion (standoffs, pilot holes, wire windows, lid) and body volumes, and the
  exported STLs were rendered in matplotlib (Fusion's own viewport screenshots come out washed out under Wine). The Fusion document is not saved; the script is the source of truth.
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
- STLs of the current design (base and lid) are in `enclosure/stl/` (exported from Fusion with the medium mesh setting).
  Regenerate them after any change to `BridgeBox.py`.
- PRINTED in PLA on a Bambu P1S and reported fine by the user (2026-11-23): no changes needed to the model (details such as the exact lid
  tightness were not recorded; if it is loose or tight later, tune `LIP_TOL`). It is a PLA fit-test box: print the car version in PETG. Do not close
  the lid on the bridge board until the TX wire move (GPIO21 -> GPIO5, see the 2026-11-22 section) is done and the ECU link is solid.
- The wire windows are open slots: use sleeving or sealant around the wires if dust or moisture is a concern; the box is not sealed against water.
- The earlier OpenSCAD version was removed (it modelled a bare C3 plus a separate buck, and was never rendered).

## Open questions / unverified

1. Realtime byte offsets now match the 61Bug mainController.ini (speeduino 202402; advance is byte 24, TPS byte 25). Still unconfirmed on the wire: whether Serial3 answers the ini's `r` command, and whether it echoes an `r` first (the code tolerates both). The secondary-serial protocol setting in TunerStudio may matter (try msDroid or Generic).
2. AFR is shown as the `afr` channel (byte 10, scale 0.1 in the ini); it only means something if a wideband is wired in.
3. "Head temp" is the Speeduino CLT input; needs a CHT sender wired to it and calibrated in TunerStudio.
4. ~~GC9B72 library on a classic ESP32~~ works (2026-11-10, tach only). Two screens on one SPI bus work too (2026-11-12).
5. Warning thresholds: redline 5400 rpm and orange from 4500 rpm are set by the user; head 190/220 C and the battery limits are still guesses.
6. Serial3 on the user's Speeduino v0.4.4d: the schematic shows J2 "HC-05 Bluetooth" is Serial0 (D1/D0, shared with USB, 2k/1k divider), NOT Serial3, so don't use it. The Mega is soldered under the shield, so the shield's holes are the Mega's pin positions. From the board photo (USB/power jack at the top = Mega rotated 90 degrees clockwise), the right-hand column of holes carries the Mega's top header; its lowest group of 8 holes, just above the double row, is the communication header: from the bottom up 21,20,19,18,17,16,15,14. So D15 (RX3) is the 2nd hole from the top of that group and D14 (TX3) the top one. Derived from the photo and the standard Mega layout, NOT yet confirmed on the board: check by continuity that the bottom hole of that group beeps to the J5 pad labelled D21. The J6 pads labelled GND sit beside the group. `bridge_c3_live` is flashed; the C3 reports link=0 until the board is connected to the ECU.

## Next steps

1. ~~Check the radio link~~ done 2026-11-02; the no-data case was confirmed on the dash on 2026-11-10.
2. ~~Round tach on `dash_sim`~~ works (2026-11-10). Info screen and shared SPI bus checked and working (2026-11-12). Optional: judge brightness/colours, test `dash` with the bridge (`bridge_c3_sim` on the C3).
3. Enclosure for the bridge board is designed (see Bridge enclosure; measure the board and print it). Solder the
   bridge wires to the Speeduino (D14 -> TX3 in screw, D15 -> RX3 out screw, J6 GND -> 12 V - screw; run the D21 continuity check first). Then test in the car with
   `bridge_c3_live` on the C3 and `display_rx` on the classic ESP32 plugged into a laptop (it prints `no data` until real values arrive).
   TunerStudio needs Secondary Serial IO enabled at 115200, burned, then power-cycled. Then verify the ECU byte offsets and try `dash`.
4. Bridge box: PLA test print done and fine (2026-11-23). Remaining: reprint in PETG for the car, and close the lid only after the TX wire fix and the in-car test.
5. Dash pod: see "Dash pod (current state)" for the print and fit checks.

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
Firmware is about 1.1 MB, 84% of the 1.31 MB OTA slot. The first OTA-capable build had to go on over USB. Upload page confirmed working from a phone, and a full browser update (firmware.bin) completed on 2026-11-12. The laptop's NetworkManager connectivity check pops up a sign-in window showing ping.archlinux.org/nm-check.txt: ignore it and open http://192.168.4.1 yourself. The access point only restarts on power-up, so power-cycle the dash before each attempt.
Checked 2026-11-12: with the test C3 sending, both screens kept updating before, during and after the access point shut off (it waited for the phone to disconnect first).
The bridge C3 (mounted in the car) has no OTA yet; it would need the same treatment.

## Dash pod (current state, 2026-11-26: first shape B print started)
**Status:** the user started printing `dash_pod_shell.stl` and `dash_pod_lid.stl` together on the P1S. Not yet test-fitted. Ask how the print and fit went.

**Design** (`enclosure/DashPod/DashPod.py`, constants at the top; run it through the Fusion MCP from the copy in Fusion's Scripts folder, with no command dialog open):
- Under-dash pod, face flat and vertical: tach on the driver's left (LHD, +X), info screen on the right, everything inside. Shape "B curved hull": 250 mm tip to tip, flat top about 182 mm (+/-90.9), 40 deg wings, sides curving to a bottom that is full depth to x = +/-66 and bows 2.1 mm lower in the middle. 3 mm round on the front edge.
- 45 mm deep assembled (`DEPTH`): shell 250 x 100.6 x 42.5, lid 250 x 82.5 x 6.5. Underside sweeps up toward the back. Lid rear top edge rounded 2 mm.
- Fixing: rivnuts in the dash and bolts up through two roof slots at x = +/-50, z 16 to 34. Drill guide: `enclosure/stl/dash_rivnut_template.stl` (holes 25 mm behind the face line).
- Lid: 4 x M3 into posts at y = 20 (x = +/-43, +/-86); the dash perfboard (70 x 50, centred, `BOARD_CY` 5, terminal toward +X) on 4 x M2 standoffs; 8 mm cable hole at x = 50, y = 10. Screens: 2 x M2 x 4 (tach), 4 x M2.5 x 4 (info).
- Printing: shell face-down, lid plate-down, supports, brim and skirt OFF (only 3 mm bed margin per side). With supports on, Bambu reports an overhang it cannot support in the shell; a layer-by-layer check of both STLs finds nothing unsupported. PLA for fit checks, PETG for the car. Dash-coloured paint planned.
- Checked in Fusion/STL: watertight, no overlap between shell, lid, perfboard, 22 mm component space and screen PCBs. Pocket walls nearly touch the side walls (0.06 mm margin at the tightest corner).

**Measured by the user:** tach PCB 59.24 round part with a 30.5 mm tail (67.47 long), glass disc 55.5, PCB+glass 3.6, PCB 1.3, holes 8 mm up from the header end. Info board 81.6 x 50, PCB+glass 4.6, PCB 1.6, four 3 mm holes 3 mm from each edge, lit area 9 mm / 15 mm from the two ends. Perfboard holes 2.0 mm in; "22 mm is plenty, 20 probably enough" for its tallest part; wires plug onto header pins. Dash: 250 mm tip to tip; underside seen from the side is flat for 45 mm from the dial face, then steps down 11 mm and slopes at 12 deg. Dash is symmetrical. Car is a 1961 LHD Beetle.

**Assumed, check on the print:** 3.0 mm behind the screen PCBs; tach hole spacing 23.88 (listing; fits the measured tail) and glass circle centred; perfboard thickness 1.6 and terminal position (from the photo); rivnut size M4 (6.0 mm drill) and slot positions; key and knee clearance.

**Open:** the steering wheel may hide part of the tach (check from the seat; the screens could be swapped); tach is held only by its two tail screws and pocket walls (top retainer proposed, not built).

**How it got here** (details in git history): plain box and tapered versions rejected as blobs -> wings matched to the dash with test pieces (40 deg) -> tilt toward the driver tried and withdrawn (too bulky; the tilt code remains, `PITCH, YAW = 0`) -> widened to 250 mm using the sliding template -> stepped roof tried, dropped for a 45 mm deep pod -> slimmer shapes mocked up, user chose B; chrome strips and bezels dropped as too hard. Style references: Buzzbug 00-3034-0, Cool Air VW JOPEX AC8573034.

## Bridge update over ESP-NOW (working, verified 2026-11-17)

VERIFIED on the bench 2026-11-17: the bridge board's C3 was flashed once over USB (JTAG) with `bridge_c3_sim`, then updated wirelessly to `bridge_c3_live` through the dash page ("Update bridge" at http://192.168.4.1) and the dash showed no data afterwards, as expected without an ECU. The bridge image is about 1 MB (74-75% of the slot), so an update takes a minute or so. Merged to main.
- Design: the dash upload page (http://192.168.4.1) gets a second "Update bridge" box. The dash relays the .bin to the bridge over ESP-NOW, stop-and-wait, 192-byte chunks, unicast to the bridge MAC learned from its telemetry. Protocol and comments: `include/BridgeUpdate.h`; bridge side in `src/bridge/main.cpp` (`updatePoll`); dash side in `src/dash/main.cpp` (`bridgeUpload`).
- Security: HMAC-SHA256 with a 16-byte key from `include/bridge_key.h` (git-ignored; `bridge_key.example.h` is committed). The bridge sends a fresh nonce per attempt; the final END message carries an HMAC over nonce + size + SHA-256 of the image, and the bridge only switches image if it matches. No time window on the bridge. The bridge refuses while the engine is running (link ok and rpm > 300). Without `bridge_key.h` both ends build with the feature off.
- The key file is NOT in the repo: on another computer, ask the user for it (or generate a new one, then the bridge must be re-flashed over USB with that key and the dash rebuilt with the same one).
- The bridge currently in the car has no receiver, so the first firmware with this code needs ONE USB flash (the user must take the bridge out of its enclosure). Bench it on the spare C3 first. A broken new image would also need USB again (no automatic rollback).
- While an update runs, the bridge stops broadcasting and the dash screens freeze (about 30 s).

## Fuel level sender (planned, not built)
- Sender: JOPEX 113919049D (coolairvw.co.uk), resistive, 80 ohm empty, 10 ohm full. The user's tank has the opening and the sender will sit very close to the dash ESP32.
- Plan: dash ESP32 GPIO34 (ADC1, input-only; ADC2 pins don't work with Wi-Fi on). 3V3 -> 47 ohm (1/4 W; the user has 22, 47 and 100 ohm) -> GPIO34 node -> sender -> GND, 100 nF at the pin (about 2.1 V empty, 0.6 V full, ~58 mA max). The 3V3 pin is on the right-hand pin row, D34 and the left GND are on the left row.
- Software to do: averaged ADC read, calibration table (fill in known steps, e.g. 5 L), slow filter, a new info panel (the 2x4 grid is full, so one cell must make room). Wiring is drawn at the bottom of `docs/solder_side_by_side.svg` (the generator script was lost with the scratchpad; the SVG is edited directly). The 100 nF capacitor is optional (user asked; the sender will be right next to the ESP32).

## Possible oil pressure sensor (undecided, 2026-11-14)
- Not needed through the ECU. Best place is a spare ADC pin on the bridge C3 (GPIO0-3 free; the sensor is on the engine next to it), carried to the dash as a new `Telemetry` field. Sensor type undecided: a stock VW oil sender is only a warning-light switch; a pressure sender is resistive or 0.5-4.5 V (needs a divider for the C3's 3.3 V).
- Decision (user): if the bridge needs changing in future, continue the ESP-NOW update work on branch `bridge-espnow-update` (bench-test on the spare C3, one USB flash of the bridge) rather than pulling the bridge for USB each time.
- Fuel sender wiring (user, 2026-11-14): the sender has ONE terminal (to the resistor/D34 junction); its case is the return through the tank and body. No separate ESP32 GND wire to it is needed because the dash buck converter is not isolated, so the ESP32 GND is already body earth.

- Dash board photo (2026-11-16): `docs/dash_board_labelled.jpg` shows the built dash perfboard (ESP32 HW-394 USB-C DevKit, two 8-pin headers right of the ESP32 with pin 1 level with D23, INFO header nearest, TACH beyond, buck converter, 3-way screw terminal, a resistor). This confirms the header layout assumed in `docs/solder_side_by_side.svg`. The board's silk labels TX2/RX2 as D17/D16.
- Dash board terminal (user, 2026-11-16): the 3-way screw terminal carries 12 V in, GND and the fuel sender wire (left to right with USB at the bottom: sender, GND, 12 V). The blue resistor beside it is the 47 ohm fuel divider resistor.
## Info screen order, AFR warning, fuel panel (2026-11-17)
Supersedes the cell order and the peak head panel in "Info screen design (2026-11-12)".
- Order (warnings first, 2 columns x 4 rows): row 1 HEAD TEMP | AFR, row 2 FUEL | BATTERY, row 3 THROTTLE | MAP, row 4 ADVANCE | INTAKE. PEAK HEAD was removed at the user's request. Cell indices are the `C_HEAD ... C_IAT` enum in `updateInfo`.
- AFR now warns lean: orange at AFR >= 15.5, red at >= 16.0 (`AFR_WARN`, `AFR_DANGER`), only when throttle >= 15% (`AFR_LOAD_TPS`, so the closed-throttle overrun doesn't trigger it) and only after the condition has held for 1 s. `o2Raw == 0` shows a dim `--`. The thresholds are guesses and the o2Raw/10 scaling is still unchecked against the ini, so verify both with real data before trusting the colours.
- FUEL panel shows a dim `--` for now (no sender fitted). Built and compiled (`dash`, `dash_sim`); NOT yet flashed or looked at on the screen.
- Fuel design (planned): sender 10-80 ohm into the divider on GPIO34 (see "Fuel level sender"). Firmware in two stages: ADC -> ohms -> float position 0..1 using this sender's measured empty/full ohms, then position -> litres through a per-tank table (the tank's shape makes the first half of the tank move the needle slowly; the stock gauge dial shows the upper half taking about a third of the sweep). Calibrate with 10 L jerry-can steps (bench, tank out of the car) or at fill-ups; a small page on the upload page (litres in the tank now + Record) should store points in flash. Averaging many ADC samples, slow filter for slosh. Panel colours: green above 10 L, orange 10 to 6 L, red at 5 L or less (the reserve), hysteresis (red on at 5 L, back to orange above 6 L), dim `--` on a bad reading. An ADS1115 (16-bit I2C ADC) is the fallback if the ESP32 ADC is too noisy for the upper half of the tank.

### AFR scaling checked, lean thresholds need changing (2026-11-17)
- Scaling verified against `~/TunerStudioProjects/61Bug/projectCfg/mainController.ini`: `afr` is U08 at byte 10, scale 0.1, so `o2Raw / 10.0` is right; `afrTarget` is U08 at byte 21, scale 0.1 (inside the 32 bytes the bridge already reads, but not in `Telemetry`). The user's tune (`CurrentTune.msq`) has `egoType` = Wide Band, PID closed loop above 1200 rpm and below 70% TPS (15 s start delay), stoich 14.7, AFR protection configured but Off (deviation 1.4 AFR).
- The AFR target table ranges from 14.7 (light load, mid rpm) down to about 12.1-12.5 at 85-100 kPa. So the absolute 15.5 / 16.0 lean thresholds in the dash are wrong: at high load 15.5 is about 3 AFR lean, far too late for an air-cooled engine, while at cruise (target 14.7) it is only 0.8 lean.
- Plan: add `afrTarget` to `Telemetry` and warn on deviation (orange at target + 1.0, red at target + 1.5, same throttle >= 15% and 1 s hold; roughly the tune's own 1.4 protection deviation). This changes the packet size, so the bridge must be reflashed (USB once, this is the natural moment to include the ESP-NOW update receiver on `bridge-espnow-update`) and a new dash ignores an old bridge's packets until then.
- The 2024 datalogs in `61Bug/DataLogs` were not usable (my quick MLVLG parse failed); export a CSV from MegaLogViewer if they should be checked.
- DONE 2026-11-17: `Telemetry` has a new `afrTarget` field (AFR x10, realtime byte 21). The bridge fills it; the dash warns orange at target + 1.0 and red at target + 1.5 (`AFR_DEV_WARN`, `AFR_DEV_DANGER`) with the same throttle >= 15% and 1 s hold; the old absolute 15.5 / 16.0 thresholds are gone. `dash_sim` drifts lean now and then so the colours can be seen. All five envs compile (`bridge_c3_sim`, `bridge_c3_live`, `display_rx`, `dash_sim`, `dash`); not flashed or checked on hardware. The packet is one byte bigger, so a dash and bridge flashed from different commits will not talk to each other (the dash ignores the old size): flash both from this commit or later.
- Key hygiene (2026-11-17): `include/bridge_key.h` was committed by mistake (542c495, d1d5e09) because the ignore rule was only on the other branch. It is now untracked and git-ignored on main, and the key was rotated. The old key never reached a device, so it is harmless, but it is still in the repo history; ask the user before rewriting history. The new key is local only: on another computer ask the user for it or generate a new one.
- History rewritten (2026-11-17, user asked): `include/bridge_key.h` was removed from every commit on `main` and `bridge-espnow-update` and both were force-pushed, so every commit id from `542c495` onward changed. Any other clone (e.g. on the other computer) must be reset, not pulled: `git fetch && git reset --hard origin/main` (or just re-clone). GitHub may keep the old commits reachable by id for a while; the old key never reached a device and has been replaced anyway. A bundle of the pre-rewrite repo is in the Claude session scratchpad only.

### Bench-test notes (2026-11-17)
- How to update the bridge: power it (not from a laptop USB port, which browned it out and made the link drop; use a charger or the buck), power-cycle the dash, join its Wi-Fi, open http://192.168.4.1, pick the bridge `.bin` (`.pio/build/bridge_c3_live/firmware.bin`) under "Update bridge". The dash must already be receiving the bridge's packets, because it learns the bridge's MAC from them.
- The dash and the bridge must come from the same commit (the telemetry packet size changed with `afrTarget`), so after a Telemetry change flash the dash first (its own Wi-Fi update works) and then the bridge from the dash page; during the gap the dash shows no data.
- Linux note: after a kernel update without a reboot the USB serial drivers (`cdc_acm`, `ch341`) can't load, so `/dev/ttyACM0` and `/dev/ttyUSB0` vanish. The C3 can still be flashed through its built-in USB JTAG with a scratch ini that extends `platformio.ini` and sets `upload_protocol = esp-builtin` (run with `pio run -c <ini> -e <env> -t upload`).

- Fuel sender measured by the user (2026-11-17): 8 ohm at full to 80 ohm at empty (the listing said 10 to 80). With the 47 ohm divider that is about 2.1 V empty and 0.5 V full at D34, about 60 mA at full (a 1/4 W resistor is fine), so both ends are inside the ESP32 ADC's accurate range. Intermediate points (e.g. half travel) not measured yet.
- Fuel sender curve (user, 2026-11-17): with the float arm at about halfway, the sender reads about 27 ohm (8 full, 80 empty), where a linear sender would read about 44. So its resistance is not linear in arm position (it fits the stock dial, whose half mark sits near 30 ohm). This replaces the "two-stage" idea above: don't split sender and tank, use ONE calibration table of ohms -> litres filled from the real fill steps (ohms are computed from the ADC with the divider formula so the table doesn't depend on the ADC's own curve). Consequence: replacing the sender means redoing the calibration. At 27 ohm D34 would be about 1.2 V.

## Fuel level firmware (2026-11-17; dash_sim seen working 2026-11-18, real dash build (86.0%) then flashed over Wi-Fi; ohms reading bench-checked with resistors 2026-11-18, real sender wired and working)
- `src/dash/main.cpp`, "Fuel level" block: GPIO34 (ADC1) read with `analogReadMilliVolts` (16 samples, slow filter of about 5 s), converted to sender ohms with the divider formula (3.3 V, 47 ohm fixed resistor, `FUEL_R_FIXED`). Readings outside 3 to 110 ohm (wire off, short, nothing connected) show a dim `--`.
- Litres come from one table of (ohms, litres) points. Default curve (a guess from the stock dial, panel shows `~` before the number): 80 ohm 0 L, 75 ohm 5 L, 30 ohm 20 L, 8 ohm 40 L. Recorded points override any default within 4 ohm and are stored in flash (Preferences, namespace `fuel`, key `pts`, up to 12 points; a new point within 1.5 ohm of an old one replaces it). Linear interpolation between points, clamped at the ends.
- Calibration page: http://192.168.4.1/fuel (dash Wi-Fi window; link on the main upload page). Shows the live ohms and litres, takes "litres in the tank now" and records a point, resets to the default. Wait about 15 s after the fuel settles. Priority points: the 5 L reserve, full, then a few between. The real tank capacity is whatever the empty-to-full fill adds up to (the bar uses the largest litres in the table, 40 L by default).
- Panel colours: green above 10 L, orange at 10 L or less, red at 5 L or less, each stays one litre longer when recovering (`FUEL_LOW_L`, `FUEL_RESERVE_L`). `dash_sim` sweeps a fake sender from 80 to 8 ohm over about two minutes so the colours can be seen.
- Bench check 2026-11-18 (resistors in place of the sender, multimeter at D34): the ESP32 reads about 23 mV high at D34 (same at 0.58 V and 1.66 V), so `FUEL_ADC_OFFSET_MV = 23` is subtracted. Divider resistor measured 47 ohm, rail 3.3 V. After the fix a 9.8 ohm resistor reads 10.0 and a 47 ohm resistor reads 47.4 (bench wiring adds about 0.2 to 0.4 ohm). A bad ground at the divider earlier made it read high, so check the earth first if the ohms look wrong. The reading takes 20 s or more to settle after a change (slow filter).
- Real sender wired and working (user report 2026-11-18). Not yet verified: recording calibration points against real fuel (5 L reserve first, then full), the /fuel page on a phone, and flash use is 86% of the OTA slot.

## Bridge hang fixed, first in-car link attempt (2026-11-21)
- Symptom: with the bridge in the car the dash showed no data. The dash now prints one status line a second over USB (`rx good=... age=...ms link=... rpm=...`): `good` counts telemetry packets from the bridge, `age` is ms since the last one, `link` is the bridge's flag for whether the ECU answered. Read it with the dash plugged into the laptop (CH340, `/dev/ttyUSB0`, 115200).
- Finding: the radio link was fine, but the live bridge sent for 5 to 10 s after power-up and then went silent (power LED still on). `bridge_c3_sim` never did this. Cause: `readSpeeduino()` waited for the ECU reply in a loop that spun flat out for 100 ms every poll; with no ECU answer the C3 (single core) starved its own radio and stopped sending. Fix: `delay(1)` inside the wait when no byte has arrived (and the stale-byte clear-out is bounded to 256 bytes). After the fix the bridge ran steadily from a phone charger with the dash next to it (about 5 packets/s while the ECU is silent, since each poll waits its 100 ms).
- Wrong turns, so nobody repeats them: it was not USB printing (the sim build prints too and works), not the car's 5 V supply (4.98 V steady, same on a charger), not range. A bisect build that skipped ECU polling (`bridge_c3_live` plus polling removed) ran steadily and pointed at the wait loop.
- WARNING: do not swap the bridge's TX and RX wires "to test". The RX line has a 1k/2k divider (GPIO4) but the TX line (GPIO5) goes straight to the Speeduino, so swapped, the ECU's 5 V TX3 output lands on the C3's TX pin. It was done once; the C3 still works, but it was a risk. Correct: bridge RX pad (divider, GPIO4) to ECU TX3 (D14), bridge TX pad (GPIO5) to ECU RX3 (D15).
- TunerStudio: Settings, "Canbus/Secondary Serial IO Interface": Enable Second Serial = on, Second Serial protocol = Generic (ini File). There is no baud rate field; Serial3 is 115200 (assumed, not confirmed). Burn and power-cycle the ECU. TunerStudio grabs `/dev/ttyACM0` when the bridge is plugged into the laptop; close it before flashing or reading the bridge.
- Still to do: reconnect the data wires and see whether `link=1` appears (ECU answering), confirm the D14/D15 pin positions by continuity (bottom hole of the comm header to the J5 pad D21), then verify the byte offsets and AFR on real data.

## First live ECU attempt, no answer yet (2026-11-21)
- Bridge TX: the TX wire on the built bridge board is soldered to GPIO21 (not GPIO5). Firmware now uses `SPEEDUINO_TX = 21` for the C3, so the board and code match; moving the wire to GPIO5 is optional. RX is GPIO4 through the 1k/2k divider (works: the ECU's TX3 line idles high and clean). Until this was found the bridge never sent a request at all.
- Ground: the bridge's GND must be connected to the ECU's ground. With it missing, the RX line was full of noise (garbage values with `link=1`); with it connected the line is clean. Careful when powering the bridge from the laptop USB: keep the GND wire to the ECU, but not the car's 5 V.
- The ECU did not answer at any baud rate (9600 to 500000), with either the `r` ini-style request (Generic (ini File)) or a single `A` (Generic (Fixed List)), with the wiring checked (continuity OK, user confirms the wires are on D14/D15, ground connected). Not yet explained. Ideas left: ECU firmware version vs the 202402 ini, Serial3 not actually running, an electrical problem at the ECU's RX3 hole (check the D15 hole voltage with the bridge sending, needs ECU access).
- ECU setting currently left on Generic (Fixed List) after the `A` test; set it back to Generic (ini File) (Settings, Canbus/Secondary Serial IO Interface), burn, power-cycle.
- Bridge debug hooks (compile-time flags, all off in `bridge_c3_live`): `BRIDGE_DEBUG` prints the raw reply, `BRIDGE_BAUDSCAN` tries baud rates 9600 to 500000, `BRIDGE_ASCAN` sends `A` instead of `r`. Use with `PLATFORMIO_BUILD_FLAGS="-DBRIDGE_BAUDSCAN=1 -DBRIDGE_DEBUG=1" pio run -e bridge_c3_live -t upload`.
- Known weakness: the bridge sets `link=1` for any 32 bytes, so line noise shows up as garbage values. Add a plausibility check before this goes in the car.
- The dash showed no data in the car because the bridge had no reply from the ECU; the dash and the radio link work (see the earlier section).

## ECU link WORKS after firmware update; bridge boot jams it (2026-11-22)
- ECU updated to speeduino 202501 (2025.01.7). Over the bridge wiring the ECU now answers Q ("speeduino 202501"), S, n, A and the 7-byte `r` request at 115200. Output-channel offsets in the new ini are unchanged (map 4, iat 6, clt 7, batt 9, rpm 14, afrTarget 21, advance 24, tps 25).
- `r` reply is `'r', 0x30` + data (34 bytes for 32 of data). The parser used to skip only one byte, so it would have read every value one byte off; it now requires the full 2-byte header and length (also stops noise giving link=1).
- Protocol setting: Generic (ini File). Secondary serial enabled.
- PROBLEM: whenever the bridge reboots (flash, reset, power-up), the ECU stops answering until the ECU is power-cycled. Reproduced: ECU power-cycle -> link=1; reset only the bridge -> link=0 and stays. Likely cause: TX is on GPIO21 = C3 UART0 TX, where the ROM bootloader prints its boot text at 115200; the ECU reads that as commands (some, like `G`, `r`, `M`, `B`, wait for more bytes) and its secondary-serial handler gets stuck.
- Tried: TX moved to GPIO5 (done 2026-11-27, SPEEDUINO_TX = 5). It did NOT cure it: after a bridge reset the ECU still stops answering until it is power-cycled. So the GPIO21 boot text is not the (only) cause. Next idea: the TX line floats while the C3 is in reset, so the ECU's RX3 may see noise; try a 10k pull-up from the bridge's TX pin (GPIO5) to 3V3 so the line idles high through a reboot. Garbage reaching the ECU could also have written to its RAM config: compare the tune with the saved .msq.
- Lesson: never open or flash the ECU's own USB port (/dev/ttyACM0) to "test" - opening it resets the Mega. The bridge is the Espressif device in /dev/serial/by-id.

## Power-on splash (2026-11-23, flashed over USB)
- Tach: the normal ring sweeps up to full scale (green to 4500, orange to 5400, red to 6000), holds briefly, falls back to zero. Uses the live tach's own block drawing, so almost no extra flash.
- Info screen: on a dark `C_BAND` panel a red line draws first, then "Schmellic" and "EFi" (both `logisoso32`, white, left-aligned, block centred, equal gaps above and below the line, measured from the real font bounds) slide in from the left. Text is erased and masked per frame because the library cannot clip.
- Sequence: backlights fade in (PWM, 500 ms), sweep and slide (about 2.5 s), fade out, then the normal faces fade in (400 ms). Total about 3.5 s before the normal screens. The OTA Wi-Fi window (120 s) is counted from power-on as before.
- Dash firmware is 87.2% of flash after this. A Beetle-with-flashing-lights splash was tried in mock-ups and dropped (looked wrong without a proper bitmap).
- Dash USB port is the CH340 `/dev/ttyUSB0`; never touch `/dev/ttyACM0` (the ECU's own USB, opening it resets the ECU).

## ECU link: fixed by switching to the framed Tuner Studio protocol (2026-11-27)
- The Generic (ini File)/(Fixed List) secondary-serial modes have no timeout: a stray byte (`M`, `p`, `r`, `b`, `B`, `d`, `G`) makes the ECU wait for 2-9 parameter bytes (or a whole `M` data chunk) and it then stops answering until power-cycled (read from Speeduino 202501 comms_secondary.cpp / comms_legacy.cpp). A bridge reset leaves the TX line glitching or floating, which is the likely source of the stray bytes. Moving TX to GPIO5 alone did not fix it.
- Fix: set the ECU's secondary serial protocol to **Tuner Studio** (Settings -> Canbus/Secondary Serial IO Interface, then Burn and power-cycle) and the bridge now speaks that protocol: request `00 07 | 'r' 00 30 offLo offHi lenLo lenHi | CRC32(payload, big-endian)`, reply `len(2) | 00 | data | CRC32`. CRC32 is the usual reflected one. A bad frame is discarded (CRC error) and the ECU times out half frames after 400 ms, so noise can no longer wedge it. `link=1` now requires a valid CRC.
- Verified on the bench 2026-11-27: link=1, and three bridge resets in a row (ECU not touched) all recovered. Not yet verified: unplugging the bridge's power completely, engine running, TunerStudio over USB while the secondary is in Tuner Studio mode (should still work; the source suggests the secondary diverts only while a frame is in progress).
- The earlier garbage could have written stray values into the ECU's RAM config (only an accidental `b`/`B` burn would be permanent): compare the ECU's tune with the saved .msq.
- Never open /dev/ttyACM*: port numbers swap between boots. Use /dev/serial/by-id (Espressif = bridge, Arduino = the ECU).

### TunerStudio connecting breaks the framed link until the ECU is power-cycled (2026-11-27)
- With the ECU's secondary serial set to Tuner Studio (burned, ECU power-cycled) and TunerStudio NOT connected: framed `Q` returns `00 11 00 "speeduino 202501" CRC`, plain commands get no answer, and the bridge link is solid through flashing and repeated resets.
- After TunerStudio connects over USB, the ECU starts treating the secondary port's bytes as plain legacy commands (framed requests come back as raw text/data, `link=0`), and it stays that way after TunerStudio is closed, until the ECU is power-cycled. Likely cause (not confirmed in the source): TunerStudio's legacy commands set the firmware's allow-legacy-comms flag. The ECU's own note also says the primary and secondary ports cannot be used simultaneously in this mode.
- Full bridge power-off and replug (TunerStudio closed, ECU untouched) verified 2026-11-27: link=1 straight back.
- Practical rule: tune with the bridge unplugged, then power-cycle the ECU (ignition off/on) afterwards. In the car every ignition cycle starts clean.
- `BRIDGE_PROBE` debug flag (src/bridge/main.cpp) prints how the ECU answers a framed `Q`, plain `Q` and plain `S`: use it to see which mode the ECU is really in. TunerStudio's dialog can show the project's value, not the ECU's.

### Bridge backs off when TunerStudio connects (2026-11-27, bench-tested)
- The ECU is not reachable once installed, so the bridge cannot be unplugged for tuning. Instead `readSpeeduino()` detects the ECU answering in plain-command mode (a complete reply without the `00 21` frame header, which is what happens after TunerStudio connects) and sets `holdOff`: the bridge sends nothing more and reports `link=0` until it is rebooted. Only one frame is sent into the ECU's plain-command parser before it stops.
- Bench test: TunerStudio connected with the bridge running: bridge printed `HOLD` after one frame and stopped polling; TunerStudio connected without errors and its gauges were live. After closing TunerStudio, an ECU power-cycle and a bridge reflash (restart) gave `link=1` again.
- Needs: bridge and ECU both restarted by the ignition (check they are fed from the same switched supply) so one ignition cycle after tuning restores the dash. If the bridge has its own always-on supply it would stay silent after tuning until it is restarted.
- Not yet tested: writing or burning in TunerStudio with the bridge running (the bridge is silent by then, so it should be the same as normal tuning), and the car with the engine running.

## Dash heard nothing from the bridge: fixed with lower bridge TX power (2026-11-27)
- Symptom: dash screens showed no data; the dash status line showed `rx good=0 other=0` (not one packet), although the bridge was alive, reading the ECU (`link=1`) and reporting `esp_now_send rc=0` and `send status 0` on channel 1, with the two boards side by side.
- Findings: the dash's radio started fine (`now=0 ch=1 mode=3`) and heard ordinary Wi-Fi traffic but zero frames from the bridge's MAC; the bridge could hear the dash's access point (-58 dBm). So the bridge's transmissions were not usable at full power (the C3 SuperMini's small 3.3 V regulator sags under transmit peaks, a known SuperMini quirk).
- Fix: `WiFi.setTxPower(WIFI_POWER_8_5dBm)` in the bridge's setup (always on). With it the dash received about 10 packets/s. The dash is only a couple of metres from the bridge, so low power is plenty. The earlier in-car "no data" was very likely this same problem.
- The dash status line now also prints `now=` (esp_now_init result), `ch=` and `mode=`. Debug flags added to the bridge: `BRIDGE_DEBUG` also prints the send result and send status; `BRIDGE_RADIOSCAN` scans for the dash's access point and prints its RSSI.
- Always flash/reset the bridge by its device id (`/dev/serial/by-id/usb-Espressif_...`): the ACM port numbers swap between boots and the ECU is the other one.
