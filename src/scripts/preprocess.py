import argparse, yaml, json
from pathlib import Path
import numpy as np, pandas as pd
import laspy
import rasterio
from pyproj import Transformer

def load_cfg(path): return yaml.safe_load(Path(path).read_text())

def read_laz_xyzi(laz_path):
    with laspy.open(laz_path) as fh:
        hdr = fh.header
        pts = fh.read()
    x, y, z = pts.x, pts.y, pts.z
    intensity = getattr(pts, "intensity", np.zeros_like(x))
    return np.vstack([x, y, z, intensity]).T

def normalize_z_with_dtm(xyz, dtm_path):
    with rasterio.open(dtm_path) as ds:
        # assume same CRS; for mismatched, add a transformer here
        rows, cols = ds.index(xyz[:,0], xyz[:,1])
        rows = np.clip(rows, 0, ds.height-1)
        cols = np.clip(cols, 0, ds.width-1)
        ground = ds.read(1)[rows, cols]
    z_norm = xyz[:,2] - ground
    return z_norm

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    args = ap.parse_args()
    cfg = load_cfg(args.cfg)
    out = Path(cfg["paths"]["out_root"]); out.mkdir(parents=True, exist_ok=True)

    laz = cfg["paths"]["als_laz"]; dtm = cfg["paths"]["dtm_tif"]
    XYZI = read_laz_xyzi(laz)
    ZN = normalize_z_with_dtm(XYZI[:,:3], dtm)
    df = pd.DataFrame({
        "x": XYZI[:,0], "y": XYZI[:,1], "z": XYZI[:,2],
        "z_norm": ZN, "intensity": XYZI[:,3]
    })
    # optional dev clip
    clip = cfg.get("preprocess",{}).get("clip_bbox")
    if clip:
        minx,miny,maxx,maxy = clip
        df = df[(df.x.between(minx,maxx)) & (df.y.between(miny,maxy))]
    # voxel-lite sample for quick iteration
    lite = df.sample(min(len(df), 500_000), random_state=42)
    df.to_parquet(out/"points.parquet", index=False)
    lite.to_parquet(out/"points_lite.parquet", index=False)
    (out/"preprocess_done.json").write_text(json.dumps({"count":len(df)}, indent=2))
    print("Preprocess OK:", len(df), "points")

if __name__=="__main__":
    main()