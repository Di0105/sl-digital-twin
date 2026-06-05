"""Quick offscreen top-down render of the .3sm leaf-node mesh to verify geometry
orientation and texture mapping, using only numpy + PIL (no GL).

Flat per-triangle shading: each triangle is filled with the texture colour
sampled at its centroid UV. Top-down orthographic, north up. A z-buffer keeps
the highest surface (roofs win over ground), which is what a nadir view shows.
"""

from __future__ import annotations

import io
import struct
import sqlite3
import zlib

import numpy as np
from PIL import Image

SM = r"e:\sl output\1\Productions\YELLOWHOUSE_FINAL2\YELLOWHOUSE_FINAL2.3sm"
OUT = r"e:\sl output\1\Productions\YELLOWHOUSE_FINAL2\export\preview_topdown.png"
W = 1400


def dec_d(b):
    r = zlib.decompress(b)
    return np.frombuffer(r, dtype="<f8").reshape(-1, 3)


def dec_u(b):
    r = zlib.decompress(b)
    return np.frombuffer(r, dtype="<u4")


def dec_f(b):
    r = zlib.decompress(b)
    return np.frombuffer(r, dtype="<f8").reshape(-1, 2)  # UVs are float64 pairs


def jpeg(b):
    s = b.find(b"\xff\xd8\xff")
    e = b.rfind(b"\xff\xd9")
    return np.asarray(Image.open(io.BytesIO(b[s:e + 2])).convert("RGB"))


conn = sqlite3.connect(SM)
cur = conn.cursor()
cur.execute("SELECT NodeId, ParentNodeId FROM SMNodeHeader")
rows = cur.fetchall()
parents = {p for _, p in rows}
leaves = sorted(n for n, _ in rows if n not in parents)

# global bounds
mins = np.array([np.inf] * 3)
maxs = np.array([-np.inf] * 3)
node_data = []
for nid in leaves:
    cur.execute("SELECT PointData, IndexData FROM SMPoint WHERE NodeId=?", (nid,))
    pd, idd = cur.fetchone()
    v = dec_d(pd)
    f = dec_u(idd).reshape(-1, 3)
    cur.execute("SELECT UVData, UVIndexData FROM SMUVs WHERE NodeId=?", (nid,))
    uvd, uvi = cur.fetchone()
    uv = dec_f(uvd)
    uvf = dec_u(uvi).reshape(-1, 3)
    cur.execute("SELECT TexData FROM SMTexture WHERE NodeId=?", (nid,))
    tex = jpeg(cur.fetchone()[0])
    mins = np.minimum(mins, v.min(0))
    maxs = np.maximum(maxs, v.max(0))
    node_data.append((v, f, uv, uvf, tex))
conn.close()

# both position and UV indices are 1-based
pos_base = 1
uv_base = 1

minx, miny, minz = mins
maxx, maxy, maxz = maxs
scale = (W - 1) / (maxx - minx)
H = int((maxy - miny) * scale) + 1
img = np.zeros((H, W, 3), dtype=np.uint8)
zbuf = np.full((H, W), -np.inf)

print(f"render {W}x{H}, leaves={len(leaves)}")

for v, f, uv, uvf, tex in node_data:
    th, tw = tex.shape[:2]
    sx = ((v[:, 0] - minx) * scale)
    sy = ((maxy - v[:, 1]) * scale)  # north up
    sz = v[:, 2]
    tri = f.astype(np.int64) - pos_base
    uvtri = uvf.astype(np.int64) - uv_base

    x = sx[tri]
    y = sy[tri]
    zt = sz[tri]
    uvt = uv[uvtri]  # (T,3,2)
    for i in range(tri.shape[0]):
        x0, x1, x2 = x[i]
        y0, y1, y2 = y[i]
        xlo = max(int(np.floor(min(x0, x1, x2))), 0)
        xhi = min(int(np.ceil(max(x0, x1, x2))), W - 1)
        ylo = max(int(np.floor(min(y0, y1, y2))), 0)
        yhi = min(int(np.ceil(max(y0, y1, y2))), H - 1)
        if xhi < xlo or yhi < ylo:
            continue
        xs, ys = np.meshgrid(np.arange(xlo, xhi + 1), np.arange(ylo, yhi + 1))
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if d == 0:
            continue
        a = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / d
        b = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / d
        g = 1 - a - b
        inside = (a >= 0) & (b >= 0) & (g >= 0)
        if not inside.any():
            continue
        zi = a * zt[i, 0] + b * zt[i, 1] + g * zt[i, 2]
        sel = inside & (zi > zbuf[ys, xs])
        if not sel.any():
            continue
        yy = ys[sel]
        xx = xs[sel]
        u = a[sel] * uvt[i, 0, 0] + b[sel] * uvt[i, 1, 0] + g[sel] * uvt[i, 2, 0]
        vv = a[sel] * uvt[i, 0, 1] + b[sel] * uvt[i, 1, 1] + g[sel] * uvt[i, 2, 1]
        tu = np.clip((u % 1.0) * (tw - 1), 0, tw - 1).astype(np.int64)
        tvv = np.clip((1.0 - (vv % 1.0)) * (th - 1), 0, th - 1).astype(np.int64)
        zbuf[yy, xx] = zi[sel]
        img[yy, xx] = tex[tvv, tu]

Image.fromarray(img).save(OUT)
print("saved", OUT)

