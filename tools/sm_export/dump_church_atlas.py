"""Dump the real decoded atlas for a few church leaves and report the texture
codec, so we can see whether the atlas is genuinely mostly black (a real
photogrammetry artifact) or whether our JPEG extraction is wrong (decoding only
part of the stream -> mostly black image)."""
import io
import sqlite3
import sys

import numpy as np
from PIL import Image

sm = sys.argv[1] if len(sys.argv) > 1 else r"e:\sl output\1\church_final\Production_3.3sm"
outdir = sys.argv[2] if len(sys.argv) > 2 else r"e:\sl output\1\tiles\church"
conn = sqlite3.connect(sm)
cur = conn.cursor()

cur.execute("SELECT NodeId, ParentNodeId FROM SMNodeHeader")
rows = cur.fetchall()
parents = {p for _, p in rows}
leaves = sorted(n for n, _ in rows if n not in parents)

print("node  codec chans  blobKB  jpegKB  WxH      meanL  black%")
for nid in leaves[:8]:
    codec, chans = cur.execute(
        "SELECT Codec, NOfChannels FROM SMTexture WHERE NodeId=?", (nid,)).fetchone()
    blob = cur.execute("SELECT TexData FROM SMTexture WHERE NodeId=?", (nid,)).fetchone()[0]
    s = blob.find(b"\xff\xd8\xff")
    e = blob.rfind(b"\xff\xd9")
    jpeg = blob[s:e + 2]
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    arr = np.asarray(img)
    lum = arr.mean(axis=2)
    black = float((lum < 8).mean() * 100)
    print(f"{nid:4d}  {codec}    {chans}    {len(blob)//1024:5d}  {len(jpeg)//1024:5d}  "
          f"{img.width}x{img.height}  {lum.mean():5.1f}  {black:5.1f}%")
    img.save(f"{outdir}\\_probe_node_{nid}.png")

conn.close()
print(f"\nsaved atlases to {outdir}\\_probe_node_*.png")
