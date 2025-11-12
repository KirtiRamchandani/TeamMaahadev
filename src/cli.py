# -*- coding: utf-8 -*-
"""
cli.py
------
Top-level CLI for the PTL3D pipeline.

Commands:
  - run             : end-to-end pipeline (config-driven)
  - preprocess      : PDAL ground/HAG + normals
  - towers          : detect/refine tower axes (LineStringZ)
  - insulators      : detect 2D (YOLO) + triangulate 3D (PointZ)
  - spans           : build spans JSON from towers + insulators
  - wires           : fit catenaries and write wires (LineStringZ)
  - package         : assemble single GeoPackage with 3 layers
  - report          : generate HTML report from QC CSVs

This wraps the previously implemented modules for reproducible runs.
"""

from __future__ import annotations
import json
import os
import pathlib
import subprocess
import sys
from typing import Optional, Sequence, Dict, Any

import typer
import yaml
from rich import print as rprint

# local imports (module CLIs)
from src.lidar.cluster_towers import main as cli_towers
from src.lidar.fit_axis import main as cli_fit_axis
from src.lidar.select_wires import main as cli_select_wires

from src.vision.infer_insulators import infer as cli_ins_infer, train as cli_ins_train
from src.vision.triangulate import main as cli_triangulate

from src.spans.build_graph import main as cli_build_graph
from src.spans.fit_catenary import main as cli_fit_catenary
from src.spans.qc_metrics import main as cli_qc

from src.io.gpkg_writer import write_layers  # used by package()
import geopandas as gpd

app = typer.Typer(add_completion=False)

# -------------------------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------------------------

def _load_yaml(path: str | pathlib.Path) -> Dict[str, Any]:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config YAML not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _ensure_dir(p: str | pathlib.Path) -> pathlib.Path:
    pp = pathlib.Path(p)
    pp.parent.mkdir(parents=True, exist_ok=True)
    return pp

