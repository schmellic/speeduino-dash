"""Fusion script: under-dash pod for the dash (2.1" round tach, 2.8" info screen, dash ESP32 perfboard).

Shaped like a curved hull under the dash: the sides curve in from the wing tips to a slightly bowed bottom, a rounded front
edge, and a flat top that ends where the dash underside steps down (DEPTH).
Two printed parts: the shell (face plate, walls, lid posts, screen pockets, screen screw posts) and the rear lid (carries the
50 x 70 mm dash perfboard on four standoffs). Print the shell face-down and the lid plate-down, no supports.
Frame (shell): the face is the XY plane at z=0 and the inside is +Z. The driver looks along +Z, so the driver's left is +X:
the tach is on the driver's left, the info screen on the right. The top of the pod is +Y. The lid is laid out beside the shell,
mirrored in X (as it will be after it is flipped onto the back).
Values marked ASSUMED are not measured yet: check them with calipers (see PROJECT_NOTES.md).
Install: copy this folder into Fusion's API/Scripts directory. All values are millimetres (the API uses cm, see mm()).
"""
import math
import traceback
import adsk.core
import adsk.fusion

# ---- Screens ------------------------------------------------------------
TACH_W, TACH_H = 59.24, 67.47     # round tach PCB (header tail at the bottom)
TACH_TAIL_W = 30.5                # width of the narrow tail with the header pins (measured by the user)
TACH_C_FROM_TOP = TACH_W / 2      # ASSUMED: circle centre from the PCB's top edge
TACH_WIN_D = 53.4                 # opening (active area is 52.9)
INFO_L, INFO_H = 81.6, 50.0       # 2.8" ILI9341 PCB, measured by the user (the listing said 86), header end on the outer (info) side
INFO_ACTIVE_FROM_FAR = 37.8       # measured (user): lit area runs 9 mm from the tach-side end to 15 mm from the header end of the 81.6 mm board, so it is 57.6 wide (the datasheet active area) and its centre is 37.8 mm from the tach-side end; centred in height
INFO_WIN_W, INFO_WIN_H = 59.6, 45.0   # opening (active area is 57.6 x 43.2): ASSUMED offsets
TACH_HOLE_UP, TACH_HOLE_SPAN = 8.0, 23.88   # tach mounting holes: 8 mm up from the header end (measured), 23.88 mm apart; ASSUMED centred across the width
SCREEN_POST_D, SCREEN_PILOT_D, SCREEN_PILOT_DEPTH = 5.0, 1.9, 3.2   # M2 x 4 mm machine screws from behind into posts on the face plate
INFO_HOLE_INSET, INFO_POST_D, INFO_PILOT_D = 3.0, 4.6, 2.1   # info screen: four 3 mm holes, 3 mm in from each edge (measured); M2.5 x 4 screws, 2.1 mm pilot
GLASS_H, PCB_T = 2.3, 1.3         # tach: measured, PCB + glass 3.6 mm, PCB 1.3 mm
INFO_GLASS_H, INFO_PCB_T = 3.0, 1.6   # info: measured, PCB + glass 4.6 mm, PCB 1.6 mm
PERF_T = 1.6                      # dash perfboard thickness (assumed)
POCKET_CLR, POCKET_WALL = 0.25, 1.2   # locating wall round each PCB
# ---- Dash perfboard (50 x 70 mm, measured from the photo) ---------------
BOARD_L, BOARD_W = 70.0, 50.0     # along X, along Y
BOARD_HOLE_INSET = 2.0            # measured by the user (2026-11-23)
STANDOFF, STANDOFF_D, PILOT_D = 4.0, 5.6, 1.9   # M2 machine screws cut their own thread in 1.9 mm
WIRE_HOLE_D, WIRE_HOLE_X, WIRE_HOLE_Y = 8.0, 50.0, 10.0   # round cable hole in the lid, below the dash step (wires leave behind the pod), door side of the perfboard (x is the shell's x)
USB_Y, USB_Z = -4.7, 5.5          # USB-C centre: across from the board centre; ASSUMED height above the perfboard
USB_SLOT_W, USB_SLOT_H = 14.0, 8.0
TERM_Y, TERM_Z = 19.8, 4.5        # 3-way terminal centre across the board; entry height above the board
TERM_SLOT_W, TERM_SLOT_H = 19.0, 9.0
# ---- Shell --------------------------------------------------------------
FACE_T, WALL, LID_T = 2.5, 2.4, 2.5
SCREEN_REAR_H = 3.0               # ASSUMED: solder joints / SD slot behind the screen PCBs
DEPTH = 45.0                      # overall, face to back of lid: the dash is flat this far back, then steps down 11 mm (user's gauge)
BOARD_COMP_H = 22.0               # room kept for the tallest thing on the perfboard (user: 22 is plenty, 20 probably enough)
IH = 71.0                         # inside height: the tach PCB (67.5) plus its pocket wall (1.45 each side) sets the minimum, 70.4
POST_D, LID_PILOT_D, LID_HOLE_D, POST_PILOT_DEPTH = 7.0, 2.8, 3.4, 12.0   # M3 machine screws
SEAM = 12.0                       # gap between the two PCBs (the two middle lid posts sit in it)
LIP_TOL, LIP_T, LIP_H = 0.2, 1.6, 2.0
FLOOR_CLR = 0.5                    # gap between the lid's lip and standoffs and the shell floor

