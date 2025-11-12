# PTL3D: Automated 3D Reconstruction of Power Transmission Lines

An open-source AI pipeline to reconstruct 3D models of power transmission lines using Airborne Laser Scanning (ALS) and Aerial Photogrammetry (AP) data.  
This project automatically extracts tower axes, wire attachment (insulator) points, and wire geometries as 3D GeoPackage layers ready for GIS integration.

--------------------------------------------------------------------------------
## Overview

PTL3D is designed to process UAV and LiDAR datasets and produce an accurate, skeletal 3D representation of power line infrastructure.  
The output model helps monitor line conditions, detect clearance violations with terrain or vegetation, and create digital twins of assets.

--------------------------------------------------------------------------------
## Features

- Tower detection and 3D axis extraction from ALS point clouds
- Insulator detection using YOLOv8 deep learning on aerial images
- Triangulation of insulator points into 3D space
- Span construction between towers with wire classification
- Robust 3D catenary fitting for wire modeling
- Final output as vector GeoPackage (LineStringZ and PointZ)
- Automated PDAL preprocessing and quality control reporting

--------------------------------------------------------------------------------
## System Requirements

Operating System: Windows 10/11, Linux, or macOS  
Python Version: 3.10 or 3.11  
Hardware: Recommended 16 GB RAM and optional GPU for YOLOv8 inference

--------------------------------------------------------------------------------
## Installation

Clone the repository and set up the environment.

```
git clone https://github.com/KirtiRamchandani/TeamMaahadev.git
cd TeamMaahadev
conda env create -f environment.yml
conda activate ptl3d
```

--------------------------------------------------------------------------------
## Folder Structure

src/
 ├── lidar/          → Tower clustering, axis fitting, wire point selection  
 ├── vision/         → Insulator detection and triangulation (YOLOv8 + geometry)  
 ├── spans/          → Span graph building, catenary fitting, QC report  
 ├── io/             → Raster and GeoPackage read/write utilities  
 ├── pipelines/      → PDAL JSONs for ground classification and HAG normalization  
 ├── conf/           → Configuration files (project.yaml, models.yaml, datasets)  
 └── cli.py          → Unified command-line interface for full pipeline

--------------------------------------------------------------------------------
## Data Preparation

Place your dataset as follows:

```
data/
 ├── als/segment.laz
 ├── rasters/
 │     ├── dtm.tif
 │     ├── dsm.tif
 │     └── ortho.tif
 └── ap/
       ├── images/IMG_*.jpg
       ├── eo/eo.csv
       └── intrinsics.yaml
```

If you are using the public dataset, download it here:
https://disk.yandex.ru/d/abJf69-FB_qesQ
Password: 20251105

--------------------------------------------------------------------------------
## Running the Pipeline

### Step 1 — Preprocessing

Run PDAL-based preprocessing to classify ground points and compute height-above-ground (HAG):

```
python -m src.cli preprocess   --las data/als/segment.laz   --dtm data/rasters/dtm.tif
```

Outputs:
- build/segment_ground.laz  
- build/segment_hag.laz  

--------------------------------------------------------------------------------
### Step 2 — Tower Detection

Detect tower clusters from ALS point cloud and estimate vertical axes:

```
python -m src.cli towers   --las-hag build/segment_hag.laz   --dtm data/rasters/dtm.tif   --out-gpkg build/tower_axis.gpkg   --crs "EPSG:32638"
```

Output:
- build/tower_axis.gpkg  (contains LineStringZ tower axes)

--------------------------------------------------------------------------------
### Step 3 — Insulator Detection and 3D Triangulation

Run YOLOv8 detection on AP imagery and triangulate attachment points:

```
python -m src.cli insulators   --images data/ap/images   --eo data/ap/eo/eo.csv   --intrinsics data/ap/intrinsics.yaml   --dtm data/rasters/dtm.tif   --weights models/vision_insulator/yolov8s_ins.pt
```

Outputs:
- build/insulators_2d.json  (2D detections)
- build/insulators_3d.gpkg  (3D PointZ layer)

--------------------------------------------------------------------------------
### Step 4 — Build Spans Between Towers

```
python -m src.cli spans   --towers-gpkg build/tower_axis.gpkg   --ins-gpkg build/insulators_3d.gpkg   --out-json build/spans.json
```

Output:
- build/spans.json  (list of spans with insulator links)

--------------------------------------------------------------------------------
### Step 5 — Wire Point Selection and 3D Fitting

Select ALS wire points and fit catenary curves:

```
python -m src.cli wires   --wire-points build/wire_points.parquet   --spans-json build/spans.json   --ins-gpkg build/insulators_3d.gpkg   --out-gpkg build/wires_3d.gpkg   --qc-csv build/qc_spans.csv
```

Outputs:
- build/wires_3d.gpkg  (3D LineStringZ layer for wires)
- build/qc_spans.csv   (fit statistics)

--------------------------------------------------------------------------------
### Step 6 — Package and Report

Merge all outputs into one GeoPackage and generate HTML QC report:

```
python -m src.cli package   --towers-gpkg build/tower_axis.gpkg   --ins-gpkg build/insulators_3d.gpkg   --wires-gpkg build/wires_3d.gpkg   --out-gpkg output/output.gpkg

python -m src.cli report   --qc-csv build/qc_spans.csv   --html reports/report.html   --towers-gpkg build/tower_axis.gpkg   --ins-gpkg build/insulators_3d.gpkg   --wires-gpkg build/wires_3d.gpkg
```

--------------------------------------------------------------------------------
### Step 7 — Full Automatic Run (All Steps)

You can run everything in one command using your project configuration file:

```
python -m src.cli run --config src/conf/project.yaml
```

Outputs:
- output/output.gpkg  
- reports/report.html  

--------------------------------------------------------------------------------
## GeoPackage Layers

| Layer        | Geometry Type | Description |
|---------------|----------------|--------------|
| tower_axis   | LineStringZ     | Vertical tower axes |
| insulator    | PointZ          | Wire attachment points |
| wire         | LineStringZ     | Catenary-shaped wire geometries |

All layers are spatially aligned to the terrain and ready for GIS visualization in QGIS or ArcGIS.

--------------------------------------------------------------------------------
## Quality Control Report

After processing, a report is automatically generated:
- reports/report.html (includes tables, RMSE stats, reprojection error plots)

--------------------------------------------------------------------------------
## Technologies Used

- PDAL for LiDAR preprocessing
- YOLOv8 for insulator detection
- SciPy, Open3D, and NumPy for geometric fitting
- GeoPandas, Rasterio, Shapely for GIS data
- Typer + Rich for command-line interface

--------------------------------------------------------------------------------

## Troubleshooting Tips

- Always activate your conda environment: `conda activate ptl3d`
- Check that GDAL and PDAL commands work (`pdal --version`, `gdalinfo --version`)
- Make sure CRS in all layers match (EPSG codes)
- For YOLO inference, CPU-only is supported; GPU improves speed

--------------------------------------------------------------------------------
## Environment Setup (Manual)

If you prefer manual setup:
```
conda create -n ptl3d python=3.11
conda activate ptl3d
conda install -c conda-forge gdal proj pdal geopandas rasterio shapely pyogrio laspy open3d
conda install -c pytorch pytorch torchvision cpuonly
pip install ultralytics typer rich scikit-learn jinja2 opencv-python networkx
```

--------------------------------------------------------------------------------

## License

MIT License © 2025 Team Maahadev

--------------------------------------------------------------------------------
