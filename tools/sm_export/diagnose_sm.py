"""Diagnose .3sm scalable-mesh structure: node tree, leaf coverage vs root
extent, whether interior nodes also carry geometry, and per-node vertex counts.
Read-only. Helps explain "fragmented / incomplete" model symptoms.
"""
from __future__ import annotations
import sqlite3
import struct
import sys
import zlib


def doubles(blob):
    raw = zlib.decompress(blob)
    return struct.unpack(f"<{len(raw)//8}d", raw)


def extent_of(blob):
    if blob and len(blob) == 48:
        return struct.unpack("<6d", blob)
    return None


def analyze(path: str) -> None:
    print("=" * 90)
    print(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.execute("SELECT NodeId, ParentNodeId, Extent FROM SMNodeHeader")
    rows = cur.fetchall()
    n_total = len(rows)
    parents = {p for _, p, _ in rows}
    leaves = [nid for nid, p, _ in rows if nid not in parents]
    interior = [nid for nid, p, _ in rows if nid in parents]
    print(f"nodes total={n_total}  leaves={len(leaves)}  interior={len(interior)}")

    # which nodes carry geometry?
    cur.execute("SELECT NodeId FROM SMPoint")
    geom_nodes = {r[0] for r in cur.fetchall()}
    leaf_set = set(leaves)
    interior_with_geom = [n for n in interior if n in geom_nodes]
    leaves_with_geom = [n for n in leaves if n in geom_nodes]
    leaves_without_geom = [n for n in leaves if n not in geom_nodes]
    print(f"nodes with SMPoint geometry = {len(geom_nodes)}")
    print(f"  leaves WITH geom    = {len(leaves_with_geom)}")
    print(f"  leaves WITHOUT geom = {len(leaves_without_geom)}  {leaves_without_geom[:10]}")
    print(f"  interior WITH geom  = {len(interior_with_geom)}  (geometry exists above leaves: {len(interior_with_geom)>0})")

    # extent coverage: union of leaf extents vs widest (root) extent
    ext_map = {nid: extent_of(e) for nid, _, e in rows}
    valid = [e for e in ext_map.values() if e]
    root = max(valid, key=lambda e: (e[3] - e[0]) * (e[4] - e[1]))
    root_area = (root[3] - root[0]) * (root[4] - root[1])

    def union_area(ids):
        es = [ext_map[i] for i in ids if ext_map.get(i)]
        if not es:
            return 0.0, None
        mnx = min(e[0] for e in es); mny = min(e[1] for e in es)
        mxx = max(e[3] for e in es); mxy = max(e[4] for e in es)
        return (mxx - mnx) * (mxy - mny), (mnx, mny, mxx, mxy)

    leaf_union_area, leaf_bbox = union_area(leaves_with_geom)
    print(f"root extent  XY = ({root[0]:.1f},{root[1]:.1f}) .. ({root[3]:.1f},{root[4]:.1f})  area={root_area:.1f}")
    if leaf_bbox:
        print(f"leaf-geom bbox  = ({leaf_bbox[0]:.1f},{leaf_bbox[1]:.1f}) .. ({leaf_bbox[2]:.1f},{leaf_bbox[3]:.1f})  area={leaf_union_area:.1f}")
        print(f"leaf coverage vs root (bbox area ratio) = {leaf_union_area/root_area*100:.1f}%")

    # per-node vertex counts on leaves
    vtot = 0
    counts = []
    for nid in leaves_with_geom:
        cur.execute("SELECT PointData FROM SMPoint WHERE NodeId=?", (nid,))
        r = cur.fetchone()
        if r and r[0]:
            nv = len(doubles(r[0])) // 3
            counts.append(nv)
            vtot += nv
    if counts:
        counts.sort()
        print(f"leaf vertices: total={vtot:,}  min={counts[0]}  med={counts[len(counts)//2]}  max={counts[-1]}")

    # also compute total verts if we took ALL geom nodes (every LOD)
    vtot_all = 0
    for nid in geom_nodes:
        cur.execute("SELECT PointData FROM SMPoint WHERE NodeId=?", (nid,))
        r = cur.fetchone()
        if r and r[0]:
            vtot_all += len(doubles(r[0])) // 3
    print(f"verts (leaves only) = {vtot:,}   verts (ALL nodes incl. LOD) = {vtot_all:,}")
    conn.close()


if __name__ == "__main__":
    targets = sys.argv[1:] or [
        r"e:\sl output\1\Productions\YELLOWHOUSE_FINAL2\YELLOWHOUSE_FINAL2.3sm",
        r"e:\sl output\1\Productions\Production_2_Trial\Production_2_Trial.3sm",
        r"e:\sl output\1\Productions\university_new\Production_1.3sm",
    ]
    for t in targets:
        analyze(t)
