.PHONY: env demo preprocess towers insulators spans wires package report run

ENV?=ptl3d

env:
	conda env create -f environment.yml || conda env update -f environment.yml
	@echo "Activate with: conda activate $(ENV)"

demo:
	python -m src.cli run --config conf/project.yaml

preprocess:
	python -m src.cli preprocess \
		--las data/als/segment.laz \
		--dtm data/rasters/dtm.tif \
		--out-ground build/segment_ground.laz \
		--out-hag build/segment_hag.laz \
		--ground-json pipelines/pdal_ground.json \
		--hag-json pipelines/pdal_hag.json

towers:
	python -m src.cli towers \
		--las-hag build/segment_hag.laz \
		--dtm data/rasters/dtm.tif \
		--out-gpkg build/tower_axis.gpkg \
		--crs "EPSG:32638" --refine True

insulators:
	python -m src.cli insulators \
		--images data/ap/images \
		--eo data/ap/eo/eo.csv \
		--intrinsics data/ap/intrinsics.yaml \
		--dtm data/rasters/dtm.tif \
		--weights models/vision_insulator/yolov8s_ins.pt \
		--det-json build/insulators_2d.json \
		--out-gpkg build/insulators_3d.gpkg \
		--crs "EPSG:32638"

spans:
	python -m src.cli spans \
		--towers-gpkg build/tower_axis.gpkg \
		--ins-gpkg build/insulators_3d.gpkg \
		--out-json build/spans.json

wires:
	python -m src.lidar.select_wires \
		--las build/segment_hag.laz \
		--towers build/tower_axis.gpkg \
		--out build/wire_points.parquet \
		--dtm data/rasters/dtm.tif

	python -m src.cli wires \
		--wire-points build/wire_points.parquet \
		--spans-json build/spans.json \
		--ins-gpkg build/insulators_3d.gpkg \
		--out-gpkg build/wires_3d.gpkg \
		--qc-csv build/qc_spans.csv \
		--crs "EPSG:32638"

package:
	python -m src.cli package \
		--towers-gpkg build/tower_axis.gpkg \
		--ins-gpkg build/insulators_3d.gpkg \
		--wires-gpkg build/wires_3d.gpkg \
		--out-gpkg output/output.gpkg

report:
	python -m src.cli report \
		--qc-csv build/qc_spans.csv \
		--html reports/report.html \
		--towers-gpkg build/tower_axis.gpkg \
		--ins-gpkg build/insulators_3d.gpkg \
		--wires-gpkg build/wires_3d.gpkg

run:
	python -m src.cli run --config conf/project.yaml

