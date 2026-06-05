"""Inventory every Production model: .3sm size, SRS, absolute UTM44N extent/centroid,
WGS84 lon/lat, and duplicate detection by centroid proximity."""

from __future__ import annotations

import glob
import os
import re
import sqlite3
import struct

from pyproj import Transformer

ROOT = r"e:\sl output\1\Productions"
T = Transformer.from_crs(32644, 4326, always_xy=True)


def widest_extent(sm_path: str):
    con = sqlite3.connect(sm_path)
    cur = con.cursor()
    cur.execute("SELECT Extent FROM SMNodeHeader WHERE Extent IS NOT NULL")
    best = None
    best_area = -1.0
    for (blob,) in cur.fetchall():
        if not blob or len(blob) != 48:
            continue
        e = struct.unpack("<6d", blob)
        area = (e[3] - e[0]) * (e[4] - e[1])
        if area > best_area:
            best_area, best = area, e
    con.close()
    return best


def read_srs(meta_path: str) -> str:
    if not os.path.exists(meta_path):
        return "?"
    txt = open(meta_path, encoding="utf-8", errors="ignore").read()
    m = re.search(r"<SRS>(.*?)</SRS>", txt, re.S)
    return m.group(1).strip() if m else "?"


rows = []
for folder in sorted(os.listdir(ROOT)):
    fdir = os.path.join(ROOT, folder)
    if not os.path.isdir(fdir):
        continue
    sm_files = glob.glob(os.path.join(fdir, "*.3sm"))
    srs = read_srs(os.path.join(fdir, "metadata.xml"))
    if not sm_files:
        rows.append((folder, None, 0.0, srs, None, None, None))
        continue
    sm = sm_files[0]
    size_mb = os.path.getsize(sm) / 1024 / 1024
    ext = widest_extent(sm)
    if ext is None:
        rows.append((folder, os.path.basename(sm), size_mb, srs, None, None, None))
        continue
    cx = (ext[0] + ext[3]) / 2
    cy = (ext[1] + ext[4]) / 2
    lon, lat = T.transform(cx, cy)
    rows.append((folder, os.path.basename(sm), size_mb, srs, (cx, cy), (lon, lat), ext))

# duplicate detection by centroid proximity (<50 m)
sites = []  # list of dict
for folder, sm, size_mb, srs, cen, ll, ext in rows:
    if cen is None:
        continue
    placed = False
    for s in sites:
        if abs(cen[0] - s["cx"]) < 50 and abs(cen[1] - s["cy"]) < 50:
            s["members"].append((folder, sm, size_mb, cen, ll))
            placed = True
            break
    if not placed:
        sites.append({"cx": cen[0], "cy": cen[1],
                      "members": [(folder, sm, size_mb, cen, ll)]})

print("=" * 110)
print(f"{'Folder':<22}{'.3sm':<26}{'MB':>7}  {'UTM E':>11} {'UTM N':>11}  {'lon':>9} {'lat':>9}")
print("-" * 110)
for folder, sm, size_mb, srs, cen, ll, ext in rows:
    if cen is None:
        print(f"{folder:<22}{(sm or 'NO .3sm'):<26}{size_mb:>7.1f}  {'-':>11} {'-':>11}  {'-':>9} {'-':>9}")
    else:
        print(f"{folder:<22}{sm:<26}{size_mb:>7.1f}  {cen[0]:>11.1f} {cen[1]:>11.1f}  {ll[0]:>9.4f} {ll[1]:>9.4f}")

print("\n" + "=" * 110)
print(f"DISTINCT SITES: {len(sites)}  (best = largest .3sm per cluster)")
print("-" * 110)
for i, s in enumerate(sites, 1):
    best = max(s["members"], key=lambda m: m[2])
    ll = best[4]
    print(f"\nSite {i}: centroid UTM ({s['cx']:.1f}, {s['cy']:.1f}) -> lon {ll[0]:.5f}, lat {ll[1]:.5f}")
    for folder, sm, size_mb, cen, mll in sorted(s["members"], key=lambda m: -m[2]):
        star = "  <== BEST" if (folder, sm) == (best[0], best[1]) else ""
        print(f"    {folder:<22}{sm:<26}{size_mb:>7.1f} MB{star}")
