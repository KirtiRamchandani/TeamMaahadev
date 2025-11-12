# -*- coding: utf-8 -*-
"""
triangulate.py
--------------
Multi-view triangulation of insulator detections into 3D PointZ attachment points.

Pipeline
1) Load EO (Omega/Phi/Kappa), intrinsics (K, dist), and 2D detections JSON from infer_insulators.py.
2) For each image, compute the **ray** for each detection (center of bbox).
3) Associate detections across images using **co-planar projection**:
    - Choose a reference ground plane Z_ref (DTM(x,y) + z_offset).
    - Project each ray to this plane; match projected points across images by proximity.
4) For each matched track (>=2 views), solve **robust least-squares ray intersection** to get 3D point.
5) Compute reprojection errors (px) back to all images; filter by max error.
6) Write `insulator` layer (PointZ) to GeoPackage, with ids and optional nearest tower ID (if provided).

CLI
  python -m src.vision.triangulate \
    --detections build/insulators_2d.json \
    --eo data/ap/eo.csv --K data/ap/intrinsics.yaml \
    --dtm data/rasters/dtm.tif --out build/insulators_3d.gpkg \
    --z-offset 8.0 --px-thresh 3.0
"""

from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import numpy as np
import geopandas as gpd
from shapely.geometry import Point

import typer
from rich import print as rprint

from src.io.read_eo import load_eo_table, load_intrinsics_yaml, build_camera_dict, pixel_to_world_ray, undistort_points
from src.io.rasters import open_raster, sample_many
from src.io.gpkg_writer import write_layers

app = typer.Typer(add_completion=False)


@dataclass
class Cam:
    name: str
    K: np.ndarray
    dist: np.ndarray
    Cw: np.ndarray
    Rcw: np.ndarray
    P: np.ndarray


def _bbox_center(b):
    x1,y1,x2,y2 = b
    return np.array([(x1+x2)/2.0, (y1+y2)/2.0], dtype=np.float64)


def _intersect_ray_with_plane(o: np.ndarray, d: np.ndarray, z_ref: float) -> Optional[np.ndarray]:
    """
    Intersect ray X = o + t d with horizontal plane Z=z_ref.
    Returns XYZ point or None if parallel/backfacing.
    """
    if abs(d[2]) < 1e-8:
        return None
    t = (z_ref - o[2]) / d[2]
    if t <= 0:
        return None
    X = o + t * d
    return X


def _associate_by_plane_proj(
    rays: Dict[str, List[Tuple[np.ndarray, np.ndarray]]],
    z_ref: float,
    radius_m: float = 1.0,
) -> List[List[Tuple[str, int, np.ndarray, np.ndarray]]]:
    """
    Project each ray from each image to Z=z_ref; greedily match points across images by proximity.

    Returns a list of tracks; each track is a list of tuples:
      (image_name, detection_idx, origin, direction)
    """
    # Build per-image projected points
    proj = {}
    for img, ray_list in rays.items():
        pts = []
        for i, (o, d) in enumerate(ray_list):
            X = _intersect_ray_with_plane(o, d, z_ref)
            if X is not None:
                pts.append((i, X))
        proj[img] = pts

    # Greedy matching: pick a reference image, match nearest neighbors in others
    tracks: List[List[Tuple[str, int, np.ndarray, np.ndarray]]] = []
    images = list(proj.keys())
    used = {img: set() for img in images}

    for ref in images:
        for (i_idx, Xi) in proj[ref]:
            if i_idx in used[ref]:
                continue
            track = [(ref, i_idx)]
            used[ref].add(i_idx)
            # try to find mates in other images
            for img in images:
                if img == ref:
                    continue
                best = None
                best_d = float("inf")
                for (j_idx, Xj) in proj[img]:
                    if j_idx in used[img]:
                        continue
                    d = np.linalg.norm(Xi - Xj)
                    if d < best_d:
                        best_d, best = d, j_idx
                if best is not None and best_d <= radius_m:
                    track.append((img, best))
                    used[img].add(best)
            # reconstruct full ray tuples
            rays_track = []
            for (img, det_idx) in track:
                o, d = rays[img][det_idx]
                rays_track.append((img, det_idx, o, d))
            if len(rays_track) >= 2:
                tracks.append(rays_track)
    return tracks


def _robust_ray_intersection(rays: List[Tuple[np.ndarray, np.ndarray]], max_iter: int = 20) -> np.ndarray:
    """
    Robust least-squares intersection of multiple rays (o_i + t_i d_i).
    Solve for X minimizing sum_i || (I - d_i d_i^T) (X - o_i) ||^2 (closest point to all lines).
    Huber-like iterations to reduce influence of outliers.
    """
    # initialization: average of pairwise closest points
    X = np.mean([o for (o, _) in rays], axis=0)

    for _ in range(max_iter):
        A = np.zeros((3, 3), dtype=np.float64)
        b = np.zeros(3, dtype=np.float64)
        weights = []
        for (o, d) in rays:
            d = d / np.linalg.norm(d)
            P = np.eye(3) - np.outer(d, d)  # projection onto normal plane
            r = P @ (X - o)
            w = 1.0 / (1.0 + np.linalg.norm(r))  # Huber-ish
            A += w * P
            b += w * P @ o
            weights.append(w)
        try:
            X_new = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            break
        if np.linalg.norm(X_new - X) < 1e-5:
            X = X_new
            break
        X = X_new
    return X


