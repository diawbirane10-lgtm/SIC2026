from __future__ import annotations

import argparse
import csv
import hashlib
import random
from pathlib import Path

from PIL import Image

EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
EXCLUDED_POSITIVE_PARTS = {'ground_truth', 'ground-truth', 'mask', 'masks', 'annotations', 'annotation'}


def images_under(root: Path, *, exclude_parts: set[str] | None = None):
    excluded = {p.lower() for p in (exclude_parts or set())}
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        lowered_parts = {part.lower() for part in p.parts}
        if lowered_parts & excluded:
            continue
        try:
            with Image.open(p) as im:
                if im.width >= 128 and im.height >= 128:
                    yield p
        except Exception:
            continue


def stable_sample(paths, n, seed):
    paths = sorted(set(paths), key=lambda p: str(p))
    rng = random.Random(seed)
    rng.shuffle(paths)
    return paths[: min(n, len(paths))]


def pseudo_group(path: Path, source: str) -> str:
    # Conservative fallback when the public dataset does not expose video/session IDs.
    # Near-duplicate grouping is performed later by t03_scene_gate.py using perceptual hashes.
    digest = hashlib.sha1(f'{source}:{path.name}'.encode()).hexdigest()[:10]
    return f'{source}:{digest}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--coal-root', type=Path, required=True)
    ap.add_argument('--negative-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--max-positive', type=int, default=180)
    ap.add_argument('--max-negative', type=int, default=300)
    ap.add_argument('--seed', type=int, default=2026)
    args = ap.parse_args()

    # IMPORTANT: CoalAD ground_truth contains segmentation masks, not camera scenes.
    # Including them as positives creates a trivial dataset-source shortcut and invalidates
    # the scene-gate evaluation. Only actual camera images are eligible here.
    pos = stable_sample(
        list(images_under(args.coal_root, exclude_parts=EXCLUDED_POSITIVE_PARTS)),
        args.max_positive,
        args.seed,
    )
    neg = stable_sample(list(images_under(args.negative_root)), args.max_negative, args.seed + 1)
    if len(pos) < 40 or len(neg) < 80:
        raise RuntimeError(f'Not enough usable images: positive={len(pos)}, negative={len(neg)}')
    if any('ground_truth' in {part.lower() for part in p.parts} for p in pos):
        raise RuntimeError('Dataset contamination: CoalAD ground_truth mask entered positive scenes')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in pos:
        rows.append({
            'image_path': str(p),
            'label': 'conveyor_applicable',
            'source': 'CoalAD-camera-only',
            'group': pseudo_group(p, 'coalad'),
            'license_note': 'CoalAD official repository/source; camera images only; verify dataset terms before redistribution',
        })
    for p in neg:
        rows.append({
            'image_path': str(p),
            'label': 'non_conveyor',
            'source': 'Imagenette-160-hard-negative',
            'group': pseudo_group(p, 'imagenette'),
            'license_note': 'Imagenette (fastai), ImageNet-derived evaluation/training images; source terms retained',
        })

    with args.out.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print({'manifest': str(args.out), 'positive': len(pos), 'negative': len(neg), 'total': len(rows)})


if __name__ == '__main__':
    main()
