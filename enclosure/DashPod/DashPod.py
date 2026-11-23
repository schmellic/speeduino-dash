"""Fusion script: under-dash pod for the dash (2.1" round tach, 2.8" info screen, dash ESP32 perfboard).

Shaped like a moulded under-dash gauge panel: wider at the top than the bottom (tapered sides), large rounded bottom corners,
a rounded front edge, and a top that is cut flat against the underside of the dash (TILT tips the face up toward the driver).
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
TACH_C_FROM_TOP = TACH_W / 2      # ASSUMED: circle centre from the PCB's top edge
TACH_WIN_D = 53.4                 # opening (active area is 52.9)
INFO_L, INFO_H = 86.0, 50.0       # 2.8" ILI9341 PCB, header end on the outer (info) side
INFO_ACTIVE_FROM_FAR = 34.6       # ASSUMED: active-area centre from the PCB end nearest the tach
INFO_WIN_W, INFO_WIN_H = 59.6, 45.0   # opening (active area is 57.6 x 43.2): ASSUMED offsets
TACH_HOLE_UP, TACH_HOLE_SPAN = 8.0, 23.88   # tach mounting holes: 8 mm up from the header end (measured), 23.88 mm apart; ASSUMED centred across the width
SCREEN_POST_D, SCREEN_PILOT_D, SCREEN_PILOT_DEPTH = 5.0, 1.9, 3.2   # M2 x 4 mm machine screws from behind into posts on the face plate
INFO_HOLE_INSET, INFO_POST_D, INFO_PILOT_D = 3.0, 4.6, 2.1   # info screen: four 3 mm holes, 3 mm in from each edge (measured); M2.5 x 4 screws, 2.1 mm pilot
GLASS_H, PCB_T = 2.5, 1.6         # ASSUMED glass height above the PCB, PCB thickness
POCKET_CLR, POCKET_WALL = 0.25, 1.2   # locating wall round each PCB
# ---- Dash perfboard (50 x 70 mm, measured from the photo) ---------------
BOARD_L, BOARD_W = 70.0, 50.0     # along X, along Y
BOARD_HOLE_INSET = 2.0            # measured by the user (2026-11-23)
STANDOFF, STANDOFF_D, PILOT_D = 4.0, 5.6, 1.9   # M2 machine screws cut their own thread in 1.9 mm
BOARD_END_GAP = 3.0               # board end to the -X end wall (USB-C and terminal face this wall)
USB_Y, USB_Z = -4.7, 5.5          # USB-C centre: across from the board centre; ASSUMED height above the perfboard
USB_SLOT_W, USB_SLOT_H = 14.0, 8.0
TERM_Y, TERM_Z = 19.8, 4.5        # 3-way terminal centre across the board; entry height above the board
TERM_SLOT_W, TERM_SLOT_H = 19.0, 9.0
# ---- Shell --------------------------------------------------------------
FACE_T, WALL, LID_T = 2.5, 2.4, 2.5
SCREEN_REAR_H = 3.0               # ASSUMED: solder joints / SD slot behind the screen PCBs
WIRE_GAP = 8.0                    # slack for the header wires between the screens and the perfboard
BOARD_COMP_H = 22.0               # ASSUMED: tallest thing on the perfboard (headers with Dupont plugs, ESP32 module, terminal)
IH = 74.0                         # inside height
POST_D, LID_PILOT_D, LID_HOLE_D, POST_PILOT_DEPTH = 7.0, 2.8, 3.4, 12.0   # M3 machine screws
SEAM = 12.0                       # gap between the two PCBs (the two middle lid posts sit in it)
LIP_TOL, LIP_T, LIP_H = 0.2, 1.6, 2.0

# ---- Shape --------------------------------------------------------------
TILT = 0.0                       # degrees: the top plane rises this much per mm of depth, so the face tips up toward the driver
SIDE_TAPER = 0.12                 # each side moves in this much per mm of height going down (wider at the top)
R_BOTTOM = 16.0                   # outer radius of the bottom corners
WING_RISE, WING_X0, WING_X1, WING_R = 24.0, 67.4, 96.0, 20.0   # WING_X0 gives a 40 deg wing (test piece fit, 2026-11-23); the top edge curves up at both ends to follow the dash lip
R_FACE = 3.0                      # rounded front edge (not on the top edge)
SWEEP_START = 14.0                # depth where the underside starts to curve up
SWEEP_RISE = 16.0                 # how far the underside has risen by the lid
BOARD_CY = 4.0                    # perfboard centre height (the lid is shorter than the face, so it sits high)

# ---- Derived layout -----------------------------------------------------
H = IH + 2 * WALL
YB = -H / 2
Z_TOP = math.ceil(FACE_T + GLASS_H + PCB_T + SCREEN_REAR_H + WIRE_GAP + STANDOFF + PCB_T + BOARD_COMP_H)   # face to lid seat
TAN_T = math.tan(math.radians(TILT))
K = math.sqrt(1 + SIDE_TAPER ** 2)
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
POST_Z0 = FACE_T + GLASS_H + PCB_T + 0.5             # posts start behind the screens and hang from the ceiling
_px0, _px1 = INFO_XMIN + POST_D / 2, LW / 2 - POST_D / 2
POSTS = [(_px0 + (_px1 - _px0) * i / 3.0, PY) for i in range(4)]
# underside sweep: a circular arc, tangent to the flat bottom at SWEEP_START, rising SWEEP_RISE by the lid
_L = Z_TOP - SWEEP_START
SW_R = (_L ** 2 + SWEEP_RISE ** 2) / (2 * SWEEP_RISE)
SW_CY = YB + SW_R
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


def outline(hb, t, yb, yt, rb, rt=0.0):
    """Tapered outline (counter-clockwise) between heights yb and yt; t insets the sloped sides."""
    hw = lambda y: hb + SIDE_TAPER * (y - YB) - t * K
    return ([(-hw(yb), yb), (hw(yb), yb), (hw(yt), yt), (-hw(yt), yt)], [rb, rb, rt, rt])


def outer_outline(yb, rb):
    """Outer face outline: tapered sides, flat middle top, and a wing at each end curving up along the dash lip."""
    hw = lambda y: HB + SIDE_TAPER * (y - YB)
    yw = H / 2 + WING_RISE
    V = [(-hw(yb), yb), (hw(yb), yb), (hw(yw), yw), (WING_X1, yw), (WING_X0, H / 2),
         (-WING_X0, H / 2), (-WING_X1, yw), (-hw(yw), yw)]
    return V, [rb, rb, 0.0, 2.0, WING_R, WING_R, 2.0, 0.0]


def cavity_outline():
    return outline(HB, WALL, YB + WALL, H / 2 - WALL, R_BOTTOM - WALL, 2.0)


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


def polyline(V, R, steps=16):
    pts = []
    for T1, T2, mid in rounded(V, R):
        if mid is None:
            pts.append(T1)
            continue
        ax, ay = T1; bx, by = mid; cx, cy = T2
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
        uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
        a0, a1, am = math.atan2(ay - uy, ax - ux), math.atan2(cy - uy, cx - ux), math.atan2(by - uy, bx - ux)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        if (am - a0 + math.pi) % (2 * math.pi) - math.pi < 0 != da < 0:
            da = da - math.copysign(2 * math.pi, da)
        r = math.hypot(ax - ux, ay - uy)
        pts += [(ux + r * math.cos(a0 + da * i / steps), uy + r * math.sin(a0 + da * i / steps)) for i in range(steps + 1)]
    return pts


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


def _fits(hb):
    pts = polyline(*outline(hb, WALL, YB + WALL, H / 2 - WALL, R_BOTTOM - WALL, 2.0))
    g = POCKET_CLR + POCKET_WALL
    for cx, cy, w, h in [(TACH_CX, TACH_PCB_CY, TACH_W, TACH_H), (INFO_CX, YC, INFO_L, INFO_H)]:
        for sx in (-1, 1):
            for sy in (-1, 1):
                if clearance((cx + sx * (w / 2 + g), cy + sy * (h / 2 + g)), pts) < -0.2:
                    return False
    return all(clearance(p, pts) >= 3.0 for p in POSTS)


HB = 60.0
while not _fits(HB):
    HB += 0.5
XOFF = 2 * (HB + SIDE_TAPER * (Y_EXT - YB)) + 15.0
_in_hw = lambda y: HB + SIDE_TAPER * (y - YB) - WALL * K
BOARD_CX = -_in_hw(BOARD_CY - BOARD_W / 2) + BOARD_END_GAP + BOARD_L / 2
HW_TOP = HB + SIDE_TAPER * H


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


def draw_outline(sk, V, R, dx=0.0, dy=0.0):
    c = rounded(V, R)
    n = len(V)
    for i in range(n):
        T1, T2, mid = c[i]
        if mid is not None:
            sk.sketchCurves.sketchArcs.addByThreePoints(P3(T1[0] + dx, T1[1] + dy), P3(mid[0] + dx, mid[1] + dy), P3(T2[0] + dx, T2[1] + dy))
        N1 = c[(i + 1) % n][0]
        if math.hypot(T2[0] - N1[0], T2[1] - N1[1]) > 1e-6:
            sk.sketchCurves.sketchLines.addByTwoPoints(P3(T2[0] + dx, T2[1] + dy), P3(N1[0] + dx, N1[1] + dy))


def extrude_outline(comp, V, R, z0, z1, op, dx=0.0, dy=0.0):
    sk = sketch_at(comp, z0)
    draw_outline(sk, V, R, dx, dy)
    return extrude(comp, sk.profiles.item(0), z1 - z0, op)


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


def yz_region(comp, segs, op):
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
    za, zb = FACE_T - 1.0, Z_TOP + 5
    Vi, Ri = cavity_outline()
    plan = extrude_outline(comp, Vi, Ri, FACE_T, Z_TOP + 1, NEW).bodies.item(0)
    prof = yz_region(comp, [('L', (S[0], za), S), ('A', S, Mp, E), ('L', E, (E[0], zb)), ('L', (E[0], zb), (top, zb)),
                            ('L', (top, zb), (top, za)), ('L', (top, za), (S[0], za))], NEW).bodies.item(0)
    combine(comp, plan, prof, INTERSECT)
    return plan


def round_front_edge(comp, body):
    face = None
    for f in body.faces:
        if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
            n = f.geometry.normal
            if abs(n.z + 1) < 1e-6 and abs(f.boundingBox.minPoint.z) < 1e-6:
                face = f
    edges = adsk.core.ObjectCollection.create()
    for e in face.edges:
        bb = e.boundingBox
        if (bb.minPoint.y + bb.maxPoint.y) / 2 * 10 < H / 2 - 1.0 or (bb.maxPoint.y - bb.minPoint.y) * 10 > 1.0:
            edges.add(e)
    inp = comp.features.filletFeatures.createInput()
    inp.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByReal(mm(R_FACE)), True)
    comp.features.filletFeatures.add(inp)


def build_shell(comp):
    V, R = outer_outline(YB, R_BOTTOM)
    shell = extrude_outline(comp, V, R, 0, Z_TOP, NEW).bodies.item(0)
    combine(comp, shell, cavity_body(comp), CUT)
    for x, y in POSTS:
        prism(comp, x - POST_D / 2, y - POST_D / 2, x + POST_D / 2, H / 2 - WALL + 0.6, POST_Z0, Z_TOP, JOIN)
    if TILT > 0:
        cut_top_slope(comp)
    cut_underside(comp)
    for x, y in POSTS:
        cyl(comp, x, y, LID_PILOT_D, Z_TOP - POST_PILOT_DEPTH, Z_TOP + 1, CUT)
    try:
        round_front_edge(comp, comp.bRepBodies.item(0))
    except Exception:
        print('front edge fillet skipped')
    ph = GLASS_H + PCB_T
    ring(comp, TACH_CX, TACH_PCB_CY, TACH_W, TACH_H, FACE_T - 0.1, FACE_T + ph, JOIN)
    ring(comp, INFO_CX, YC, INFO_L, INFO_H, FACE_T - 0.1, FACE_T + ph, JOIN)
    # tach screw posts: the PCB rests on them (glass height) and an M2 screw goes through its hole from behind
    thy = TACH_PCB_CY - TACH_H / 2 + TACH_HOLE_UP
    for sx in (-1, 1):
        px = TACH_CX + sx * TACH_HOLE_SPAN / 2
        cyl(comp, px, thy, SCREEN_POST_D, FACE_T - 0.1, FACE_T + GLASS_H, JOIN)
        cyl(comp, px, thy, SCREEN_PILOT_D, FACE_T + GLASS_H - SCREEN_PILOT_DEPTH, FACE_T + GLASS_H + 0.1, CUT)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = INFO_CX + sx * (INFO_L / 2 - INFO_HOLE_INSET), YC + sy * (INFO_H / 2 - INFO_HOLE_INSET)
            cyl(comp, px, py, INFO_POST_D, FACE_T - 0.1, FACE_T + GLASS_H, JOIN)
            cyl(comp, px, py, INFO_PILOT_D, FACE_T + GLASS_H - SCREEN_PILOT_DEPTH, FACE_T + GLASS_H + 0.1, CUT)
    cyl(comp, TACH_CX, YC, TACH_WIN_D, -1, FACE_T + 0.1, CUT)
    prism(comp, INFO_WIN_CX - INFO_WIN_W / 2, YC - INFO_WIN_H / 2, INFO_WIN_CX + INFO_WIN_W / 2,
          YC + INFO_WIN_H / 2, -1, FACE_T + 0.1, CUT)
    # terminal window in the info-side end wall, at the board's height (no USB-C window: OTA update, user decision 2026-11-23)
    zb = Z_TOP - (STANDOFF + PCB_T)
    for y, w, zc, h in [(BOARD_CY + TERM_Y, TERM_SLOT_W, TERM_Z, TERM_SLOT_H)]:
        z = zb - zc
        prism(comp, -HB - 60, y - w / 2, BOARD_CX - BOARD_L / 2 - BOARD_END_GAP + 0.5, y + w / 2, z - h / 2, z + h / 2, CUT)


def build_lid(comp):
    lx = lambda x: XOFF - x
    V, R = outer_outline(Y_BOT_OUT, 0.0)
    extrude_outline(comp, V, R, 0, LID_T, NEW, XOFF)
    # lip: a ring that follows the cavity at the back, notched round the posts
    Vo, Ro = outline(HB, WALL + LIP_TOL, Y_BOT_IN + LIP_TOL, H / 2 - WALL - LIP_TOL, 0.0)
    Vn, Rn = outline(HB, WALL + LIP_TOL + LIP_T, Y_BOT_IN + LIP_TOL + LIP_T, H / 2 - WALL - LIP_TOL - LIP_T, 0.0)
    sk = sketch_at(comp, LID_T - 0.1)
    draw_outline(sk, Vo, Ro, XOFF)
    draw_outline(sk, Vn, Rn, XOFF)
    ringp = [p for p in sk.profiles if p.profileLoops.count == 2][0]
    extrude(comp, ringp, LIP_H + 0.1, JOIN)
    for x, y in POSTS:
        prism(comp, lx(x) - POST_D / 2 - 0.5, y - POST_D / 2 - 0.5, lx(x) + POST_D / 2 + 0.5, y + POST_D / 2 + 0.5,
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


def build_all():
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    build_shell(comp)
    build_lid(comp)
    lines = ['Outer: %.1f mm wide at the bottom, %.1f at the top, %.1f high, %.1f deep, lid %.1f mm; sweep R%.0f' % (
        2 * HB, 2 * HW_TOP, H, Z_TOP, LID_T, SW_R)]
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
    V, R = outer_outline(YB, R_BOTTOM)
    extrude_outline(comp, V, R, 0, 3.0, NEW)
    prism(comp, -300, -300, 300, H / 2 - band, -1.0, 4.0, CUT)                 # everything below the band
    prism(comp, -0.75, H / 2 - 6.0, 0.75, H / 2 + 1.0, -1.0, 4.0, CUT)     # centre mark on the top edge
    b = comp.bRepBodies.item(0)
    bb = b.boundingBox
    return 'Template %.1f x %.1f x %.1f mm' % ((bb.maxPoint.x - bb.minPoint.x) * 10, (bb.maxPoint.y - bb.minPoint.y) * 10,
                                              (bb.maxPoint.z - bb.minPoint.z) * 10)


def build_wing_tests(angles=(30, 40, 50, 60), band=14.0):
    """Four small 3 mm pieces, each the left wing end of the top edge with the wing's inner edge at a different angle
    (degrees from horizontal) and that many notches along the bottom (1 = first angle, ...). Hold them against the left end
    of the dash recess to see which angle matches."""
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    comp = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    hw = lambda y: HB + SIDE_TAPER * (y - YB)
    yw, yb = H / 2 + WING_RISE, H / 2 - band
    for k, ang in enumerate(angles):
        x0 = WING_X1 - WING_RISE / math.tan(math.radians(ang))
        dx, dy = (k % 2) * 75.0, -(k // 2) * 50.0
        V = [(-hw(yb), yb), (-(x0 - 12.0), yb), (-(x0 - 12.0), H / 2), (-x0, H / 2), (-WING_X1, yw), (-hw(yw), yw)]
        R = [0.0, 0.0, 0.0, WING_R, 2.0, 0.0]
        extrude_outline(comp, V, R, 0, 3.0, NEW, dx, dy)
        for j in range(k + 1):
            nx = dx - (x0 - 12.0) - 8.0 - 6.0 * j
            sk = sketch_at(comp, -1.0)
            sk.sketchCurves.sketchLines.addTwoPointRectangle(P3(nx - 1.0, yb + dy - 1.0), P3(nx + 1.0, yb + dy + 3.0))
            extrude(comp, sk.profiles.item(0), 5.0, CUT)
    return '%d pieces, %.0f x %.0f mm layout' % (comp.bRepBodies.count, 75 + hw(yw) + 20, 50 + yw - yb)


def run(context):
    ui = None
    try:
        ui = adsk.core.Application.get().userInterface
        ui.messageBox(build_all())
    except Exception:
        if ui:
            ui.messageBox('Failed:\n' + traceback.format_exc())
