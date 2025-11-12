# -*- coding: utf-8 -*-
"""
select_wires.py
---------------
Extract candidate wire points from ALS using local PCA linearity; assign points to spans
between neighboring towers; save a tidy per-span table for catenary fitting.

Inputs:
  - LAS/LAZ (same CRS as tower GPKG)
  - tower_axis.gpkg
Outputs:
  - Parquet with columns: x,y,z, span_id, tower_start, tower_end, linearity, dist_to_chord

Method:
  1) Read ALS -> filter by HAG > hag_min.
  2) Compute local PCA per point (kNN) → linearity = λ1 / (λ2 + λ3); keep > tau.
  3) Build tower neighbor graph via KNN (k=2) on tower centroids → edges = spans.
  4) For each span edge, select points within corridor buffer and vertical band; assign by
     closest projection along the chord, keeping projections within segment.
"""

from __future__ import annotations
import pathlib
import logging
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from sklearn.neighbors import KDTree, NearestNeighbors

import laspy
from src.io.rasters import open_raster, sample_many
import typer

app = typer.Typer(add_completion=False)
log = logging.getLogger("select_wires")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _read_xyz_hag(path: str | pathlib.Path, dtm: str | None) -> Tuple[np.ndarray, np.ndarray]:
    with laspy.open(path) as f:
        las = f.read()
    xyz = np.vstack([las.x, las.y, las.z]).T.astype(np.float64)
    hag = None
    if "HeightAboveGround" in las.point_format.extra_dimension_names:
        hag = np.asarray(getattr(las, "heightaboveground"), dtype=np.float64)
    if hag is None and dtm:
        ds = open_raster(dtm)
        dtm_z = sample_many(ds, [(x, y) for x, y in xyz[:, :2]])
        hag = xyz[:, 2] - dtm_z
    if hag is None:
        raise ValueError("HAG not available; provide DTM or precomputed HAG.")
    return xyz, hag


def _local_linearity(xyz: np.ndarray, k: int = 20) -> np.ndarray:
    """
    Compute eigenvalue-based linearity per point using kNN covariance.
    linearity = lambda1 / (lambda2 + lambda3), with lambda1 >= lambda2 >= lambda3.
    """
    tree = KDTree(xyz, metric="euclidean")
    idx = tree.query(xyz, k=k, return_distance=False)
    linearity = np.zeros(len(xyz), dtype=np.float64)
    for i in range(len(xyz)):
        P = xyz[idx[i]]
        C = np.cov(P.T)
        w, _ = np.linalg.eigh(C)  # ascending
        w = np.sort(w)[::-1]      # descending
        if w[1] + w[2] == 0:
            linearity[i] = 0.0
        else:
            linearity[i] = float(w[0] / (w[1] + w[2] + 1e-12))
    return linearity


