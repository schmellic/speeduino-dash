"""Fusion script: under-dash pod for the dash (2.1" round tach, 2.8" info screen, dash ESP32 perfboard).

Two printed parts: the shell (face plate, walls, four lid posts, screen pockets, two mounting ears) and the rear lid
(carries the 50 x 70 mm dash perfboard on four standoffs). Print the shell face-down and the lid plate-down, no supports.
Frame (shell): the face is the XY plane at z=0 and the inside is +Z. The driver looks along +Z, so the driver's left is +X:
the tach is on the driver's left, the info screen on the right. The top of the pod is +Y (the ears are on top, to screw up into
the dash lip). The lid is laid out beside the shell, mirrored in X (as it will be after it is flipped onto the back).
Values marked ASSUMED are not measured yet: check them with calipers (see PROJECT_NOTES.md).
Install: copy this folder into Fusion's API/Scripts directory. All values are millimetres (the API uses cm, see mm()).
"""
import traceback
import adsk.core
import adsk.fusion

# ---- Screens ------------------------------------------------------------
TACH_W, TACH_H = 59.24, 67.47     # round tach PCB (header tail at the bottom)
TACH_C_FROM_TOP = TACH_W / 2      # ASSUMED: circle centre from the PCB's top edge
TACH_WIN_D = 53.4                 # opening (active area is 52.9)
INFO_L, INFO_H = 86.0, 50.0       # 2.8" ILI9341 PCB, header end on the outer (info) side
INFO_ACTIVE_FROM_FAR = 34.6       # ASSUMED: active-area centre from the PCB end nearest the tach
INFO_WIN_W, INFO_WIN_H = 59.6, 45.0   # opening (active area is 57.6 x 43.2): ASSUMED offsets
GLASS_H, PCB_T = 2.5, 1.6         # ASSUMED glass height above the PCB, PCB thickness
POCKET_CLR, POCKET_WALL = 0.25, 1.2   # locating wall round each PCB
# ---- Dash perfboard (50 x 70 mm, measured from the photo) ---------------
BOARD_L, BOARD_W = 70.0, 50.0     # along X, along Y
BOARD_HOLE_INSET = 2.5            # ASSUMED corner hole inset
STANDOFF, STANDOFF_D, PILOT_D = 4.0, 5.6, 1.9   # M2 machine screws cut their own thread in 1.9 mm
BOARD_END_GAP = 3.0               # board end to the -X end wall (USB-C and terminal face this wall)
USB_Y, USB_Z = -4.7, 5.5          # USB-C centre: across from the board centre; ASSUMED height above the perfboard
USB_SLOT_W, USB_SLOT_H = 14.0, 8.0
TERM_Y, TERM_Z = 19.8, 4.5        # 3-way terminal centre across the board; entry height above the board
TERM_SLOT_W, TERM_SLOT_H = 19.0, 9.0
# ---- Shell --------------------------------------------------------------
FACE_T, WALL, LID_T = 2.5, 2.4, 2.5
INNER_D = 40.0                    # depth behind the face plate (headers + wires + perfboard parts)
IH = 73.0                         # inside height
POST_D, LID_PILOT_D, LID_HOLE_D, POST_PILOT_DEPTH = 7.0, 2.8, 3.4, 12.0   # M3 machine screws
SEAM = 6.0                        # gap between the two PCBs
LIP_TOL, LIP_T, LIP_H = 0.2, 1.6, 2.0
EAR_L, EAR_T, EAR_Z0, EAR_Z1 = 16.0, 4.0, 6.0, 32.0   # mounting ears on the top, flush with it
EAR_SLOT_W, EAR_SLOT_Z0, EAR_SLOT_Z1 = 4.5, 13.0, 25.0   # screws up into the dash lip (slot along Z)

# ---- Derived layout -----------------------------------------------------
MARGIN_T = POST_D + 1.0           # outer end beside the tach, so its tail clears the corner posts
IW = MARGIN_T + TACH_W + SEAM + INFO_L + 1.5
OW, OH = IW + 2 * WALL, IH + 2 * WALL
Z_TOP = FACE_T + INNER_D
TACH_CX = IW / 2 - MARGIN_T - TACH_W / 2
INFO_XMAX = TACH_CX - TACH_W / 2 - SEAM
INFO_CX = INFO_XMAX - INFO_L / 2
INFO_WIN_CX = INFO_XMAX - INFO_ACTIVE_FROM_FAR
YC = (TACH_H - TACH_C_FROM_TOP) - (IH / 2 - 1.5)     # circle / info window centre height
TACH_PCB_CY = YC + (TACH_C_FROM_TOP - (TACH_H - TACH_C_FROM_TOP)) / 2
BOARD_CX = -IW / 2 + BOARD_END_GAP + BOARD_L / 2
XOFF = OW + 15.0                  # lid layout offset (lid_x = XOFF - x)

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


def prism(comp, x0, y0, x1, y1, z0, z1, op):
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(mm(x0), mm(y0), 0), adsk.core.Point3D.create(mm(x1), mm(y1), 0))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def cyl(comp, cx, cy, d, z0, z1, op):
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(mm(cx), mm(cy), 0), mm(d / 2))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def ring(comp, cx, cy, w, h, z0, z1, op):
    """Four overlapping strips forming a rectangular locating wall round a w x h PCB."""
    a, t = POCKET_CLR, POCKET_WALL
    x0, x1, y0, y1 = cx - w / 2 - a, cx + w / 2 + a, cy - h / 2 - a, cy + h / 2 + a
    for (p, q, r, s) in [(x0 - t, y0 - t, x1 + t, y0), (x0 - t, y1, x1 + t, y1 + t),
                         (x0 - t, y0, x0, y1), (x1, y0, x1 + t, y1)]:
        prism(comp, p, q, r, s, z0, z1, op)


