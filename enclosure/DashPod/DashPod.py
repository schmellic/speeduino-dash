"""Fusion script: under-dash pod for the dash (2.1" round tach, 2.8" info screen, dash ESP32 perfboard).

Shaped like a moulded under-dash gauge panel: wider at the top than the bottom (tapered sides), large rounded bottom corners,
a rounded front edge, and a top that is cut flat against the underside of the dash (TILT tips the face up toward the driver).
Two printed parts: the shell (face plate, walls, lid posts, screen pockets, two mounting ears) and the rear lid (carries the
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
IH = 74.0                         # inside height
POST_D, LID_PILOT_D, LID_HOLE_D, POST_PILOT_DEPTH = 7.0, 2.8, 3.4, 12.0   # M3 machine screws
SEAM = 12.0                       # gap between the two PCBs (the two middle lid posts sit in it)
LIP_TOL, LIP_T, LIP_H = 0.2, 1.6, 2.0
EAR_L, EAR_T, EAR_Z0, EAR_Z1 = 16.0, 4.0, 6.0, 32.0   # mounting ears on the top, flush with the top plane
EAR_SLOT_W, EAR_SLOT_Z0, EAR_SLOT_Z1 = 4.5, 13.0, 25.0   # screws up into the dash lip (slot along Z)

# ---- Shape --------------------------------------------------------------
TILT = 10.0                       # degrees: the top plane rises this much per mm of depth, so the face tips up toward the driver
SIDE_TAPER = 0.12                 # each side moves in this much per mm of height going down (wider at the top)
R_BOTTOM = 16.0                   # outer radius of the bottom corners
R_FACE = 3.0                      # rounded front edge (not on the top edge)

# ---- Derived layout -----------------------------------------------------
H = IH + 2 * WALL
YB = -H / 2
Z_TOP = FACE_T + INNER_D
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
Y_EXT = H / 2 + Z_TOP * TAN_T + 4.0                  # outline top before the sloped cut
PY = IH / 2 - POST_D / 2
POSTS = [(SEAM_X, PY), (SEAM_X, -PY), (INFO_XMIN + POST_D / 2, PY), (INFO_XMIN + POST_D / 2, -PY)]
XOFF = 0.0                                           # lid layout offset (set below once the width is known)

NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def y_plane(z):
    """Height of the sloped top plane at depth z."""
    return H / 2 + z * TAN_T


def outline(hb, t, ytop, rt=0.0):
    """Tapered outline inset by t: vertices and corner radii (counter-clockwise)."""
    hw = lambda y: hb + SIDE_TAPER * (y - YB) - t * K
    yb, yt = YB + t, ytop - t
    return ([(-hw(yb), yb), (hw(yb), yb), (hw(yt), yt), (-hw(yt), yt)], [R_BOTTOM - t, R_BOTTOM - t, rt, rt])


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
    """Return [(T1, T2, mid)] for each corner; the outline runs T2[i] -> T1[i+1] along straight edges."""
    n = len(V)
    return [_corner(V[i - 1], V[i], V[(i + 1) % n], R[i]) for i in range(n)]


def polyline(V, R, steps=16):
    pts = []
    for T1, T2, mid in rounded(V, R):
        if mid is None:
            pts.append(T1)
            continue
        # sample the arc through T1, mid, T2
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
    pts = polyline(*outline(hb, WALL, H / 2))
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
BOARD_CX = -_in_hw(-BOARD_W / 2) + BOARD_END_GAP + BOARD_L / 2
HW_TOP = HB + SIDE_TAPER * (H - 0)                      # outer half width at the top plane's front edge


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


def draw_outline(sk, V, R, dx=0.0):
    c = rounded(V, R)
    n = len(V)
    for i in range(n):
        T1, T2, mid = c[i]
        if mid is not None:
            sk.sketchCurves.sketchArcs.addByThreePoints(P3(T1[0] + dx, T1[1]), P3(mid[0] + dx, mid[1]), P3(T2[0] + dx, T2[1]))
        N1 = c[(i + 1) % n][0]
        if math.hypot(T2[0] - N1[0], T2[1] - N1[1]) > 1e-6:
            sk.sketchCurves.sketchLines.addByTwoPoints(P3(T2[0] + dx, T2[1]), P3(N1[0] + dx, N1[1]))


def extrude_outline(comp, V, R, z0, z1, op, dx=0.0):
    sk = sketch_at(comp, z0)
    draw_outline(sk, V, R, dx)
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
    """Four overlapping strips forming a rectangular locating wall round a w x h PCB."""
    a, t = POCKET_CLR, POCKET_WALL
    x0, x1, y0, y1 = cx - w / 2 - a, cx + w / 2 + a, cy - h / 2 - a, cy + h / 2 + a
    for (p, q, r, s) in [(x0 - t, y0 - t, x1 + t, y0), (x0 - t, y1, x1 + t, y1 + t),
                         (x0 - t, y0, x0, y1), (x1, y0, x1 + t, y1)]:
        prism(comp, p, q, r, s, z0, z1, op)


def cut_top_slope(comp):
    """Remove everything above the sloped top plane (plane through the face's top edge, rising TILT deg with depth)."""
    sk = comp.sketches.add(comp.yZConstructionPlane)
    big = H + 200
    pts = [(y_plane(-5), -5), (y_plane(Z_TOP + 5), Z_TOP + 5), (big, Z_TOP + 5), (big, -5)]
    sp = [sk.modelToSketchSpace(adsk.core.Point3D.create(0, mm(y), mm(z))) for y, z in pts]
    for i in range(4):
        sk.sketchCurves.sketchLines.addByTwoPoints(sp[i], sp[(i + 1) % 4])
    inp = comp.features.extrudeFeatures.createInput(sk.profiles.item(0), CUT)
    inp.setSymmetricExtent(adsk.core.ValueInput.createByReal(mm(1000)), True)
    comp.features.extrudeFeatures.add(inp)


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
    V, R = outline(HB, 0.0, Y_EXT)
    extrude_outline(comp, V, R, 0, Z_TOP, NEW)
    # mounting ears on the top corners: plates with a vertical screw slot (four pieces), trimmed by the sloped cut
    hwt = HB + SIDE_TAPER * (H - 0.0)
    for s in (-1, 1):
        a, b = s * (hwt - 1.5), s * (hwt + EAR_L)
        c0, c1 = s * (hwt + EAR_L / 2 - EAR_SLOT_W / 2), s * (hwt + EAR_L / 2 + EAR_SLOT_W / 2)
        y0, y1 = H / 2 - EAR_T, Y_EXT
        for (xa, xb, za, zb) in [(a, b, EAR_Z0, EAR_SLOT_Z0), (a, b, EAR_SLOT_Z1, EAR_Z1),
                                 (a, c0, EAR_SLOT_Z0, EAR_SLOT_Z1), (c1, b, EAR_SLOT_Z0, EAR_SLOT_Z1)]:
            prism(comp, min(xa, xb), y0, max(xa, xb), y1, za, zb, JOIN)
    if TILT > 0:
        cut_top_slope(comp)
    try:
        round_front_edge(comp, comp.bRepBodies.item(0))
    except Exception:
        print('front edge fillet skipped')
    Vi, Ri = outline(HB, WALL, H / 2, 2.0)
    extrude_outline(comp, Vi, Ri, FACE_T, Z_TOP + 1, CUT)
    for x, y in POSTS:
        cyl(comp, x, y, POST_D, FACE_T - 0.1, Z_TOP, JOIN)
    for x, y in POSTS:
        cyl(comp, x, y, LID_PILOT_D, Z_TOP - POST_PILOT_DEPTH, Z_TOP + 1, CUT)
    ph = GLASS_H + PCB_T
    ring(comp, TACH_CX, TACH_PCB_CY, TACH_W, TACH_H, FACE_T - 0.1, FACE_T + ph, JOIN)
    ring(comp, INFO_CX, YC, INFO_L, INFO_H, FACE_T - 0.1, FACE_T + ph, JOIN)
    cyl(comp, TACH_CX, YC, TACH_WIN_D, -1, FACE_T + 0.1, CUT)
    prism(comp, INFO_WIN_CX - INFO_WIN_W / 2, YC - INFO_WIN_H / 2, INFO_WIN_CX + INFO_WIN_W / 2,
          YC + INFO_WIN_H / 2, -1, FACE_T + 0.1, CUT)
    # USB-C and terminal windows in the info-side end wall, at the board's height
    zb = Z_TOP - (STANDOFF + PCB_T)
    for y, w, zc, h in [(USB_Y, USB_SLOT_W, USB_Z, USB_SLOT_H), (TERM_Y, TERM_SLOT_W, TERM_Z, TERM_SLOT_H)]:
        z = zb - zc
        prism(comp, -HB - 60, y - w / 2, BOARD_CX - BOARD_L / 2 - BOARD_END_GAP + 0.5, y + w / 2, z - h / 2, z + h / 2, CUT)


def build_lid(comp):
    lx = lambda x: XOFF - x
    V, R = outline(HB, 0.0, y_plane(Z_TOP))
    extrude_outline(comp, V, R, 0, LID_T, NEW, XOFF)
    # lip: a ring that follows the cavity, notched round the posts
    Vo, Ro = outline(HB, WALL + LIP_TOL, H / 2, 2.0)
    Vn, Rn = outline(HB, WALL + LIP_TOL + LIP_T, H / 2, 2.0)
    sk = sketch_at(comp, LID_T - 0.1)
    draw_outline(sk, Vo, Ro, XOFF)
    draw_outline(sk, Vn, Rn, XOFF)
    ringp = [p for p in sk.profiles if p.profileLoops.count == 2][0]
    extrude(comp, ringp, LIP_H + 0.1, JOIN)
    for x, y in POSTS:
        cyl(comp, lx(x), y, POST_D + 1.0, LID_T - 0.2, LID_T + LIP_H + 1, CUT)
    hx = (BOARD_CX - BOARD_L / 2 + BOARD_HOLE_INSET, BOARD_CX + BOARD_L / 2 - BOARD_HOLE_INSET)
    hy = (-BOARD_W / 2 + BOARD_HOLE_INSET, BOARD_W / 2 - BOARD_HOLE_INSET)
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
    lines = ['Outer: %.1f mm wide at the bottom, %.1f at the top, %.1f high, %.1f deep (+ ears), lid %.1f mm' % (
        2 * HB, 2 * HW_TOP, H, Z_TOP, LID_T)]
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