# ---- Shape --------------------------------------------------------------
PITCH, YAW = 0.0, 0.0            # degrees: the face plate tips up (bottom toward the driver) and turns to face the driver, who sits to the LEFT of the pod (LHD): the right-hand (info) end comes toward the driver; pivot is the top edge at the tach end
TILT = 0.0                       # degrees: the top plane rises this much per mm of depth, so the face tips up toward the driver
WIDEN = 23.5                      # extra on each side to match the dash: 250 mm tip to tip, measured with the sliding template (2026-11-26)
WING_RISE, WING_X0, WING_X1, WING_R = 22.74, 67.4 + WIDEN, 94.5 + WIDEN, 20.0   # 40 deg wing (test piece fit, 2026-11-23), flattening 1.5 mm early so the 3 mm front round fits at the tips
RIV_D, RIV_X, RIV_Z0, RIV_Z1 = 4.5, 50.0, 16.0, 34.0   # roof bolt slots for rivnuts in the dash lip (M4 clearance, x each side, along the depth): ASSUMED, check against the dash
TIP_X = 125.0                     # half width at the wing tips (250 mm, measured)
BOT_X = 66.0                      # the bottom is full depth out to here, then the side curves up
BOW = 2.1                         # how far the middle of the bottom hangs below its ends
SIDE_C1_X, SIDE_C2 = 82.0, (86.0, 0.0)   # control points of the side curve, from (BOT_X, bottom) to the wing tip
R_FACE = 3.0                      # rounded front edge (not on the top edge)
BACK_R = 2.0                      # slight round on the lid's rear top edge, where the dash curves at the step
LID_POST_Y, LID_POST_X, LID_POST_OUT = 20.0, 43.0, 86.0   # screw heads sit below the dash step; the middle pair stands clear of the perfboard
SWEEP_START = 14.0                # depth where the underside starts to curve up
SWEEP_RISE = 16.0                 # how far the underside has risen by the lid
BOARD_CY = 5.0                    # perfboard centre height (the lid is shorter than the face, so it sits high)

# ---- Derived layout -----------------------------------------------------
H = IH + 2 * WALL
YB = -H / 2
Z_TOP = DEPTH - LID_T                                                      # face to lid seat
# what is left for the wires between the back of the screens and the parts on the perfboard
WIRE_GAP = Z_TOP - (FACE_T + max(GLASS_H + PCB_T, INFO_GLASS_H + INFO_PCB_T) + SCREEN_REAR_H + STANDOFF + PERF_T + BOARD_COMP_H)
assert WIRE_GAP >= 4.0, 'too little room behind the screens'
TAN_T = math.tan(math.radians(TILT))
PIV_X, PIV_Y = (TACH_W + SEAM + INFO_L) / 2, H / 2      # tilt pivot: top edge, tach end (nearest the driver in a LHD car)


def tilt_pt(x, y, z):
    """Where a point of the flat face frame ends up after the pitch (about X) then the yaw (about Y)."""
    rx, ry, rz = x - PIV_X, y - PIV_Y, z
    a, b = math.radians(PITCH), -math.radians(YAW)
    y1, z1 = ry * math.cos(a) - rz * math.sin(a), ry * math.sin(a) + rz * math.cos(a)
    return (PIV_X + rx * math.cos(b) + z1 * math.sin(b), PIV_Y + y1, -rx * math.sin(b) + z1 * math.cos(b))

LW = TACH_W + SEAM + INFO_L
TACH_CX = LW / 2 - TACH_W / 2
INFO_XMIN, INFO_XMAX = -LW / 2, -LW / 2 + INFO_L
INFO_CX = (INFO_XMIN + INFO_XMAX) / 2
INFO_WIN_CX = INFO_XMAX - INFO_ACTIVE_FROM_FAR
SEAM_X = (INFO_XMAX + TACH_CX - TACH_W / 2) / 2
YC = (TACH_H - TACH_C_FROM_TOP) - (IH / 2 - 1.5)     # circle / info window centre height
TACH_PCB_CY = YC + (TACH_C_FROM_TOP - (TACH_H - TACH_C_FROM_TOP)) / 2
Y_EXT = H / 2 + WING_RISE                            # top of the end wings
PY = IH / 2 - POST_D / 2
POST_Z0 = FACE_T + max(GLASS_H + PCB_T, INFO_GLASS_H + INFO_PCB_T) + 0.5             # posts start behind the screens and hang from the ceiling
POSTS = [(x, LID_POST_Y) for x in (-LID_POST_OUT, -LID_POST_X, LID_POST_X, LID_POST_OUT)]
# underside sweep: a circular arc, tangent to the flat bottom at SWEEP_START, rising SWEEP_RISE by the lid
_L = Z_TOP - SWEEP_START
YBL = YB - BOW                       # lowest point of the face: the sweep starts here
_RISE = SWEEP_RISE + BOW
SW_R = (_L ** 2 + _RISE ** 2) / (2 * _RISE)
SW_CY = YBL + SW_R
SW_PHI = math.asin(_L / SW_R)


