"""Convert a Bentley iTwin Capture / ContextCapture Scalable Mesh (.3sm) directly
to OGC 3D Tiles 1.1 (a glTF-2.0 binary `content.glb` + `tileset.json`) that drops
into CesiumJS / Resium at its true real-world location.

Pipeline
--------
1. Decode leaf nodes from the .3sm SQLite container (positions = float64 absolute
   UTM 44N, 1-based uint32 face indices; UVs = float64 (u,v) pairs with their own
   1-based uint32 index array; one JPEG atlas per node).
2. Re-weld each (positionIndex, uvIndex) corner pair into a single glTF vertex
   (glTF primitives share one index buffer across attributes).
3. Georeference: project every vertex UTM 44N (EPSG:32644) -> WGS84 (EPSG:4326)
   -> ECEF (EPSG:4978) with pyproj, express it in a local East-North-Up frame at
   the model centroid, and emit the ENU->ECEF frame as the tileset root transform.
   This is rigorous horizontally (exact inverse Transverse Mercator) and correct
   vertically up to the (locally constant) EGM96 geoid undulation, which is logged.
4. Write one glTF/GLB per leaf node (each keeps its own JPEG texture/material),
    then build a tileset.json with child tiles and padded bounding spheres.

Output: <out_dir>/<name>/tileset.json, <out_dir>/<name>/nodes/node_<id>.glb,
        <out_dir>/<name>/model.json (georef registry record).
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import struct
import sys
import zlib

import numpy as np
import pyproj
from pyproj import Transformer

# Allow PROJ to fetch the EGM96 geoid grid on demand so EPSG:5773 vertical
# heights convert to correct WGS84 ellipsoidal heights. Falls back gracefully
# (geoid_undulation -> 0) when no network/grid is available.
try:
    pyproj.network.set_network_enabled(True)
except Exception:
    pass

sys.path.insert(0, os.path.dirname(__file__))
from sm_to_obj import (  # noqa: E402
    extract_jpeg,
    leaf_nodes,
    read_blob_doubles,
    read_blob_uint32,
    read_blob_uv,
)

# ---- coordinate transformers ---------------------------------------------------
_T_LL = Transformer.from_crs(32644, 4326, always_xy=True)        # UTM44N -> lon,lat
_T_ECEF = Transformer.from_crs(4979, 4978, always_xy=True)        # lon,lat,h -> ECEF
try:
    _T_H = Transformer.from_crs("EPSG:32644+5773", "EPSG:4979", always_xy=True)
except Exception:  # pragma: no cover - compound CRS unavailable
    _T_H = None


def geoid_undulation(ec: float, nc: float, zc: float) -> float:
    """EGM96 geoid undulation (h_ellipsoidal - H_orthometric) at the centroid.
    Returns 0.0 (and the caller treats Z as ellipsoidal) if the geoid grid is
    unavailable, in which case the vertical anchor is approximate."""
    if _T_H is None:
        return 0.0
    try:
        lon0, lat0, h_ell = _T_H.transform(ec, nc, zc)
        n = h_ell - zc
        return n if math.isfinite(n) and abs(n) < 130.0 else 0.0
    except Exception:
        return 0.0


def enu_basis(lon_deg: float, lat_deg: float):
    lon, lat = math.radians(lon_deg), math.radians(lat_deg)
    sl, cl = math.sin(lon), math.cos(lon)
    sp, cp = math.sin(lat), math.cos(lat)
    east = np.array([-sl, cl, 0.0])
    north = np.array([-sp * cl, -sp * sl, cp])
    up = np.array([cp * cl, cp * sl, sp])
    return east, north, up


def widest_extent(cur: sqlite3.Cursor):
    cur.execute("SELECT Extent FROM SMNodeHeader WHERE Extent IS NOT NULL")
    best, best_area = None, -1.0
    for (blob,) in cur.fetchall():
        if blob and len(blob) == 48:
            e = struct.unpack("<6d", blob)
            area = (e[3] - e[0]) * (e[4] - e[1])
            if area > best_area:
                best, best_area = e, area
    return best


def _pad4(buf: bytearray) -> None:
    while len(buf) % 4:
        buf.append(0)


def _sphere_from_bounds(bounds_min: np.ndarray, bounds_max: np.ndarray,
                        min_padding: float = 2.0, padding_ratio: float = 0.08):
    center = (bounds_min + bounds_max) / 2
    radius = float(np.linalg.norm(bounds_max - bounds_min) / 2)
    radius += max(min_padding, radius * padding_ratio)
    return center, radius


def _build_leaf_glb(node_name: str, gpos: np.ndarray, guv: np.ndarray,
                    tri: np.ndarray, jpeg: bytes):
    bin_buf = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []

    def add_view(data: bytes, target: int | None = None) -> int:
        _pad4(bin_buf)
        offset = len(bin_buf)
        bin_buf.extend(data)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        buffer_views.append(view)
        return len(buffer_views) - 1

    pmin = gpos.min(axis=0)
    pmax = gpos.max(axis=0)

    pos_view = add_view(gpos.tobytes(), target=34962)
    accessors.append({"bufferView": pos_view, "componentType": 5126,
                      "count": int(gpos.shape[0]), "type": "VEC3",
                      "min": pmin.tolist(), "max": pmax.tolist()})

    uv_view = add_view(guv.tobytes(), target=34962)
    accessors.append({"bufferView": uv_view, "componentType": 5126,
                      "count": int(guv.shape[0]), "type": "VEC2"})

    idx_view = add_view(tri.tobytes(), target=34963)
    accessors.append({"bufferView": idx_view, "componentType": 5125,
                      "count": int(tri.shape[0]), "type": "SCALAR"})

    img_view = add_view(jpeg)
    gltf = {
        "asset": {"version": "2.0", "generator": "sm_to_3dtiles"},
        "extensionsUsed": ["KHR_materials_unlit"],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": node_name}],
        "meshes": [{"primitives": [{
            "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
            "indices": 2,
            "material": 0,
        }]}],
        "materials": [{
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0.0,
                "roughnessFactor": 1.0,
            },
            "doubleSided": True,
            "extensions": {"KHR_materials_unlit": {}},
            "name": node_name,
        }],
        "textures": [{"sampler": 0, "source": 0}],
        "images": [{"bufferView": img_view, "mimeType": "image/jpeg"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987,
                      "wrapS": 10497, "wrapT": 10497}],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_buf)}],
    }
    return gltf, bin_buf


def convert(sm_path: str, out_dir: str, name: str, place: str = "") -> dict:
    conn = sqlite3.connect(sm_path)
    cur = conn.cursor()
    leaves = leaf_nodes(cur)
    ext = widest_extent(cur)
    ec, nc, zc = (ext[0] + ext[3]) / 2, (ext[1] + ext[4]) / 2, (ext[2] + ext[5]) / 2

    n_geoid = geoid_undulation(ec, nc, zc)
    lon0, lat0 = _T_LL.transform(ec, nc)
    h_ell0 = zc + n_geoid
    ox, oy, oz = _T_ECEF.transform(lon0, lat0, h_ell0)
    origin = np.array([ox, oy, oz])
    east, north, up = enu_basis(lon0, lat0)
    rot_t = np.vstack([east, north, up])  # rows = ENU axes; local = rot_t @ (ecef-O)

    tile_min = np.array([np.inf] * 3)
    tile_max = np.array([-np.inf] * 3)
    total_v = total_t = 0
    up_accum: list = []   # local ENU Up (elevation) of every vertex, for robust base
    children: list[dict] = []

    out_model = os.path.join(out_dir, name)
    if os.path.isdir(out_model):
        shutil.rmtree(out_model)
    nodes_dir = os.path.join(out_model, "nodes")
    os.makedirs(nodes_dir, exist_ok=True)

    for nid in leaves:
        cur.execute("SELECT PointData, IndexData FROM SMPoint WHERE NodeId=?", (nid,))
        point_data, index_data = cur.fetchone()
        verts = np.asarray(read_blob_doubles(point_data), dtype=np.float64).reshape(-1, 3)
        pos_idx = np.asarray(read_blob_uint32(index_data), dtype=np.int64) - 1  # ->0-based

        cur.execute("SELECT UVData, UVIndexData FROM SMUVs WHERE NodeId=?", (nid,))
        uv_data, uv_index_data = cur.fetchone()
        uvs = np.asarray(read_blob_uv(uv_data), dtype=np.float64).reshape(-1, 2)
        uv_idx = np.asarray(read_blob_uint32(uv_index_data), dtype=np.int64) - 1

        cur.execute("SELECT TexData FROM SMTexture WHERE NodeId=?", (nid,))
        jpeg = extract_jpeg(cur.fetchone()[0])

        # re-weld (pos, uv) corner pairs into unique glTF vertices
        pairs = np.stack([pos_idx, uv_idx], axis=1)
        uniq, inverse = np.unique(pairs, axis=0, return_inverse=True)
        up_pos = verts[uniq[:, 0]]            # (m,3) UTM
        up_uv = uvs[uniq[:, 1]]               # (m,2)
        tri = inverse.astype(np.uint32)       # one shared index array

        # UTM -> lon/lat -> ECEF -> local ENU
        lon, lat = _T_LL.transform(up_pos[:, 0], up_pos[:, 1])
        h = up_pos[:, 2] + n_geoid
        ex, ey, ez = _T_ECEF.transform(lon, lat, h)
        ecef = np.vstack([ex, ey, ez]).T
        local = (ecef - origin) @ rot_t.T     # (m,3) = (East, North, Up)
        tile_min = np.minimum(tile_min, local.min(axis=0))
        tile_max = np.maximum(tile_max, local.max(axis=0))

        # glTF is Y-up; Cesium rotates Y-up->Z-up, so store (East, Up, -North)
        gpos = np.empty_like(local, dtype=np.float32)
        gpos[:, 0] = local[:, 0]
        gpos[:, 1] = local[:, 2]
        gpos[:, 2] = -local[:, 1]
        guv = np.empty_like(up_uv, dtype=np.float32)
        guv[:, 0] = up_uv[:, 0]
        guv[:, 1] = 1.0 - up_uv[:, 1]         # glTF texcoord origin = top-left

        up_accum.append(gpos[:, 1].copy())   # gpos[:,1] = Up = elevation

        node_name = f"node_{nid}"
        node_uri = f"nodes/{node_name}.glb"
        gltf, leaf_bin = _build_leaf_glb(node_name, gpos, guv, tri, jpeg)
        _write_glb(os.path.join(out_model, node_uri), gltf, leaf_bin)

        leaf_min = local.min(axis=0)
        leaf_max = local.max(axis=0)
        leaf_center, leaf_radius = _sphere_from_bounds(leaf_min, leaf_max)
        children.append({
            "boundingVolume": {"sphere": [leaf_center[0], leaf_center[1], leaf_center[2], leaf_radius]},
            "geometricError": 0.0,
            "refine": "ADD",
            "content": {"uri": node_uri},
            "extras": {"nodeId": int(nid), "vertices": int(gpos.shape[0]), "triangles": int(tri.shape[0] // 3)},
        })

        total_v += int(gpos.shape[0])
        total_t += int(tri.shape[0] // 3)

    conn.close()

    # Robust local base/top elevation (Up axis) from percentiles, so isolated
    # outlier vertices (stray water / floating noise) do not drag the ground
    # anchor and leave the building hovering after terrain-snap.
    up_all = np.concatenate(up_accum)
    base_height_local = float(np.percentile(up_all, 1.0))
    top_height_local = float(np.percentile(up_all, 99.0))

    # tileset root transform: ENU local -> ECEF (column-major 4x4)
    transform = [
        east[0], east[1], east[2], 0.0,
        north[0], north[1], north[2], 0.0,
        up[0], up[1], up[2], 0.0,
        origin[0], origin[1], origin[2], 1.0,
    ]
    root_center, root_radius = _sphere_from_bounds(tile_min, tile_max, min_padding=10.0, padding_ratio=0.12)
    geo_err = float(root_radius * 2)

    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": geo_err,
        "root": {
            "transform": transform,
            "boundingVolume": {"sphere": [root_center[0], root_center[1], root_center[2], root_radius]},
            "geometricError": geo_err,
            "refine": "ADD",
            "children": children,
        },
    }
    with open(os.path.join(out_model, "tileset.json"), "w", encoding="utf-8") as f:
        json.dump(tileset, f, indent=2)

    project_root = os.path.dirname(os.path.abspath(out_dir))
    source_3sm = os.path.relpath(os.path.abspath(sm_path), project_root).replace(os.sep, "/")

    record = {
        "id": name,
        "name": name,
        "place": place,
        "source_3sm": source_3sm,
        "srs": "EPSG:32644+5773 (WGS84 / UTM zone 44N + EGM96 height)",
        "utm_zone": "44N",
        "centroid_utm": {"easting": ec, "northing": nc, "z_egm96": zc},
        "centroid_wgs84": {"lon": lon0, "lat": lat0,
                           "h_ellipsoidal": h_ell0, "geoid_undulation_egm96": n_geoid},
        "ecef_origin": {"x": ox, "y": oy, "z": oz},
        "bbox_local_enu_m": {"min": tile_min.tolist(), "max": tile_max.tolist()},
        "gltf_axis_order": "[East, Up, -North] (Y-up); elevation = index 1",
        "base_height_local_m": base_height_local,
        "top_height_local_m": top_height_local,
        "tile_layout": "per-leaf",
        "tile_count": len(children),
        "vertices": total_v,
        "triangles": total_t,
        "leaf_nodes": len(leaves),
        "georef_method": "drone-GPS (PositionMetadata), no GCP/RTK; "
                         "projection exact, absolute horizontal ~few m (drone-GPS), "
                         "vertical = EGM96 orthometric (~5-15 m absolute, terrain-snap in viewer)",
        "geoid_grid_applied": bool(abs(n_geoid) > 1e-6),
        "tileset": "tileset.json",
        "content": "nodes/*.glb",
    }
    with open(os.path.join(out_model, "model.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    print(f"[{name}] place={place or '?'}")
    print(f"  leaves={len(leaves)} verts={total_v:,} tris={total_t:,}")
    print(f"  centroid UTM44N = ({ec:.2f}, {nc:.2f}, {zc:.2f})  geoidN={n_geoid:.2f} m")
    print(f"  centroid WGS84  = lon {lon0:.6f}, lat {lat0:.6f}, h_ell {h_ell0:.2f}")
    tile_bytes = sum(os.path.getsize(os.path.join(root, file))
                     for root, _, files in os.walk(out_model) for file in files)
    print(f"  tiles = {out_model} ({len(children)} leaf GLBs, {tile_bytes/1024/1024:.1f} MB)")
    return record


def _write_glb(path: str, gltf: dict, bin_buf: bytearray) -> None:
    json_bytes = bytearray(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    while len(json_bytes) % 4:
        json_bytes.append(0x20)  # pad with spaces
    bin_bytes = bytearray(bin_buf)
    while len(bin_bytes) % 4:
        bin_bytes.append(0)
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with open(path, "wb") as f:
        f.write(b"glTF")
        f.write(struct.pack("<II", 2, total))
        f.write(struct.pack("<I", len(json_bytes)))
        f.write(b"JSON")
        f.write(json_bytes)
        f.write(struct.pack("<I", len(bin_bytes)))
        f.write(b"BIN\x00")
        f.write(bin_bytes)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert .3sm to 3D Tiles (GLB + tileset.json)")
    parser.add_argument("sm", help="path to the .3sm file")
    parser.add_argument("out", help="output root directory (a <name>/ subfolder is created)")
    parser.add_argument("name", help="model id/name, e.g. yellow_house")
    parser.add_argument("--place", default="", help="human-readable place label")
    args = parser.parse_args()
    convert(args.sm, args.out, args.name, args.place)
