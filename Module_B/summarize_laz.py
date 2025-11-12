"""
summarize_laz.py
----------------
Windows-friendly LAZ inspector. Reads a .laz (or .las) file and produces:
 - Console summary (pretty print)
 - JSON summary (metadata + stats)
 - CSV dimension coverage table (which attributes exist)
 - CSV classification histogram (if classification dimension exists)
 - Optional sample PLY export (for quick visualization apps)

Dependencies:
  pip install "laspy[lazrs]" numpy

Usage:
  py summarize_laz.py --input data\\ALS\\point_cloud.laz
  py summarize_laz.py --input point_cloud.laz --out outdir --sample-ply 100000

Author: Kirtikumar Anandrao Ramchandani
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

import numpy as np
import laspy


def human(n: float) -> str:
    """Human-friendly number formatting."""
    if n >= 1e9: return f"{n/1e9:.2f} B"
    if n >= 1e6: return f"{n/1e6:.2f} M"
    if n >= 1e3: return f"{n/1e3:.2f} K"
    return f"{n:.0f}"


def has_dim(las, name: str) -> bool:
    """Check if dimension exists in LAS/LAZ file."""
    try:
        _ = las[name]
        return True
    except Exception:
        return False


def array_or_none(las, name):
    try:
        return las[name]
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Summarize a LAZ/LAS file and export stats.")
    parser.add_argument("--input", "-i", required=True, help="Path to .laz or .las (e.g., data\\ALS\\point_cloud.laz)")
    parser.add_argument("--out", "-o", default="outputs", help="Output directory (default: outputs)")
    parser.add_argument("--sample-ply", type=int, default=0,
                        help="If >0, write a random sample of N points to PLY for quick preview.")
    args = parser.parse_args()

    in_path = args.input
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    # Read point cloud
    try:
        las = laspy.read(in_path)
    except Exception as e:
        print(f"[ERROR] Could not read {in_path}: {e}")
        print("Tip: Ensure 'laspy[lazrs]' is installed for LAZ support.")
        sys.exit(1)

    # Header/basic info
    header = las.header
    point_count = len(las.x)
    has_rgb = all(has_dim(las, d) for d in ("red", "green", "blue"))
    has_intensity = has_dim(las, "intensity")
    has_class = has_dim(las, "classification")
    has_returns = has_dim(las, "return_number")

    # Bounds (double-check via numpy for safety)
    x = np.asarray(las.x)
    y = np.asarray(las.y)
    z = np.asarray(las.z)

    minx, maxx = float(np.min(x)), float(np.max(x))
    miny, maxy = float(np.min(y)), float(np.max(y))
    minz, maxz = float(np.min(z)), float(np.max(z))

    # Spatial reference (CRS) if present
    crs_wkt = None
    try:
        if header.parse_crs() is not None:
            crs = header.parse_crs()
            crs_wkt = crs.to_wkt()
    except Exception:
        crs_wkt = None

    # Approximate area + density (using bounding box area; conservative lower bound)
    width = maxx - minx
    height = maxy - miny
    bbox_area_m2 = float(width * height) if width > 0 and height > 0 else None
    density_pts_per_m2 = (point_count / bbox_area_m2) if bbox_area_m2 else None

    # Classification histogram (if available)
    class_hist = {}
    if has_class:
        cls_vals = np.asarray(las.classification)
        unique, counts = np.unique(cls_vals, return_counts=True)
        for c, k in zip(unique.tolist(), counts.tolist()):
            class_hist[int(c)] = int(k)

    # Return number histogram (if available)
    return_hist = {}
    if has_returns:
        rn = np.asarray(las.return_number)
        unique, counts = np.unique(rn, return_counts=True)
        for c, k in zip(unique.tolist(), counts.tolist()):
            return_hist[int(c)] = int(k)

    # Dimension presence table
    dims_to_check = [
        "x", "y", "z",
        "intensity",
        "red", "green", "blue",
        "classification",
        "return_number", "number_of_returns",
        "scan_angle", "gps_time", "user_data", "point_source_id"
    ]
    dim_presence = []
    for d in dims_to_check:
        dim_presence.append({"dimension": d, "present": has_dim(las, d)})

    # Build summary JSON
    summary = {
        "input_file": os.path.abspath(in_path),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "point_count": point_count,
        "bounds": {
            "minx": minx, "maxx": maxx,
            "miny": miny, "maxy": maxy,
            "minz": minz, "maxz": maxz
        },
        "bbox_area_m2": bbox_area_m2,
        "density_pts_per_m2_estimate": density_pts_per_m2,
        "has_rgb": has_rgb,
        "has_intensity": has_intensity,
        "has_classification": has_class,
        "has_returns": has_returns,
        "crs_wkt": crs_wkt,
        "classification_histogram": class_hist if class_hist else None,
        "return_number_histogram": return_hist if return_hist else None
    }

    # Write JSON summary
    json_path = os.path.join(out_dir, "point_cloud_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] JSON summary: {json_path}")

    # Write dimension coverage CSV
    dims_csv = os.path.join(out_dir, "dimensions_coverage.csv")
    with open(dims_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dimension", "present"])
        w.writeheader()
        for row in dim_presence:
            w.writerow(row)
    print(f"[OK] Dimensions CSV: {dims_csv}")

    # Write classification histogram CSV (if present)
    if class_hist:
        cls_csv = os.path.join(out_dir, "classification_histogram.csv")
        with open(cls_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["class_code", "count"])
            for k in sorted(class_hist.keys()):
                w.writerow([k, class_hist[k]])
        print(f"[OK] Classification histogram CSV: {cls_csv}")

    # Friendly console print
    print("\n=== LAZ / LAS SUMMARY ===")
    print(f"File: {os.path.abspath(in_path)}")
    print(f"Points: {human(point_count)}  ({point_count})")
    print(f"Bounds X: [{minx:.3f}, {maxx:.3f}]  Δ={width:.3f} m")
    print(f"Bounds Y: [{miny:.3f}, {maxy:.3f}]  Δ={height:.3f} m")
    print(f"Bounds Z: [{minz:.3f}, {maxz:.3f}]  Δ={maxz-minz:.3f} m")
    if bbox_area_m2:
        print(f"BBox area: {bbox_area_m2:.2f} m²")
    if density_pts_per_m2:
        print(f"Est. density: {density_pts_per_m2:.2f} pts/m² (bbox-based)")
    print(f"Has RGB: {has_rgb}  Has Intensity: {has_intensity}  Has Classification: {has_class}  Has Returns: {has_returns}")
    print(f"CRS WKT present: {crs_wkt is not None}")

    if class_hist:
        print("Class histogram (code: count):")
        line = ", ".join([f"{k}:{v}" for k, v in sorted(class_hist.items())])
        print("  " + line)

    if return_hist:
        print("Return-number histogram (n: count):")
        line = ", ".join([f"{k}:{v}" for k, v in sorted(return_hist.items())])
        print("  " + line)

    # Optional: write a sampled PLY for quick visualization
    if args.sample_ply and args.sample_ply > 0:
        n = min(args.sample_ply, point_count)
        idx = np.random.default_rng(42).choice(point_count, size=n, replace=False)
        xyz = np.column_stack((x[idx], y[idx], z[idx]))

        # Colors if present, else grayscale by normalized Z
        if has_rgb:
            r = np.asarray(las.red)[idx]
            g = np.asarray(las.green)[idx]
            b = np.asarray(las.blue)[idx]
            # Normalize to 0..255 if needed
            r = np.clip(r, 0, 65535) / 257.0 if r.dtype != np.uint8 else r
            g = np.clip(g, 0, 65535) / 257.0 if g.dtype != np.uint8 else g
            b = np.clip(b, 0, 65535) / 257.0 if b.dtype != np.uint8 else b
        else:
            zmin, zmax = float(np.min(z)), float(np.max(z))
            norm = (xyz[:, 2] - zmin) / max(1e-9, (zmax - zmin))
            r = g = b = (norm * 255.0)

        r = r.astype(np.uint8)
        g = g.astype(np.uint8)
        b = b.astype(np.uint8)

        ply_path = os.path.join(out_dir, "sample_points.ply")
        with open(ply_path, "w", encoding="utf-8") as f:
            f.write("ply\nformat ascii 1.0\n")
            f.write(f"element vertex {xyz.shape[0]}\n")
            f.write("property float x\nproperty float y\nproperty float z\n")
            f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
            f.write("end_header\n")
            for (px, py, pz), rr, gg, bb in zip(xyz, r, g, b):
                f.write(f"{px:.6f} {py:.6f} {pz:.6f} {int(rr)} {int(gg)} {int(bb)}\n")
        print(f"[OK] Sample PLY written: {ply_path}")

    # Also write a simple Markdown report for your repo
    md_path = os.path.join(out_dir, "point_cloud_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# LAZ/LAS Summary Report\n\n")
        f.write(f"- **Input file**: `{os.path.abspath(in_path)}`\n")
        f.write(f"- **Points**: {point_count}\n")
        f.write(f"- **Bounds**: X[{minx:.3f}, {maxx:.3f}], Y[{miny:.3f}, {maxy:.3f}], Z[{minz:.3f}, {maxz:.3f}]\n")
        if bbox_area_m2:
            f.write(f"- **BBox area**: {bbox_area_m2:.2f} m²\n")
        if density_pts_per_m2:
            f.write(f"- **Estimated density**: {density_pts_per_m2:.2f} pts/m² (bbox-based)\n")
        f.write(f"- **Has RGB**: {has_rgb}, **Has Intensity**: {has_intensity}, **Has Classification**: {has_class}, **Has Returns**: {has_returns}\n")
        f.write(f"- **CRS WKT present**: {crs_wkt is not None}\n\n")
        if class_hist:
            f.write("## Classification Histogram (code: count)\n\n")
            for k in sorted(class_hist.keys()):
                f.write(f"- {k}: {class_hist[k]}\n")
            f.write("\n")
        if return_hist:
            f.write("## Return Number Histogram (n: count)\n\n")
            for k in sorted(return_hist.keys()):
                f.write(f"- {k}: {return_hist[k]}\n")
            f.write("\n")
        f.write("_Generated by summarize_laz.py_\n")
    print(f"[OK] Markdown report: {md_path}")


if __name__ == "__main__":
    main()