def sweep_pt(r, a):
    """Point (y, z) on the sweep circle of radius r at angle a from straight down."""
    return (SW_CY - r * math.cos(a), SWEEP_START + r * math.sin(a))


Y_BOT_OUT = sweep_pt(SW_R, SW_PHI)[0]                # outer underside height at the lid
Y_BOT_IN = sweep_pt(SW_R - WALL, SW_PHI)[0]          # inner floor height at the lid
XOFF = 0.0




NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
INTERSECT = adsk.fusion.FeatureOperations.IntersectFeatureOperation


def y_plane(z):
    """Height of the sloped top plane at depth z."""
    return H / 2 + z * TAN_T


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _corner(p, c, n, r):
    if r <= 0:
        return c, c, None
    d1, d2 = _unit((p[0] - c[0], p[1] - c[1])), _unit((n[0] - c[0], n[1] - c[1]))
    phi = math.acos(max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1])))
    td = r / math.tan(phi / 2)
    bis = _unit((d1[0] + d2[0], d1[1] + d2[1]))
    ctr = (c[0] + bis[0] * r / math.sin(phi / 2), c[1] + bis[1] * r / math.sin(phi / 2))
    return ((c[0] + d1[0] * td, c[1] + d1[1] * td), (c[0] + d2[0] * td, c[1] + d2[1] * td),
            (ctr[0] - bis[0] * r, ctr[1] - bis[1] * r))


def rounded(V, R):
    n = len(V)
    return [_corner(V[i - 1], V[i], V[(i + 1) % n], R[i]) for i in range(n)]


