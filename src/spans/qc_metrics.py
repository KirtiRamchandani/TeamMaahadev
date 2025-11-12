# -*- coding: utf-8 -*-
"""
qc_metrics.py
-------------
Aggregate pipeline metrics and emit a compact HTML report.

Inputs (any available of):
  - qc_spans.csv           (from fit_catenary.py)
  - triangulation.csv      (from triangulate.py; optional)
  - tower_axis.gpkg        (optional to compute tilt stats if refined)

Output:
  - reports/report.html

The HTML contains:
  - Summary cards: number of towers/insulators/spans/wires
  - Tables with RMSE stats per span
  - Histograms for RMSE and reprojection errors
"""

from __future__ import annotations
import pathlib
import math
from typing import Optional

import numpy as np
import pandas as pd
import geopandas as gpd
from jinja2 import Template
import typer

app = typer.Typer(add_completion=False)

HTML_TPL = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>PTL3D — QC Report</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 24px; color: #222; }
  h1 { margin-bottom: 0; }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
  table { border-collapse: collapse; width: 100%; margin-top: 12px; }
  th, td { border: 1px solid #eee; padding: 6px 8px; text-align: left; }
  th { background: #fafafa; }
  .muted { color: #666; }
</style>
</head>
<body>
<h1>PTL3D — Quality Report</h1>
<p class="muted">Generated: {{ generated }}</p>

<div class="grid">
  <div class="card"><b>Towers</b><div>{{ n_towers }}</div></div>
  <div class="card"><b>Insulators</b><div>{{ n_ins }}</div></div>
  <div class="card"><b>Spans</b><div>{{ n_spans }}</div></div>
  <div class="card"><b>Wires</b><div>{{ n_wires }}</div></div>
</div>

<h2>Wire Fit Quality</h2>
<p>RMSE is computed against ALS wire points projected to the span plane (vertical residuals).</p>
<table>
  <thead><tr><th>Span</th><th>Status</th><th>Points</th><th>RMSE (m)</th></tr></thead>
  <tbody>
  {% for r in rows %}
    <tr>
      <td>{{ r.span_id }}</td>
      <td>{{ r.status }}</td>
      <td>{{ r.n }}</td>
      <td>{{ "%.3f"|format(r.rmse) if r.rmse==r.rmse else "—" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

{% if reproj|length > 0 %}
<h2>Insulator Triangulation</h2>
<table>
  <thead><tr><th>Track</th><th>Views</th><th>Mean Reproj (px)</th><th>Max Reproj (px)</th></tr></thead>
  <tbody>
  {% for r in reproj %}
    <tr>
      <td>{{ r.track }}</td>
      <td>{{ r.nviews }}</td>
      <td>{{ "%.2f"|format(r.mean_px) }}</td>
      <td>{{ "%.2f"|format(r.max_px) }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}

</body>
</html>
"""

@app.command()
def main(
    qc_csv: str = typer.Option(..., help="qc_spans.csv from fit_catenary.py"),
    html: str = typer.Option(..., help="Output HTML report"),
    triangulation_csv: Optional[str] = typer.Option(None, help="Optional triangulation CSV from triangulate.py"),
    towers_gpkg: Optional[str] = typer.Option(None, help="Optional tower_axis.gpkg for counts"),
    ins_gpkg: Optional[str] = typer.Option(None, help="Optional insulator.gpkg for counts"),
    wires_gpkg: Optional[str] = typer.Option(None, help="Optional wires.gpkg for counts"),
):
    qc = pd.read_csv(qc_csv)
    rows = qc.to_dict(orient="records")

    reproj = []
    if triangulation_csv and pathlib.Path(triangulation_csv).exists():
        reproj = pd.read_csv(triangulation_csv).to_dict(orient="records")

    def _count(path: Optional[str], layer: Optional[str]) -> int:
        if not path: return 0
        p = pathlib.Path(path)
        if not p.exists(): return 0
        try:
            import geopandas as gpd
            return len(gpd.read_file(p, layer=layer) if layer else gpd.read_file(p))
        except Exception:
            return 0

    n_towers = _count(towers_gpkg, "tower_axis")
    n_ins = _count(ins_gpkg, "insulator")
    n_wires = _count(wires_gpkg, "wire")
    n_spans = qc["span_id"].nunique() if "span_id" in qc.columns else len(qc)

    html_txt = Template(HTML_TPL).render(
        generated=pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        n_towers=n_towers, n_ins=n_ins, n_wires=n_wires, n_spans=n_spans,
        rows=rows, reproj=reproj
    )
    pathlib.Path(html).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(html).write_text(html_txt, encoding="utf-8")


if __name__ == "__main__":
    app()
