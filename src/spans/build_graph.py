# -*- coding: utf-8 -*-
"""
build_graph.py
--------------
Associate 3D insulator points to towers and form spans between neighboring towers.

Inputs:
  - tower_axis.gpkg (layer: tower_axis)
  - insulators.gpkg (layer: insulator)

Outputs:
  - JSON spans with records:
      {
        "span_id": "S0001-0002-r1c1",
        "tower_start": "T0001", "tower_end": "T0002",
        "ins_start": "I00012",  "ins_end": "I00034",
        "row": 1, "col": 1
      }

Method:
  1) For each tower, build a local frame:
       X = unit vector to nearest neighbor tower (chainage direction)
       Z = global up (0,0,1)
       Y = Z × X
  2) Assign each insulator to the nearest tower (XY within max_radius).
  3) For each tower, bin insulators by "row" (height) and "column" (lateral Y)
     using 1D clustering (KMeans or quantile split), then sort.
  4) For each neighbor pair of towers, match rows/cols across towers to define spans.
"""

from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import KMeans

import typer
from rich import print as rprint

app = typer.Typer(add_completion=False)

UP = np.array([0.0, 0.0, 1.0], dtype=np.float64)

@dataclass
class Tower:
    id: str
    id_tower: str
    center: np.ndarray  # (x,y,z_ground)
    top_z: float
    x_axis: np.ndarray  # chainage direction
    y_axis: np.ndarray
    z_axis: np.ndarray


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < 1e-9:
        return v
    return v / n