def _bez(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def lower_curve(t=0.0, top=None):
    """The curved lower boundary of the face, left to right: from the left side, round the bowed bottom, up the right side.
    t offsets it inward; it stops at height `top` (the wing tips if not given)."""
    yw = H / 2 + WING_RISE
    right = _bez((0.0, YB - BOW), (30.0, YB - BOW), (48.0, YB), (BOT_X, YB), 24)
    right += _bez((BOT_X, YB), (SIDE_C1_X, YB), SIDE_C2, (TIP_X, yw), 48)[1:]
    if t:
        off = []
        for i, (x, y) in enumerate(right):
            a, b = right[max(i - 1, 0)], right[min(i + 1, len(right) - 1)]
            tx, ty = _unit((b[0] - a[0], b[1] - a[1])) if i else (1.0, 0.0)
            off.append((x - ty * t, y + tx * t))
        right = off
    if top is not None:
        for i in range(1, len(right)):
            if right[i][1] >= top > right[i - 1][1]:
                (x0, y0), (x1, y1) = right[i - 1], right[i]
                end = (x0 + (x1 - x0) * (top - y0) / (y1 - y0), top)
                keep = right[:i]
                if math.hypot(end[0] - keep[-1][0], end[1] - keep[-1][1]) < 1.0:
                    keep = keep[:-1]
                right = keep + [end]
                break
    return [(-x, y) for x, y in right[:0:-1]] + right


def clearance(pt, pts):
    """Signed distance from pt to the polygon boundary (positive inside)."""
    inside, best = False, 1e9
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        if (y1 > pt[1]) != (y2 > pt[1]) and pt[0] < (x2 - x1) * (pt[1] - y1) / (y2 - y1) + x1:
            inside = not inside
        dx, dy = x2 - x1, y2 - y1
        u = 0 if dx == dy == 0 else max(0, min(1, ((pt[0] - x1) * dx + (pt[1] - y1) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(pt[0] - x1 - u * dx, pt[1] - y1 - u * dy))
    return best if inside else -best


XOFF = 2 * TIP_X + 15.0
BOARD_CX = 0.0                    # perfboard centred across the pod; its terminal end faces +X (door side)
HW_TOP = TIP_X
ZF = math.ceil(-min(tilt_pt(x, y, 0.0)[2] for x in (-HW_TOP - 10, HW_TOP + 10) for y in (YB, Y_EXT))) + 3 if (PITCH or YAW) else 0   # how far the blank extends in front of z=0 before the tilted face plane trims it


def _check_fit():
    """Every screen pocket corner (and the round part of the tach pocket) must be inside the walls."""
    inner = lower_curve(WALL, H / 2 - WALL)
    g = POCKET_CLR + POCKET_WALL
    r = TACH_W / 2 + g
    pts = [(TACH_CX + r * math.cos(a * math.pi / 45), YC + r * math.sin(a * math.pi / 45)) for a in range(90)]
    pts += [(TACH_CX + s * (TACH_TAIL_W / 2 + g), TACH_PCB_CY - TACH_H / 2 - g) for s in (-1, 1)]
    pts += [(INFO_CX + sx * (INFO_L / 2 + g), YC + sy * (INFO_H / 2 + g)) for sx in (-1, 1) for sy in (-1, 1)]
    return min(clearance(p, inner) for p in pts)


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


def P3(x, y):
    return adsk.core.Point3D.create(mm(x), mm(y), 0)


def _fit_spline(sk, pts, dx, dy):
    col = adsk.core.ObjectCollection.create()
    for x, y in pts:
        col.add(P3(x + dx, y + dy))
    return sk.sketchCurves.sketchFittedSplines.add(col)


def face_body(comp, z0, z1, op=None, dx=0.0, dy=0.0):
    """The outer face outline (curved hull below, flat middle top, a wing at each end) extruded from z0 to z1."""
    sk = sketch_at(comp, z0)
    sp = _fit_spline(sk, lower_curve(), dx, dy)
    T, yw = H / 2, H / 2 + WING_RISE
    V = [(TIP_X, yw), (WING_X1, yw), (WING_X0, T), (-WING_X0, T), (-WING_X1, yw), (-TIP_X, yw)]
    R = [0.0, 2.5, WING_R, WING_R, 2.5, 0.0]
    c = [rounded(V, R)[i] if 0 < i < len(V) - 1 else (V[i], V[i], None) for i in range(len(V))]
    lines, arcs = sk.sketchCurves.sketchLines, sk.sketchCurves.sketchArcs
    prev = sp.endSketchPoint                      # right wing tip
    for i in range(1, len(V)):
        T1, T2, mid = c[i]
        end = sp.startSketchPoint if i == len(V) - 1 else P3(T1[0] + dx, T1[1] + dy)
        ln = lines.addByTwoPoints(prev, end)
        if mid is None:
            continue
        arc = arcs.addByThreePoints(ln.endSketchPoint, P3(mid[0] + dx, mid[1] + dy), P3(T2[0] + dx, T2[1] + dy))
        a, b = arc.startSketchPoint, arc.endSketchPoint      # the arc may store its ends in either order
        here = ln.endSketchPoint.geometry
        prev = a if a.geometry.distanceTo(here) > b.geometry.distanceTo(here) else b
    assert sk.profiles.count == 1, 'face outline: %d profiles' % sk.profiles.count
    return extrude(comp, sk.profiles.item(0), z1 - z0, op if op is not None else NEW)


def inset_body(comp, t, top, z0, z1, dx=0.0):
    """The face outline offset inward by t, cut off flat at height `top`, as a new body."""
    sk = sketch_at(comp, z0)
    sp = _fit_spline(sk, lower_curve(t, top), dx, 0.0)
    sk.sketchCurves.sketchLines.addByTwoPoints(sp.endSketchPoint, sp.startSketchPoint)
    assert sk.profiles.count == 1, 'inset outline: %d profiles' % sk.profiles.count
    return extrude(comp, sk.profiles.item(0), z1 - z0, NEW).bodies.item(0)


def clip_below(comp, body, y, z0, z1):
    """Remove the part of one body below height y."""
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(P3(-2 * XOFF, YB - 60), P3(2 * XOFF, y))
    inp = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), CUT)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(z1 - z0)))
    inp.participantBodies = [body]
    comp.features.extrudeFeatures.add(inp)


def prism(comp, x0, y0, x1, y1, z0, z1, op):
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(P3(x0, y0), P3(x1, y1))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def cyl(comp, cx, cy, d, z0, z1, op):
    sk = sketch_at(comp, z0)
    sk.sketchCurves.sketchCircles.addByCenterRadius(P3(cx, cy), mm(d / 2))
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


def ring(comp, cx, cy, w, h, z0, z1, op):
    a, t = POCKET_CLR, POCKET_WALL
    x0, x1, y0, y1 = cx - w / 2 - a, cx + w / 2 + a, cy - h / 2 - a, cy + h / 2 + a
    for (p, q, r, s) in [(x0 - t, y0 - t, x1 + t, y0), (x0 - t, y1, x1 + t, y1 + t),
                         (x0 - t, y0, x0, y1), (x1, y0, x1 + t, y1)]:
        prism(comp, p, q, r, s, z0, z1, op)


