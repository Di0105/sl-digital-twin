"""Export a Bentley iTwin Capture / ContextCapture Scalable Mesh (.3sm) to a
textured Wavefront OBJ in its native CRS.

The .3sm container is a SQLite database. Leaf nodes hold the full-resolution
mesh. Geometry vertices are stored as zlib-compressed absolute float64 X/Y/Z in
the master GCS (here WGS 84 / UTM zone 44N, EPSG:32644, height on a generic
geoid ~ EGM96). Triangle indices are zlib-compressed uint32. Texture
coordinates are zlib-compressed float32 (u, v) pairs with their own uint32
index array. Each node carries one JPEG texture atlas.

Output: <out_dir>/YellowHouse.obj + YellowHouse.mtl + textures/node<id>.jpg
Coordinates are written in absolute UTM 44N metres (full text precision), so the
result can be uploaded to Cesium ion with input SRS EPSG:32644 to be tiled into
3D Tiles with correct georeferencing.
"""

from __future__ import annotations

import os
import struct
import sqlite3
import zlib
from pathlib import Path


def read_blob_doubles(blob: bytes) -> tuple[float, ...]:
    raw = zlib.decompress(blob)
    return struct.unpack(f"<{len(raw) // 8}d", raw)


def read_blob_uint32(blob: bytes) -> tuple[int, ...]:
    raw = zlib.decompress(blob)
    return struct.unpack(f"<{len(raw) // 4}I", raw)


def read_blob_uv(blob: bytes) -> tuple[float, ...]:
    """UV coordinates are zlib-compressed float64 (u, v) pairs."""
    raw = zlib.decompress(blob)
    return struct.unpack(f"<{len(raw) // 8}d", raw)


def extract_jpeg(tex_data: bytes) -> bytes:
    start = tex_data.find(b"\xff\xd8\xff")
    end = tex_data.rfind(b"\xff\xd9")
    if start < 0 or end < 0:
        raise ValueError("no JPEG stream found in texture blob")
    return tex_data[start:end + 2]


def leaf_nodes(cur: sqlite3.Cursor) -> list[int]:
    cur.execute("SELECT NodeId, ParentNodeId FROM SMNodeHeader")
    rows = cur.fetchall()
    parents = {parent for _, parent in rows}
    return sorted(node for node, _ in rows if node not in parents)


def export(sm_path: str, out_dir: str, flip_v: bool = False) -> None:
    out = Path(out_dir)
    tex_dir = out / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(sm_path)
    cur = conn.cursor()
    leaves = leaf_nodes(cur)

    obj_path = out / "YellowHouse.obj"
    mtl_path = out / "YellowHouse.mtl"

    v_offset = 0
    vt_offset = 0
    min_xyz = [float("inf")] * 3
    max_xyz = [float("-inf")] * 3
    total_v = total_f = 0

    with open(obj_path, "w", encoding="ascii") as obj, \
            open(mtl_path, "w", encoding="ascii") as mtl:
        obj.write(f"mtllib {mtl_path.name}\n")
        obj.write("# CRS: EPSG:32644 (WGS84 / UTM zone 44N), Z on generic geoid (~EGM96)\n")

        for nid in leaves:
            cur.execute(
                "SELECT PointData, IndexData FROM SMPoint WHERE NodeId=?", (nid,))
            point_data, index_data = cur.fetchone()
            verts = read_blob_doubles(point_data)
            faces = read_blob_uint32(index_data)

            cur.execute(
                "SELECT UVData, UVIndexData FROM SMUVs WHERE NodeId=?", (nid,))
            uv_data, uv_index_data = cur.fetchone()
            uvs = read_blob_uv(uv_data)
            uv_faces = read_blob_uint32(uv_index_data)

            cur.execute(
                "SELECT TexID FROM SMNodeHeader WHERE NodeId=?", (nid,))
            row = cur.fetchone()
            tex_id = row[0] if row and row[0] is not None else nid
            cur.execute(
                "SELECT TexData FROM SMTexture WHERE NodeId=?", (tex_id,))
            tex_data = cur.fetchone()[0]
            tex_name = f"node{nid}.jpg"
            (tex_dir / tex_name).write_bytes(extract_jpeg(tex_data))

            mat = f"mat{nid}"
            mtl.write(f"newmtl {mat}\nKa 1 1 1\nKd 1 1 1\nd 1\n"
                      f"illum 1\nmap_Kd textures/{tex_name}\n\n")

            n_v = len(verts) // 3
            for i in range(0, len(verts), 3):
                x, y, z = verts[i], verts[i + 1], verts[i + 2]
                obj.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
                min_xyz = [min(min_xyz[0], x), min(min_xyz[1], y), min(min_xyz[2], z)]
                max_xyz = [max(max_xyz[0], x), max(max_xyz[1], y), max(max_xyz[2], z)]

            n_vt = len(uvs) // 2
            for i in range(0, len(uvs), 2):
                u, v = uvs[i], uvs[i + 1]
                obj.write(f"vt {u:.6f} {1.0 - v if flip_v else v:.6f}\n")

            obj.write(f"usemtl {mat}\n")
            # Source position and UV indices are both 1-based; offset by the
            # cumulative vertex/UV counts of previously written nodes.
            for t in range(0, len(faces), 3):
                a, b, c = faces[t] + v_offset, faces[t + 1] + v_offset, faces[t + 2] + v_offset
                ta = uv_faces[t] + vt_offset
                tb = uv_faces[t + 1] + vt_offset
                tc = uv_faces[t + 2] + vt_offset
                obj.write(f"f {a}/{ta} {b}/{tb} {c}/{tc}\n")

            v_offset += n_v
            vt_offset += n_vt
            total_v += n_v
            total_f += len(faces) // 3

    conn.close()
    print(f"leaf nodes exported : {len(leaves)}")
    print(f"vertices            : {total_v:,}")
    print(f"triangles           : {total_f:,}")
    print(f"bbox min (UTM 44N)  : {min_xyz}")
    print(f"bbox max (UTM 44N)  : {max_xyz}")
    print(f"size (m)            : "
          f"{max_xyz[0]-min_xyz[0]:.1f} x {max_xyz[1]-min_xyz[1]:.1f} x {max_xyz[2]-min_xyz[2]:.1f}")
    print(f"OBJ                 : {obj_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export .3sm scalable mesh to textured OBJ")
    parser.add_argument("sm", help="path to the .3sm file")
    parser.add_argument("out", help="output directory")
    parser.add_argument("--no-flip-v", action="store_true", help="do not flip V texture coordinate")
    args = parser.parse_args()
    export(args.sm, args.out, flip_v=not args.no_flip_v)