def _reprojection_error_px(
    K: np.ndarray, Rcw: np.ndarray, Cw: np.ndarray, Xw: np.ndarray, uv_obs: np.ndarray
) -> float:
    """
    Project world point to pixel and compute Euclidean error (pixels).
    """
    # camera coords
    Xc = Rcw @ (Xw - Cw.reshape(3))
    if Xc[2] <= 1e-6:
        return 1e9
    x = Xc[0] / Xc[2]
    y = Xc[1] / Xc[2]
    u = K[0, 0] * x + K[0, 2]
    v = K[1, 1] * y + K[1, 2]
    return float(np.linalg.norm(np.array([u, v]) - uv_obs))


@app.command()
def main(
    detections: str = typer.Option(..., help="JSON from infer_insulators.py"),
    eo: str = typer.Option(..., help="EO table (CSV/TSV/TXT) with image,X,Y,Z,Omega,Phi,Kappa"),
    K: str = typer.Option(..., help="Intrinsics YAML (K, dist, size)"),
    dtm: str = typer.Option(..., help="DTM (to estimate local reference Z)"),
    out: str = typer.Option(..., help="Output GeoPackage for insulator 3D points"),
    z_offset: float = typer.Option(8.0, help="Meters above local DTM to use for plane association"),
    px_thresh: float = typer.Option(3.0, help="Max allowed reprojection error (pixels)"),
    cls_keep: int = typer.Option(0, help="Class index to keep (insulator class id in your model)"),
    ins_layer_name: str = typer.Option("insulator", help="GeoPackage layer name"),
    crs: str = typer.Option("EPSG:32638", help="Output CRS"),
):
    """
    Triangulate insulators from multi-view detections + EO.
    """
    det_map = json.loads(pathlib.Path(detections).read_text())
    eo_df = load_eo_table(eo)
    intr = load_intrinsics_yaml(K)

    # Build camera dicts by image name
    cams: Dict[str, Cam] = {}
    for _, row in eo_df.iterrows():
        camd = build_camera_dict(row, intr)
        cams[row["image"]] = Cam(
            name=row["image"],
            K=camd["K"], dist=intr["dist"],
            Cw=camd["Cw"], Rcw=camd["Rcw"], P=camd["P"]
        )

    # rays per image
    rays: Dict[str, List[Tuple[np.ndarray, np.ndarray]]] = {}
    uv_centers: Dict[str, List[np.ndarray]] = {}
    images = []
    for img, dets in det_map.items():
        if img not in cams:
            # tolerate filename differences (strip path)
            base = pathlib.Path(img).name
            if base in cams:
                cam = cams[base]
                img = base
            else:
                continue
        cam = cams[img]
        images.append(img)
        rays[img] = []
        uv_centers[img] = []
        for d in dets:
            if int(d.get("cls", -1)) != int(cls_keep):
                continue
            uv = _bbox_center(d["bbox"])
            o, dirw = pixel_to_world_ray(
                P=cam.P, K=cam.K, Rcw=cam.Rcw, Cw=cam.Cw,
                uv=uv, undistort=False, dist=cam.dist
            )
            rays[img].append((o, dirw))
            uv_centers[img].append(uv)

    # Estimate local Z_ref per image using DTM at camera XY then add z_offset
    ds_dtm = open_raster(dtm)
    z_refs = {}
    for img in images:
        cam = cams[img]
        z_ground = float(sample_many(ds_dtm, [(cam.Cw[0], cam.Cw[1])])[0])
        z_refs[img] = z_ground + z_offset
    # Use median across images as a global plane for association
    z_ref = float(np.median(list(z_refs.values())))

    # Associate detections across images
    tracks = _associate_by_plane_proj(rays, z_ref=z_ref, radius_m=1.0)

    # Triangulate each track with >= 2 views
    pts3d, ids = [], []
    reproj_rows = []
    for tidx, track in enumerate(tracks, start=1):
        # rays for intersection
        rset = [(o, d) for (_, _, o, d) in track]
        Xw = _robust_ray_intersection(rset)

        # reprojection error across the track
        ok = True
        errs = []
        for (img, det_idx, o, d) in track:
            cam = cams[img]
            uv_obs = uv_centers[img][det_idx]
            e = _reprojection_error_px(cam.K, cam.Rcw, cam.Cw, Xw, uv_obs)
            errs.append(e)
            if e > px_thresh:
                ok = False
        mean_e = float(np.mean(errs)) if errs else 1e9
        reproj_rows.append({"track": tidx, "nviews": len(track), "mean_px": mean_e, "max_px": float(np.max(errs))})
        if not ok:
            continue
        pts3d.append(Xw)
        ids.append(f"I{tidx:05d}")

    # GeoPackage layer
    gdf_ins = gpd.GeoDataFrame(
        {"id": ids, "id_tower": ["" for _ in ids], "id_wire": ["" for _ in ids]},
        geometry=[Point(p[0], p[1], p[2]) for p in pts3d],
        crs=crs
    )

    # Empty placeholders for other layers to satisfy writer
    empty_towers = gpd.GeoDataFrame({"id": [], "id_tower": []}, geometry=[], crs=crs)
    empty_wires = gpd.GeoDataFrame({"id": [], "id_insulator_start": [], "id_insulator_end": []}, geometry=[], crs=crs)

    write_layers(out, empty_towers, gdf_ins, empty_wires)
    rprint(f"[green]Wrote insulator 3D layer →[/] {out}")

    # Save reprojection stats (sidecar CSV)
    reproj_csv = pathlib.Path(out).with_suffix(".triangulation.csv")
    pd = __import__("pandas")
    pd.DataFrame(reproj_rows).to_csv(reproj_csv, index=False)
    rprint(f"[green]Wrote reprojection stats →[/] {reproj_csv}")


if __name__ == "__main__":
    app()
