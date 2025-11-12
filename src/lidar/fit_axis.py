# -*- coding: utf-8 -*-
"""
fit_axis.py
-----------
Refine tower axes with PCA (tilt-aware). Useful when towers lean and you want the
axis to represent the structure more faithfully than a purely vertical line.

Inputs:
  - LAS/LAZ
  - initial tower_axis.gpkg (centers)
  - DTM (for base snap)

Outputs:
  - refined tower_axis.gpkg (LineStringZ) with same schema (id, id_tower, geometry)

Method:
  For each tower center:
    1) Gather ALS points in a radius around (xc,yc) and above min_hag.
    2) PCA → principal direction (unit vector) = structural axis.
    3) Project points onto axis to get extents; base Z = DTM(xc,yc), top Z = base + max_proj.
    4) Compose LineString from base to top along axis passing through center.
"""

from __future__ import annotations
import pathlib
import logging
from typing import Tuple

import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, Point
from sklearn.neighbors import KDTree

import laspy
from src.io.rasters import open_raster, sample_many
from src.io.gpkg_writer import write_layers
import typer

app = typer.Typer(add_completion=False)
log = logging.getLogger("fit_axis")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _load_xyz(path: str | pathlib.Path) -> np.ndarray:
    with laspy.open(path) as f:
        las = f.read()
    return np.vstack([las.x, las.y, las.z]).T.astype(np.float64)


def _pca_axis(P: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return centroid and principal direction (unit vector) via PCA.
    """
    c = P.mean(axis=0)
    X = P - c
    C = np.cov(X.T)
    w, V = np.linalg.eigh(C)
    idx = np.argsort(w)[::-1]
    v = V[:, idx[0]]
    v = v / np.linalg.norm(v)
    return c, v


@app.command()
def main(
    las: str = typer.Option(..., help="Input LAS/LAZ"),
    in_towers: str = typer.Option(..., help="Input tower_axis GPKG (initial)"),
    dtm: str = typer.Option(..., help="DTM raster"),
    out: str = typer.Option(..., help="Output refined tower_axis GPKG"),
    radius_m: float = typer.Option(6.0, help="Neighborhood radius around tower center"),
    min_hag: float = typer.Option(6.0, help="Minimum HAG for tower points"),
    top_pct: float = typer.Option(98.5, help="Percentile for top along axis"),
):
    """
    Refine tower axes with PCA-based tilt. Preserves IDs.
    """
    xyz = _load_xyz(las)

    # Build KDTree in XY for fast radius selection
    XY = xyz[:, :2]
    tree = KDTree(XY, metric="euclidean")

    towers = gpd.read_file(in_towers, layer="tower_axis")
    ds_dtm = open_raster(dtm)

    refined = []
    ids, id_towers = [], []
    for idx, row in towers.iterrows():
        # tower center XY from geometry
        xc, yc, _ = row.geometry.coords[0]
        # radius query
        inds = tree.query_radius([[xc, yc]], r=radius_m)[0]
        if len(inds) < 50:
            continue
        P = xyz[inds]
        # HAG filter via DTM
        z_ground = float(sample_many(ds_dtm, [(xc, yc)])[0])
        hag = P[:, 2] - sample_many(ds_dtm, [(x, y) for x, y in P[:, :2]])
        mask = hag >= min_hag
        P = P[mask]
        if len(P) < 50:
            continue

        # PCA axis
        c, v = _pca_axis(P)
        # force axis to roughly align with vertical: flip sign if more upward
        if v[2] < 0:
            v = -v

        # project points onto axis to find extent above base
        # param t where point = c + t*v
        t = ((P - c) @ v)
        t_top = np.percentile(t, top_pct)
        # base anchored to ground at center
        base = np.array([xc, yc, z_ground], dtype=np.float64)
        # ensure axis passes through (xc,yc) in XY; compute Z by intersecting with line passing c offset
        # use same direction v; set base point = [xc,yc,z_ground]
        top = base + t_top * v

        line = LineString([(base[0], base[1], base[2]), (top[0], top[1], top[2])])
        refined.append(line)
        ids.append(row["id"])
        id_towers.append(row["id_tower"])

    crs = towers.crs
    gdf_ref = gpd.GeoDataFrame({"id": ids, "id_tower": id_towers}, geometry=refined, crs=crs)

    # empty placeholders
    empty_ins = gpd.GeoDataFrame({"id": [], "id_tower": [], "id_wire": []}, geometry=[], crs=crs)
    empty_wire = gpd.GeoDataFrame({"id": [], "id_insulator_start": [], "id_insulator_end": []}, geometry=[], crs=crs)
    write_layers(out, gdf_ref, empty_ins, empty_wire)
    log.info(f"Wrote refined tower_axis → {out}")


if __name__ == "__main__":
    app()