def _pdal_pipeline(pipeline_json: str, readers: Dict[str, str], writers: Dict[str, str]) -> None:
    """
    Run a PDAL pipeline JSON with reader/writer substitutions at runtime.
    """
    cmd = ["pdal", "pipeline", pipeline_json]
    for k, v in readers.items():
        cmd.append(f"--readers.las.{k}={v}")
    for k, v in writers.items():
        cmd.append(f"--writers.las.{k}={v}")
    rprint(f"[cyan]PDAL:[/] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

# -------------------------------------------------------------------------------------
# Composite commands
# -------------------------------------------------------------------------------------

@app.command()
def preprocess(
    las: str = typer.Option(..., help="ALS LAS/LAZ file"),
    dtm: str = typer.Option(..., help="DTM raster"),
    out_ground: str = typer.Option("build/segment_ground.laz", help="Output ground-classified LAZ"),
    out_hag: str = typer.Option("build/segment_hag.laz", help="Output HAG+normals LAZ"),
    ground_json: str = typer.Option("pipelines/pdal_ground.json", help="PDAL pipeline JSON for ground"),
    hag_json: str = typer.Option("pipelines/pdal_hag.json", help="PDAL pipeline JSON for HAG/normals"),
):
    """
    Run PDAL preprocessing: ground classification + HAG/normals.
    """
    _ensure_dir(out_ground)
    _ensure_dir(out_hag)

    _pdal_pipeline(
        ground_json,
        readers={"filename": las},
        writers={"filename": out_ground},
    )
    _pdal_pipeline(
        hag_json,
        readers={"filename": las},
        writers={"filename": out_hag},
    )

    rprint(f"[green]Preprocessing complete.[/]\n  {out_ground}\n  {out_hag}")


@app.command()
def towers(
    las_hag: str = typer.Option(..., help="HAG LAZ from preprocess"),
    dtm: str = typer.Option(..., help="DTM raster"),
    out_gpkg: str = typer.Option("build/tower_axis.gpkg", help="Output GeoPackage (tower_axis)"),
    eps: float = typer.Option(2.0),
    min_samples: int = typer.Option(120),
    min_hag: float = typer.Option(8.0),
    min_height: float = typer.Option(15.0),
    top_pct: float = typer.Option(98.5),
    crs: str = typer.Option("EPSG:32638"),
    refine: bool = typer.Option(True, help="Run PCA-based tilt refinement after detection"),
):
    """
    Detect tower axes (and optionally refine).
    """
    # run detection
    cli_towers.callback(
        las=las_hag, dtm=dtm, out=out_gpkg, eps=eps, min_samples=min_samples,
        min_hag=min_hag, min_height=min_height, top_pct=top_pct, crs=crs
    )
    rprint(f"[green]Towers written →[/] {out_gpkg}")

    if refine:
        out_ref = pathlib.Path(out_gpkg).with_name("tower_axis_refined.gpkg")
        cli_fit_axis.callback(
            las=las_hag, in_towers=out_gpkg, dtm=dtm, out=str(out_ref)
        )
        rprint(f"[green]Refined towers →[/] {out_ref}")


@app.command()
def insulators(
    images: str = typer.Option(..., help="Folder with AP images"),
    eo: str = typer.Option(..., help="EO table (CSV/TSV/TXT)"),
    intrinsics: str = typer.Option(..., help="Camera intrinsics YAML"),
    dtm: str = typer.Option(..., help="DTM raster"),
    weights: str = typer.Option(..., help="Trained YOLOv8 weights (.pt) for insulators"),
    det_json: str = typer.Option("build/insulators_2d.json", help="Detections JSON"),
    out_gpkg: str = typer.Option("build/insulators_3d.gpkg", help="Triangulated insulator PointZ layer"),
    conf: float = typer.Option(0.25),
    iou: float = typer.Option(0.45),
    imgsz: int = typer.Option(1280),
    z_offset: float = typer.Option(8.0),
    px_thresh: float = typer.Option(3.0),
    cls_keep: int = typer.Option(0),
    crs: str = typer.Option("EPSG:32638"),
):
    """
    Run 2D detection with YOLOv8 and triangulate to 3D PointZ.
    """
    # infer 2D
    cli_ins_infer.callback(
        weights=weights, images=images, out=det_json, conf=conf, iou=iou, imgsz=imgsz, save_csv=None, class_filter=str(cls_keep)
    )
    # triangulate
    cli_triangulate.callback(
        detections=det_json, eo=eo, K=intrinsics, dtm=dtm, out=out_gpkg,
        z_offset=z_offset, px_thresh=px_thresh, cls_keep=cls_keep, crs=crs
    )
    rprint(f"[green]Insulators written →[/] {out_gpkg}")


@app.command()
def spans(
    towers_gpkg: str = typer.Option(..., help="tower_axis GeoPackage"),
    ins_gpkg: str = typer.Option(..., help="insulator GeoPackage"),
    out_json: str = typer.Option("build/spans.json", help="Output spans JSON"),
):
    """
    Build spans from towers + insulators.
    """
    cli_build_graph.callback(towers_gpkg=towers_gpkg, ins_gpkg=ins_gpkg, out=out_json)
    rprint(f"[green]Spans written →[/] {out_json}")


@app.command()
def wires(
    wire_points: str = typer.Option(..., help="Per-span ALS wire points Parquet (from select_wires.py)"),
    spans_json: str = typer.Option(..., help="spans.json path"),
    ins_gpkg: str = typer.Option(..., help="insulator GeoPackage"),
    out_gpkg: str = typer.Option("build/wires_3d.gpkg", help="Output wire layer"),
    qc_csv: str = typer.Option("build/qc_spans.csv", help="QC CSV"),
    crs: str = typer.Option("EPSG:32638"),
):
    """
    Fit catenaries per span and output wire layer.
    """
    cli_fit_catenary.callback(
        wire_points=wire_points, spans_json=spans_json, ins_gpkg=ins_gpkg,
        out_gpkg=out_gpkg, qc_csv=qc_csv, crs=crs
    )
    rprint(f"[green]Wires written →[/] {out_gpkg}\n[green]QC →[/] {qc_csv}")


@app.command()
def package(
    towers_gpkg: str = typer.Option(..., help="tower_axis GPKG"),
    ins_gpkg: str = typer.Option(..., help="insulator GPKG"),
    wires_gpkg: str = typer.Option(..., help="wire GPKG"),
    out_gpkg: str = typer.Option("output/output.gpkg", help="Combined GeoPackage"),
):
    """
    Assemble the three layers into one GeoPackage (schema enforced).
    """
    gt = gpd.read_file(towers_gpkg, layer="tower_axis")
    gi = gpd.read_file(ins_gpkg, layer="insulator")
    gw = gpd.read_file(wires_gpkg, layer="wire")
    # ensure shared CRS
    if not (gt.crs == gi.crs == gw.crs):
        raise typer.Exit("CRS mismatch between layers. Reproject before packaging.")
    write_layers(out_gpkg, gt, gi, gw)
    rprint(f"[green]Packaged →[/] {out_gpkg}")


@app.command()
def report(
    qc_csv: str = typer.Option(..., help="QC CSV (from wires step)"),
    html: str = typer.Option("reports/report.html", help="Output HTML report"),
    triangulation_csv: Optional[str] = typer.Option(None, help="Optional triangulation CSV"),
    towers_gpkg: Optional[str] = typer.Option(None, help="Optional towers GPKG"),
    ins_gpkg: Optional[str] = typer.Option(None, help="Optional insulators GPKG"),
    wires_gpkg: Optional[str] = typer.Option(None, help="Optional wires GPKG"),
):
    """
    Generate HTML summary report.
    """
    cli_qc.callback(
        qc_csv=qc_csv, html=html, triangulation_csv=triangulation_csv,
        towers_gpkg=towers_gpkg, ins_gpkg=ins_gpkg, wires_gpkg=wires_gpkg
    )
    rprint(f"[green]Report →[/] {html}")


# -------------------------------------------------------------------------------------
# End-to-end "run" (config-driven)
# -------------------------------------------------------------------------------------

@app.command()
def run(
    config: str = typer.Option(..., help="Path to conf/project.yaml"),
):
    """
    Execute the full pipeline using a project YAML.
    Required keys in conf/project.yaml:
      crs, als_tiles, dtm, dsm, orthomosaic, ap_images (list or folder)
    """
    cfg = _load_yaml(config)
    crs = cfg.get("crs", "EPSG:32638")
    dtm = cfg["dtm"]
    las = cfg.get("als", "data/als/segment.laz")
    las_hag = "build/segment_hag.laz"
    towers_gpkg = "build/tower_axis.gpkg"
    ins_gpkg = "build/insulators_3d.gpkg"
    spans_json = "build/spans.json"
    wire_pts = "build/wire_points.parquet"
    wires_gpkg = "build/wires_3d.gpkg"
    pkg = "output/output.gpkg"
    qc_csv = "build/qc_spans.csv"
    tri_csv = pathlib.Path(ins_gpkg).with_suffix(".triangulation.csv")

    # 1) preprocess
    preprocess(
        las=las, dtm=dtm,
        out_ground="build/segment_ground.laz",
        out_hag=las_hag,
        ground_json="pipelines/pdal_ground.json",
        hag_json="pipelines/pdal_hag.json",
    )

    # 2) towers
    towers(las_hag=las_hag, dtm=dtm, out_gpkg=towers_gpkg, crs=crs, refine=True)

    # 3) insulators (2D + triangulate)
    images = cfg.get("ap_images_dir", "data/ap/images")
    eo = cfg.get("eo", "data/ap/eo/eo.csv")
    intr = cfg.get("intrinsics", "data/ap/intrinsics.yaml")
    weights = cfg.get("insulator_weights", "models/vision_insulator/yolov8s_ins.pt")
    insulators(images=images, eo=eo, intrinsics=intr, dtm=dtm, weights=weights,
               det_json="build/insulators_2d.json", out_gpkg=ins_gpkg, crs=crs)

    # 4) wire point selection (ALS → span corridors)
    cli_select_wires.callback(
        las=las_hag, towers=towers_gpkg, out=wire_pts, dtm=dtm,
        hag_min=cfg.get("thresholds", {}).get("wire_hag_min", 8.0),
        k_nn=20,
        linearity_tau=cfg.get("thresholds", {}).get("linearity_tau", 6.0),
        span_buffer_m=cfg.get("thresholds", {}).get("span_buffer_m", 20.0),
        k_tower_neighbors=2,
    )

    # 5) spans
    spans(towers_gpkg=towers_gpkg, ins_gpkg=ins_gpkg, out_json=spans_json)

    # 6) wires (catenary fit)
    wires(wire_points=wire_pts, spans_json=spans_json, ins_gpkg=ins_gpkg,
          out_gpkg=wires_gpkg, qc_csv=qc_csv, crs=crs)

    # 7) package
    package(towers_gpkg=towers_gpkg, ins_gpkg=ins_gpkg, wires_gpkg=wires_gpkg, out_gpkg=pkg)

    # 8) report
    report(qc_csv=qc_csv, html="reports/report.html", triangulation_csv=str(tri_csv),
           towers_gpkg=towers_gpkg, ins_gpkg=ins_gpkg, wires_gpkg=wires_gpkg)

    rprint(f"[bold green]All done.[/]\n → {pkg}\n → reports/report.html")


if __name__ == "__main__":
    app()
