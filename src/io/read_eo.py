# -*- coding: utf-8 -*-
"""
read_eo.py
----------
Utilities for reading camera intrinsics and exterior orientation (EO) for AP imagery,
and for constructing projection matrices / world-space rays.

Supports:
- EO tables in CSV/TSV/TXT with columns:
  image, X, Y, Z, Omega, Phi, Kappa   (angles in degrees; right-handed)
- Intrinsics in YAML (OpenCV-style) with keys:
  K (3x3), distCoeffs (k1,k2,p1,p2,k3[,k4...]), image_width, image_height

Core functions:
- load_eo_table()
- load_intrinsics_yaml()
- opk_to_R()
- build_projection_matrix()
- pixel_to_world_ray()
- undistort_points()

All outputs are numpy arrays with explicit dtypes.
"""

from __future__ import annotations
import io
import math
import json
import pathlib
from typing import Dict, Tuple, Iterable, List, Optional

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------
# Parsing & validation
# ---------------------------------------------------------------------

def _read_table(path: str | pathlib.Path) -> pd.DataFrame:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"EO file not found: {p}")
    # try csv, then tsv, then space-delimited
    for sep in [",", "\t", r"\s+"]:
        try:
            df = pd.read_csv(p, sep=sep, engine="python")
            if {"X","Y","Z","Omega","Phi","Kappa"}.issubset(df.columns):
                return df
        except Exception:
            continue
    raise ValueError(
        "Failed to parse EO table. Expect CSV/TSV/TXT with columns: "
        "[image, X, Y, Z, Omega, Phi, Kappa]"
    )

