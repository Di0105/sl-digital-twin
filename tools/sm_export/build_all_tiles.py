"""Batch-convert the four distinct Sri Lanka reality-mesh sites to 3D Tiles and
emit a consolidated registry the Resium app consumes."""

from __future__ import annotations

import json
import os

from sm_to_3dtiles import convert

ROOT = r"e:\sl output\1"
PRODUCTIONS = os.path.join(ROOT, "Productions")
OUT = os.path.join(ROOT, "tiles")

MODELS = [
    ("yellow_house", os.path.join(PRODUCTIONS, "YELLOWHOUSE_FINAL2", "YELLOWHOUSE_FINAL2.3sm"),
     "Yellow House", "Galle Dutch Fort"),
    ("church", os.path.join(ROOT, "church_final", "Production_3.3sm"),
     "Galle Fort Church", "Galle Dutch Fort"),
    ("lighthouse", os.path.join(PRODUCTIONS, "Production_2_Trial", "Production_2_Trial.3sm"),
     "Galle Lighthouse", "Galle Dutch Fort"),
    ("university", os.path.join(PRODUCTIONS, "university_new", "Production_1.3sm"),
     "University (Peradeniya area)", "Kandy region"),
]


def main() -> None:
    registry = []
    for mid, sm_path, label, region in MODELS:
        rec = convert(sm_path, OUT, mid, place=f"{label}, {region}")
        rec["label"] = label
        rec["region"] = region
        registry.append(rec)
        print()

    with open(os.path.join(OUT, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
    print(f"registry -> {os.path.join(OUT, 'registry.json')}  ({len(registry)} models)")


if __name__ == "__main__":
    main()
