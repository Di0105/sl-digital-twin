"""Read-only: count JPEG streams per leaf texture and dump a few to disk so we
can see whether extract_jpeg is merging multiple streams (garbled texture)."""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sm_to_obj import leaf_nodes  # noqa: E402


def jpeg_spans(blob: bytes):
    """Return list of (start, end) for every SOI..EOI JPEG in the blob."""
    spans = []
    i = 0
    n = len(blob)
    while True:
        s = blob.find(b"\xff\xd8\xff", i)
        if s < 0:
            break
        e = blob.find(b"\xff\xd9", s + 3)
        if e < 0:
            break
        spans.append((s, e + 2))
        i = e + 2
    return spans


def analyse(sm_path: str, dump_dir: str | None = None) -> None:
    conn = sqlite3.connect(sm_path)
    cur = conn.cursor()
    leaves = leaf_nodes(cur)
    counts = {}
    first_dumped = 0
    for nid in leaves:
        cur.execute("SELECT TexData FROM SMTexture WHERE NodeId=?", (nid,))
        row = cur.fetchone()
        if not row or row[0] is None:
            counts[0] = counts.get(0, 0) + 1
            continue
        blob = row[0]
        spans = jpeg_spans(blob)
        counts[len(spans)] = counts.get(len(spans), 0) + 1
        tail = len(blob) - (spans[-1][1] if spans else 0)
        if dump_dir and first_dumped < 3 and spans:
            os.makedirs(dump_dir, exist_ok=True)
            s, e = spans[0]
            with open(os.path.join(dump_dir, f"node{nid}_first.jpg"), "wb") as f:
                f.write(blob[s:e])
            # what extract_jpeg currently returns (first SOI .. last EOI)
            with open(os.path.join(dump_dir, f"node{nid}_extract.jpg"), "wb") as f:
                f.write(blob[blob.find(b"\xff\xd8\xff"): blob.rfind(b"\xff\xd9") + 2])
            first_dumped += 1
            print(f"  node {nid}: {len(spans)} jpeg stream(s), blob {len(blob):,} B, "
                  f"trailing {tail} B, first stream {e - s:,} B")
    conn.close()
    print(f"file: {sm_path}")
    print(f"  leaves: {len(leaves)}  jpeg-stream-count histogram: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    analyse(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