def tach_pocket(comp, z0, z1):
    """Locating wall round the real tach PCB outline: a disc (the round part) plus the narrow tail down to the header end."""
    a, t = POCKET_CLR, POCKET_WALL
    yb = TACH_PCB_CY - TACH_H / 2
    for g in (a + t, ):
        cyl(comp, TACH_CX, YC, TACH_W + 2 * g, z0, z1, JOIN)
        prism(comp, TACH_CX - TACH_TAIL_W / 2 - g, yb - g, TACH_CX + TACH_TAIL_W / 2 + g, YC, z0, z1, JOIN)
    cyl(comp, TACH_CX, YC, TACH_W + 2 * a, FACE_T, z1 + 0.5, CUT)
    prism(comp, TACH_CX - TACH_TAIL_W / 2 - a, yb - a, TACH_CX + TACH_TAIL_W / 2 + a, YC, FACE_T, z1 + 0.5, CUT)


def yz_region(comp, segs, op, bodies=None):
    """Extrude a region drawn in the side (YZ) plane across the whole width. segs: ('L', (y,z), (y,z)) or ('A', p, mid, q)."""
    sk = comp.sketches.add(comp.yZConstructionPlane)
    sp = lambda p: sk.modelToSketchSpace(adsk.core.Point3D.create(0, mm(p[0]), mm(p[1])))
    for sg in segs:
        if sg[0] == 'L':
            sk.sketchCurves.sketchLines.addByTwoPoints(sp(sg[1]), sp(sg[2]))
        else:
            sk.sketchCurves.sketchArcs.addByThreePoints(sp(sg[1]), sp(sg[2]), sp(sg[3]))
    inp = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), op)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(1000)), True)
    if bodies:
        inp.participantBodies = bodies
    return comp.features.extrudeFeatures.add(inp)


def combine(comp, target, tool, op):
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool)
    inp = comp.features.combineFeatures.createInput(target, tools)
    inp.operation = op
    inp.isKeepToolBodies = False
    comp.features.combineFeatures.add(inp)


def cut_top_slope(comp):
    big = H + 200
    a, b = (y_plane(-5), -5), (y_plane(Z_TOP + 5), Z_TOP + 5)
    yz_region(comp, [('L', a, b), ('L', b, (big, Z_TOP + 5)), ('L', (big, Z_TOP + 5), (big, -5)), ('L', (big, -5), a)], CUT)


def cut_underside(comp):
    """Remove everything below the swept underside (flat to SWEEP_START, then the arc up to the lid)."""
    S = sweep_pt(SW_R, 0.0)
    Mp = sweep_pt(SW_R, SW_PHI / 2)
    E = sweep_pt(SW_R, SW_PHI)
    low = YB - 50
    z1 = Z_TOP + 10
    yz_region(comp, [('A', S, Mp, E), ('L', E, (E[0], z1)), ('L', (E[0], z1), (low, z1)),
                     ('L', (low, z1), (low, SWEEP_START)), ('L', (low, SWEEP_START), S)], CUT)


def cavity_body(comp):
    """The inside space: tapered plan inset, floor following the swept underside, ceiling flat at the top."""
    r = SW_R - WALL
    S, Mp, E = sweep_pt(r, 0.0), sweep_pt(r, SW_PHI / 2), sweep_pt(r, SW_PHI)
    top = H / 2 + 50
    za, zb = (-ZF if ZF else FACE_T) - 1.0, Z_TOP + 5
    plan = inset_body(comp, WALL, H / 2 - WALL, -ZF if ZF else FACE_T, Z_TOP + 1)
    prof = yz_region(comp, [('L', (S[0], za), S), ('A', S, Mp, E), ('L', E, (E[0], zb)), ('L', (E[0], zb), (top, zb)),
                            ('L', (top, zb), (top, za)), ('L', (top, za), (S[0], za))], NEW).bodies.item(0)
    combine(comp, plan, prof, INTERSECT)
    return plan


def round_front_edge(comp, body, radius=None):
    """Round every edge of the flat front face (called on the solid blank, before the cavity is cut)."""
    face = None
    for f in body.faces:
        if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
            n = f.geometry.normal
            if abs(abs(n.z) - 1) < 1e-6 and abs(f.boundingBox.minPoint.z) < 1e-6 and abs(f.boundingBox.maxPoint.z) < 1e-6:
                face = f
    edges = adsk.core.ObjectCollection.create()
    for e in face.edges:
        edges.add(e)
    inp = comp.features.filletFeatures.createInput()
    inp.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByReal(mm(radius or R_FACE)), True)
    comp.features.filletFeatures.add(inp)


def half_space(comp, w):
    """A huge block in front of the flat plane z = w (flat frame; tilted later with the face)."""
    return prism(comp, -600, -600, 600, 600, -500, w, NEW).bodies.item(0)


def tilt_bodies(comp, bodies):
    """Rotate bodies about the pivot: pitch about X, then yaw about Y (same order as tilt_pt)."""
    for ang, axis in ((PITCH, (1, 0, 0)), (-YAW, (0, 1, 0))):
        if not ang:
            continue
        m = adsk.core.Matrix3D.create()
        m.setToRotation(math.radians(ang), adsk.core.Vector3D.create(*axis), adsk.core.Point3D.create(mm(PIV_X), mm(PIV_Y), 0))
        col = adsk.core.ObjectCollection.create()
        for b in bodies:
            col.add(b)
        inp = comp.features.moveFeatures.createInput2(col)
        inp.defineAsFreeMove(m)
        comp.features.moveFeatures.add(inp)


