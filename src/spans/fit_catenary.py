# -*- coding: utf-8 -*-
"""
fit_catenary.py
---------------
Fit 3D catenary curves for each span and write the `wire` (LineStringZ) layer.

Inputs:
  - Per-span wire points parquet (from select_wires.py) with columns:
      x,y,z, span_id, tower_start, tower_end, dist_to_chord, t_param
  - spans.json from build_graph.py
  - insulators.gpkg with 3D attachment points (to snap endpoints)
Outputs:
  - wires_3d.gpkg (layer: wire) schema:
      id, id_insulator_start, id_insulator_end, geometry(LineStringZ)
  - qc_spans.csv with RMSE and stats

Method (per span):
  1) Collect candidate wire points for span_id; downweight outliers (Huber).
  2) Build span plane using tower centers (XY) → define local 2D (u,v) basis.
  3) Project ALS points to (u,z) curve; fit catenary z(u) = a cosh((u - u0)/a) + c.
  4) Sample curve between attachment u-parameters; map back to 3D LineStringZ.
  5) Snap endpoints to nearest insulator PointZ (start/end).
"""

from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from scipy.optimize import least_squares

import typer
from rich import print as rprint

from src.io.gpkg_writer import write_layers

app = typer.Typer(add_completion=False)

@dataclass
class SpanDef:
    span_id: str
    A: str
    B: str
    insA: str
    insB: str
    row: int
    col: int

# ---------------------- geometry helpers ------------------------------

def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < 1e-12: return v
    return v / n

