"""Render the exported OBJ (parsing the file itself) to validate that the
written vertex/UV indices, per-material texture groups and offsets are correct.
Top-down orthographic, north up, per-pixel texture sampling.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

EXPORT = r"e:\sl output\1\Productions\YELLOWHOUSE_FINAL2\export"
OBJ = os.path.join(EXPORT, "YellowHouse.obj")
MTL = os.path.join(EXPORT, "YellowHouse.mtl")
OUT = os.path.join(EXPORT, "preview_from_obj.png")
W = 1400


def load_mtl(path):
    mats, cur = {}, None
    for line in open(path, encoding="ascii"):
        p = line.split()
        if not p:
            continue
        if p[0] == "newmtl":
            cur = p[1]
        elif p[0] == "map_Kd" and cur:
            mats[cur] = os.path.join(EXPORT, p[1].replace("/", os.sep))
    return {m: np.asarray(Image.open(f).convert("RGB")) for m, f in mats.items()}


textures = load_mtl(MTL)

verts, uvs = [], []
faces = []  # (vi[3], ti[3], mat)
cur_mat = None
for line in open(OBJ, encoding="ascii"):
    p = line.split()
    if not p:
        continue
    t = p[0]
    if t == "v":
        verts.append((float(p[1]), float(p[2]), float(p[3])))
    elif t == "vt":
        uvs.append((float(p[1]), float(p[2])))
    elif t == "usemtl":
        cur_mat = p[1]
    elif t == "f":
        vi, ti = [], []
        for c in p[1:4]:
            a, b = c.split("/")[:2]
            vi.append(int(a) - 1)
            ti.append(int(b) - 1)
        faces.append((vi, ti, cur_mat))

verts = np.array(verts)
uvs = np.array(uvs)
print(f"OBJ: v={len(verts)} vt={len(uvs)} f={len(faces)} mats={len(textures)}")
print(f"vt range U[{uvs[:,0].min():.3f},{uvs[:,0].max():.3f}] V[{uvs[:,1].min():.3f},{uvs[:,1].max():.3f}]")

minx, miny = verts[:, 0].min(), verts[:, 1].min()
maxx, maxy = verts[:, 0].max(), verts[:, 1].max()
scale = (W - 1) / (maxx - minx)
H = int((maxy - miny) * scale) + 1
img = np.zeros((H, W, 3), dtype=np.uint8)
zbuf = np.full((H, W), -np.inf)

sx = (verts[:, 0] - minx) * scale
sy = (maxy - verts[:, 1]) * scale
sz = verts[:, 2]

for vi, ti, mat in faces:
    tex = textures.get(mat)
    if tex is None:
        continue
    th, tw = tex.shape[:2]
    x0, x1, x2 = sx[vi]
    y0, y1, y2 = sy[vi]
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
    zi = a * sz[vi[0]] + b * sz[vi[1]] + g * sz[vi[2]]
    sel = inside & (zi > zbuf[ys, xs])
    if not sel.any():
        continue
    yy, xx = ys[sel], xs[sel]
    uv0, uv1, uv2 = uvs[ti[0]], uvs[ti[1]], uvs[ti[2]]
    u = a[sel] * uv0[0] + b[sel] * uv1[0] + g[sel] * uv2[0]
    vv = a[sel] * uv0[1] + b[sel] * uv1[1] + g[sel] * uv2[1]
    tu = np.clip((u % 1.0) * (tw - 1), 0, tw - 1).astype(np.int64)
    tvv = np.clip((1.0 - (vv % 1.0)) * (th - 1), 0, th - 1).astype(np.int64)
    zbuf[yy, xx] = zi[sel]
    img[yy, xx] = tex[tvv, tu]

Image.fromarray(img).save(OUT)
print("saved", OUT)
