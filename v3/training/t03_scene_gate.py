from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import imagehash
import joblib
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torchvision import transforms

MODEL_ID = 'facebookresearch/dinov2:dinov2_vitl14_reg'
BACKBONE_NAME = 'DINOv2 ViT-L/14 with registers'


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def read_manifest(path: Path):
    with path.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError('empty manifest')
    for r in rows:
        if r['label'] not in {'conveyor_applicable', 'non_conveyor'}:
            raise ValueError(r['label'])
        if not Path(r['image_path']).exists():
            raise FileNotFoundError(r['image_path'])
    return rows


def perceptual_groups(rows, max_hamming=4):
    hashes = []
    for i, r in enumerate(rows):
        with Image.open(r['image_path']) as im:
            hashes.append(imagehash.phash(im.convert('RGB')))
        if (i + 1) % 50 == 0:
            print(f'pHash {i+1}/{len(rows)}')
    uf = UnionFind(len(rows))
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            # Only merge near duplicates inside the same semantic class.
            if rows[i]['label'] == rows[j]['label'] and hashes[i] - hashes[j] <= max_hamming:
                uf.union(i, j)
    roots = {}
    out = []
    for i, r in enumerate(rows):
        root = uf.find(i)
        roots.setdefault((r['label'], root), len(roots))
        out.append(f"{r['label']}:{roots[(r['label'], root)]:04d}")
    return out


def split_groupwise(rows, groups, seed=2026):
    rng = np.random.default_rng(seed)
    split = np.empty(len(rows), dtype=object)
    for label in ('conveyor_applicable', 'non_conveyor'):
        idx = np.array([i for i, r in enumerate(rows) if r['label'] == label])
        unique = np.array(sorted(set(groups[i] for i in idx)))
        if len(unique) < 6:
            raise RuntimeError(f'Not enough deduplicated groups for {label}: {len(unique)}')
        rng.shuffle(unique)
        ntr = max(1, int(round(len(unique) * .70)))
        nva = max(1, int(round(len(unique) * .15)))
        train_g = set(unique[:ntr])
        val_g = set(unique[ntr:ntr+nva])
        test_g = set(unique[ntr+nva:])
        if not test_g:
            test_g = {unique[-1]}; val_g.discard(unique[-1])
        for i in idx:
            split[i] = 'train' if groups[i] in train_g else 'val' if groups[i] in val_g else 'test'
    return split


def preprocess():
    return transforms.Compose([
        transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])


def extract(rows, device, batch_size, cache: Path):
    if cache.exists():
        d = np.load(cache, allow_pickle=False)
        if list(d['paths'].astype(str)) == [r['image_path'] for r in rows]:
            print('Using cached embeddings')
            return d['X'], int(d['parameters'])

    model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitl14_reg', trust_repo=True).to(device).eval()
    params = int(sum(p.numel() for p in model.parameters()))
    print(f'{BACKBONE_NAME}: {params:,} parameters on {device}')
    tfm = preprocess()
    chunks = []
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            batch = []
            for r in rows[start:start+batch_size]:
                with Image.open(r['image_path']) as im:
                    batch.append(tfm(im.convert('RGB')))
            x = torch.stack(batch).to(device)
            z = model(x)
            if isinstance(z, dict):
                z = z.get('x_norm_clstoken') or z.get('x_prenorm')
            chunks.append(z.float().cpu().numpy())
            print(f'embedded {min(start+batch_size, len(rows))}/{len(rows)}')
    X = np.concatenate(chunks)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, X=X, paths=np.array([r['image_path'] for r in rows]), parameters=params)
    return X, params


def choose_threshold(y, p, max_fpr=.01):
    candidates = np.unique(np.concatenate([np.linspace(.50, .995, 100), p]))
    feasible = []
    for t in candidates:
        pred = p >= t
        neg = y == 0
        pos = y == 1
        fpr = float(pred[neg].mean()) if neg.any() else 1.0
        rec = float(pred[pos].mean()) if pos.any() else 0.0
        if fpr <= max_fpr:
            feasible.append((rec, -t, t, fpr))
    if not feasible:
        return .995
    feasible.sort(reverse=True)
    return float(feasible[0][2])


