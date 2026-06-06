"""Probe the .3sm SQLite schema to test the multi-texture-per-node hypothesis:
if a leaf node references more than one texture page, our exporter (which keeps
only the first JPEG and one UV set) would map many faces onto the wrong/black
atlas region -> the black, fragmented look that survives the mipmap fix.
"""
import sqlite3
import struct
import sys
import zlib

sm = sys.argv[1] if len(sys.argv) > 1 else r"e:\sl output\1\church_final\Production_3.3sm"
conn = sqlite3.connect(sm)
cur = conn.cursor()

# schema
print("=== tables ===")
for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(" ", name)

for tbl in ("SMTexture", "SMUVs", "SMPoint", "SMNodeHeader"):
    try:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({tbl})")]
        print(f"--- {tbl} cols: {cols}")
    except Exception as e:
        print(f"--- {tbl}: {e}")

# leaves
cur.execute("SELECT NodeId, ParentNodeId FROM SMNodeHeader")
rows = cur.fetchall()
parents = {p for _, p in rows}
leaves = sorted(n for n, _ in rows if n not in parents)
print(f"\nleaves: {len(leaves)}  first few: {leaves[:8]}")

# textures per node
print("\n=== textures per leaf node ===")
multi = 0
for nid in leaves[:20]:
    n_tex = cur.execute("SELECT COUNT(*) FROM SMTexture WHERE NodeId=?", (nid,)).fetchone()[0]
    n_uv = cur.execute("SELECT COUNT(*) FROM SMUVs WHERE NodeId=?", (nid,)).fetchone()[0]
    if n_tex > 1:
        multi += 1
    print(f" node {nid}: SMTexture rows={n_tex}  SMUVs rows={n_uv}")
print(f"nodes with >1 texture (of first 20): {multi}")

# count JPEG streams inside one texture blob (atlas pages packed in one blob?)
print("\n=== JPEG streams inside one TexData blob ===")
for nid in leaves[:6]:
    blob = cur.execute("SELECT TexData FROM SMTexture WHERE NodeId=?", (nid,)).fetchone()[0]
    # count SOI markers
    n_soi = blob.count(b"\xff\xd8\xff")
    n_eoi = blob.count(b"\xff\xd9")
    print(f" node {nid}: blob {len(blob)} bytes, SOI(ffd8ff)={n_soi}, EOI(ffd9)~={n_eoi}")

# UV value range (are UVs outside [0,1]? -> atlas pages stacked via integer part)
print("\n=== UV value ranges (raw) ===")
for nid in leaves[:6]:
    uv_data = cur.execute("SELECT UVData FROM SMUVs WHERE NodeId=?", (nid,)).fetchone()[0]
    raw = zlib.decompress(uv_data)
    vals = struct.unpack(f"<{len(raw)//8}d", raw)
    us = vals[0::2]
    vs = vals[1::2]
    print(f" node {nid}: u[{min(us):.3f},{max(us):.3f}] v[{min(vs):.3f},{max(vs):.3f}] n={len(us)}")

conn.close()
