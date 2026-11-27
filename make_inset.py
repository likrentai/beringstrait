"""Build the inset map land path (SVG) for beringstrait.html.

Reads world-atlas land TopoJSON (Natural Earth, public domain) as plain data,
projects with spherical Lambert azimuthal equal-area, scales to inset pixels.
Usage: python3 -I make_inset.py <land-50m.json> <out.json>
"""
import json, math, sys

CENTRE_LAT, CENTRE_LON = 59.0, -175.0   # inset projection centre
HALF_W_KM, TOP_KM, BOTTOM_KM = 3900.0, 3700.0, -2200.0  # visible extent (km from centre)
W_PX = 270                                # inset width in pixels
R_KM = 6371.0

def laea(lon, lat):
    p0, l0 = math.radians(CENTRE_LAT), math.radians(CENTRE_LON)
    p, l = math.radians(lat), math.radians(lon)
    c = 1 + math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(l - l0)
    if c < 1e-6:
        return None
    k = math.sqrt(2 / c)
    x = R_KM * k * math.cos(p) * math.sin(l - l0)
    y = R_KM * k * (math.cos(p0) * math.sin(p) - math.sin(p0) * math.cos(p) * math.cos(l - l0))
    return x, y

scale = W_PX / (2 * HALF_W_KM)
H_PX = round((TOP_KM - BOTTOM_KM) * scale)

def to_px(x, y):
    return (x + HALF_W_KM) * scale, (TOP_KM - y) * scale

topo = json.load(open(sys.argv[1]))
sx, sy = topo["transform"]["scale"]
tx, ty = topo["transform"]["translate"]
arcs = []
for arc in topo["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)

def ring_coords(idx_list):
    out = []
    for i in idx_list:
        pts = arcs[i] if i >= 0 else arcs[~i][::-1]
        out.extend(pts if not out else pts[1:])
    return out

geoms = topo["objects"]["land"]["geometries"]
polys = []
for g in geoms:
    if g["type"] == "Polygon":
        polys.append(g["arcs"])
    elif g["type"] == "MultiPolygon":
        polys.extend(g["arcs"])

parts = []
margin = 20
for poly in polys:
    for ring in poly:
        ll = ring_coords(ring)
        if max(p[1] for p in ll) < 20:   # far south: never visible
            continue
        px = []
        for lon, lat in ll:
            q = laea(lon, lat)
            if q is None:
                continue
            px.append(to_px(*q))
        if not px:
            continue
        xs = [p[0] for p in px]; ys = [p[1] for p in px]
        if max(xs) < -margin or min(xs) > W_PX + margin or max(ys) < -margin or min(ys) > H_PX + margin:
            continue
        # thin to about 0.6 px steps
        kept = [px[0]]
        for p in px[1:]:
            if abs(p[0] - kept[-1][0]) + abs(p[1] - kept[-1][1]) >= 1.3:
                kept.append(p)
        if len(kept) < 3:
            continue
        # skip specks
        area = 0.5 * abs(sum(kept[i][0] * kept[i - 1][1] - kept[i - 1][0] * kept[i][1] for i in range(len(kept))))
        if area < 1.5:
            continue
        parts.append("M" + "L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in kept) + "Z")

d = "".join(parts)
json.dump({"centre": [CENTRE_LAT, CENTRE_LON], "half_w_km": HALF_W_KM, "top_km": TOP_KM, "bottom_km": BOTTOM_KM,
           "w": W_PX, "h": H_PX, "scale_px_per_km": scale, "land_path": d}, open(sys.argv[2], "w"))
print("size", W_PX, "x", H_PX, "path chars", len(d), "rings", len(parts))