def face_parts(comp):
    """Everything that sits on the face plate, built flat (face at z=0) so it can be tilted as one piece: a thin base under
    the pockets, the pocket walls, the screw posts, plus separate tool bodies for the two windows."""
    g = POCKET_CLR + POCKET_WALL
    yb = TACH_PCB_CY - TACH_H / 2
    z0 = 0.5     # starts behind the outer face so it stays inside the shell plate after tilting
    feat = cyl(comp, TACH_CX, YC, TACH_W + 2 * g, z0, FACE_T, NEW).bodies.item(0)
    prism(comp, TACH_CX - TACH_TAIL_W / 2 - g, yb - g, TACH_CX + TACH_TAIL_W / 2 + g, YC, z0, FACE_T, JOIN)
    info = prism(comp, INFO_CX - INFO_L / 2 - g, YC - INFO_H / 2 - g, INFO_CX + INFO_L / 2 + g, YC + INFO_H / 2 + g, z0, FACE_T, NEW).bodies.item(0)   # apart from the tach base
    tach_pocket(comp, FACE_T - 0.1, FACE_T + GLASS_H + PCB_T)
    ring(comp, INFO_CX, YC, INFO_L, INFO_H, FACE_T - 0.1, FACE_T + INFO_GLASS_H + INFO_PCB_T, JOIN)
    # tach screw posts: the PCB rests on them (glass height) and an M2 screw goes through its hole from behind
    thy = TACH_PCB_CY - TACH_H / 2 + TACH_HOLE_UP
    for sx in (-1, 1):
        px = TACH_CX + sx * TACH_HOLE_SPAN / 2
        cyl(comp, px, thy, SCREEN_POST_D, FACE_T - 0.1, FACE_T + GLASS_H, JOIN)
        cyl(comp, px, thy, SCREEN_PILOT_D, FACE_T + GLASS_H - SCREEN_PILOT_DEPTH, FACE_T + GLASS_H + 0.1, CUT)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = INFO_CX + sx * (INFO_L / 2 - INFO_HOLE_INSET), YC + sy * (INFO_H / 2 - INFO_HOLE_INSET)
            cyl(comp, px, py, INFO_POST_D, FACE_T - 0.1, FACE_T + INFO_GLASS_H, JOIN)
            cyl(comp, px, py, INFO_PILOT_D, FACE_T + INFO_GLASS_H - SCREEN_PILOT_DEPTH, FACE_T + INFO_GLASS_H + 0.1, CUT)
    tools = [cyl(comp, TACH_CX, YC, TACH_WIN_D, -1, FACE_T + 0.1, NEW).bodies.item(0),
             prism(comp, INFO_WIN_CX - INFO_WIN_W / 2, YC - INFO_WIN_H / 2, INFO_WIN_CX + INFO_WIN_W / 2,
                   YC + INFO_WIN_H / 2, -1, FACE_T + 0.1, NEW).bodies.item(0)]
    return [feat, info], tools


def roof_slots(comp):
    """Two slots through the roof (the flat top against the dash), along the depth, for bolts up into rivnuts."""
    yc = H / 2 - WALL / 2
    pl = comp.constructionPlanes
    pin = pl.createInput()
    pin.setByOffset(comp.xZConstructionPlane, adsk.core.ValueInput.createByReal(mm(yc)))
    plane = pl.add(pin)
    for sx in (-1, 1):
        sk = comp.sketches.add(plane)
        sp = lambda x, z: sk.modelToSketchSpace(adsk.core.Point3D.create(mm(sx * RIV_X + x), mm(yc), mm(z)))
        r = RIV_D / 2
        sk.sketchCurves.sketchCircles.addByCenterRadius(sp(0, RIV_Z0), mm(r))
        sk.sketchCurves.sketchCircles.addByCenterRadius(sp(0, RIV_Z1), mm(r))
        sk.sketchCurves.sketchLines.addTwoPointRectangle(sp(-r, RIV_Z0), sp(r, RIV_Z1))
        for prof in list(sk.profiles):
            inp = comp.features.extrudeFeatures.createInput(prof, CUT)
            inp.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(WALL + 4)), True)
            comp.features.extrudeFeatures.add(inp)


def lid_post(comp, x, y):
    """Lid screw post hanging from the ceiling, with a 45 deg underside so it prints face-down without support."""
    ceil, lo = H / 2 - WALL, y - POST_D / 2
    body = prism(comp, x - POST_D / 2, lo, x + POST_D / 2, y + POST_D / 2, POST_Z0, Z_TOP, NEW).bodies.item(0)
    web = prism(comp, x - POST_D / 2, y + POST_D / 2 - 0.1, x + POST_D / 2, ceil + 0.6, POST_Z0, Z_TOP, NEW).bodies.item(0)
    combine(comp, body, web, JOIN)      # NEW then combine: a plain join would merge the web into the shell
    z = lambda yy: POST_Z0 + ceil - yy
    a, b = (lo - 1, z(lo - 1)), (ceil + 1, z(ceil + 1))
    yz_region(comp, [('L', a, b), ('L', b, (ceil + 1, -5)), ('L', (ceil + 1, -5), (lo - 1, -5)), ('L', (lo - 1, -5), a)], CUT, [body])
    return body