def _span_basis(Axy: np.ndarray, Bxy: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return (u_hat, v_hat) unit vectors in XY plane:
      u_hat: from A to B (chord direction), v_hat: left normal in XY.
    """
    u = _normalize(Bxy - Axy)
    v = np.array([-u[1], u[0]], dtype=np.float64)
    return u, v

def _project_to_uvz(Pxyz: np.ndarray, Axy: np.ndarray, u_hat: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Project 3D points to (u, z) w.r.t chord AB:
      u = (Pxy - Axy) · u_hat
      z = Z
    """
    Pxy = Pxyz[:, :2]
    d = Pxy - Axy
    u = d @ u_hat
    z = Pxyz[:, 2]
    return u, z

def _catenary(u, a, u0, c):
    return a*np.cosh((u - u0)/a) + c

def _fit_catenary(u: np.ndarray, z: np.ndarray, weights: np.ndarray) -> Tuple[float,float,float]:
    """
    Fit z(u) = a cosh((u - u0)/a) + c with robust LS (Huber weighting via `weights`).
    """
    # initialize from quadratic fit z ≈ alpha u^2 + beta u + gamma
    U = np.column_stack([u**2, u, np.ones_like(u)])
    try:
        alpha, beta, gamma = np.linalg.lstsq(U, z, rcond=None)[0]
    except Exception:
        alpha, beta, gamma = 0.01, 0.0, np.mean(z)
    a0 = max(0.5, np.sqrt(1.0/abs(alpha)) if abs(alpha) > 1e-6 else 20.0)
    u00 = np.median(u)
    c0 = np.median(z) - a0*np.cosh((u00 - u00)/a0)

    def resid(theta):
        a, u0, c = theta
        pred = _catenary(u, a, u0, c)
        r = (pred - z) * np.sqrt(np.clip(weights, 1e-3, 1e3))
        return r

    res = least_squares(resid, x0=np.array([a0, u00, c0], dtype=np.float64), loss="huber", f_scale=1.0, max_nfev=200)
    a, u0, c = res.x
    return float(a), float(u0), float(c)

def _huber_weights(residuals: np.ndarray, delta: float = 0.5) -> np.ndarray:
    """
    Compute Huber weights from raw residuals.
    """
    r = np.abs(residuals)
    w = np.ones_like(r)
    mask = r > delta
    w[mask] = delta / r[mask]
    return w

# ---------------------- main routine ----------------------------------

@app.command()
def main(
    wire_points: str = typer.Option(..., help="Per-span wire points (.parquet)"),
    spans_json: str = typer.Option(..., help="spans.json from build_graph.py"),
    ins_gpkg: str = typer.Option(..., help="Insulator GeoPackage"),
    out_gpkg: str = typer.Option(..., help="Output wires GeoPackage (layer: wire)"),
    qc_csv: str = typer.Option(..., help="QC CSV output"),
    ins_layer: str = typer.Option("insulator", help="Insulator layer name"),
    crs: str = typer.Option("EPSG:32638", help="CRS for outputs"),
    step_m: float = typer.Option(1.0, help="Sampling step along span (meters)"),
    huber_delta: float = typer.Option(0.5, help="Huber delta for robust fit"),
    min_points: int = typer.Option(20, help="Minimum ALS points to fit a span"),
):
    """
    Fit catenary per span and write GeoPackage + QC CSV.
    """
    df = pd.read_parquet(wire_points)
    spans = json.loads(pathlib.Path(spans_json).read_text())["spans"]
    g_ins = gpd.read_file(ins_gpkg, layer=ins_layer)

    # index insulators by id → 3D point
    ins_xyz: Dict[str, np.ndarray] = {}
    for _, r in g_ins.iterrows():
        p = r.geometry
        ins_xyz[str(r["id"])] = np.array([p.x, p.y, p.z], dtype=np.float64)

    # group per span
    wires_geom = []
    ids = []
    id_s = []
    id_e = []
    qc_rows = []

    for s in spans:
        sid = s["span_id"]
        A_id = s["tower_start"]; B_id = s["tower_end"]
        insA = s["ins_start"]; insB = s["ins_end"]
        if insA not in ins_xyz or insB not in ins_xyz:
            continue
        PA = ins_xyz[insA]; PB = ins_xyz[insB]
        Axy = PA[:2]; Bxy = PB[:2]
        u_hat, _ = _span_basis(Axy, Bxy)

        pts = df[df["span_id"] == sid][["x","y","z"]].to_numpy()
        if len(pts) < min_points:
            qc_rows.append({"span_id": sid, "rmse": np.nan, "n": len(pts), "status": "too_few_points"})
            continue

        # project to (u,z)
        u, z = _project_to_uvz(pts, Axy, u_hat)
        # initial residuals w.r.t. straight line (for robust seed)
        p_lin = np.polyfit(u, z, 1)
        z_lin = np.polyval(p_lin, u)
        w = _huber_weights(z - z_lin, delta=huber_delta)

        # fit catenary
        try:
            a,u0,c = _fit_catenary(u, z, w)
        except Exception as e:
            qc_rows.append({"span_id": sid, "rmse": np.nan, "n": len(pts), "status": f"fit_failed:{e}"})
            continue

        # sample from u=0..L (L = chord length in XY); snap ends to insA/insB Z
        L = float(np.linalg.norm(Bxy - Axy))
        us = np.arange(0.0, L + step_m, step_m)
        zs = _catenary(us, a, u0, c)

        # convert back to 3D: X(u) = Axy + u*u_hat, Z = zs
        XY = Axy[None, :] + us[:, None] * u_hat[None, :]
        pts3d = np.column_stack([XY, zs])

        # snap endpoints to insulator XYZ
        if len(pts3d) > 0:
            pts3d[0] = PA
            pts3d[-1] = PB

        # compute RMSE to inlier ALS points (distance in vertical z space)
        z_pred = _catenary(u, a, u0, c)
        rmse = float(np.sqrt(np.mean((z - z_pred)**2)))
        qc_rows.append({"span_id": sid, "rmse": rmse, "n": int(len(pts)), "status": "ok"})

        wires_geom.append(LineString([tuple(p) for p in pts3d]))
        ids.append(sid)
        id_s.append(insA)
        id_e.append(insB)

    g_wires = gpd.GeoDataFrame(
        {"id": ids, "id_insulator_start": id_s, "id_insulator_end": id_e},
        geometry=wires_geom, crs=crs
    )

    # Empty placeholders for writer
    empty_towers = gpd.GeoDataFrame({"id": [], "id_tower": []}, geometry=[], crs=crs)
    empty_ins = gpd.GeoDataFrame({"id": [], "id_tower": [], "id_wire": []}, geometry=[], crs=crs)

    write_layers(out_gpkg, empty_towers, empty_ins, g_wires)
    rprint(f"[green]Wrote wires →[/] {out_gpkg}")

    pd.DataFrame(qc_rows).to_csv(qc_csv, index=False)
    rprint(f"[green]Wrote QC →[/] {qc_csv}")


if __name__ == "__main__":
    app()
