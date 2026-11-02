// Enclosure for the bridge node: ESP32-C3 dev board + 12V->5V buck converter + input filter parts.
// Parametric OpenSCAD. Print in PETG (hot engine bay / cabin). Measure your real boards and edit the
// "Board dimensions" section before printing.
//
// Render one part at a time:  part = "base" or "lid" (or "both" for a preview).

part = "both";

// ---- Board dimensions (mm) -- MEASURE THESE ----------------------------
c3_len = 55;      // ESP32-C3-DevKitM-1 is roughly 55 x 26; check yours
c3_wid = 26;
c3_hole_dx = 0;   // set to 0 to skip C3 standoffs and let it sit on a foam pad instead
buck_len = 25;    // buck + TVS + caps area (D24V10F5 itself is smaller; leave room for the 100uF cap)
buck_wid = 20;
comp_height = 14; // tallest part above the PCB (pin headers / electrolytic cap)

// ---- Box settings -------------------------------------------------------
wall = 2.4;
floor_t = 2.0;
gap = 4;                  // clearance between boards and walls
standoff_h = 3;           // lifts boards off the floor
lid_t = 2.4;
screw_d = 3.0;            // M3 self-tapping into corner posts
post_d = 7;
tol = 0.3;                // lid fit

// ---- Derived ------------------------------------------------------------
in_len = c3_len + buck_len + 3 * gap;
in_wid = max(c3_wid, buck_wid) + 2 * gap;
in_hgt = standoff_h + comp_height + 3;
out_len = in_len + 2 * wall;
out_wid = in_wid + 2 * wall;
out_hgt = in_hgt + floor_t;

usb_w = 10; usb_h = 4;     // USB-C opening (on the -X end wall, so it faces the C3's USB port)
gland_d = 8;               // cable gland / grommet hole for 12V in and ECU serial wires (+X end wall)

module post(x, y, h) {
  translate([x, y, 0]) difference() {
    cylinder(d = post_d, h = h, $fn = 32);
    translate([0, 0, h - 8]) cylinder(d = screw_d, h = 8.1, $fn = 24);
  }
}

module base() {
  difference() {
    cube([out_len, out_wid, out_hgt]);
    // cavity
    translate([wall, wall, floor_t]) cube([in_len, in_wid, out_hgt]);
    // USB-C slot, centred on the C3 board, at board height
    translate([-1, out_wid / 2 - usb_w / 2, floor_t + standoff_h + 1])
      cube([wall + 2, usb_w, usb_h + 2]);
    // wire holes on the far end: 12V in, ECU TX/RX/GND out
    for (dy = [-7, 7])
      translate([out_len - wall - 1, out_wid / 2 + dy, floor_t + in_hgt / 2])
        rotate([0, 90, 0]) cylinder(d = gland_d, h = wall + 2, $fn = 32);
    // vent slots in the floor (buck gets warm)
    for (i = [0 : 3])
      translate([wall + c3_len + 2 * gap + 3 + i * 6, out_wid / 2 - 6, -1])
        cube([2.5, 12, floor_t + 2]);
  }
  // corner screw posts, flush into the corners
  p = post_d / 2;
  for (x = [wall + p, out_len - wall - p], y = [wall + p, out_wid - wall - p])
    post(x, y, out_hgt - lid_t);
  // board standoffs
  if (c3_hole_dx != 0 || true) {
    // C3 rests on two rails (keeps pin headers clear underneath)
    for (dy = [-c3_wid / 2 + 2, c3_wid / 2 - 2])
      translate([wall + gap, out_wid / 2 + dy - 1, floor_t])
        cube([c3_len, 2, standoff_h]);
    // buck area: four small pads
    bx = wall + c3_len + 2 * gap;
    for (x = [bx, bx + buck_len - 3], y = [out_wid / 2 - buck_wid / 2, out_wid / 2 + buck_wid / 2 - 3])
      translate([x, y, floor_t]) cube([3, 3, standoff_h]);
  }
}

module lid() {
  p = post_d / 2;
  difference() {
    union() {
      cube([out_len, out_wid, lid_t]);
      // inner lip locates the lid
      translate([wall + tol, wall + tol, lid_t])
        difference() {
          cube([in_len - 2 * tol, in_wid - 2 * tol, 2]);
          translate([wall, wall, -1]) cube([in_len - 2 * tol - 2 * wall, in_wid - 2 * tol - 2 * wall, 4]);
        }
    }
    for (x = [wall + p, out_len - wall - p], y = [wall + p, out_wid - wall - p])
      translate([x, y, -1]) cylinder(d = screw_d + 0.6, h = lid_t + 4, $fn = 24);
  }
}

if (part == "base" || part == "both") base();
if (part == "lid" || part == "both") translate([0, part == "both" ? out_wid + 10 : 0, 0]) lid();

echo(str("Outer size: ", out_len, " x ", out_wid, " x ", out_hgt + lid_t, " mm"));