def build_shell(comp):
    feat, tools = face_parts(comp)
    parts = feat + tools
    cut_out = cut_in = None
    if ZF:
        cut_out, cut_in = half_space(comp, 0.0), half_space(comp, FACE_T)
        parts += [cut_out, cut_in]
    tilt_bodies(comp, parts)
    shell = face_body(comp, -ZF, Z_TOP).bodies.item(0)
    if not ZF:
        try:
            round_front_edge(comp, shell)
        except Exception:
            print('front edge fillet skipped')
    cav = cavity_body(comp)
    if ZF:
        combine(comp, shell, cut_out, CUT)
        combine(comp, cav, cut_in, CUT)
    combine(comp, shell, cav, CUT)
    for f in feat:
        combine(comp, shell, f, JOIN)
    for t in tools:
        combine(comp, shell, t, CUT)
    for x, y in POSTS:
        combine(comp, shell, lid_post(comp, x, y), JOIN)
    if TILT > 0:
        cut_top_slope(comp)
    cut_underside(comp)
    for x, y in POSTS:
        cyl(comp, x, y, LID_PILOT_D, Z_TOP - POST_PILOT_DEPTH, Z_TOP + 1, CUT)
    roof_slots(comp)
def trim_to_floor(comp, lid):
    """Keep the lip and the lower standoffs clear of the shell's swept floor. The cut is level (the floor is highest at the
    lid), so nothing is left overhanging when the lid prints plate-down."""
    clip_below(comp, lid, Y_BOT_IN + FLOOR_CLR, LID_T, LID_T + STANDOFF + 1.0)


def round_back_edge(comp, lid):
    """Slightly round the top edge (flat and wings) of the lid's outer face, which lies at z=0 in the lid layout."""
    edges = adsk.core.ObjectCollection.create()
    for e in lid.edges:
        bb = e.boundingBox
        if abs(bb.minPoint.z) < 1e-5 and abs(bb.maxPoint.z) < 1e-5 and bb.minPoint.y > mm(H / 2) - 1e-5:
            edges.add(e)
    inp = comp.features.filletFeatures.createInput()
    inp.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByReal(mm(BACK_R)), False)
    comp.features.filletFeatures.add(inp)


def build_lid(comp):
    lx = lambda x: XOFF - x
    lid = face_body(comp, 0, LID_T, NEW, XOFF).bodies.item(0)
    clip_below(comp, lid, Y_BOT_OUT, -1.0, LID_T + 1.0)
    round_back_edge(comp, lid)
    # lip: a ring that follows the cavity at the back, notched round the posts
    t0, t1 = WALL + LIP_TOL, WALL + LIP_TOL + LIP_T
    lip = inset_body(comp, t0, H / 2 - t0, LID_T - 0.1, LID_T + LIP_H, XOFF)
    clip_below(comp, lip, Y_BOT_IN + LIP_TOL, LID_T - 1.0, LID_T + LIP_H + 1)
    hole = inset_body(comp, t1, H / 2 - t1, LID_T - 0.1, LID_T + LIP_H, XOFF)
    clip_below(comp, hole, Y_BOT_IN + LIP_TOL + LIP_T, LID_T - 1.0, LID_T + LIP_H + 1)
    combine(comp, lip, hole, CUT)
    combine(comp, lid, lip, JOIN)
    for x, y in POSTS:
        prism(comp, lx(x) - POST_D / 2 - 0.5, y - POST_D / 2 - 0.5, lx(x) + POST_D / 2 + 0.5, H / 2 - WALL,      # post and its web
              LID_T - 0.2, LID_T + LIP_H + 1, CUT)
    hx = (BOARD_CX - BOARD_L / 2 + BOARD_HOLE_INSET, BOARD_CX + BOARD_L / 2 - BOARD_HOLE_INSET)
    hy = (BOARD_CY - BOARD_W / 2 + BOARD_HOLE_INSET, BOARD_CY + BOARD_W / 2 - BOARD_HOLE_INSET)
    for x in hx:
        for y in hy:
            cyl(comp, lx(x), y, STANDOFF_D, LID_T - 0.1, LID_T + STANDOFF, JOIN)
    for x in hx:
        for y in hy:
            cyl(comp, lx(x), y, PILOT_D, LID_T + STANDOFF - 6, LID_T + STANDOFF + 1, CUT)
    for x, y in POSTS:
        cyl(comp, lx(x), y, LID_HOLE_D, -1, LID_T + 1, CUT)
    # cable hole high on the lid but below the dash step, beside the board's door-side end (wires run inside from the terminal)
    cyl(comp, lx(WIRE_HOLE_X), WIRE_HOLE_Y, WIRE_HOLE_D, -1, LID_T + 1, CUT)
    trim_to_floor(comp, lid)


