from __future__ import annotations

import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_REGISTRY = ROOT / "v2" / "config" / "model_registry.json"
DATA_REGISTRY = ROOT / "v2" / "config" / "data_registry.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    models = load_json(MODEL_REGISTRY)
    data = load_json(DATA_REGISTRY)

    print("FLOWTRUST-AFR V2 — Training 01 preflight")
    print("Date: 2026-08-12")
    print(f"Python platform: {platform.platform()}")
    print(f"Models registered: {len(models['models'])}")
    print(f"Datasets registered: {len(data['datasets'])}")

    numeric_params = [
        m["parameters"]
        for m in models["models"]
        if isinstance(m.get("parameters"), int)
    ]
    print(f"Largest selected model: {max(numeric_params)/1e6:.0f}M parameters")
    print(f"Total parameters across independent selected foundations: {sum(numeric_params)/1e9:.2f}B")
    print("NOTE: models are independent specialists; their parameter counts are not summed into one monolithic network.")

    try:
        import torch
    except ImportError:
        print("PyTorch: NOT INSTALLED")
        print("Install requirements-v2.txt on a GPU runner before training.")
        return 2

    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        print(f"GPU count: {count}")
        for i in range(count):
            props = torch.cuda.get_device_properties(i)
            print(f"GPU {i}: {props.name} — {props.total_memory/1024**3:.1f} GiB")
        print("READY FOR GPU EXPERIMENTS")
        return 0

    print("NO CUDA GPU DETECTED")
    print("Registry/data preparation can run here, but do not claim 100M+ fine-tuning as completed.")
    print("Recommended Training 01 execution target: NVIDIA GPU with 24–48+ GiB VRAM; SAM3.1 full tuning may require more or multi-GPU.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