def _tower_centers(tower_gpkg: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(tower_gpkg, layer="tower_axis")
    # center XY from segment start (base) — both points share same XY
    x = gdf.geometry.apply(lambda g: g.coords[0][0])
    y = gdf.geometry.apply(lambda g: g.coords[0][1])
    z0 = gdf.geometry.apply(lambda g: g.coords[0][2])
    z1 = gdf.geometry.apply(lambda g: g.coords[-1][2])
    centers = gpd.GeoDataFrame({"id_tower": gdf["id_tower"], "id": gdf["id"],
                                "zmin": z0, "zmax": z1},
                               geometry=gpd.points_from_xy(x, y, z=z0), crs=gdf.crs)
    return centers


def _knn_edges(centers: gpd.GeoDataFrame, k: int = 2) -> List[Tuple[int, int]]:
    """Return undirected KNN edges (unique, sorted i<j)."""
    X = np.vstack([centers.geometry.x.values, centers.geometry.y.values]).T
    nbrs = NearestNeighbors(n_neighbors=min(k+1, len(X)), algorithm="kd_tree").fit(X)
    distances, indices = nbrs.kneighbors(X)
    edges = set()
    for i, neighs in enumerate(indices):
        for j in neighs[1:]:  # skip self
            a, b = (i, j) if i < j else (j, i)
            edges.add((a, b))
    return sorted(list(edges))


def _assign_points_to_spans(xyz: np.ndarray,
                            pts_mask: np.ndarray,
                            centers: gpd.GeoDataFrame,
                            edges: List[Tuple[int,int]],
                            buffer_m: float,
                            zpad_m: float) -> pd.DataFrame:
    """
    For each edge (tower_i, tower_j), create a corridor buffer around the chord and
    assign candidate wire points to the span based on closest projection inside segment.
    """
    rows = []
    X = xyz[pts_mask]
    idx_active = np.where(pts_mask)[0]

    cx = centers.geometry.x.values
    cy = centers.geometry.y.values
    czmin = centers["zmin"].values
    czmax = centers["zmax"].values

    # Precompute
    for e_idx, (i, j) in enumerate(edges, start=1):
        Pi = np.array([cx[i], cy[i]])
        Pj = np.array([cx[j], cy[j]])
        v = Pj - Pi
        L2 = v @ v
        if L2 < 1e-6:
            continue
        # vertical band: between min(zmax_i, zmax_j)+zpad down to some HAG; we keep generous band
        # project all candidate points to chord
        P = X[:, :2]
        t = ((P - Pi) @ v) / L2
        # inside segment
        inside = (t >= 0.0) & (t <= 1.0)
        # distance to chord
        proj = Pi + t[:, None] * v
        d = np.linalg.norm(P - proj, axis=1)
        inbuf = d <= buffer_m
        sel = inside & inbuf
        if not np.any(sel):
            continue

        chosen_idx = idx_active[sel]
        dist_sel = d[sel]
        t_sel = t[sel]
        pts_sel = X[sel]
        # build rows
        span_id = f"S{min(i,j):04d}-{max(i,j):04d}"
        for k_idx, pt in zip(chosen_idx, pts_sel):
            rows.append({
                "x": pt[0], "y": pt[1], "z": pt[2],
                "span_id": span_id,
                "tower_start": centers.iloc[i]["id_tower"],
                "tower_end": centers.iloc[j]["id_tower"],
                "dist_to_chord": float(dist_sel[np.where(chosen_idx==k_idx)][0]),
                "t_param": float(t_sel[np.where(chosen_idx==k_idx)][0]),
            })

    return pd.DataFrame(rows)


@app.command()
def main(
    las: str = typer.Option(..., help="Input LAS/LAZ"),
    towers: str = typer.Option(..., help="tower_axis GeoPackage"),
    out: str = typer.Option(..., help="Output Parquet file of per-span wire points"),
    dtm: str = typer.Option(None, help="DTM (if HAG not in LAS)"),
    hag_min: float = typer.Option(8.0, help="Minimum HAG for candidate wire points"),
    k_nn: int = typer.Option(20, help="kNN for local PCA"),
    linearity_tau: float = typer.Option(6.0, help="Keep points with linearity >= tau"),
    span_buffer_m: float = typer.Option(20.0, help="Half-width buffer around chord [m]"),
    k_tower_neighbors: int = typer.Option(2, help="K for tower neighbor graph"),
):
    """
    Select wire candidate points and assign them to spans. Writes Parquet.
    """
    xyz, hag = _read_xyz_hag(las, dtm)
    sel_h = hag >= hag_min
    if not np.any(sel_h):
        raise typer.Exit("No points above HAG threshold.")

    log.info(f"Computing local linearity for {sel_h.sum():,} points (k={k_nn})...")
    linearity = _local_linearity(xyz[sel_h], k=k_nn)
    sel_lin = linearity >= linearity_tau
    if not np.any(sel_lin):
        raise typer.Exit("No points passed linearity threshold. Tune parameters.")

    # Mask back into original index
    mask = np.zeros(len(xyz), dtype=bool)
    mask[np.where(sel_h)[0][sel_lin]] = True
    log.info(f"Wire-like points: {mask.sum():,}")

    centers = _tower_centers(towers)
    edges = _knn_edges(centers, k=k_tower_neighbors)
    log.info(f"Span edges from towers: {len(edges)}")

    df = _assign_points_to_spans(
        xyz=xyz,
        pts_mask=mask,
        centers=centers,
        edges=edges,
        buffer_m=span_buffer_m,
        zpad_m=5.0,
    )
    if df.empty:
        log.warning("No points fell inside span buffers. Try increasing buffer or lowering thresholds.")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info(f"Wrote per-span wire points → {out}")


if __name__ == "__main__":
    app()
