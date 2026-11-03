"""Fusion script: fit-and-forget enclosure for the bridge board (40 x 60 mm perfboard with the ESP32-C3 SuperMini,
12V->5V buck, 1k/2k divider and two screw terminals).

The board sits on four standoffs; no access to the USB-C port or the screw terminals is provided (the lid screws on and
stays on). Wires leave through two square holes in the +X end wall. Two bodies are made: the base and the lid (laid out
beside it, with a locating lip and screw holes).

Install: copy this folder into Fusion's API/Scripts directory, then Utilities > Scripts and Add-ins > BridgeBox > Run.
All values are millimetres; the Fusion API works in cm, so mm() converts. Edit the constants to match your board.
"""
import traceback
import adsk.core
import adsk.fusion

# ---- Board (mm): MEASURE the height, check the corner holes -----------
BOARD_LEN, BOARD_WID, BOARD_T = 60.0, 40.0, 1.6
COMP_H = 14.0            # tallest part above the board (C3 headers / terminals / buck cap): MEASURE
STANDOFF = 5.0           # board lift off the floor (clears the solder side)
STANDOFF_D = 6.0
PILOT_D = 1.8            # pilot hole for an M2 self-tapping screw (needs a hole near each board corner)
HOLE_INSET = 3.5         # corner standoff centre, in from the board edges

# ---- Box ---------------------------------------------------------------
WALL, FLOOR, LID_T = 2.4, 2.0, 2.4
SIDE_GAP = 2.0           # clearance board <-> side walls
WIRE_GAP = 8.0           # extra room at the +X end for wires to turn
POST_D, SCREW_D = 7.0, 3.0   # corner lid posts, M3 self-tapping
TOL = 0.3                # lid lip clearance
WIRE_HOLE = 8.0          # square wire holes in the +X end wall (use grommets / strain relief)
WIRE_DY = 7.0            # wire hole offset from the centreline

BOARD_X0 = WALL + POST_D + 1                      # board clears the lid posts at the -X end
IN_LEN = (POST_D + 1) + BOARD_LEN + WIRE_GAP + 1
IN_WID = BOARD_WID + 2 * SIDE_GAP
IN_HGT = STANDOFF + BOARD_T + COMP_H + 2
OUT_LEN, OUT_WID = IN_LEN + 2 * WALL, IN_WID + 2 * WALL
OUT_HGT = IN_HGT + FLOOR

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def mm(v):
    return v / 10.0


def extrude(comp, profile, dist_mm, op):
    inp = comp.features.extrudeFeatures.createInput(profile, op)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(dist_mm)))
    return comp.features.extrudeFeatures.add(inp)


def sketch_at(comp, z0):
    planes = comp.constructionPlanes
    pin = planes.createInput()
    pin.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(mm(z0)))
    return comp.sketches.add(planes.add(pin))


def prism(comp, x0, y0, x1, y1, z0, z1, op, ys=0.0):
    """Extrude an axis-aligned box from z0 to z1 (mm)."""
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(mm(x0), mm(y0 + ys), 0), adsk.core.Point3D.create(mm(x1), mm(y1 + ys), 0))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def cyl(comp, cx, cy, d, z0, z1, op, ys=0.0):
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy + ys), 0), mm(d / 2))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def build_base(comp):
    mid_y = OUT_WID / 2
    prism(comp, 0, 0, OUT_LEN, OUT_WID, 0, OUT_HGT, NEW)                              # outer shell
    prism(comp, WALL, WALL, WALL + IN_LEN, WALL + IN_WID, FLOOR, OUT_HGT + 1, CUT)    # cavity

    # lid screw posts in the four corners, then their screw holes
    p = POST_D / 2
    corners = [(x, y) for x in (WALL + p, OUT_LEN - WALL - p) for y in (WALL + p, OUT_WID - WALL - p)]
    for x, y in corners:
        cyl(comp, x, y, POST_D, FLOOR - 0.1, OUT_HGT - LID_T, JOIN)
    for x, y in corners:
        cyl(comp, x, y, SCREW_D, OUT_HGT - LID_T - 8, OUT_HGT, CUT)

    # board standoffs (one near each board corner) with M2 pilot holes
    by0 = WALL + SIDE_GAP
    for x in (BOARD_X0 + HOLE_INSET, BOARD_X0 + BOARD_LEN - HOLE_INSET):
        for y in (by0 + HOLE_INSET, by0 + BOARD_WID - HOLE_INSET):
            cyl(comp, x, y, STANDOFF_D, FLOOR - 0.1, FLOOR + STANDOFF, JOIN)
            cyl(comp, x, y, PILOT_D, FLOOR + STANDOFF - 6, FLOOR + STANDOFF, CUT)

    # two wire holes on the +X end wall (12 V in, ECU serial out)
    zc = FLOOR + STANDOFF + BOARD_T + 4
    for dy in (-WIRE_DY, WIRE_DY):
        prism(comp, OUT_LEN - WALL - 1, mid_y + dy - WIRE_HOLE / 2, OUT_LEN + 1, mid_y + dy + WIRE_HOLE / 2,
              zc - WIRE_HOLE / 2, zc + WIRE_HOLE / 2, CUT)


def build_lid(comp):
    ys = OUT_WID + 10   # lay the lid next to the base
    prism(comp, 0, 0, OUT_LEN, OUT_WID, 0, LID_T, NEW, ys)
    x0, y0 = WALL + TOL, WALL + TOL
    x1, y1 = WALL + IN_LEN - TOL, WALL + IN_WID - TOL
    t = 2.0
    for (a, b, c, d) in [(x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1)]:
        prism(comp, a, b, c, d, LID_T - 0.1, LID_T + 2, JOIN, ys)
    p = POST_D / 2
    for x in (WALL + p, OUT_LEN - WALL - p):
        for y in (WALL + p, OUT_WID - WALL - p):
            cyl(comp, x, y, SCREW_D + 0.6, -1, LID_T + 3, CUT, ys)


def build_all():
    """Create a new design and build both parts (no exception handling, so callers see failures)."""
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    build_base(comp)
    build_lid(comp)
    lines = ['Outer size: %.1f x %.1f x %.1f mm (+ %.1f mm lid)' % (OUT_LEN, OUT_WID, OUT_HGT, LID_T)]
    for b in comp.bRepBodies:
        bb = b.boundingBox
        lines.append('%s %.1f x %.1f x %.1f mm' % (b.name, (bb.maxPoint.x - bb.minPoint.x) * 10,
                                                   (bb.maxPoint.y - bb.minPoint.y) * 10,
                                                   (bb.maxPoint.z - bb.minPoint.z) * 10))
    return '\n'.join(lines)


def run(context):
    ui = None
    try:
        ui = adsk.core.Application.get().userInterface
        ui.messageBox(build_all())
    except Exception:
        if ui:
            ui.messageBox('Failed:\n' + traceback.format_exc())