def metrics(y, p, threshold):
    pred = (p >= threshold).astype(int)
    neg = y == 0
    fpr = float(pred[neg].mean()) if neg.any() else math.nan
    return {
        'balanced_accuracy': float(balanced_accuracy_score(y, pred)),
        'f1': float(f1_score(y, pred, zero_division=0)),
        'precision': float(precision_score(y, pred, zero_division=0)),
        'conveyor_recall': float(recall_score(y, pred, zero_division=0)),
        'false_conveyor_accept_rate': fpr,
        'roc_auc': float(roc_auc_score(y, p)),
        'brier': float(brier_score_loss(y, p)),
        'confusion_matrix': confusion_matrix(y, pred, labels=[0,1]).tolist(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--outdir', type=Path, default=Path('artifacts/t03a0'))
    ap.add_argument('--batch-size', type=int, default=2)
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--allow-cpu', action='store_true')
    args = ap.parse_args()
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cpu' and not args.allow_cpu:
        raise RuntimeError('Final T03 candidate requires CUDA; --allow-cpu is bootstrap only.')

    rows = read_manifest(args.manifest)
    groups = perceptual_groups(rows)
    splits = split_groupwise(rows, groups, args.seed)
    y = np.array([1 if r['label'] == 'conveyor_applicable' else 0 for r in rows], dtype=int)
    args.outdir.mkdir(parents=True, exist_ok=True)
    X, parameters = extract(rows, device, args.batch_size, args.outdir / 'embeddings.npz')

    tr = np.flatnonzero(splits == 'train')
    va = np.flatnonzero(splits == 'val')
    te = np.flatnonzero(splits == 'test')
    if min(len(tr), len(va), len(te)) == 0:
        raise RuntimeError({'train':len(tr),'val':len(va),'test':len(te)})

    head = Pipeline([
        ('scale', StandardScaler()),
        ('clf', LogisticRegression(C=.35, class_weight='balanced', max_iter=3000, random_state=args.seed)),
    ])
    head.fit(X[tr], y[tr])
    p_val = head.predict_proba(X[va])[:,1]
    threshold = choose_threshold(y[va], p_val, max_fpr=.01)
    p_test = head.predict_proba(X[te])[:,1]
    m = metrics(y[te], p_test, threshold)

    report = {
        'run_id': 'FLOWTRUST-T03-A0-REAL-SCENE-GATE',
        'date': '2026-08-13',
        'device': device,
        'tier': 'candidate_gpu' if device == 'cuda' else 'cpu_bootstrap',
        'backbone': BACKBONE_NAME,
        'backbone_parameters': parameters,
        'backbone_pretraining': 'DINOv2 LVD-142M (Meta pretrained weights)',
        'task': 'conveyor_applicable vs non_conveyor scene gate',
        'split': '70/15/15 after perceptual near-duplicate grouping (pHash Hamming <=4)',
        'counts': {'train':int(len(tr)), 'validation':int(len(va)), 'test':int(len(te))},
        'acceptance_threshold': threshold,
        'validation_target': 'choose threshold with <=1% false conveyor accepts on validation when feasible',
        'closed_test': m,
        'gates': {
            'false_conveyor_accept_rate_le_0_02': bool(m['false_conveyor_accept_rate'] <= .02),
            'conveyor_recall_ge_0_90': bool(m['conveyor_recall'] >= .90),
            'brier_le_0_12': bool(m['brier'] <= .12),
        },
    }
    report['statistical_gate_passed'] = all(report['gates'].values())
    report['integration_gate_passed'] = bool(report['statistical_gate_passed'] and device == 'cuda')
    if device != 'cuda':
        report['integration_block_reason'] = 'CPU bootstrap only; unchanged closed-test protocol must pass on CUDA before production integration.'

    joblib.dump({'head':head,'threshold':threshold,'backbone':'dinov2_vitl14_reg','parameters':parameters}, args.outdir/'scene_gate_head.joblib')
    with (args.outdir/'closed_test_predictions.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['image_path','source','truth','probability_conveyor','prediction','group'])
        for i, p in zip(te, p_test):
            w.writerow([rows[i]['image_path'], rows[i]['source'], rows[i]['label'], float(p), 'conveyor_applicable' if p >= threshold else 'non_conveyor', groups[i]])
    (args.outdir/'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
