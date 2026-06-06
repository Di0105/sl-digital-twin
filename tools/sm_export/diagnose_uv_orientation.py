"""Decisive test: for each leaf GLB, sample its embedded atlas at every vertex UV
and report the fraction of vertices that land on near-black atlas pixels, for
BOTH the stored UV.v and the vertically-flipped (1-v) variant. Whichever variant
yields far LESS black tells us the correct texcoord orientation; a high black
fraction in both means the source faces genuinely point at empty atlas space."""
from __future__ import annotations

import json
import struct
import sys
import io
from pathlib import Path

import numpy as np
from PIL import Image


def read_glb(path: Path):
    data = path.read_bytes()
    _, _, _ = struct.unpack("<4sII", data[:12])
    off = 12
    json_obj = bin_chunk = None
    while off < len(data):
        clen, ctype = struct.unpack("<I4s", data[off:off + 8])
        body = data[off + 8: off + 8 + clen]
        if ctype == b"JSON":
            json_obj = json.loads(body.decode("utf-8"))
        elif ctype == b"BIN\x00":
            bin_chunk = body
        off += 8 + clen
    return json_obj, bin_chunk


def accessor_array(gltf, bin_chunk, idx):
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    comp = {5125: ("<u4", 4), 5126: ("<f4", 4)}[acc["componentType"]]
    ncol = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[acc["type"]]
    count = acc["count"]
    raw = bin_chunk[start:start + count * ncol * comp[1]]
    arr = np.frombuffer(raw, dtype=comp[0]).reshape(count, ncol)
    return arr


def sample_black_frac(atlas: np.ndarray, uv: np.ndarray) -> float:
    h, w = atlas.shape
    u = np.clip(uv[:, 0], 0, 1)
    v = np.clip(uv[:, 1], 0, 1)
    px = np.clip((u * (w - 1)).astype(int), 0, w - 1)
    py = np.clip((v * (h - 1)).astype(int), 0, h - 1)
    lum = atlas[py, px]
    return float((lum < 12).mean())


def main(model_dir: str):
    nodes = sorted(Path(model_dir, "nodes").glob("*.glb"))
    print(f"{'node':16} {'stored_v':>9} {'flip_v':>8}  verdict")
    worse = 0
    for n in nodes:
        gltf, bin_chunk = read_glb(n)
        # find TEXCOORD_0 accessor
        prim = gltf["meshes"][0]["primitives"][0]
        uv = accessor_array(gltf, bin_chunk, prim["attributes"]["TEXCOORD_0"]).astype(np.float32)
        img = gltf["images"][0]
        bv = gltf["bufferViews"][img["bufferView"]]
        start = bv.get("byteOffset", 0)
        jpeg = bin_chunk[start:start + bv["byteLength"]]
        atlas = np.asarray(Image.open(io.BytesIO(jpeg)).convert("L"), dtype=np.float32)
        bf_stored = sample_black_frac(atlas, uv)
        uv_flip = uv.copy()
        uv_flip[:, 1] = 1.0 - uv_flip[:, 1]
        bf_flip = sample_black_frac(atlas, uv_flip)
        verdict = "stored OK" if bf_stored <= bf_flip else "FLIP BETTER"
        if bf_stored > bf_flip + 0.05:
            worse += 1
        print(f"{n.name:16} {bf_stored*100:8.1f}% {bf_flip*100:7.1f}%  {verdict}")
    print(f"\nleaves where flipping V would reduce black by >5%: {worse}/{len(nodes)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"e:\sl output\1\tiles\yellow_house")
