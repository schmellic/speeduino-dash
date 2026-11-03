# Speeduino dash: shopping list

Already have: ESP32 DevKitC (WROOM-32), ESP32-C3. Prices not checked.

## Screens
- 2.1" round 360x360 SPI, GC9B72 driver (the one you're buying). Ask the seller for sample code and the datasheet.
- 2.8" ILI9341 240x320 SPI TFT, NON-touch, 3.3V logic OK. PCB about 86 x 50 mm.

## Power (12V car to 5V)
- Automotive-rated 12V to 5V buck converter, 36V+ input, 1A+ (e.g. Pololu D24V10F5).
- Inline blade fuse holder + 1 A fuse.
- 100 uF 35 V electrolytic and 0.1 uF ceramic capacitor (input filter).
- SMBJ24A (or similar 24 V) TVS diode across the converter input.

## ECU link (bridge, C3 side)
- 1 k and 2 k resistors (5 V to 3.3 V divider on Speeduino TX3 -> C3 RX).
- 4-pin header / JST-XH plug to fit the Speeduino Serial3 pads (check your v0.4 board).
- Automotive wire, heat-shrink, small project box with cable gland for the bridge.

## Build and test
- Jumper wires (female-female and male-female) and a breadboard for bench testing.
- Perfboard or screw-terminal breakout for the dash ESP32.
- USB cables for the two ESP32 boards (C3 and WROOM-32 are USB-C).
- Multimeter.
- PETG filament (heat resistant, better than PLA for a hot glovebox) for the 3D-printed mount.
- M3 x 8-10 mm self-tapping screws (4) for the bridge box lid, and rubber grommets for its wire holes.
- M2 x 6 mm screws (4) to hold the bridge board on its standoffs (machine screws work: they cut their own thread in the 1.9 mm pilot holes; do not go longer than 8 mm).