def build_all():
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    build_shell(comp)
    build_lid(comp)
    lines = ['Outer: %.1f mm full-depth bottom, %.1f tip to tip, %.1f high, %.1f deep, lid %.1f mm; sweep R%.0f' % (
        2 * BOT_X, 2 * TIP_X, H + BOW, Z_TOP, LID_T, SW_R)]
    for b in comp.bRepBodies:
        bb = b.boundingBox
        lines.append('%s %.1f x %.1f x %.1f mm' % (b.name, (bb.maxPoint.x - bb.minPoint.x) * 10,
                                                   (bb.maxPoint.y - bb.minPoint.y) * 10,
                                                   (bb.maxPoint.z - bb.minPoint.z) * 10))
    return '\n'.join(lines)


def build_template(band=14.0):
    """A 3 mm full-size cut-out of just the top edge of the face outline (the top `band` mm of the flat middle plus the
    end wings), to hold against the dash lip and check the shape before printing the whole pod."""
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    face_body(comp, 0, 3.0)
    prism(comp, -300, -300, 300, H / 2 - band, -1.0, 4.0, CUT)                 # everything below the band
    prism(comp, -0.75, H / 2 - 6.0, 0.75, H / 2 + 1.0, -1.0, 4.0, CUT)     # centre mark on the top edge
    b = comp.bRepBodies.item(0)
    bb = b.boundingBox
    return 'Template %.1f x %.1f x %.1f mm' % ((bb.maxPoint.x - bb.minPoint.x) * 10, (bb.maxPoint.y - bb.minPoint.y) * 10,
                                              (bb.maxPoint.z - bb.minPoint.z) * 10)


def build_drill_template(drill=6.0, half_w=70.0, plate_t=3.0, lip_h=8.0):
    """Drill guide for the rivnut holes: a flat plate the size of the pod's roof (depth 0 = the face line) with a lip along the
    front edge, and a guide hole where each roof slot is centred (slot centre = middle of RIV_Z0..RIV_Z1). Print it flat (lip up);
    in use the flat side goes against the dash underside with the lip hanging down, lined up exactly where the pod's face will
    sit. `drill` is the rivnut hole size: check the packet (M4 is usually 6.0 mm)."""
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    prism(comp, -half_w, 0, half_w, Z_TOP, 0, plate_t, NEW)                       # plate: x across, y = depth behind the face line
    prism(comp, -half_w, 0, half_w, 3.0, plate_t - 0.1, plate_t + lip_h, JOIN)    # lip along the face line
    prism(comp, -0.75, -1, 0.75, 4, plate_t + lip_h - 3.0, plate_t + lip_h + 1, CUT)   # centre notch
    zc = (RIV_Z0 + RIV_Z1) / 2
    for sx in (-1, 1):
        cyl(comp, sx * RIV_X, zc, drill, -1, plate_t + 1, CUT)
    bb = comp.bRepBodies.item(0).boundingBox
    return 'Template %.1f x %.1f x %.1f mm, holes %.1f mm at x +-%.1f, %.1f mm behind the face line' % (
        (bb.maxPoint.x - bb.minPoint.x) * 10, (bb.maxPoint.y - bb.minPoint.y) * 10, (bb.maxPoint.z - bb.minPoint.z) * 10, drill, RIV_X, zc)


def build_split_template(band=16.0, over=40.0):
    """The top-edge template as two halves that overlap by `over` mm past the centre, to find the right width: slide them apart
    until both wings sit on the dash, tape them, and measure across the outer top corners (the difference from the pod's top
    width at those corners is what to add)."""
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    for sx, dy in ((-1, 0.0), (1, -(WING_RISE + band + 10.0))):
        body = face_body(comp, 0, 3.0, NEW, 0.0, dy).bodies.item(0)
        for x0, x1, y0, y1 in ((-300, 300, -150, H / 2 - band), (over, 300, H / 2 - band - 1, Y_EXT + 1)):
            xa, xb = (x0, x1) if sx < 0 or x0 == -300 else (-x1, -x0)
            tool = prism(comp, xa, y0 + dy, xb, y1 + dy, -1.0, 4.0, NEW).bodies.item(0)
            combine(comp, body, tool, CUT)
    yw = H / 2 + WING_RISE
    corner = TIP_X
    return '%d pieces; width across the outer top corners at the current design: %.1f mm' % (comp.bRepBodies.count, 2 * corner)


def run(context):
    ui = None
    try:
        ui = adsk.core.Application.get().userInterface
        ui.messageBox(build_all())
    except Exception:
        if ui:
            ui.messageBox('Failed:\n' + traceback.format_exc())