def _tower_centroids(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    # axis defined by two vertices (same XY); take first coord as base point
    x = gdf.geometry.apply(lambda g: g.coords[0][0]).to_numpy()
    y = gdf.geometry.apply(lambda g: g.coords[0][1]).to_numpy()
    z0 = gdf.geometry.apply(lambda g: g.coords[0][2]).to_numpy()
    z1 = gdf.geometry.apply(lambda g: g.coords[-1][2]).to_numpy()
    df = pd.DataFrame({
        "id": gdf["id"].astype(str).to_numpy(),
        "id_tower": gdf["id_tower"].astype(str).to_numpy(),
        "x": x, "y": y, "z0": z0, "z1": z1
    })
    return df


def _nearest_neighbor_dir(XY: np.ndarray) -> np.ndarray:
    """
    For each tower XY, compute unit vector to its nearest neighbor.
    """
    nbrs = NearestNeighbors(n_neighbors=min(2, len(XY)), algorithm="kd_tree").fit(XY)
    dist, idx = nbrs.kneighbors(XY)
    # idx[:,0] is self; idx[:,1] is nearest other
    dirs = []
    for i in range(len(XY)):
        j = idx[i, 1] if idx.shape[1] > 1 else i
        v = XY[j] - XY[i]
        dirs.append(_normalize(v))
    return np.array(dirs)


def _build_towers(g_towers: gpd.GeoDataFrame) -> Dict[str, Tower]:
    df = _tower_centroids(g_towers)
    XY = df[["x","y"]].to_numpy()
    Xdirs = _nearest_neighbor_dir(XY)
    towers: Dict[str, Tower] = {}
    for k in range(len(df)):
        x_axis = _normalize(np.array([Xdirs[k,0], Xdirs[k,1], 0.0]))
        z_axis = UP.copy()
        y_axis = _normalize(np.cross(z_axis, x_axis))
        t = Tower(
            id=df.loc[k, "id"],
            id_tower=df.loc[k, "id_tower"],
            center=np.array([df.loc[k,"x"], df.loc[k,"y"], df.loc[k,"z0"]], dtype=np.float64),
            top_z=float(df.loc[k,"z1"]),
            x_axis=x_axis, y_axis=y_axis, z_axis=z_axis
        )
        towers[t.id_tower] = t
    return towers


def _assign_insulators_to_towers(g_ins: gpd.GeoDataFrame, towers: Dict[str, Tower],
                                 max_radius: float = 25.0) -> pd.DataFrame:
    """
    Return a DataFrame of insulators with assigned tower id + local coords in tower frame.
    """
    I = g_ins.copy()
    I["ix"] = I.geometry.x
    I["iy"] = I.geometry.y
    I["iz"] = I.geometry.apply(lambda p: p.z)
    Tids = list(towers.keys())
    TXY = np.array([[towers[t].center[0], towers[t].center[1]] for t in Tids], dtype=np.float64)

    nbrs = NearestNeighbors(n_neighbors=1, algorithm="kd_tree").fit(TXY)
    dist, idx = nbrs.kneighbors(I[["ix","iy"]].to_numpy())
    I["id_tower"] = [Tids[i0] for i0 in idx[:,0]]
    I["tower_dist"] = dist[:,0]
    # filter by radius
    I = I[I["tower_dist"] <= max_radius].copy()
    # local frame coordinates
    u = []
    v = []
    w = []
    for _, row in I.iterrows():
        t = towers[row["id_tower"]]
        p = np.array([row["ix"], row["iy"], row["iz"]], dtype=np.float64)
        d = p - t.center
        u.append(float(d @ t.x_axis))  # along chainage
        v.append(float(d @ t.y_axis))  # lateral (phase columns)
        w.append(float(d @ t.z_axis))  # up (phase rows)
    I["u"] = u; I["v"] = v; I["w"] = w
    return I


def _bin_rows_and_cols(I: pd.DataFrame, max_rows: int = 5, max_cols: int = 4) -> pd.DataFrame:
    """
    Per tower: cluster w (height) into rows, and v (lateral) into cols.
    K is chosen adaptively (<= max_*), but at least 1.
    """
    out = []
    for tid, grp in I.groupby("id_tower"):
        g = grp.copy()
        # rows (height)
        n_r = min(max_rows, max(1, int(round(np.clip(len(g)/3, 1, max_rows)))))
        if len(g) >= 2:
            r_km = KMeans(n_clusters=n_r, n_init=10, random_state=42).fit(g[["w"]].to_numpy())
            g["row"] = r_km.labels_
        else:
            g["row"] = 0
        # cols (lateral)
        n_c = min(max_cols, max(1, int(round(np.clip(len(g)/3, 1, max_cols)))))
        if len(g) >= 2:
            c_km = KMeans(n_clusters=n_c, n_init=10, random_state=42).fit(g[["v"]].to_numpy())
            g["col"] = c_km.labels_
        else:
            g["col"] = 0
        # normalize indices by sorting cluster centers
        # rows: sort by mean(w) ascending; cols: by mean(v) ascending (left->right)
        row_map = {old:i for i, old in enumerate(np.argsort(g.groupby("row")["w"].mean()).tolist())}
        col_map = {old:i for i, old in enumerate(np.argsort(g.groupby("col")["v"].mean()).tolist())}
        g["row"] = g["row"].map(row_map)
        g["col"] = g["col"].map(col_map)
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else I


def _tower_edges(towers: Dict[str, Tower]) -> List[Tuple[str,str]]:
    """
    Create edges between nearest neighbors; returns list of (towerA, towerB) with sorted ids.
    """
    ids = list(towers.keys())
    XY = np.array([[towers[i].center[0], towers[i].center[1]] for i in ids])
    nbrs = NearestNeighbors(n_neighbors=min(2, len(ids))).fit(XY)
    _, idx = nbrs.kneighbors(XY)
    edges = set()
    for i in range(len(ids)):
        j = idx[i,1] if idx.shape[1]>1 else i
        a, b = (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
        if a != b:
            edges.add((a,b))
    return sorted(list(edges))


def _match_rows_cols(I: pd.DataFrame, tA: str, tB: str) -> List[Tuple[int,int]]:
    """
    Align rows and columns between tower A and tower B by nearest centroid pairs.
    """
    out = []
    for (attr, label) in [("row","row"), ("col","col")]:
        # not used directly here, we match per (row,col) pairs below
        pass
    # Build all unique (row,col) combos per tower and match by minimizing distance in (mean v, mean w) space
    A = I[I["id_tower"]==tA].groupby(["row","col"])[["v","w"]].mean().reset_index()
    B = I[I["id_tower"]==tB].groupby(["row","col"])[["v","w"]].mean().reset_index()
    matches = []
    for _, a in A.iterrows():
        # find closest (row,col) in B
        diffs = (B[["v","w"]] - a[["v","w"]]).pow(2).sum(axis=1)
        j = int(np.argmin(diffs.values)) if len(diffs)>0 else None
        if j is None: continue
        b = B.iloc[j]
        matches.append(((int(a["row"]), int(a["col"])), (int(b["row"]), int(b["col"]))))
    return matches


@app.command()
def main(
    towers_gpkg: str = typer.Option(..., help="GeoPackage with tower_axis layer"),
    ins_gpkg: str = typer.Option(..., help="GeoPackage with insulator layer"),
    out: str = typer.Option(..., help="Output spans.json"),
    tower_layer: str = typer.Option("tower_axis", help="Layer name for towers"),
    ins_layer: str = typer.Option("insulator", help="Layer name for insulators"),
    max_assign_radius: float = typer.Option(25.0, help="Max XY distance to assign insulator to a tower [m]"),
):
    """
    Build span definitions by associating insulators to towers and matching row/col across neighbors.
    """
    g_towers = gpd.read_file(towers_gpkg, layer=tower_layer)
    g_ins = gpd.read_file(ins_gpkg, layer=ins_layer)
    crs = g_towers.crs

    towers = _build_towers(g_towers)
    I = _assign_insulators_to_towers(g_ins, towers, max_radius=max_assign_radius)
    if I.empty:
        rprint("[yellow]No insulators assigned to towers. Check radius or triangulation.[/]")
        pathlib.Path(out).write_text(json.dumps({"spans":[]}, indent=2))
        return

    I = _bin_rows_and_cols(I)

    # For each neighbor edge, produce span pairs by matching (row,col)
    edges = _tower_edges(towers)
    spans = []
    for (A, B) in edges:
        matches = _match_rows_cols(I, A, B)
        for (ra, ca), (rb, cb) in matches:
            IA = I[(I["id_tower"]==A) & (I["row"]==ra) & (I["col"]==ca)].sort_values("u")
            IB = I[(I["id_tower"]==B) & (I["row"]==rb) & (I["col"]==cb)].sort_values("u")
            if IA.empty or IB.empty:
                continue
            # pick nearest along chainage: start = farthest towards +X at A, end = farthest towards -X at B
            insA = IA.iloc[-1]  # largest u
            insB = IB.iloc[0]   # smallest u
            span_id = f"S{A.replace('T',''):>s}-{B.replace('T',''):>s}-r{ra}c{ca}"
            spans.append({
                "span_id": span_id,
                "tower_start": A, "tower_end": B,
                "ins_start": insA["id"], "ins_end": insB["id"],
                "row": int(ra), "col": int(ca)
            })

    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text(json.dumps({"spans": spans}, indent=2))
    rprint(f"[green]Wrote spans →[/] {out}")


if __name__ == "__main__":
    app()
