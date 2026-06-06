"""Patch every per-leaf GLB sampler in tiles/*/nodes/*.glb to stop the sparse
ContextCapture texture atlas from bleeding to black.

ContextCapture node atlases pack small texture patches over a black background.
With LINEAR_MIPMAP_LINEAR minification the coarse mip levels average each patch
with its surrounding black, so textured roofs/walls turn dark/black at any
non-extreme zoom. Switching to LINEAR (no mipmaps) samples the full-resolution
atlas directly, keeping surfaces textured. REPEAT->CLAMP_TO_EDGE avoids wrapping
the patch edge into the opposite black margin.

All three substitutions are the same byte length as the originals, so the GLB
JSON chunk length and overall structure stay valid without re-packing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENTS = [
    (b'"minFilter":9987', b'"minFilter":9729'),   # LINEAR_MIPMAP_LINEAR -> LINEAR
    (b'"wrapS":10497', b'"wrapS":33071'),          # REPEAT -> CLAMP_TO_EDGE
    (b'"wrapT":10497', b'"wrapT":33071'),
]


def patch_file(path: Path) -> bool:
    data = path.read_bytes()
    out = data
    for old, new in REPLACEMENTS:
        assert len(old) == len(new), f"length mismatch {old!r}->{new!r}"
        out = out.replace(old, new)
    if out != data:
        assert len(out) == len(data), "patched GLB changed size"
        path.write_bytes(out)
        return True
    return False


def main(tiles_root: str):
    root = Path(tiles_root)
    glbs = sorted(root.glob("*/nodes/*.glb"))
    changed = 0
    for g in glbs:
        if patch_file(g):
            changed += 1
    print(f"scanned {len(glbs)} GLBs, patched {changed}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"e:\sl output\1\tiles")