def corners():
    return [(sx * (IW / 2 - POST_D / 2), sy * (IH / 2 - POST_D / 2)) for sx in (-1, 1) for sy in (-1, 1)]


def build_shell(comp):
    prism(comp, -OW / 2, -OH / 2, OW / 2, OH / 2, 0, Z_TOP, NEW)
    prism(comp, -IW / 2, -IH / 2, IW / 2, IH / 2, FACE_T, Z_TOP + 1, CUT)
    for x, y in corners():
        cyl(comp, x, y, POST_D, FACE_T - 0.1, Z_TOP, JOIN)
    for x, y in corners():
        cyl(comp, x, y, LID_PILOT_D, Z_TOP - POST_PILOT_DEPTH, Z_TOP + 1, CUT)
    # screen pockets (locating walls) and openings
    ph = GLASS_H + PCB_T
    ring(comp, TACH_CX, TACH_PCB_CY, TACH_W, TACH_H, FACE_T - 0.1, FACE_T + ph, JOIN)
    ring(comp, INFO_CX, YC, INFO_L, INFO_H, FACE_T - 0.1, FACE_T + ph, JOIN)
    cyl(comp, TACH_CX, YC, TACH_WIN_D, -1, FACE_T + 0.1, CUT)
    prism(comp, INFO_WIN_CX - INFO_WIN_W / 2, YC - INFO_WIN_H / 2, INFO_WIN_CX + INFO_WIN_W / 2,
          YC + INFO_WIN_H / 2, -1, FACE_T + 0.1, CUT)
    # mounting ears: plates on the top corners with a vertical screw slot (built from four pieces)
    for s in (-1, 1):
        a = s * (OW / 2 - 0.5)
        b = s * (OW / 2 + EAR_L)
        c0, c1 = s * (OW / 2 + EAR_L / 2 - EAR_SLOT_W / 2), s * (OW / 2 + EAR_L / 2 + EAR_SLOT_W / 2)
        y0, y1 = OH / 2 - EAR_T, OH / 2
        for (xa, xb, za, zb) in [(a, b, EAR_Z0, EAR_SLOT_Z0), (a, b, EAR_SLOT_Z1, EAR_Z1),
                                 (a, c0, EAR_SLOT_Z0, EAR_SLOT_Z1), (c1, b, EAR_SLOT_Z0, EAR_SLOT_Z1)]:
            prism(comp, min(xa, xb), y0, max(xa, xb), y1, za, zb, JOIN)
    # USB-C and terminal windows in the -X end wall, at the board's height
    zb = Z_TOP - (STANDOFF + PCB_T)
    for y, w, zc, h in [(USB_Y, USB_SLOT_W, USB_Z, USB_SLOT_H), (TERM_Y, TERM_SLOT_W, TERM_Z, TERM_SLOT_H)]:
        z = zb - zc
        prism(comp, -OW / 2 - 1, y - w / 2, -IW / 2 + 0.01, y + w / 2, z - h / 2, z + h / 2, CUT)


def build_lid(comp):
    lx = lambda x: XOFF - x
    prism(comp, lx(OW / 2), -OH / 2, lx(-OW / 2), OH / 2, 0, LID_T, NEW)
    xo, yo = IW / 2 - LIP_TOL, IH / 2 - LIP_TOL
    xs, ys = IW / 2 - POST_D - 0.4, IH / 2 - POST_D - 0.4
    for (x0, y0, x1, y1) in [(-xs, yo - LIP_T, xs, yo), (-xs, -yo, xs, -yo + LIP_T),
                             (xo - LIP_T, -ys, xo, ys), (-xo, -ys, -xo + LIP_T, ys)]:
        prism(comp, lx(x1), y0, lx(x0), y1, LID_T - 0.1, LID_T + LIP_H, JOIN)
    for x in (BOARD_CX - BOARD_L / 2 + BOARD_HOLE_INSET, BOARD_CX + BOARD_L / 2 - BOARD_HOLE_INSET):
        for y in (-BOARD_W / 2 + BOARD_HOLE_INSET, BOARD_W / 2 - BOARD_HOLE_INSET):
            cyl(comp, lx(x), y, STANDOFF_D, LID_T - 0.1, LID_T + STANDOFF, JOIN)
    for x in (BOARD_CX - BOARD_L / 2 + BOARD_HOLE_INSET, BOARD_CX + BOARD_L / 2 - BOARD_HOLE_INSET):
        for y in (-BOARD_W / 2 + BOARD_HOLE_INSET, BOARD_W / 2 - BOARD_HOLE_INSET):
            cyl(comp, lx(x), y, PILOT_D, LID_T + STANDOFF - 6, LID_T + STANDOFF + 1, CUT)
    for x, y in corners():
        cyl(comp, lx(x), y, LID_HOLE_D, -1, LID_T + 1, CUT)


def build_all():
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    build_shell(comp)
    build_lid(comp)
    lines = ['Shell %.1f x %.1f x %.1f mm (+ ears), lid %.1f mm' % (OW, OH, Z_TOP, LID_T)]
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
