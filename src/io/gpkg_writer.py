# -*- coding: utf-8 -*-
"""
gpkg_writer.py
--------------
GeoPackage writer for the three required layers:
- tower_axis (LineStringZ)  : id, id_tower, geometry
- insulator (PointZ)        : id, id_tower, id_wire, geometry
- wire (LineStringZ)        : id, id_insulator_start, id_insulator_end, geometry

Ensures:
- 3D geometries (has Z)
- Required attribute columns exist and are correct dtype
- Target CRS preserved across layers
"""

from __future__ import annotations
import pathlib
from typing import Optional, Iterable

import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
from shapely.geometry.base import BaseGeometry


REQUIRED_SCHEMAS = {
    "tower_axis": ["id", "id_tower", "geometry"],
    "insulator": ["id", "id_tower", "id_wire", "geometry"],
    "wire": ["id", "id_insulator_start", "id_insulator_end", "geometry"],
}

def _ensure_z(geom: BaseGeometry) -> BaseGeometry:
    """Coerce Point/LineString to have Z. If missing, set Z=0."""
    if geom is None:
        return geom
    if isinstance(geom, Point):
        if geom.has_z:
            return geom
        x, y = geom.x, geom.y
        return Point(x, y, 0.0)
    if isinstance(geom, LineString):
        coords = []
        for c in geom.coords:
            if len(c) == 3:
                coords.append(c)
            else:
                coords.append((c[0], c[1], 0.0))
        return LineString(coords)
    # Optionally support Multi* later; for now, enforce simple geometries.
    raise TypeError(f"Unsupported geometry type for 3D coercion: {geom.geom_type}")

def _validate_df(name: str, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cols = REQUIRED_SCHEMAS[name]
    missing = [c for c in cols if c not in gdf.columns]
    if missing:
        raise ValueError(f"[{name}] missing required columns: {missing}")
    # basic dtype normalization
    gdf = gdf.copy()
    gdf["id"] = gdf["id"].astype(str)
    if name == "tower_axis":
        gdf["id_tower"] = gdf["id_tower"].astype(str)
    elif name == "insulator":
        gdf["id_tower"] = gdf["id_tower"].astype(str)
        gdf["id_wire"] = gdf["id_wire"].astype(str)
    elif name == "wire":
        gdf["id_insulator_start"] = gdf["id_insulator_start"].astype(str)
        gdf["id_insulator_end"] = gdf["id_insulator_end"].astype(str)

    # Ensure 3D geoms
    gdf["geometry"] = gdf["geometry"].apply(_ensure_z)
    if gdf.crs is None:
        raise ValueError(f"[{name}] CRS is missing. Set gdf.crs appropriately before writing.")
    return gdf

def write_layers(
    out_path: str | pathlib.Path,
    towers: gpd.GeoDataFrame,
    insulators: gpd.GeoDataFrame,
    wires: gpd.GeoDataFrame,
    overwrite: bool = True,
) -> None:
    """
    Write all layers to a single GeoPackage with enforced schema and 3D geometries.
    """
    out = pathlib.Path(out_path)
    if overwrite and out.exists():
        out.unlink()

    towers_ok = _validate_df("tower_axis", towers)
    ins_ok = _validate_df("insulator", insulators)
    wires_ok = _validate_df("wire", wires)

    # Layer write
    towers_ok.to_file(out, layer="tower_axis", driver="GPKG")
    ins_ok.to_file(out, layer="insulator", driver="GPKG")
    wires_ok.to_file(out, layer="wire", driver="GPKG")

def merge_and_write(
    out_path: str | pathlib.Path,
    tower_layers: Iterable[gpd.GeoDataFrame],
    insulator_layers: Iterable[gpd.GeoDataFrame],
    wire_layers: Iterable[gpd.GeoDataFrame],
    overwrite: bool = True,
) -> None:
    """
    Convenience: merge multiple per-tile GeoDataFrames and write once.
    All layers must share the same CRS.
    """
    def _cat(layers):
        gdfs = [g for g in layers if g is not None and len(g) > 0]
        if not gdfs:
            return gpd.GeoDataFrame(columns=["id","geometry"], geometry="geometry", crs=None)
        crs = gdfs[0].crs
        for g in gdfs[1:]:
            if g.crs != crs:
                raise ValueError("CRS mismatch among layers to merge.")
        return gpd.pd.concat(gdfs, ignore_index=True).set_geometry("geometry").set_crs(crs)

    towers = _cat(list(tower_layers))
    ins = _cat(list(insulator_layers))
    wires = _cat(list(wire_layers))
    write_layers(out_path, towers, ins, wires, overwrite=overwrite)
