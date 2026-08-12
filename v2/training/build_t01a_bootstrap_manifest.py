from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect_images(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def add_chunked(rows, paths, label, source, license_name, chunk_size):
    for i, path in enumerate(paths):
        group = f"{source}:{i // chunk_size:05d}"
        rows.append({
            "image_path": str(path.resolve()),
            "label": label,
            "group": group,
            "source": source,
            "license": license_name,
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--positive-root", type=Path, help="Root containing real conveyor-scene images")
    ap.add_argument("--coalad", type=Path, help="Backward-compatible alias for --positive-root")
    ap.add_argument("--positive-source", default="coalad_2026")
    ap.add_argument("--positive-license", default="dataset_terms_upstream")
    ap.add_argument("--negative-root", type=Path, required=True, help="High-resolution non-conveyor images")
    ap.add_argument("--out", type=Path, default=Path("data/manifests/t01a_bootstrap.csv"))
    ap.add_argument("--max-positive", type=int, default=3500)
    ap.add_argument("--max-negative", type=int, default=3500)
    ap.add_argument("--positive-chunk", type=int, default=40, help="Approximate sequential-frame/waypoint group size")
    ap.add_argument("--negative-chunk", type=int, default=20)
    args = ap.parse_args()

    positive_root = args.positive_root or args.coalad
    if positive_root is None:
        raise ValueError("Provide --positive-root (or legacy --coalad)")

    positive = collect_images(positive_root)
    positive = [p for p in positive if "ground_truth" not in {x.lower() for x in p.parts}]
    positive = [p for p in positive if "_mask" not in p.stem.lower()]
    negative = collect_images(args.negative_root)

    if not positive:
        raise RuntimeError(f"No positive conveyor images under {positive_root}")
    if not negative:
        raise RuntimeError(f"No negative images under {args.negative_root}")

    def spread(items, limit):
        if len(items) <= limit:
            return items
        step = len(items) / limit
        return [items[int(i * step)] for i in range(limit)]

    positive = spread(positive, args.max_positive)
    negative = spread(negative, args.max_negative)

    rows = []
    add_chunked(
        rows,
        positive,
        "conveyor_applicable",
        args.positive_source,
        args.positive_license,
        args.positive_chunk,
    )
    add_chunked(
        rows,
        negative,
        "non_industrial",
        "coco2017_val_hard_negative",
        "per-image COCO/Flickr terms; evaluation/training only, not redistributed",
        args.negative_chunk,
    )

    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    print(df.groupby(["source", "label"]).size())
    print(f"manifest={args.out} rows={len(df)} groups={df.group.nunique()}")


if __name__ == "__main__":
    main()
