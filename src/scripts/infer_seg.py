import argparse, yaml
from pathlib import Path
import pandas as pd
import numpy as np

def load_cfg(p): 
    import yaml; from pathlib import Path
    return yaml.safe_load(Path(p).read_text())

def infer_stub(df):
    # Simple heuristic: very low z_norm -> ground; thin high -> wire; else tower-ish
    labels = np.zeros(len(df), dtype=np.int32)
    labels[df["z_norm"] < 0.5] = 0
    high = df["z_norm"] >= 8.0
    # thin “wire-like” by intensity + local density proxy
    wire_like = high & (df["intensity"] < np.percentile(df["intensity"], 40))
    labels[wire_like] = 2   # wire
    labels[(labels==0) | (labels==2) == False] = 1  # tower/other
    return labels

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--ckpt", required=False)
    args = ap.parse_args()
    cfg = load_cfg(args.cfg)
    out_root = Path(cfg["paths"]["out_root"]); out_root.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(out_root/"points_lite.parquet")
    df["label"] = infer_stub(df)
    pred_path = out_root/"preds"; pred_path.mkdir(exist_ok=True)
    df.to_parquet(pred_path/"labeled_points.parquet", index=False)
    print("Wrote", pred_path/"labeled_points.parquet")

if __name__=="__main__":
    main()
