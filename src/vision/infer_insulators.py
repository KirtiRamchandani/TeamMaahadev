# -*- coding: utf-8 -*-
"""
infer_insulators.py
-------------------
YOLOv8 wrapper for insulator detection in AP imagery.

Features
- Train: runs Ultralytics YOLOv8 with small-object-friendly settings.
- Infer: batch prediction on a folder of images; emits:
    * JSON: detections per image with bbox [x1,y1,x2,y2], conf, cls
    * CSV : flat table (optional)
- Export: ONNX / TensorRT (if available) for edge deployment.

Assumptions
- Dataset YAML (Ultralytics format) for MPID/PLAD/etc. lives in conf/datasets/*.yaml
- Class index for "insulator" is known (default: 0); can be overridden.

CLI
  Train:
    python -m src.vision.infer_insulators train --data conf/datasets/mpid.yaml --epochs 60
  Infer:
    python -m src.vision.infer_insulators infer --weights models/vision_insulator/yolov8s_ins.pt --images data/ap/images --out build/insulators_2d.json
  Export:
    python -m src.vision.infer_insulators export --weights ... --onnx build/insulator.onnx
"""

from __future__ import annotations
import json
import pathlib
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import typer
from rich import print as rprint
from ultralytics import YOLO

app = typer.Typer(add_completion=False)

# ----------------------------- helpers --------------------------------

def _ensure_dir(p: str | pathlib.Path) -> pathlib.Path:
    pp = pathlib.Path(p)
    pp.parent.mkdir(parents=True, exist_ok=True)
    return pp

def _images_in(dir_path: str | pathlib.Path) -> List[str]:
    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    paths = []
    for p in sorted(pathlib.Path(dir_path).glob("*")):
        if p.suffix.lower() in exts:
            paths.append(str(p))
    if not paths:
        raise FileNotFoundError(f"No images found in {dir_path}")
    return paths

# ----------------------------- train ----------------------------------

@app.command()
def train(
    data: str = typer.Option(..., help="Ultralytics dataset YAML (e.g., conf/datasets/mpid.yaml)"),
    model: str = typer.Option("yolov8s.pt", help="Base model to fine-tune"),
    epochs: int = typer.Option(60, help="Training epochs"),
    imgsz: int = typer.Option(1280, help="Image size (long edge)"),
    batch: int = typer.Option(16, help="Batch size"),
    lr0: float = typer.Option(0.01, help="Initial learning rate"),
    mosaic: float = typer.Option(0.7, help="Mosaic prob for small-object enrichment"),
    hsv_h: float = typer.Option(0.02, help="HSV hue aug"),
    hsv_s: float = typer.Option(0.6, help="HSV sat aug"),
    hsv_v: float = typer.Option(0.4, help="HSV val aug"),
    flips: float = typer.Option(0.5, help="Horizontal flip prob"),
    patience: int = typer.Option(20, help="Early stopping patience"),
    project: str = typer.Option("runs/insulator", help="Ultralytics output dir"),
):
    """
    Fine-tune YOLOv8 on an insulator dataset (MPID/PLAD/etc).
    """
    rprint(f"[bold cyan]Training YOLOv8[/] :: data={data}, base={model}")
    y = YOLO(model)

    # augmentations tuned for small, slender insulators
    # note: Ultralytics handles YAML parsing & caching internally
    results = y.train(
        data=data,
        imgsz=imgsz,
        epochs=epochs,
        batch=batch,
        lr0=lr0,
        hsv_h=hsv_h, hsv_s=hsv_s, hsv_v=hsv_v,
        fliplr=flips,
        mosaic=mosaic,
        cos_lr=True,
        patience=patience,
        device=0 if torch_ok() else "cpu",
        project=project,
        name=time.strftime("exp_%Y%m%d_%H%M%S"),
        cache=True,
        workers=8,
    )
    rprint("[green]Training complete.[/]")


def torch_ok() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False

# ----------------------------- inference --------------------------------

@app.command()
def infer(
    weights: str = typer.Option(..., help="Trained YOLO weights (.pt)"),
    images: str = typer.Option(..., help="Folder with images"),
    out: str = typer.Option("build/insulators_2d.json", help="Output JSON with detections"),
    conf: float = typer.Option(0.25, help="Confidence threshold"),
    iou: float = typer.Option(0.45, help="NMS IoU threshold"),
    imgsz: int = typer.Option(1280, help="Inference size"),
    save_csv: Optional[str] = typer.Option(None, help="Optional CSV dump"),
    class_filter: Optional[str] = typer.Option(None, help="Comma list of class indices to keep (e.g., '0')"),
):
    """
    Run detection on a folder; emit JSON in the form:
      {
        "image_001.jpg": [
          {"bbox":[x1,y1,x2,y2], "conf":0.93, "cls":0}
        ],
        ...
      }
    and optional CSV with columns: image,x1,y1,x2,y2,conf,cls
    """
    paths = _images_in(images)
    y = YOLO(weights)
    keep = None
    if class_filter:
        keep = {int(c.strip()) for c in class_filter.split(",")}

    det_map: Dict[str, List[Dict]] = {}
    rows = []
    for p in paths:
        res = y.predict(
            source=p,
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            device=0 if torch_ok() else "cpu",
            verbose=False,
        )
        # Ultralytics returns list; take first result
        r = res[0]
        boxes = r.boxes
        dets = []
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if keep is not None and cls_id not in keep:
                continue
            xyxy = boxes.xyxy[i].cpu().numpy().tolist()
            conf_i = float(boxes.conf[i].item())
            dets.append({"bbox": [float(v) for v in xyxy], "conf": conf_i, "cls": cls_id})
            rows.append({"image": pathlib.Path(p).name, "x1": xyxy[0], "y1": xyxy[1],
                         "x2": xyxy[2], "y2": xyxy[3], "conf": conf_i, "cls": cls_id})
        det_map[pathlib.Path(p).name] = dets

    _ensure_dir(out).write_text(json.dumps(det_map, indent=2))
    rprint(f"[green]Wrote[/] {out}")
    if save_csv:
        df = pd.DataFrame(rows)
        _ensure_dir(save_csv).write_text("")  # ensure parent
        df.to_csv(save_csv, index=False)
        rprint(f"[green]Wrote[/] {save_csv}")

# ----------------------------- export --------------------------------

@app.command()
def export(
    weights: str = typer.Option(..., help=".pt weights"),
    onnx: Optional[str] = typer.Option(None, help="Path to export ONNX"),
    trt: Optional[str] = typer.Option(None, help="Path to export TensorRT engine (requires environment)"),
    imgsz: int = typer.Option(1280, help="Export input size"),
):
    """
    Export to ONNX / TensorRT for edge deployment.
    """
    y = YOLO(weights)
    if onnx:
        y.export(format="onnx", imgsz=imgsz, dynamic=True, opset=13)
        rprint("[green]Exported ONNX (see runs/weights/*.onnx)[/]")
    if trt:
        try:
            y.export(format="engine", imgsz=imgsz, half=True, dynamic=True)
            rprint("[green]Exported TensorRT engine[/]")
        except Exception as e:
            rprint(f"[red]TensorRT export failed:[/] {e}")


if __name__ == "__main__":
    app()
