import argparse, yaml
from pathlib import Path
import pandas as pd
import numpy as np
import torch

def load_cfg(p): return yaml.safe_load(Path(p).read_text())

def train_stub(points_path, out_dir):
    # Dummy “training” — we save class priors to emulate a trained model
    df = pd.read_parquet(points_path)
    priors = {"ground":0.7, "tower":0.15, "wire":0.15}
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out/"best.pt").write_text(str(priors))
    print("Saved stub checkpoint:", out/"best.pt")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    args = ap.parse_args()
    cfg = load_cfg(args.cfg)
    out = Path(cfg["paths"]["out_root"])/"checkpoints"
    arch = cfg["model"]["arch"].lower()
    points = Path(cfg["paths"]["out_root"])/"points_lite.parquet"
    if arch == "stub":
        train_stub(points, out)
    else:
        print(f"[TODO] Train real model: {arch}")
        train_stub(points, out)  # fallback so pipeline continues

if __name__=="__main__":
    main()
