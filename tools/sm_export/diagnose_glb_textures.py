"""Read-only: extract the embedded JPEG from each per-leaf GLB and report its
mean luminance, so we can tell whether 'black' leaves are caused by dark/empty
texture atlases (vs a geometry/UV problem). Saves the darkest atlas as PNG."""
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
    assert data[:4] == b"glTF", f"{path} not a GLB"
    _, _, total = struct.unpack("<4sII", data[:12])
    off = 12
    json_obj = None
    bin_chunk = None
    while off < len(data):
        clen, ctype = struct.unpack("<I4s", data[off:off + 8])
        body = data[off + 8: off + 8 + clen]
        if ctype == b"JSON":
            json_obj = json.loads(body.decode("utf-8"))
        elif ctype == b"BIN\x00":
            bin_chunk = body
        off += 8 + clen
    return json_obj, bin_chunk


def main(model_dir: str):
    nodes = sorted(Path(model_dir, "nodes").glob("*.glb"))
    rows = []
    darkest = None
    for n in nodes:
        gltf, bin_chunk = read_glb(n)
        img = gltf["images"][0]
        bv = gltf["bufferViews"][img["bufferView"]]
        start = bv.get("byteOffset", 0)
        jpeg = bin_chunk[start:start + bv["byteLength"]]
        im = Image.open(io.BytesIO(jpeg)).convert("L")
        arr = np.asarray(im, dtype=np.float32)
        mean = float(arr.mean())
        # fraction of near-black pixels
        black_frac = float((arr < 12).mean())
        rows.append((n.name, im.size, mean, black_frac, len(jpeg)))
        if darkest is None or mean < darkest[1]:
            darkest = (n.name, mean, jpeg)
    rows.sort(key=lambda r: r[2])
    print(f"model: {model_dir}  leaves: {len(rows)}")
    print(f"{'node':18} {'size':>12} {'meanL':>7} {'black%':>7} {'jpegKB':>7}")
    for name, size, mean, bf, nb in rows:
        print(f"{name:18} {str(size):>12} {mean:7.1f} {bf*100:6.1f}% {nb/1024:7.1f}")
    if darkest:
        out = Path(model_dir, f"_darkest_{darkest[0]}.png")
        Image.open(io.BytesIO(darkest[2])).save(out)
        print(f"\nsaved darkest atlas ({darkest[0]}, meanL={darkest[1]:.1f}) -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"e:\sl output\1\tiles\yellow_house")
