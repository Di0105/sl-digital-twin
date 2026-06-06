"""Save the embedded atlas of specific leaf GLBs as PNG for visual inspection."""
import json, struct, sys, io
from pathlib import Path
from PIL import Image


def read_glb(path: Path):
    data = path.read_bytes()
    off = 12
    j = b = None
    while off < len(data):
        clen, ctype = struct.unpack("<I4s", data[off:off + 8])
        body = data[off + 8: off + 8 + clen]
        if ctype == b"JSON":
            j = json.loads(body.decode("utf-8"))
        elif ctype == b"BIN\x00":
            b = body
        off += 8 + clen
    return j, b


def dump(model_dir: str, node_names: list[str]):
    for nm in node_names:
        p = Path(model_dir, "nodes", nm)
        g, b = read_glb(p)
        img = g["images"][0]
        bv = g["bufferViews"][img["bufferView"]]
        s = bv.get("byteOffset", 0)
        jpeg = b[s:s + bv["byteLength"]]
        out = Path(model_dir, f"_atlas_{nm}.png")
        Image.open(io.BytesIO(jpeg)).save(out)
        print(f"{nm} -> {out}")


if __name__ == "__main__":
    md = r"e:\sl output\1\tiles\yellow_house"
    dump(md, ["node_25.glb", "node_27.glb", "node_30.glb"])