def load_eo_table(path: str | pathlib.Path) -> pd.DataFrame:
    """
    Load exterior orientation table.

    Returns a DataFrame with columns:
      image(str), X(float), Y(float), Z(float), Omega, Phi, Kappa (deg)
    """
    df = _read_table(path).copy()
    # normalize column names
    rename = {c: c.strip().lower() for c in df.columns}
    df.columns = list(rename.values())
    # flexible aliases
    aliases = {
        "img": "image", "filename": "image", "photo": "image",
        "x_cam": "x", "y_cam": "y", "z_cam": "z",
        "omega_deg": "omega", "phi_deg": "phi", "kappa_deg": "kappa",
    }
    for a, b in aliases.items():
        if a in df.columns and b not in df.columns:
            df[b] = df[a]
    required = ["image", "x", "y", "z", "omega", "phi", "kappa"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"EO missing columns: {missing}")

    # ensure dtypes
    df = df[required].copy()
    df["image"] = df["image"].astype(str)
    for c in ["x","y","z","omega","phi","kappa"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[["x","y","z","omega","phi","kappa"]].isna().any().any():
        raise ValueError("EO table contains NaNs after numeric conversion.")
    return df


def load_intrinsics_yaml(path: str | pathlib.Path) -> Dict[str, np.ndarray | int | Tuple[int,int]]:
    """
    Load intrinsics from YAML.

    Expected keys:
      K: 3x3
      distCoeffs: list (k1,k2,p1,p2,k3[,k4,k5,k6])
      image_width: int
      image_height: int

    Returns dict: { "K": np.ndarray(3x3), "dist": np.ndarray(n,), "size": (W,H) }
    """
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Intrinsics YAML not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    if "K" not in y or "distCoeffs" not in y:
        raise ValueError("YAML missing required keys: K, distCoeffs")
    K = np.array(y["K"], dtype=np.float64).reshape(3, 3)
    dist = np.array(y["distCoeffs"], dtype=np.float64).reshape(-1)
    W = int(y.get("image_width", 0))
    H = int(y.get("image_height", 0))
    size = (W, H) if W and H else None
    return {"K": K, "dist": dist, "size": size}


# ---------------------------------------------------------------------
# Geometry: OPK → rotation, projections, rays
# ---------------------------------------------------------------------

def deg2rad(d: float) -> float:
    return d * math.pi / 180.0

def opk_to_R(omega_deg: float, phi_deg: float, kappa_deg: float) -> np.ndarray:
    """
    Convert photogrammetric Omega-Phi-Kappa (deg) to rotation matrix Rcw (world->camera).

    Convention:
      - Omega: rotation around X
      - Phi:   rotation around Y
      - Kappa: rotation around Z
    Total rotation: R = Rz(kappa) @ Ry(phi) @ Rx(omega)
    """
    om, ph, ka = map(deg2rad, (omega_deg, phi_deg, kappa_deg))
    Rx = np.array([[1,0,0],
                   [0, math.cos(om), -math.sin(om)],
                   [0, math.sin(om),  math.cos(om)]], dtype=np.float64)
    Ry = np.array([[ math.cos(ph), 0, math.sin(ph)],
                   [0,            1, 0],
                   [-math.sin(ph),0, math.cos(ph)]], dtype=np.float64)
    Rz = np.array([[ math.cos(ka), -math.sin(ka), 0],
                   [ math.sin(ka),  math.cos(ka), 0],
                   [0,              0,            1]], dtype=np.float64)
    R = Rz @ Ry @ Rx
    return R

def build_projection_matrix(K: np.ndarray, Rcw: np.ndarray, Cw: np.ndarray) -> np.ndarray:
    """
    Build 3x4 projection matrix:  P = K [R | -R C]
    K: 3x3 intrinsics
    Rcw: world->camera rotation (3x3)
    Cw: camera center in world coords (3,)
    """
    if K.shape != (3,3): raise ValueError("K must be 3x3")
    if Rcw.shape != (3,3): raise ValueError("Rcw must be 3x3")
    Cw = np.asarray(Cw, dtype=np.float64).reshape(3,1)
    Rt = np.hstack([Rcw, -Rcw @ Cw])
    P = K @ Rt
    return P

def undistort_points(uv: np.ndarray, K: np.ndarray, dist: np.ndarray, max_iter: int = 5) -> np.ndarray:
    """
    Iteratively undistort normalized points with radial/tangential params.
    uv: Nx2 pixel coordinates
    returns: Nx2 undistorted pixel coordinates (approximate, OpenCV-compatible)
    """
    uv = np.asarray(uv, dtype=np.float64)
    fx, fy = K[0,0], K[1,1]
    cx, cy = K[0,2], K[1,2]
    k1, k2, p1, p2 = (dist.tolist() + [0,0,0,0])[:4]  # minimal set
    # to normalized
    x = (uv[:,0] - cx) / fx
    y = (uv[:,1] - cy) / fy
    x_u, y_u = x.copy(), y.copy()
    for _ in range(max_iter):
        r2 = x_u**2 + y_u**2
        radial = 1 + k1*r2 + k2*(r2**2)
        x_t = x_u + 2*p1*x_u*y_u + p2*(r2 + 2*x_u**2)
        y_t = y_u + p1*(r2 + 2*y_u**2) + 2*p2*x_u*y_u
        x_u = (x - x_t)/radial
        y_u = (y - y_t)/radial
    # back to pixels
    u = x_u * fx + cx
    v = y_u * fy + cy
    return np.column_stack([u, v])

def pixel_to_world_ray(P: np.ndarray, K: np.ndarray, Rcw: np.ndarray, Cw: np.ndarray,
                       uv: np.ndarray, undistort: bool = False, dist: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute world-space ray (origin, direction) from a pixel.

    Inputs:
      P    : 3x4 projection matrix
      K    : intrinsics 3x3
      Rcw  : world->camera rotation
      Cw   : camera center (3,)
      uv   : (u,v) pixel (or Nx2)
      undistort: if True, undistort with dist before ray cast
      dist : distortion coeffs

    Returns:
      origin (3,) and unit direction (3,) or arrays shaped (N,3)
    """
    uv = np.asarray(uv, dtype=np.float64)
    scalar = uv.ndim == 1
    if scalar:
        uv = uv.reshape(1,2)

    if undistort and dist is not None:
        uv = undistort_points(uv, K, dist)

    fx, fy = K[0,0], K[1,1]
    cx, cy = K[0,2], K[1,2]

    # Camera-frame direction
    x = (uv[:,0] - cx) / fx
    y = (uv[:,1] - cy) / fy
    z = np.ones_like(x)
    d_cam = np.stack([x,y,z], axis=1)
    # normalize then rotate to world
    d_cam = d_cam / np.linalg.norm(d_cam, axis=1, keepdims=True)
    # camera->world direction: Rwc = Rcw.T
    Rwc = Rcw.T
    d_world = (Rwc @ d_cam.T).T
    d_world = d_world / np.linalg.norm(d_world, axis=1, keepdims=True)

    Cw = np.asarray(Cw, dtype=np.float64).reshape(1,3)
    origins = np.repeat(Cw, d_world.shape[0], axis=0)

    if scalar:
        return origins[0], d_world[0]
    return origins, d_world


# ---------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------

def build_camera_dict(eo_row: pd.Series, intr: Dict[str, np.ndarray | int]) -> Dict[str, np.ndarray]:
    """
    Build a camera dict with K, Rcw, Cw, P for one EO row.
    """
    K = np.asarray(intr["K"], dtype=np.float64)
    Cw = np.array([eo_row["x"], eo_row["y"], eo_row["z"]], dtype=np.float64)
    Rcw = opk_to_R(float(eo_row["omega"]), float(eo_row["phi"]), float(eo_row["kappa"]))
    P = build_projection_matrix(K, Rcw, Cw)
    return {"K":K, "Rcw":Rcw, "Cw":Cw, "P":P}
