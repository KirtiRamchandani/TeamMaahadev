# -*- coding: utf-8 -*-
"""
cluster_towers.py
-----------------
Detect transmission towers in ALS and produce vertical axis segments (LineStringZ).

Inputs:
  - LAS/LAZ with XYZ (optionally HeightAboveGround/HAG and normals).
  - DTM raster to anchor tower base Z.
Outputs:
  - GeoPackage (layer: tower_axis) with schema: id, id_tower, geometry(LineStringZ)

Method:
  1) Load ALS -> filter by height (HAG > min_hag) -> optional voxel thinning for speed.
  2) DBSCAN in XY for tall clusters; keep clusters with vertical extent >= min_height.
  3) Robust XY center (median), ground Z from DTM(xc,yc), top Z = cluster Z 98–99th pct.
  4) Write axis line from (xc,yc,z_ground) to (xc,yc,z_top).

CLI:
  python -m src.lidar.cluster_towers --las data/als/segment.laz --dtm data/rasters/dtm.tif --out build/tower_axis.gpkg
"""

from __future__ import annotations
import pathlib
import logging
from typing import Tuple, Optional

import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from sklearn.cluster import DBSCAN

import laspy
from rasterio import open as rio_open

from src.io.rasters import open_raster, sample_many
from src.io.gpkg_writer import write_layers  # reuse schema validator (we'll build layer and call it)
import typer

app = typer.Typer(add_completion=False)
log = logging.getLogger("cluster_towers")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _read_las_xyz_hag(path: str | pathlib.Path, dtm_path: Optional[str] = None) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Return XYZ (N,3) and HAG (N,) if present; else compute HAG via DTM."""
    p = pathlib.Path(path)
    with laspy.open(p) as f:
        las = f.read()
    xyz = np.vstack([las.x, las.y, las.z]).T.astype(np.float64)

    # Check for HeightAboveGround or UserData dims
    hag = None
    for cand in ["HeightAboveGround", "hag", "point_source_id"]:  # last resort nonsense
        if cand in las.point_format.extra_dimension_names:
            hag = getattr(las, cand.lower(), None)
            if hag is not None:
                hag = np.asarray(hag, dtype=np.float64)
                break

    if hag is None and dtm_path is not None:
        # compute HAG = Z - DTM(x,y)
        ds = open_raster(dtm_path)
        dtm_z = sample_many(ds, [(x, y) for x, y in xyz[:, :2]])
        hag = xyz[:, 2] - dtm_z
    return xyz, hag


def _dbscan_towers(xy: np.ndarray, z: np.ndarray, min_samples: int, eps: float, min_height: float):
    """DBSCAN in XY then filter clusters by vertical extent >= min_height."""
    labels = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1).fit_predict(xy)
    towers = []
    for lab in np.unique(labels):
        if lab < 0:
            continue
        mask = labels == lab
        zmin, zmax = np.percentile(z[mask], [5, 99.5])
        if (zmax - zmin) >= min_height:
            towers.append(mask)
    return towers


@app.command()
def main(
    las: str = typer.Option(..., help="Input LAS/LAZ (ALS)"),
    dtm: str = typer.Option(..., help="DTM raster (TIFF)"),
    out: str = typer.Option(..., help="Output GeoPackage path for tower_axis layer"),
    eps: float = typer.Option(2.0, help="DBSCAN eps [meters] in XY"),
    min_samples: int = typer.Option(120, help="DBSCAN min_samples"),
    min_hag: float = typer.Option(8.0, help="Minimum HAG to consider as structure"),
    min_height: float = typer.Option(15.0, help="Minimum vertical extent of a tower cluster [m]"),
    top_pct: float = typer.Option(98.5, help="Percentile for tower top Z from cluster"),
    crs: str = typer.Option("EPSG:32638", help="Output CRS (must match ALS CRS)"),
):
    """
    Detect towers and write tower_axis (LineStringZ) to a GeoPackage.
    """
    xyz, hag = _read_las_xyz_hag(las, dtm)
    if hag is None:
        raise typer.Exit("Could not compute HeightAboveGround (HAG). Provide DTM or precomputed HAG.")

    # Filter tall structures
    sel = hag >= min_hag
    pts = xyz[sel]
    if len(pts) == 0:
        raise typer.Exit("No high-above-ground points found; check thresholds.")
    log.info(f"High-structure points: {len(pts):,}")

    # Cluster towers
    towers = _dbscan_towers(pts[:, :2], pts[:, 2], min_samples=min_samples, eps=eps, min_height=min_height)
    log.info(f"Tower clusters: {len(towers)}")

    # Build axes
    ds_dtm = rio_open(dtm)
    geoms = []
    ids = []
    id_towers = []
    for i, mask in enumerate(towers, start=1):
        P = pts[mask]
        xy_center = np.median(P[:, :2], axis=0)
        # ground and top
        z_ground = float(sample_many(ds_dtm, [tuple(xy_center)])[0])
        z_top = float(np.percentile(P[:, 2], top_pct))
        if not np.isfinite(z_ground) or not np.isfinite(z_top) or (z_top - z_ground) < min_height * 0.5:
            # safeguard
            continue
        line = LineString([(xy_center[0], xy_center[1], z_ground),
                           (xy_center[0], xy_center[1], z_top)])
        geoms.append(line)
        tid = f"T{i:04d}"
        ids.append(tid)
        id_towers.append(tid)

    gdf_towers = gpd.GeoDataFrame(
        {"id": ids, "id_tower": id_towers},
        geometry=geoms, crs=crs
    )

    # Write as single-layer gpkg; reuse writer by creating empty others
    empty_ins = gpd.GeoDataFrame({"id": [], "id_tower": [], "id_wire": []},
                                 geometry=[], crs=crs)
    empty_wire = gpd.GeoDataFrame({"id": [], "id_insulator_start": [], "id_insulator_end": []},
                                  geometry=[], crs=crs)

    write_layers(out, gdf_towers, empty_ins, empty_wire)
    log.info(f"Wrote tower_axis → {out}")


if __name__ == "__main__":
    app()
