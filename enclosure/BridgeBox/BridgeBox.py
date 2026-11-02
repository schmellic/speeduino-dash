"""Fusion script: enclosure for the bridge node (ESP32-C3 dev board + 12V->5V buck converter).

Install: Fusion > Utilities > Scripts and Add-ins > Scripts (green +) > pick this BridgeBox folder, then Run.
Creates two bodies: the base (with corner posts, board rails, USB-C slot, wire holes, floor vents) and the lid
(placed beside it, with a locating lip and screw holes). Edit the dimensions below to match your real boards
before printing. All values are millimetres; the Fusion API works in cm, so mm() converts.
"""
import traceback
import adsk.core
import adsk.fusion

# ---- Board dimensions (mm): MEASURE THESE ------------------------------
C3_LEN, C3_WID = 55.0, 26.0     # ESP32-C3 dev board footprint (DevKitM-1 is about 55 x 26)
BUCK_LEN, BUCK_WID = 25.0, 20.0 # buck + TVS + input caps area
COMP_H = 14.0                   # tallest part above the PCB (headers / electrolytic)

# ---- Box settings ------------------------------------------------------
WALL, FLOOR, LID_T = 2.4, 2.0, 2.4
GAP = 4.0                       # clearance board <-> wall
STANDOFF = 3.0                  # board lift off the floor
POST_D, SCREW_D = 7.0, 3.0      # corner posts, M3 self-tapping
TOL = 0.3                       # lid lip clearance
USB_W, USB_H = 10.0, 4.0        # USB-C slot on the -X end wall
WIRE_HOLE = 8.0                 # square wire holes on the +X end wall (use grommets / strain relief)

IN_LEN = C3_LEN + BUCK_LEN + 3 * GAP
IN_WID = max(C3_WID, BUCK_WID) + 2 * GAP
IN_HGT = STANDOFF + COMP_H + 3
OUT_LEN, OUT_WID = IN_LEN + 2 * WALL, IN_WID + 2 * WALL
OUT_HGT = IN_HGT + FLOOR


def mm(v):
    return v / 10.0


def prism(comp, x0, y0, x1, y1, z0, z1, op, y_shift=0.0):
    """Extrude an axis-aligned box from z0 to z1 (mm) using a rectangle on an offset XY plane."""
    planes = comp.constructionPlanes
    pin = planes.createInput()
    pin.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(mm(z0)))
    sk = comp.sketches.add(planes.add(pin))
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(mm(x0), mm(y0 + y_shift), 0),
        adsk.core.Point3D.create(mm(x1), mm(y1 + y_shift), 0))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def cylinder(comp, cx, cy, d, z0, z1, op, y_shift=0.0):
    planes = comp.constructionPlanes
    pin = planes.createInput()
    pin.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(mm(z0)))
    sk = comp.sketches.add(planes.add(pin))
    sk.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(cx), mm(cy + y_shift), 0), mm(d / 2))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def extrude(comp, profile, dist_mm, op):
    inp = comp.features.extrudeFeatures.createInput(profile, op)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(dist_mm)))
    return comp.features.extrudeFeatures.add(inp)


def build_base(comp):
    NEW, JOIN, CUT = (adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation,
                      adsk.fusion.FeatureOperations.CutFeatureOperation)
    mid_y = OUT_WID / 2

    prism(comp, 0, 0, OUT_LEN, OUT_WID, 0, OUT_HGT, NEW)                         # outer shell
    prism(comp, WALL, WALL, WALL + IN_LEN, WALL + IN_WID, FLOOR, OUT_HGT + 1, CUT)  # cavity

    # corner posts, then screw holes
    p = POST_D / 2
    corners = [(x, y) for x in (WALL + p, OUT_LEN - WALL - p) for y in (WALL + p, OUT_WID - WALL - p)]
    for x, y in corners:
        cylinder(comp, x, y, POST_D, FLOOR - 0.1, OUT_HGT - LID_T, JOIN)
    for x, y in corners:
        cylinder(comp, x, y, SCREW_D, OUT_HGT - LID_T - 8, OUT_HGT, CUT)

    # C3 rails and buck pads
    for dy in (-C3_WID / 2 + 2, C3_WID / 2 - 2):
        prism(comp, WALL + GAP, mid_y + dy - 1, WALL + GAP + C3_LEN, mid_y + dy + 1,
              FLOOR - 0.1, FLOOR + STANDOFF, JOIN)
    bx = WALL + C3_LEN + 2 * GAP
    for x in (bx, bx + BUCK_LEN - 3):
        for y in (mid_y - BUCK_WID / 2, mid_y + BUCK_WID / 2 - 3):
            prism(comp, x, y, x + 3, y + 3, FLOOR - 0.1, FLOOR + STANDOFF, JOIN)

    # USB-C slot (-X wall) and two wire holes (+X wall)
    prism(comp, -1, mid_y - USB_W / 2, WALL + 1, mid_y + USB_W / 2,
          FLOOR + STANDOFF + 1, FLOOR + STANDOFF + 1 + USB_H, CUT)
    for dy in (-7, 7):
        prism(comp, OUT_LEN - WALL - 1, mid_y + dy - WIRE_HOLE / 2, OUT_LEN + 1, mid_y + dy + WIRE_HOLE / 2,
              FLOOR + IN_HGT / 2 - WIRE_HOLE / 2, FLOOR + IN_HGT / 2 + WIRE_HOLE / 2, CUT)

    # floor vents under the buck
    for i in range(4):
        x = WALL + C3_LEN + 2 * GAP + 3 + i * 6
        prism(comp, x, mid_y - 6, x + 2.5, mid_y + 6, -1, FLOOR + 1, CUT)


def build_lid(comp):
    NEW, JOIN, CUT = (adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                      adsk.fusion.FeatureOperations.JoinFeatureOperation,
                      adsk.fusion.FeatureOperations.CutFeatureOperation)
    ys = OUT_WID + 10   # lay the lid next to the base

    prism(comp, 0, 0, OUT_LEN, OUT_WID, 0, LID_T, NEW, ys)

    # locating lip: four thin walls just inside the box opening
    x0, y0 = WALL + TOL, WALL + TOL
    x1, y1 = WALL + IN_LEN - TOL, WALL + IN_WID - TOL
    t = 2.0
    for (a, b, c, d) in [(x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1)]:
        prism(comp, a, b, c, d, LID_T - 0.1, LID_T + 2, JOIN, ys)

    p = POST_D / 2
    for x in (WALL + p, OUT_LEN - WALL - p):
        for y in (WALL + p, OUT_WID - WALL - p):
            cylinder(comp, x, y, SCREW_D + 0.6, -1, LID_T + 3, CUT, ys)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Open or create a Fusion design first.')
            return
        comp = design.rootComponent
        build_base(comp)
        build_lid(comp)
        ui.messageBox('Bridge box created.\nOuter size: %.1f x %.1f x %.1f mm (+ %.1f mm lid)'
                      % (OUT_LEN, OUT_WID, OUT_HGT, LID_T))
    except Exception:
        if ui:
            ui.messageBox('Failed:\n' + traceback.format_exc())
