# -*- coding: utf-8 -*-
"""
rasters.py
----------
Raster utilities: open raster, sample Z at XY (bilinear), mask reads, and CRS-safe
reprojection of vector data.

Key functions:
- open_raster()
- sample_z_bilinear()
- sample_many()
- reproject_gdf()
"""

from __future__ import annotations
import pathlib
from typing import Iterable, Tuple, Sequence, Optional

import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import rowcol
from rasterio import Affine
import geopandas as gpd
from pyproj import CRS, Transformer


def open_raster(path: str | pathlib.Path) -> rasterio.io.DatasetReader:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Raster not found: {p}")
    return rasterio.open(p)

def _bilinear(arr: np.ndarray, r: float, c: float, nodata: Optional[float]) -> float:
    r0, c0 = int(np.floor(r)), int(np.floor(c))
    dr, dc = r - r0, c - c0
    r1, c1 = r0 + 1, c0 + 1
    if (r0 < 0 or c0 < 0 or r1 >= arr.shape[0] or c1 >= arr.shape[1]):
        return float("nan")
    q11 = arr[r0, c0]
    q21 = arr[r0, c1]
    q12 = arr[r1, c0]
    q22 = arr[r1, c1]
    if nodata is not None:
        if any(np.isclose([q11, q21, q12, q22], nodata)):
            # conservative: if any corner is nodata, return nodata
            return nodata
    # bilinear interpolation
    top = q11 * (1 - dc) + q21 * dc
    bot = q12 * (1 - dc) + q22 * dc
    return float(top * (1 - dr) + bot * dr)

def sample_z_bilinear(
    ds: rasterio.io.DatasetReader,
    xy: Tuple[float, float],
) -> float:
    """
    Sample a single Z value at (x,y) using bilinear interpolation on band 1.
    Returns float (can be NaN if outside or nodata).
    """
    x, y = xy
    # row/col in pixel coords
    r, c = ds.index(x, y)
    # center of the pixel -> use fractional row/col for bilinear
    # compute exact fractional indices via inverse affine transform
    inv = ~ds.transform
    rr = inv * (x, y)
    r_f, c_f = rr[1], rr[0]  # inv returns (col,row); reorder
    arr = ds.read(1, masked=False)
    nodata = ds.nodata
    return _bilinear(arr, r_f, c_f, nodata)

def sample_many(
    ds: rasterio.io.DatasetReader,
    coords: Sequence[Tuple[float, float]],
) -> np.ndarray:
    """
    Vectorized sampling of many XY points; returns np.ndarray of shape (N,)
    """
    inv = ~ds.transform
    cols_rows = np.array([inv * (x, y) for (x, y) in coords], dtype=np.float64)
    c_f = cols_rows[:, 0]
    r_f = cols_rows[:, 1]
    arr = ds.read(1, masked=False)
    nodata = ds.nodata
    out = np.empty(len(coords), dtype=np.float64)
    for i, (r, c) in enumerate(zip(r_f, c_f)):
        out[i] = _bilinear(arr, r, c, nodata)
    return out

def reproject_gdf(gdf: gpd.GeoDataFrame, dst_crs: str | CRS) -> gpd.GeoDataFrame:
    """
    Safe reprojection for GeoDataFrames; preserves 3D coordinates.
    """
    if gdf.crs is None:
        raise ValueError("Input GeoDataFrame has no CRS.")
    if str(gdf.crs) == str(dst_crs):
        return gdf.copy()
    # GeoPandas handles Z preservation when using pyproj >= 3
    return gdf.to_crs(dst_crs)
