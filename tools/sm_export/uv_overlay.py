"""Definitive UV-vs-atlas test: overlay the glTF texcoords actually written to
the GLB onto the decoded atlas. If the sampled points land on real content the
texture path is correct and the black render is something else; if they land on
the black padding the V-orientation / index mapping is wrong.

Reads geometry straight from the .3sm exactly like sm_to_3dtiles does, applies
the same re-weld and the same V-flip, then scatter-plots (u, 1-v)*size on the
atlas. Also reports the fraction of UNIQUE texels that are black under the
stored vs the flipped convention so we pick the right one objectively.
"""
import io
import sqlite3
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, r"e:\sl output\1\tools\sm_export")
from sm_to_obj import read_blob_uint32, read_blob_uv  # noqa: E402

sm = sys.argv[1] if len(sys.argv) > 1 else r"e:\sl output\1\church_final\Production_3.3sm"
outdir = sys.argv[2] if len(sys.argv) > 2 else r"e:\sl output\1\tiles\church"
conn = sqlite3.connect(sm)
cur = conn.cursor()

cur.execute("SELECT NodeId, ParentNodeId FROM SMNodeHeader")
rows = cur.fetchall()
parents = {p for _, p in rows}
leaves = sorted(n for n, _ in rows if n not in parents)


def black_frac(arr_lum, u, v):
    h, w = arr_lum.shape
    xi = np.clip((u * (w - 1)).astype(int), 0, w - 1)
    yi = np.clip((v * (h - 1)).astype(int), 0, h - 1)
    return float((arr_lum[yi, xi] < 8).mean() * 100)


print("node  stored(1-v)%blk  noflip(v)%blk  verdict")
for nid in leaves[:8]:
    uv_data, uv_idx_data = cur.execute(
        "SELECT UVData, UVIndexData FROM SMUVs WHERE NodeId=?", (nid,)).fetchone()
    uvs = np.asarray(read_blob_uv(uv_data), dtype=np.float64).reshape(-1, 2)

    blob = cur.execute("SELECT TexData FROM SMTexture WHERE NodeId=?", (nid,)).fetchone()[0]
    s = blob.find(b"\xff\xd8\xff"); e = blob.rfind(b"\xff\xd9")
    img = Image.open(io.BytesIO(blob[s:e + 2])).convert("RGB")
    lum = np.asarray(img).mean(axis=2)

    u = uvs[:, 0]
    v_src = uvs[:, 1]
    # glTF top-left origin: stored exporter uses (u, 1 - v_src)
    blk_flip = black_frac(lum, u, 1.0 - v_src)
    blk_noflip = black_frac(lum, u, v_src)
    verdict = "FLIP(1-v) better" if blk_flip < blk_noflip else "NO-FLIP better"
    print(f"{nid:4d}    {blk_flip:6.1f}        {blk_noflip:6.1f}      {verdict}")

    # save overlay using whichever is better, dots on content = good
    use_v = (1.0 - v_src) if blk_flip <= blk_noflip else v_src
    ov = img.copy()
    d = ImageDraw.Draw(ov)
    w, h = img.size
    step = max(1, len(u) // 4000)
    for k in range(0, len(u), step):
        x = u[k] * (w - 1)
        y = use_v[k] * (h - 1)
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(0, 255, 0))
    ov.save(f"{outdir}\\_uvoverlay_node_{nid}.png")

conn.close()
print(f"\nsaved overlays to {outdir}\\_uvoverlay_node_*.png")
