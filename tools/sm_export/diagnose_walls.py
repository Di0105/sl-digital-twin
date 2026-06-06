"""Read-only diagnostic: quantify how well VERTICAL surfaces (walls) are
reconstructed in a .3sm scalable mesh, and whether the leaf set has spatial
holes. UAV/nadir photogrammetry typically under-samples walls, which shows up
in Cesium as "fragmented" walls even though the converter is correct.

Usage:
    python diagnose_walls.py "..\\..\\church_final\\Production_3.3sm"
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from sm_to_obj import (  # noqa: E402
    leaf_nodes,
    read_blob_doubles,
    read_blob_uint32,
)


def analyse(sm_path: str) -> None:
    conn = sqlite3.connect(sm_path)
    cur = conn.cursor()
    leaves = leaf_nodes(cur)

    all_v: list[np.ndarray] = []
    tri_normals: list[np.ndarray] = []
    tri_areas: list[np.ndarray] = []
    tri_centroids: list[np.ndarray] = []
    degenerate = 0

    for nid in leaves:
        cur.execute("SELECT PointData, IndexData FROM SMPoint WHERE NodeId=?", (nid,))
        point_data, index_data = cur.fetchone()
        verts = np.asarray(read_blob_doubles(point_data), dtype=np.float64).reshape(-1, 3)
        idx = np.asarray(read_blob_uint32(index_data), dtype=np.int64) - 1
        tri = idx.reshape(-1, 3)

        a = verts[tri[:, 0]]
        b = verts[tri[:, 1]]
        c = verts[tri[:, 2]]
        n = np.cross(b - a, c - a)          # area-weighted normal (UTM: z = up)
        area2 = np.linalg.norm(n, axis=1)   # = 2*area
        degenerate += int(np.count_nonzero(area2 < 1e-12))
        nz = np.divide(np.abs(n[:, 2]), area2, out=np.zeros(len(n)), where=area2 > 0)

        all_v.append(verts)
        tri_normals.append(nz)              # |cos(angle from vertical axis)| -> 0 = wall
        tri_areas.append(0.5 * area2)
        tri_centroids.append((a + b + c) / 3.0)

    conn.close()

    V = np.vstack(all_v)
    nz = np.concatenate(tri_normals)        # 0 = vertical wall, 1 = horizontal
    area = np.concatenate(tri_areas)
    cen = np.vstack(tri_centroids)

    wall = nz < 0.30                        # within ~17 deg of vertical
    roof = nz > 0.80
    other = ~wall & ~roof

    total_a = area.sum()
    bb_min, bb_max = V.min(axis=0), V.max(axis=0)
    size = bb_max - bb_min

    print(f"file               : {sm_path}")
    print(f"leaves             : {len(leaves)}")
    print(f"triangles          : {len(area):,}  (degenerate {degenerate:,})")
    print(f"bbox size (E,N,Up) : {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} m")
    print(f"total surface area : {total_a:,.0f} m^2")
    print("-- surface area by orientation --")
    print(f"  walls  (<17 deg)  : {area[wall].sum():9,.0f} m^2  {100*area[wall].sum()/total_a:5.1f}%  ({np.count_nonzero(wall):,} tris)")
    print(f"  slopes            : {area[other].sum():9,.0f} m^2  {100*area[other].sum()/total_a:5.1f}%  ({np.count_nonzero(other):,} tris)")
    print(f"  roof/ground       : {area[roof].sum():9,.0f} m^2  {100*area[roof].sum()/total_a:5.1f}%  ({np.count_nonzero(roof):,} tris)")

    # Wall triangle SIZE distribution: huge stretched wall triangles == holes
    # bridged by the mesher (the classic "fragmented wall" look).
    if np.count_nonzero(wall) > 0:
        wa = np.sort(area[wall])
        edge = np.sqrt(2 * wa)              # approx triangle edge length
        print("-- wall triangle size (approx edge length) --")
        for p in (50, 90, 99, 100):
            print(f"  p{p:<3d}            : {np.percentile(edge, p):6.2f} m")
        big = edge > 1.0
        print(f"  walls w/ edge>1m  : {100*big.mean():.1f}% of wall tris "
              f"(stretched = source holes bridged)")

    # Vertical-coverage probe: for a grid over the footprint, how high above the
    # lowest point does wall geometry actually reach? Low/empty cells = missing
    # wall (the building "dissolves" near the ground/edges).
    gx = np.linspace(bb_min[0], bb_max[0], 21)
    gy = np.linspace(bb_min[1], bb_max[1], 21)
    wall_cen = cen[wall]
    if len(wall_cen):
        ix = np.clip(np.searchsorted(gx, wall_cen[:, 0]) - 1, 0, 19)
        iy = np.clip(np.searchsorted(gy, wall_cen[:, 1]) - 1, 0, 19)
        occupied = len(set(zip(ix.tolist(), iy.tolist())))
        print(f"-- wall footprint coverage: {occupied}/400 grid cells contain wall geometry "
              f"({100*occupied/400:.1f}%) --")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        analyse(p)
        print()
